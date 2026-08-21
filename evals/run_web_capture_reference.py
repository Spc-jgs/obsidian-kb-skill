#!/usr/bin/env python3
"""Run the synthetic Web Capture gate with an isolated reference Agent.

What this scorer can and cannot establish, stated once so no report has to
overclaim it: every rule here is mechanical. It checks a declared outcome, the
shape of a stated blocker, and whether specific term sets appear as unnegated
assertions. It cannot read a note and decide whether its claims are true, and a
run with zero hard failures means only that nothing tripped these rules.

The depth and refusal rules being graded live in Skill prose, so only a real
Agent exercises them, and *which* Agent is a property of a run rather than of
the eval. Two products do not produce comparable numbers: a baseline is only a
baseline for the agent that produced it. `summary.json` records the agent, and
`reference_agent` in the fixture names the one a stored baseline came from
rather than pinning every future run to it.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "web_capture_semantic_eval_cases.json"
SKILL_SOURCE = ROOT / "skills" / "obsidian-knowledge-base"
TEMPLATE_SOURCE = SKILL_SOURCE / "assets" / "templates"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--rescore-messages",
        type=Path,
        help=(
            "Re-grade the final messages saved by an earlier run, offline. "
            "Message-level rules only: vault, receipt, and isolation checks "
            "need that run's live workspace and are reported as not applicable"
        ),
    )
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--repeats", type=int)
    parser.add_argument(
        "--agent",
        choices=sorted(AGENT_BACKENDS),
        help=(
            "Reference-Agent product to drive. Defaults to the one the fixture "
            "records for its stored baseline. Results from two products are "
            "not comparable and summary.json records which produced them"
        ),
    )
    parser.add_argument(
        "--model",
        help="Override the selected agent's default model for every run",
    )
    parser.add_argument(
        "--stop-on-hard-failure",
        action="store_true",
        help=(
            "Stop before the next case once one hard fails. Off by default: a "
            "hard failure means this run does not count, which the exit code "
            "already carries, and stopping additionally discards the "
            "measurement the run existed to collect"
        ),
    )
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser.parse_args()


def snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@dataclass(frozen=True)
class CommandExecution:
    """One shell command an Agent ran, in a shape no backend's format leaks into.

    The receipt check needs the command line, its exit status and its output.
    Each product streams those differently, so each backend normalises to this
    and the grading rules stay written once.
    """

    command: str
    exit_code: int | None
    output: str


class AgentBackend:
    """One reference-Agent product the gate can be driven with.

    A backend owns three things a scorer must not know about: how the product
    is invoked, how its event stream encodes shell commands, and which file in
    `$HOME` carries its credential. Everything else — isolation, scaffolding,
    grading — is shared, so adding a product cannot quietly change what passes.
    """

    name = ""
    default_model: str | None = None
    # Where the disposable HOME is applied, which is not the same choice for
    # every product. Codex authenticates from the operator's own HOME and
    # injects the disposable one into the tools it spawns, so it inherits.
    # A product without that mechanism must run under the disposable HOME
    # itself, which is why its credential has to be copied there.
    inherits_operator_environment = False
    # Whether the product takes a material asset as an attachment. A backend
    # that cannot must be given the path in the prompt instead. Leaving it out
    # does not hide the file — it sits in the workspace and the runs measured
    # here went and found it — but it leaves the case to chance, and an agent
    # that did not explore would write the note blind while still scoring well,
    # because that case's other facts are all recoverable from the text.
    attaches_material = False
    # Files copied from the real HOME into the disposable one. Credentials
    # only. A product's config file is deliberately never copied: this
    # machine's grok config enables a plugin and pins a reasoning effort, and
    # importing either would make the eval measure the operator's setup as
    # much as the Skill. Model and effort are passed as flags instead, so a
    # summary states them rather than inheriting them invisibly.
    credential_files: tuple[str, ...] = ()
    credential_dir = ""

    executable = ""

    def version(self) -> str:
        raise NotImplementedError

    def ensure_available(self) -> str:
        """Resolve the product's binary, or refuse before any run starts.

        Deliberately not done while building a command: constructing one is how
        the safety assertions inspect a backend, and a check with a side effect
        there means those assertions can only run on a machine with every
        supported product installed. CI has none of them.
        """
        resolved = shutil.which(self.executable)
        if resolved is None:
            raise SystemExit(f"{self.name}: {self.executable} not found on PATH")
        return resolved

    def seed_home(self, home: Path) -> list[str]:
        """Copy the credential into the disposable HOME, and nothing else.

        Redirecting HOME is what keeps the run away from the operator's own
        global Skills — on this machine `~/.agents/skills/obsidian-knowledge-base`
        is a symlink to an installed copy of the very Skill under test — and
        away from the real `~/.obsidian-kb-skill/runtime.json`. The credential
        has to follow, or the product cannot authenticate at all.
        """
        if not self.credential_files:
            return []
        target = home / self.credential_dir
        target.mkdir(parents=True, exist_ok=True)
        target.chmod(0o700)
        copied: list[str] = []
        for name in self.credential_files:
            source = Path.home() / self.credential_dir / name
            if not source.is_file():
                continue
            destination = target / name
            shutil.copy2(source, destination)
            destination.chmod(0o600)
            copied.append(name)
        if not copied:
            raise SystemExit(
                f"{self.name}: no credential found under ~/{self.credential_dir}; "
                f"expected one of {', '.join(self.credential_files)}"
            )
        return copied

    def command(
        self,
        *,
        workspace: Path,
        final_path: Path,
        material: Path | None,
        model: str | None,
        prompt: str,
    ) -> list[str]:
        raise NotImplementedError

    def environment(self, workspace: Path, vault: Path, cache: Path) -> dict[str, str]:
        raise NotImplementedError

    def executions(self, stdout: str) -> list[CommandExecution]:
        raise NotImplementedError

    def inspected(self, stdout: str, material: Path) -> bool:
        """Whether the run actually opened the material asset.

        A required fact drawn from an image cannot tell reading it apart from
        guessing a plausible answer — "the left path is blue" is both a
        finding and a good guess. The evidence that the image was opened lives
        in the transcript, not in the note, so the gate has to look there.

        A backend that attaches the asset has put it in the context by
        construction and needs no search. Any other must say how it knows —
        the filename merely appearing in the transcript is not knowing, since
        a directory listing prints it without anything having read it.
        """
        if self.attaches_material:
            return True
        raise NotImplementedError

    def final_message(self, stdout: str, final_path: Path) -> str:
        raise NotImplementedError


class CodexBackend(AgentBackend):
    """Codex CLI, the product v1.30's stored baseline was measured with."""

    name = "codex"
    executable = "codex"
    default_model = "gpt-5.6-sol"
    inherits_operator_environment = True
    attaches_material = True

    def version(self) -> str:
        return subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip()

    def command(
        self,
        *,
        workspace: Path,
        final_path: Path,
        material: Path | None,
        model: str | None,
        prompt: str,
    ) -> list[str]:
        vault = workspace / "vault"
        cache = workspace / ".preflight-cache"
        command = [
            shutil.which(self.executable) or self.executable,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--json",
            "-C",
            str(workspace),
            "-o",
            str(final_path),
            "-c",
            "model_reasoning_effort=\"medium\"",
            "-c",
            "tools.web_search=false",
            "-c",
            "shell_environment_policy.inherit=\"core\"",
            "-c",
            "shell_environment_policy.set={"
            f"HOME={json.dumps(str(workspace / '.home'))},"
            f"OBSIDIAN_KB_VAULT={json.dumps(str(vault))},"
            f"OBSIDIAN_KB_PREFLIGHT_CACHE={json.dumps(str(cache))}"
            "}",
        ]
        if model:
            command.extend(("--model", model))
        if material:
            command.extend(("--image", str(material)))
        # --image accepts one or more values, so a following option is required
        # to keep the positional prompt from being consumed as another image.
        command.extend(("--color", "never"))
        command.append(prompt)
        return command

    def environment(self, workspace: Path, vault: Path, cache: Path) -> dict[str, str]:
        # Codex injects the run's environment into the tools it spawns through
        # its own config, so the parent process keeps the operator's.
        return os.environ.copy()

    def executions(self, stdout: str) -> list[CommandExecution]:
        found: list[CommandExecution] = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            item = event.get("item", {})
            if (
                event.get("type") != "item.completed"
                or item.get("type") != "command_execution"
            ):
                continue
            command = item.get("command")
            found.append(
                CommandExecution(
                    command=command if isinstance(command, str) else "",
                    exit_code=item.get("exit_code"),
                    output=item.get("aggregated_output") or "",
                )
            )
        return found

    def final_message(self, stdout: str, final_path: Path) -> str:
        return final_path.read_text(encoding="utf-8") if final_path.is_file() else ""


