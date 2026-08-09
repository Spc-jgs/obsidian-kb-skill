#!/usr/bin/env python3
"""Run the synthetic Web Capture gate with an isolated Codex CLI reference Agent."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--repeats", type=int)
    parser.add_argument(
        "--model",
        help="Override the fixture-pinned Codex model for every selected run",
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


def scaffold_workspace(base: Path, case: dict[str, object]) -> tuple[Path, Path, Path | None]:
    workspace = base / "workspace"
    vault = workspace / "vault"
    runtime_dir = workspace / ".home" / ".obsidian-kb-skill"
    skill = workspace / ".agents" / "skills" / "obsidian-knowledge-base"
    shutil.copytree(SKILL_SOURCE, skill)
    runtime_dir.mkdir(parents=True)
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


def prompt_for(case: dict[str, object]) -> str:
    availability = (
        "This snapshot is the complete, adequate representation of the public source."
        if case["expected_outcome"] == "write"
        else "This snapshot accurately describes the incomplete or blocked representation available."
    )
    material = (
        " The attached image is a material source asset and must be inspected."
        if case.get("material_asset")
        else ""
    )
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

At the end, state whether you wrote a note or stopped, and why. Keep the response concise.
"""


def knowledge_notes(vault: Path) -> list[Path]:
    return [
        path
        for path in sorted(vault.rglob("*.md"))
        if "Templates" not in path.parts
    ]


def contains(text: str, value: str) -> bool:
    return value.casefold() in text.casefold()


def semantic_contains(text: str, value: str) -> bool:
    """Match facts across harmless Markdown and separator differences."""
    normalize = lambda item: "".join(character for character in item.casefold() if character.isalnum())
    return normalize(value) in normalize(text)


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
    r"(?<=\.)\s+|(?<=[!?;。！？；])\s*|\b(?:but|however|yet)\b|(?:但是|但|然而|不过)",
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
    chinese_negation = re.search(
        r"(?:未|没有)(?:成功)?(?:保存|沉淀|写入|创建|完成)", clause
    )
    return bool(english_negation or chinese_negation) or any(
        marker in folded for marker in NEGATION_MARKERS
    )


def forbidden_assertions(text: str, claims: list[str]) -> list[str]:
    """Return forbidden claims that appear as assertions, not stated absences."""
    matches: list[str] = []
    for claim in claims:
        if any(contains(clause, claim) and not is_negated(clause) for clause in clauses(text)):
            matches.append(claim)
    return matches


def claims_write_completion(final_message: str) -> bool:
    patterns = (
        r"\b(?:i|we)\s+(?:successfully\s+)?(?:wrote|saved|created|completed)\b",
        r"\b(?:the\s+)?(?:requested\s+)?(?:note|capture)\s+(?:was\s+)?"
        r"(?:successfully\s+)?(?:written|saved|created|completed)\b",
        r"(?:已|成功)(?:保存|沉淀|写入|创建|完成)",
        r"(?:笔记|内容)(?:已|成功)(?:保存|写入|创建|完成)",
        r"\b(?:saved|written|created|captured|completed)\s+successfully\b",
        r"\bcaptured\s+(?:the\s+)?(?:requested\s+)?"
        r"(?:note|capture|tutorial|content|article)\b",
        r"\bdone\b[^.!?。！？]*(?:note|capture)\s+is\s+complete\b",
    )
    for clause in clauses(final_message):
        for pattern in patterns:
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


def receipt_binds_note(agent_events: str, note: Path) -> bool:
    """Prove that helper apply accepted a receipt bound to the written bytes."""
    note_sha256 = hashlib.sha256(note.read_bytes()).hexdigest()
    for line in agent_events.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item", {})
        if event.get("type") != "item.completed" or item.get("type") != "command_execution":
            continue
        arguments = helper_apply_arguments(item.get("command"))
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
            payload = json.loads(item.get("aggregated_output", ""))
        except (json.JSONDecodeError, TypeError):
            continue
        receipt = payload.get("semantic_receipt", {})
        audit = payload.get("audit", {})
        if (
            item.get("exit_code") == 0
            and payload.get("applied") is True
            and audit.get("ok") is True
            and receipt.get("ok") is True
            and receipt.get("content_sha256") == note_sha256
            and receipt.get("sha256") == receipt_argument
            and payload.get("path") == str(note.resolve())
        ):
            return True
    return False


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
    if case["expected_outcome"] == "zero-write":
        if after != before:
            hard_failures.append("unexpected-vault-write")
        if claims_write_completion(final_message):
            hard_failures.append("false-completion")
        stop_evidence = case.get("stop_evidence", [])
        if not any(semantic_contains(final_message, item) for item in stop_evidence):
            hard_failures.append("incorrect-stop-reason")
    elif len(notes) != 1:
        hard_failures.append("missing-or-multiple-note")
    elif case["requires_receipt"] and not receipt_binds_note(agent_events, notes[0]):
        hard_failures.append("receipt-candidate-mismatch")

    forbidden = forbidden_assertions(assessed_text, case["forbidden_claims"])
    if forbidden:
        hard_failures.append("forbidden-claim")

    facts = case["required_facts"]
    labels = case["required_labels"]
    fact_hits = [fact for fact in facts if semantic_contains(note_text, fact)]
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
        "final_message": final_message,
    }


def run_case(
    case: dict[str, object],
    repeat: int,
    output_dir: Path,
    model: str | None,
    timeout_seconds: int,
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=f"obsidian-eval-{case['id']}-") as raw:
        workspace, vault, material = scaffold_workspace(Path(raw), case)
        cache = workspace / ".preflight-cache"
        before = snapshot(vault)
        final_path = output_dir / f"{case['id']}-{repeat}-final.md"
        events_path = output_dir / f"{case['id']}-{repeat}-events.jsonl"
        command = [
            "codex",
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
        command.append(prompt_for(case))
        env = os.environ.copy()
        forbidden_vault_value = env.get("OBSIDIAN_KB_VAULT")
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
        final_message = final_path.read_text(encoding="utf-8") if final_path.is_file() else ""
        result = score_run(
            case,
            vault,
            before,
            final_message,
            completed.returncode,
            duration,
            completed.stdout,
            forbidden_vault_value,
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


def main() -> int:
    args = parse_args()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    selected = fixture["cases"]
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
    model = args.model or fixture["reference_agent"]["model"]
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for case in selected:
        with ThreadPoolExecutor(max_workers=min(args.jobs, repeats)) as executor:
            futures = {}
            for repeat in range(1, repeats + 1):
                print(f"START {case['id']} repeat={repeat}", flush=True)
                future = executor.submit(
                    run_case,
                    case,
                    repeat,
                    output_dir,
                    model,
                    args.timeout_seconds,
                )
                futures[future] = repeat
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
            print("STOP hard gate failed; later evaluation is blocked", flush=True)
            break

    summary = {
        "schema_version": 1,
        "fixture_schema_version": fixture["schema_version"],
        "codex_version": subprocess.run(
            ["codex", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        "model": model,
        "reasoning_effort": "medium",
        "timeout_seconds": args.timeout_seconds,
        "planned_runs": len(selected) * repeats,
        "completed_runs": len(results),
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