class GrokBackend(AgentBackend):
    """grok CLI.

    Chosen over the other locally installed products for one measured reason:
    its credential is a file, so the disposable HOME that provides this eval's
    isolation can carry it. The alternative keeps its credential in the system
    keyring keyed to the real HOME and re-prompts for an interactive login
    under a redirected one, which a batch run cannot answer.
    """

    name = "grok"
    executable = "grok"
    default_model = "grok-4.6"
    credential_dir = ".grok"
    credential_files = ("auth.json",)

    def version(self) -> str:
        return subprocess.run(
            ["grok", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip()

    def command(
        self,
        *,
        workspace: Path,
        final_path: Path,
        material: Path | None,
        model: str | None,
        prompt: str,
    ) -> list[str]:
        # Resolved against the operator's PATH, because the environment handed
        # to the run deliberately holds a minimal one — an isolated PATH is
        # part of the point, and it does not contain this binary. Falls back to
        # the bare name so a command can still be built for inspection where
        # the product is not installed; `ensure_available` is what refuses.
        command = [
            shutil.which(self.executable) or self.executable,
            "--cwd",
            str(workspace),
            "--always-approve",
            "--disable-web-search",
            "--output-format",
            "streaming-json",
            "--reasoning-effort",
            "medium",
        ]
        if model:
            command.extend(("--model", model))
        command.extend(("-p", prompt))
        return command

    def environment(self, workspace: Path, vault: Path, cache: Path) -> dict[str, str]:
        # A named environment rather than the operator's: HOME is the whole
        # isolation mechanism here, since it is what decides which Skills are
        # in scope and which runtime record the helpers read.
        return {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(workspace / ".home"),
            "TMPDIR": str(workspace / ".tmp"),
            "TERM": "dumb",
            "LANG": "en_US.UTF-8",
            "OBSIDIAN_KB_VAULT": str(vault),
            "OBSIDIAN_KB_PREFLIGHT_CACHE": str(cache),
        }

    def executions(self, stdout: str) -> list[CommandExecution]:
        # Only the terminal update carries the finished command's exit code and
        # full output; the in-progress ones repeat it partially, and counting
        # those would let a receipt be "seen" in a command still running.
        found: list[CommandExecution] = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "tool_call_update" or event.get("status") != "completed":
                continue
            raw = event.get("rawOutput")
            if not isinstance(raw, dict) or raw.get("type") != "Bash":
                continue
            command = raw.get("command")
            found.append(
                CommandExecution(
                    command=command if isinstance(command, str) else "",
                    exit_code=raw.get("exit_code"),
                    output=raw.get("output_for_prompt") or "",
                )
            )
        return found

    # Tools that put a file's *content* in front of the model. `list_dir` and
    # `grep` are deliberately absent: both print the name of an image without
    # anyone having looked at it, and on the 2026-08-17 baseline the runs that
    # were never handed the asset still found it by listing the workspace.
    READING_TOOLS = frozenset({"read_file", "view_image"})

    def inspected(self, stdout: str, material: Path) -> bool:
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "tool_call":
                continue
            if event.get("toolName") not in self.READING_TOOLS:
                continue
            arguments = json.dumps(event.get("rawInput", {}), ensure_ascii=False)
            if material.name in arguments:
                return True
        return False

    def final_message(self, stdout: str, final_path: Path) -> str:
        """Return the assistant text of the last turn, not of the whole run.

        `text` deltas are emitted before each tool call as well as after the
        last one, and Codex's `-o` writes only the closing message. Grading the
        concatenation would put narration the other backend never saw in front
        of the forbidden-claim and dismissal rules, so a run would be graded on
        which product it used. A tool call ends a turn; the last turn's text is
        the final message.
        """
        turn: list[str] = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "text":
                data = event.get("data")
                if isinstance(data, str):
                    turn.append(data)
            elif kind in ("tool_call", "tool_call_update"):
                turn.clear()
        return "".join(turn)


AGENT_BACKENDS: dict[str, AgentBackend] = {
    backend.name: backend for backend in (CodexBackend(), GrokBackend())
}


def scaffold_workspace(base: Path, case: dict[str, object]) -> tuple[Path, Path, Path | None]:
    workspace = base / "workspace"
    vault = workspace / "vault"
    runtime_dir = workspace / ".home" / ".obsidian-kb-skill"
    skill = workspace / ".agents" / "skills" / "obsidian-knowledge-base"
    shutil.copytree(SKILL_SOURCE, skill)
    runtime_dir.mkdir(parents=True)
    # A scratch directory inside the disposable workspace, so a backend given a
    # named environment has a TMPDIR that dies with the run.
    (workspace / ".tmp").mkdir()
    (runtime_dir / "runtime.json").write_text(
        json.dumps({"schema_version": 1, "python": [sys.executable]}) + "\n",
        encoding="utf-8",
    )
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    for directory in (
        "00-Inbox",
        "10-Work",
        "15-Daily",
        "20-Learning",
        "30-Insights",
        "40-Projects",
        "50-People",
    ):
        (vault / directory).mkdir()
    for template in TEMPLATE_SOURCE.glob("*.md"):
        target = vault / "Templates" / template.name
        shutil.copy2(template, target)

    material = case.get("material_asset")
    if material is None:
        return workspace, vault, None
    material_path = workspace / "source-assets" / Path(material).name
    material_path.parent.mkdir()
    shutil.copy2(ROOT / material, material_path)
    return workspace, vault, material_path


def prompt_for(case: dict[str, object], material_path: str | None = None) -> str:
    availability = (
        "This snapshot is the complete, adequate representation of the public source."
        if case["expected_outcome"] == "write"
        else "This snapshot accurately describes the incomplete or blocked representation available."
    )
    if not case.get("material_asset"):
        material = ""
    elif material_path is None:
        material = " The attached image is a material source asset and must be inspected."
    else:
        # Naming the file is the same instruction as attaching it for a product
        # with no attachment flag. Saying "the attached image" to a run with
        # nothing attached points at nothing, and the run proceeds without the
        # material rather than reporting that it is missing.
        material = (
            f" The image at `{material_path}`, relative to the working directory,"
            " is a material source asset and must be opened and inspected."
        )
    # The outcome block is the scorer's structured input. Asking for prose and
    # then guessing at it with regexes is what let "Your note is ready." pass a
    # zero-write case: the grader had to infer a status nobody ever declared.
    # The blocker is asked for in the agent's own words on purpose — naming the
    # allowed reasons here would let a run that stopped for the wrong reason
    # copy the right one off the prompt.
    return f"""Use $obsidian-knowledge-base for this explicit save request.

This is an isolated release evaluation with a disposable Vault. Do not browse or fetch the
.invalid URL: the source snapshot below is the authoritative acquisition result for this run.
{availability}{material} Follow the Skill's normal standard/verified choice, preflight/apply,
zero-write, and receipt rules. Never invent missing material. Write at most one knowledge note.

User request:
{case['prompt']}

Canonical source URL: {case['source_url']}

Source snapshot:
{case['source_markdown']}

Keep the response concise. End it with exactly this block, on its own lines and
nothing after it:

OUTCOME: written
BLOCKER: none

or, when you stopped without writing:

OUTCOME: stopped
BLOCKER: <the specific material that was missing, blocked, or unusable, and why
it could not be obtained — one line, in your own words>
"""


def knowledge_notes(vault: Path) -> list[Path]:
    return [
        path
        for path in sorted(vault.rglob("*.md"))
        if "Templates" not in path.parts
    ]


def contains(text: str, value: str) -> bool:
    return value.casefold() in text.casefold()


# Programs that exist to move bytes off this machine. The gate keys on the
# program being *run*, never on a URL appearing somewhere in the command line:
# every write puts `source: https://eval.invalid/...` into the note, so the
# helper's own argv carries the URL, and sixty command events in the
# 2026-08-17 baseline do. A URL-anywhere rule would fail every case while the
# runs behaved exactly as intended.
NETWORK_PROGRAMS = frozenset({
    "curl", "wget", "httpie", "http", "https", "xh", "aria2c", "axel",
    "nc", "ncat", "netcat", "telnet", "ftp", "sftp", "scp", "rsync",
    "lynx", "w3m", "links", "elinks", "fetch",
})
# Python reaches the network through a library rather than a binary, so the
# inline-script form is read for the import instead of the program name.
NETWORK_MODULES = ("urllib", "requests", "httpx", "aiohttp", "socket", "http.client")
# `git` is local until it names a remote.
GIT_REMOTE_SUBCOMMANDS = frozenset({"clone", "fetch", "pull", "push", "ls-remote", "remote"})
# Where one command ends and the next begins. A fetch hidden behind a pipe or
# a `&&` is still a fetch, and reading only the first token of the whole line
# would miss it.
COMMAND_SEPARATORS = frozenset({"|", "||", "&", "&&", ";", ";;", "\n"})
# Words that stand in front of the program that actually runs.
COMMAND_PREFIXES = frozenset({"env", "sudo", "nohup", "time", "xargs", "exec", "command"})


def command_programs(command: str) -> list[list[str]]:
    """Split a shell line into segments and return each segment's tokens.

    Quoting is resolved before separators are, not after. A `python3 -c` body
    routinely contains `;`, and splitting the raw line on punctuation tears
    the script in half — the inline-script check then never sees its own
    import, which is how the first draft of this passed while missing a fetch.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        # Unbalanced quotes: fall back rather than lose the command entirely.
        tokens = command.split()

    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in COMMAND_SEPARATORS:
            if current:
                segments.append(current)
            current = []
            continue
        current.append(token)
    if current:
        segments.append(current)

    trimmed = []
    for segment in segments:
        # Drop leading `VAR=value` assignments and wrapper words.
        while segment and (
            re.fullmatch(r"[A-Za-z_]\w*=.*", segment[0])
            or Path(segment[0]).name in COMMAND_PREFIXES
        ):
            segment = segment[1:]
            while segment and segment[0].startswith("-"):
                segment = segment[1:]
        if segment:
            trimmed.append(segment)
    return trimmed


def network_fetches(executions: list["CommandExecution"]) -> list[str]:
    """Commands that went to the network instead of using the given snapshot."""
    offending = []
    for execution in executions:
        for tokens in command_programs(execution.command):
            program = Path(tokens[0]).name
            if program in NETWORK_PROGRAMS:
                offending.append(execution.command)
                break
            if program == "git" and len(tokens) > 1 and tokens[1] in GIT_REMOTE_SUBCOMMANDS:
                offending.append(execution.command)
                break
            if program.startswith("python") and "-c" in tokens:
                script = tokens[tokens.index("-c") + 1] if tokens.index("-c") + 1 < len(tokens) else ""
                if any(module in script for module in NETWORK_MODULES):
                    offending.append(execution.command)
                    break
    return offending


def semantic_contains(text: str, value: str) -> bool:
    """Match facts across harmless Markdown and separator differences."""
    normalize = lambda item: "".join(character for character in item.casefold() if character.isalnum())
    return normalize(value) in normalize(text)


def fact_forms(fact: object) -> list[str]:
    """Return the ways one required fact may legitimately be written.

    A fact used to be one English literal against a Chinese prompt, so the
    score partly measured which language the note came out in. Measured on the
    2026-08-17 baseline: two notes for the same case both recorded all five
    facts in Chinese, and one scored 5/5 while the other scored 1/5 — the whole
    difference being whether the note happened to echo each English term once
    somewhere. They preserved the same knowledge.

    Every alternative form in the fixture was written by a real run and is
    listed in `fact_form_provenance` with its count, on the rule #75 set: a
    vocabulary grows from forms that were observed, never from forms that
    sound plausible.
    """
    return [str(fact)] if isinstance(fact, str) else [str(form) for form in fact]


def fact_present(text: str, fact: object) -> bool:
    return any(semantic_contains(text, form) for form in fact_forms(fact))


def label_present(text: str, label: str) -> bool:
    if semantic_contains(text, label):
        return True
    aliases = {
        "source-self-report": ("厂商自报", "来源自报", "作者自测", "自报结果"),
        "primary": ("主要规范", "主来源", "一手来源", "官方规范"),
        "community": ("社区来源", "社区帖子", "社区主张"),
    }
    return any(alias in text for alias in aliases.get(label, ()))


CLAUSE_SPLIT_RE = re.compile(
    # `，` and `、` are clause boundaries here while English `,` is not, and the
    # asymmetry is the point rather than an oversight: Chinese chains
    # independent clauses with `，` where English would start a new sentence,
    # so treating a comma-joined run as one clause makes an unrelated pair of
    # terms look like one assertion. Measured on this eval: a note recording
    # `原文把 2.4.1 和 Python 3.12 绑定，并单独排除 3.10` was graded as
    # asserting that Python 3.10 is supported, from two terms belonging to
    # different statements. A genuine assertion still sits inside one comma
    # clause, so the gate keeps its bite.
    r"(?<=\.)\s+|(?<=[!?;。！？；，、])\s*|\b(?:but|however|yet)\b|(?:但是|但|然而|不过)",
    re.I,
)
NEGATION_MARKERS = (
    "not available",
    "unavailable",
    "not provided",
    "not specified",
    "not stated",
    "cannot determine",
    "can't determine",
    "could not determine",
    "unknown",
    "missing",
    "absent",
    "did not",
    "was not",
    "were not",
    "no note",
    "未写入",
    "没有写入",
    "未保存",
    "没有保存",
    "未创建",
    "没有创建",
    "不可用",
    "未提供",
    "未说明",
    "无法确定",
    "不能确定",
    "不能推断",
    "未知",
    "缺失",
)


def clauses(text: str) -> list[str]:
    return [clause.strip() for clause in CLAUSE_SPLIT_RE.split(text) if clause.strip()]


def is_negated(clause: str) -> bool:
    folded = clause.casefold()
    english_negation = re.search(
        r"\b(?:(?:do|does|did|is|are|was|were|can|could|would|will|has|have|had)\s+not|"
        r"cannot|can't|won't|isn't|aren't|doesn't|don't|didn't|no\s+(?:evidence|proof|note))\b",
        folded,
    )
    # Chinese negates a predicate with a closed class of particles placed
    # directly before it. The write-outcome verbs were the only ones listed,
    # which read as coverage and was a list of four: a note recording the
    # source's own `不支持 Python 3.10` — a required fact, and the exact
    # opposite of the forbidden claim — was graded as asserting it. Any of the
    # particles before any predicate now negates its clause, matching how the
    # English branch already treats one `not` as negating the whole clause.
    chinese_negation = re.search(r"[不未没][㐀-䶿一-鿿]|无法|并非|均非", clause)
    return bool(english_negation or chinese_negation) or any(
        marker in folded for marker in NEGATION_MARKERS
    )


def forbidden_assertions(text: str, claims: list[dict[str, object]]) -> list[str]:
    """Return the ids of forbidden claims asserted somewhere in the text.

    A claim is a set of terms that must all land in one clause, unnegated —
    not a phrase to be matched verbatim. Exact-phrase matching graded the
    wording rather than the assertion: `CVSS 9.8` was forbidden and
    "The score is 9.8 on the CVSS scale" said the same thing and scored clean.

    Order-independent within a clause, and the clause boundary is what keeps it
    honest: two terms a paragraph apart are not one claim. This is an auditable
    rule, not comprehension — a rewrite that avoids every declared term still
    passes, and the fixture is where that gap gets closed, one curated term set
    at a time.

    A term may be written as a list of forms, any one of which satisfies it,
    for the same reason required facts may: the prompts are Chinese and the
    terms are English, so a claim whose predicate exists only in English is
    a gate that a Chinese note walks straight through.

    Every term set must contain the predicate that makes it an assertion.
    A set of nothing but the case's own required facts is matched by any note
    that does its job, and then only the negation detector stands between a
    correct note and a hard failure — `test_no_forbidden_claim_is_satisfied_
    by_the_facts_the_case_demands` refuses that shape.
    """
    matches: list[str] = []
    for claim in claims:
        terms = [fact_forms(term) for term in claim["all_of"]]
        if any(
            all(any(contains(clause, form) for form in forms) for forms in terms)
            and not is_negated(clause)
            for clause in clauses(text)
        ):
            matches.append(str(claim["id"]))
    return matches


OUTCOME_RE = re.compile(r"(?mi)^\s*OUTCOME:\s*(written|stopped)\s*$")
BLOCKER_RE = re.compile(r"(?mi)^\s*BLOCKER:\s*(.+?)\s*$")
# A blocker has to assert that something could not be obtained. "I was bored" is
# a reason without one of these; it is also not a fact about the source.
UNAVAILABILITY_MARKERS = (
    "missing", "unavailable", "not available", "empty", "blocked", "truncated",
    "incomplete", "cut off", "did not load", "does not load", "failed to load",
    "not provided", "not included", "not accessible", "inaccessible",
    "paywall", "requires a subscription", "subscription", "login", "403", "404",
    "缺失", "缺少", "没有", "未提供", "未加载", "加载失败", "不可用", "无法访问",
    "被截断", "不完整", "打不开", "需要订阅", "需要登录", "访问受限", "为空",
)
# The opposite move: name the required material and wave it away. "transaction
# handler is irrelevant" both names the subject a keyword check wants and denies
# that its absence mattered.
DISMISSAL_MARKERS = (
    "irrelevant", "not relevant", "unnecessary", "not necessary", "not needed",
    "does not matter", "doesn't matter", "no longer needed", "optional",
    "无关", "不相关", "不重要", "不需要", "没必要", "可有可无", "无所谓",
)
# Prose that announces a finished note. Kept as a second net behind the OUTCOME
# declaration: a message that declares `stopped` and then tells the reader their
# note is ready is contradicting itself, and the contradiction is the finding.
COMPLETION_PROSE = (
    r"\b(?:i|we)\s+(?:successfully\s+)?(?:wrote|saved|created|completed)\b",
    r"\b(?:the\s+)?(?:requested\s+)?(?:note|capture)\s+(?:was\s+)?"
    r"(?:successfully\s+)?(?:written|saved|created|completed)\b",
    r"\b(?:your|the|this)\s+(?:requested\s+)?(?:note|capture|summary)\s+is\s+"
    r"(?:now\s+)?(?:ready|complete|available|saved|written|in\s+your\s+vault)\b",
    r"\b(?:note|capture)\s+is\s+(?:now\s+)?(?:ready|complete)\b",
    r"(?:已|成功)(?:保存|沉淀|写入|创建|完成)",
    r"(?:笔记|内容)(?:已|成功)(?:保存|写入|创建|完成|就绪|生成)",
    r"(?:笔记|内容)(?:已经)?(?:写好|做好|准备好)",
    r"\b(?:saved|written|created|captured|completed)\s+successfully\b",
    r"\bcaptured\s+(?:the\s+)?(?:requested\s+)?"
    r"(?:note|capture|tutorial|content|article)\b",
    r"\bdone\b[^.!?。！？]*(?:note|capture)\s+is\s+complete\b",
)


def declared_outcome(final_message: str) -> str | None:
    """Return the run's own statement of what it did, or None when it made none.

    Last match wins: the block is specified as the end of the message, and a
    run that quotes the template earlier should not be graded on the quote.
    """
    matches = OUTCOME_RE.findall(final_message)
    return matches[-1].casefold() if matches else None


def declared_blocker(final_message: str) -> str | None:
    matches = BLOCKER_RE.findall(final_message)
    return matches[-1].strip() if matches else None


def dismissed_subjects(text: str, subjects: list[str]) -> list[str]:
    """Return required material the run named and then called unimportant."""
    found: list[str] = []
    for clause in clauses(text):
        folded = clause.casefold()
        if not any(marker in folded for marker in DISMISSAL_MARKERS):
            continue
        found.extend(
            subject
            for subject in subjects
            if semantic_contains(clause, subject) and subject not in found
        )
    return found


def blocker_is_case_specific(blocker: str, subjects: list[str]) -> bool:
    """True when the declared blocker names required material and its absence.

    Both halves are needed. Naming the material alone was the old rule and it
    accepted "transaction handler is irrelevant"; asserting unavailability alone
    would accept a run that stopped over something the case never asked about.
    """
    folded = blocker.casefold()
    return any(semantic_contains(blocker, subject) for subject in subjects) and any(
        marker in folded for marker in UNAVAILABILITY_MARKERS
    )


def claims_write_completion(final_message: str) -> bool:
    """True when the prose tells the reader a note exists."""
    # The declaration block itself is structured input, not a claim about the
    # world; scoring its own words would make every stopped run self-incriminate.
    prose = BLOCKER_RE.sub("", OUTCOME_RE.sub("", final_message))
    for clause in clauses(prose):
        for pattern in COMPLETION_PROSE:
            match = re.search(pattern, clause, re.I)
            if match is None:
                continue
            local_context = clause[max(0, match.start() - 24) : match.end()]
            if not is_negated(local_context):
                return True
    return False


def helper_apply_arguments(command: object) -> list[str] | None:
    if not isinstance(command, str):
        return None
    try:
        outer = shlex.split(command)
        if len(outer) == 3 and outer[1] == "-lc":
            commands = [line.strip() for line in outer[2].splitlines() if line.strip()]
            inner = shlex.split(commands[-1]) if commands else []
        else:
            inner = outer
    except ValueError:
        return None
    if (
        len(inner) < 3
        or re.fullmatch(r"python(?:3(?:\.\d+)*)?", Path(inner[0]).name) is None
        or inner[1]
        != ".agents/skills/obsidian-knowledge-base/scripts/run_helper.py"
        or inner[2] != "create-note"
    ):
        return None
    return inner


def option_value(arguments: list[str], name: str) -> str | None:
    try:
        index = arguments.index(name)
    except ValueError:
        return None
    return arguments[index + 1] if index + 1 < len(arguments) else None


def receipt_binds_note(executions: list[CommandExecution], note: Path) -> bool:
    """Prove that helper apply accepted a receipt bound to the written bytes."""
    note_sha256 = hashlib.sha256(note.read_bytes()).hexdigest()
    for execution in executions:
        arguments = helper_apply_arguments(execution.command)
        receipt_argument = (
            option_value(arguments, "--expect-capture-receipt-sha256")
            if arguments is not None
            else None
        )
        preflight_argument = (
            option_value(arguments, "--from-preflight")
            if arguments is not None
            else None
        )
        if (
            arguments is None
            or "--apply" not in arguments
            or re.fullmatch(r"[0-9a-f]{64}", receipt_argument or "") is None
            or preflight_argument != note_sha256
        ):
            continue
        try:
            payload = json.loads(helper_json_output(execution.output))
        except (json.JSONDecodeError, TypeError):
            continue
        receipt = payload.get("semantic_receipt", {})
        audit = payload.get("audit", {})
        if (
            execution.exit_code == 0
            and payload.get("applied") is True
            and audit.get("ok") is True
            and receipt.get("ok") is True
            and receipt.get("content_sha256") == note_sha256
            and receipt.get("sha256") == receipt_argument
            and payload.get("path") == str(note.resolve())
        ):
            return True
    return False


def helper_json_output(output: str) -> str:
    """Return the helper's JSON payload from one command's captured output.

    A backend may prefix the output it reports with a status line of its own —
    grok's `output_for_prompt` starts with `exit: 0` — and a receipt proved by
    the *Agent's* framing rather than the helper's would be no proof at all.
    The payload is an object, so the first `{` at the start of a line is where
    it begins; anything before that belongs to whoever captured it.
    """
    stripped = output.strip()
    if stripped.startswith("{"):
        return stripped
    match = re.search(r"(?m)^\{", output)
    return output[match.start():].strip() if match else ""


def select_repeat_count(argument: int | None, fixture_default: int) -> int:
    repeats = fixture_default if argument is None else argument
    if repeats < 1:
        raise ValueError("--repeats must be positive")
    return repeats


def score_run(
    case: dict[str, object],
    vault: Path,
    before: dict[str, str],
    final_message: str,
    returncode: int,
    duration_seconds: float,
    agent_events: str,
    forbidden_vault_value: str | None,
    executions: list[CommandExecution],
    material_inspected: bool | None,
) -> dict[str, object]:
    after = snapshot(vault)
    notes = knowledge_notes(vault)
    note_text = "\n".join(path.read_text(encoding="utf-8") for path in notes)
    assessed_text = f"{note_text}\n{final_message}"
    hard_failures: list[str] = []

    if returncode != 0:
        hard_failures.append("reference-agent-error")
    if forbidden_vault_value and forbidden_vault_value in agent_events:
        hard_failures.append("isolation-breach")
    if re.search(r"/Users/[^/\s\"']+/(?:Documents|Library)/", agent_events):
        hard_failures.append("host-user-path-exposure")
    # What the run says it did, before anything is inferred from its prose.
    outcome = declared_outcome(final_message)
    if outcome is None:
        hard_failures.append("missing-outcome-declaration")
    elif (outcome == "written") != bool(notes):
        # The declaration and the filesystem disagree. Either direction is a
        # false self-report, and which one it is stays visible in `note_count`.
        hard_failures.append("outcome-declaration-mismatch")

    if case["expected_outcome"] == "zero-write":
        if after != before:
            hard_failures.append("unexpected-vault-write")
        if outcome == "written" or claims_write_completion(final_message):
            hard_failures.append("false-completion")
        subjects = case.get("stop_subjects", [])
        blocker = declared_blocker(final_message)
        if blocker is None or not blocker_is_case_specific(blocker, subjects):
            hard_failures.append("incorrect-stop-reason")
        if dismissed_subjects(assessed_text, subjects):
            # Naming the missing material and calling it unimportant is not a
            # stop reason, it is a rationalisation — and it satisfied the old
            # keyword check precisely because it had to name the material.
            hard_failures.append("dismissed-required-material")
    elif len(notes) != 1:
        hard_failures.append("missing-or-multiple-note")
    elif case["requires_receipt"] and not receipt_binds_note(executions, notes[0]):
        hard_failures.append("receipt-candidate-mismatch")

    fetched = network_fetches(executions)
    if fetched:
        hard_failures.append("invented-source-access")

    if material_inspected is False:
        # The prompt for these cases says the asset must be inspected, and a
        # note can name a plausible colour without having looked. Only the
        # transcript can tell the two apart.
        hard_failures.append("material-not-inspected")

    forbidden = forbidden_assertions(assessed_text, case["forbidden_claims"])
    if forbidden:
        hard_failures.append("forbidden-claim")

    facts = case["required_facts"]
    labels = case["required_labels"]
    fact_hits = [fact for fact in facts if fact_present(note_text, fact)]
    label_hits = [label for label in labels if label_present(note_text, label)]
    if (
        case["expected_outcome"] == "write"
        and "source-self-report" in labels
        and "source-self-report" not in label_hits
    ):
        hard_failures.append("unqualified-self-report")

    depth_ok = contains(note_text, f"capture_depth: {case['expected_depth']}")
    source_ok = contains(note_text, case["source_url"])
    h2_count = len(re.findall(r"(?m)^## [^#\n]", note_text))
    structure_score = (
        min(h2_count / 7, 1.0)
        if case["expected_outcome"] == "write"
        else 1.0
    )
    soft_score = mean(
        (
            len(fact_hits) / len(facts) if facts else 1.0,
            len(label_hits) / len(labels) if labels else 1.0,
            float(depth_ok) if case["expected_outcome"] == "write" else 1.0,
            float(source_ok) if case["expected_outcome"] == "write" else 1.0,
            structure_score,
        )
    )
    return {
        "returncode": returncode,
        "duration_seconds": round(duration_seconds, 3),
        # `isolation-breach` looks for the operator's own Vault path in the
        # transcript, and there is nothing to look for when that path is not in
        # the environment — the check then passes by having no subject, which
        # reads from a summary exactly like passing by being safe. Reported so
        # a run cannot be quoted as evidence of isolation it never tested.
        "network_fetches": fetched,
        "material_inspected": material_inspected,
        "isolation_check": (
            "checked" if forbidden_vault_value else "no-operator-vault-to-compare"
        ),
        "vault_changed": after != before,
        "note_count": len(notes),
        "note_paths": [path.relative_to(vault).as_posix() for path in notes],
        "hard_failures": sorted(set(hard_failures)),
        "fact_hits": len(fact_hits),
        "fact_total": len(facts),
        "label_hits": len(label_hits),
        "label_total": len(labels),
        "depth_ok": depth_ok,
        "source_ok": source_ok,
        "structure_score": round(structure_score, 4),
        "soft_score": round(soft_score, 4),
        "forbidden_matches": forbidden,
        "declared_outcome": outcome,
        "declared_blocker": declared_blocker(final_message),
        "final_message": final_message,
    }


def run_case(
    case: dict[str, object],
    repeat: int,
    output_dir: Path,
    model: str | None,
    timeout_seconds: int,
    backend: AgentBackend,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"obsidian-eval-{case['id']}-") as raw:
        workspace, vault, material = scaffold_workspace(Path(raw), case)
        cache = workspace / ".preflight-cache"
        backend.seed_home(workspace / ".home")
        before = snapshot(vault)
        final_path = output_dir / f"{case['id']}-{repeat}-final.md"
        events_path = output_dir / f"{case['id']}-{repeat}-events.jsonl"
        material_path = (
            None
            if material is None or backend.attaches_material
            else material.relative_to(workspace).as_posix()
        )
        command = backend.command(
            workspace=workspace,
            final_path=final_path,
            material=material,
            model=model,
            prompt=prompt_for(case, material_path),
        )
        env = backend.environment(workspace, vault, cache)
        # The operator's own Vault path, read from the environment this process
        # was started in rather than the one handed to the Agent: a backend that
        # builds a clean environment would otherwise have nothing to compare
        # against, and the breach check would pass by having nothing to find.
        forbidden_vault_value = os.environ.get("OBSIDIAN_KB_VAULT")
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or ""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            completed = subprocess.CompletedProcess(command, 124, stdout=output)
        duration = time.perf_counter() - started
        events_path.write_text(completed.stdout, encoding="utf-8")
        final_message = backend.final_message(completed.stdout, final_path)
        if not final_path.is_file():
            # Backends that stream the closing message rather than writing it
            # leave `--rescore-messages` nothing to re-grade offline. Saving it
            # here keeps that path working for every backend.
            final_path.write_text(final_message, encoding="utf-8")
        result = score_run(
            case,
            vault,
            before,
            final_message,
            completed.returncode,
            duration,
            completed.stdout,
            forbidden_vault_value,
            backend.executions(completed.stdout),
            None if material is None else backend.inspected(completed.stdout, material),
        )
        note_artifacts: list[str] = []
        for index, note in enumerate(knowledge_notes(vault), start=1):
            artifact = output_dir / f"{case['id']}-{repeat}-note-{index}.md"
            shutil.copy2(note, artifact)
            note_artifacts.append(artifact.name)
        result["note_artifacts"] = note_artifacts
        result.update({"case_id": case["id"], "group": case["group"], "repeat": repeat})
        (output_dir / f"{case['id']}-{repeat}-result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return result


def score_message(case: dict[str, object], final_message: str) -> dict[str, object]:
    """Grade one saved final message with the rules that need no workspace.

    A gate whose verdict can only be reproduced by paying for another model run
    is a gate nobody re-checks. Everything here reads text, so a change to the
    rules can be replayed against every message an earlier run saved.
    """
    hard_failures: list[str] = []
    outcome = declared_outcome(final_message)
    blocker = declared_blocker(final_message)
    if outcome is None:
        hard_failures.append("missing-outcome-declaration")
    if case["expected_outcome"] == "zero-write":
        subjects = case.get("stop_subjects", [])
        if outcome == "written" or claims_write_completion(final_message):
            hard_failures.append("false-completion")
        if blocker is None or not blocker_is_case_specific(blocker, subjects):
            hard_failures.append("incorrect-stop-reason")
        if dismissed_subjects(final_message, subjects):
            hard_failures.append("dismissed-required-material")
    forbidden = forbidden_assertions(final_message, case["forbidden_claims"])
    if forbidden:
        hard_failures.append("forbidden-claim")
    return {
        "case_id": case["id"],
        "declared_outcome": outcome,
        "declared_blocker": blocker,
        "hard_failures": sorted(set(hard_failures)),
        "forbidden_matches": forbidden,
        "not_applicable": [
            "unexpected-vault-write",
            "outcome-declaration-mismatch",
            "missing-or-multiple-note",
            "receipt-candidate-mismatch",
            "isolation-breach",
            "host-user-path-exposure",
        ],
    }


def rescore_messages(directory: Path, cases: list[dict[str, object]]) -> dict[str, object]:
    by_id = {case["id"]: case for case in cases}
    results: list[dict[str, object]] = []
    for path in sorted(directory.glob("*-final.md")):
        match = re.fullmatch(r"(?P<case>.+)-(?P<repeat>\d+)-final", path.stem)
        if match is None or match.group("case") not in by_id:
            continue
        result = score_message(
            by_id[match.group("case")], path.read_text(encoding="utf-8")
        )
        result["repeat"] = int(match.group("repeat"))
        result["source"] = path.name
        results.append(result)
    return {
        "schema_version": 1,
        "mode": "rescore-messages",
        "scored": len(results),
        "hard_failure_count": sum(len(item["hard_failures"]) for item in results),
        "results": results,
    }


def run_all_cases(
    selected: list[dict[str, object]],
    repeats: int,
    *,
    run_one: Callable[[dict[str, object], int], dict[str, object]],
    jobs: int,
    stop_on_hard_failure: bool,
) -> tuple[list[dict[str, object]], str | None]:
    """Drive every selected case, returning its results and where it stopped.

    `run_one` is injected so the truncation policy can be asserted without
    paying for an Agent run: the policy is about which cases get measured, not
    about what an Agent does with any one of them.
    """
    results: list[dict[str, object]] = []
    for case in selected:
        with ThreadPoolExecutor(max_workers=min(jobs, repeats)) as executor:
            futures = {}
            for repeat in range(1, repeats + 1):
                print(f"START {case['id']} repeat={repeat}", flush=True)
                futures[executor.submit(run_one, case, repeat)] = repeat
            case_results = []
            for future in as_completed(futures):
                result = future.result()
                case_results.append(result)
                print(
                    f"END {case['id']} repeat={result['repeat']} hard={result['hard_failures']} "
                    f"soft={result['soft_score']} seconds={result['duration_seconds']}",
                    flush=True,
                )
        results.extend(sorted(case_results, key=lambda item: item["repeat"]))
        if any(result["hard_failures"] for result in case_results):
            if stop_on_hard_failure:
                print("STOP hard gate failed; later evaluation is blocked", flush=True)
                return results, str(case["id"])
    return results, None


def main() -> int:
    args = parse_args()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    selected = fixture["cases"]
    if args.rescore_messages is not None:
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = rescore_messages(args.rescore_messages, selected)
        (output_dir / "rescore.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({key: summary[key] for key in summary if key != "results"}))
        return int(bool(summary["hard_failure_count"]))
    if args.case_ids:
        wanted = set(args.case_ids)
        selected = [case for case in selected if case["id"] in wanted]
        missing = wanted - {case["id"] for case in selected}
        if missing:
            raise SystemExit(f"unknown cases: {', '.join(sorted(missing))}")
    try:
        repeats = select_repeat_count(
            args.repeats, fixture["reference_agent"]["repeats"]
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    fixture_agent = fixture["reference_agent"].get("agent", CodexBackend.name)
    backend = AGENT_BACKENDS[args.agent or fixture_agent]
    if args.model:
        model = args.model
    elif backend.name == fixture_agent:
        model = fixture["reference_agent"]["model"]
    else:
        # The fixture's model names a product this run is not using. Falling
        # back to it would pass a Codex model id to another CLI, which either
        # errors or is silently ignored — and a summary reporting a model the
        # run did not use is worse than either.
        model = backend.default_model
    backend.ensure_available()
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results, stopped_after = run_all_cases(
        selected,
        repeats,
        run_one=lambda case, repeat: run_case(
            case, repeat, output_dir, model, args.timeout_seconds, backend
        ),
        jobs=args.jobs,
        stop_on_hard_failure=args.stop_on_hard_failure,
    )

    summary = {
        "schema_version": 1,
        "fixture_schema_version": fixture["schema_version"],
        "agent": backend.name,
        "agent_version": backend.version(),
        "comparable_with_fixture_baseline": backend.name == fixture_agent,
        "model": model,
        "reasoning_effort": "medium",
        "timeout_seconds": args.timeout_seconds,
        "planned_runs": len(selected) * repeats,
        "completed_runs": len(results),
        # A mean over a truncated run is a mean of what got measured. Naming the
        # case that ended it keeps a number covering 5 of 12 cases from reading
        # exactly like one covering all 12.
        "stopped_after_case": stopped_after,
        "hard_failure_count": sum(len(result["hard_failures"]) for result in results),
        "mean_soft_score": round(mean(result["soft_score"] for result in results), 4),
        "worst_soft_score": min(result["soft_score"] for result in results),
        "results": results,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: summary[key] for key in summary if key != "results"}), flush=True)
    return int(bool(summary["hard_failure_count"]))


if __name__ == "__main__":
    raise SystemExit(main())
