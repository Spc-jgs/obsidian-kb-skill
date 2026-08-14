#!/usr/bin/env python3
"""Launch one helper bundled with the standard Obsidian Skill."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


HELPERS = {
    "audit-vault": "obsidian_kb_skill.scripts.audit_vault",
    "capture-receipt": "obsidian_kb_skill.scripts.capture_receipt",
    "process-inbox": "obsidian_kb_skill.scripts.process_inbox",
    "suggest-links": "obsidian_kb_skill.scripts.suggest_links",
    "template-contract": "obsidian_kb_skill.scripts.template_contract",
    "create-category": "obsidian_kb_skill.scripts.create_category",
    "create-note": "obsidian_kb_skill.scripts.create_note",
    "archive-source": "obsidian_kb_skill.scripts.archive_source",
    "update-note": "obsidian_kb_skill.scripts.update_note",
    "vault-info": "obsidian_kb_skill.scripts.vault_info",
    "detect-index": "obsidian_kb_skill.scripts.detect_index",
    "scaffold-templates": "obsidian_kb_skill.scripts.scaffold_templates",
    "doctor": "obsidian_kb_skill.scripts.doctor",
}

# Helpers this Skill does not carry, and where they do live. Names only — no
# import, no dependency, nothing that would pull the other Skill's modules in.
#
# Without this, asking the wrong runner for a real capability returns nothing
# but `invalid choice`, which reads as "no such capability". That has already
# cost someone two rounds and a hand-rolled PYTHONPATH workaround for a helper
# that was working the whole time.
PEER_SKILL = "obsidian-knowledge-retrieval"
PEER_HELPERS = frozenset({
    "explore-neighborhood",
    "resume-project",
    "review-projects",
    "run-retrieval-view",
    "search-vault",
})


def python_command(home: Path | None = None) -> list[str]:
    """Return the installer-selected Python command, or this interpreter."""
    runtime_file = (home or Path.home()) / ".obsidian-kb-skill" / "runtime.json"
    if not runtime_file.is_file():
        return [sys.executable]
    try:
        payload = json.loads(runtime_file.read_text(encoding="utf-8"))
        command = payload["python"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid Skill runtime record: {runtime_file}: {exc}") from exc
    if not isinstance(command, list) or not command or not all(
        isinstance(part, str) and part for part in command
    ):
        raise RuntimeError(
            f"invalid Skill runtime record: {runtime_file}: python must be a string list"
        )
    return command


def helper_environment(skill_root: Path, *, home: Path | None = None) -> dict[str, str]:
    """Build an environment that imports only installed Skill-owned code."""
    resolved_home = home or Path.home()
    scripts_dir = skill_root / "scripts"
    vendor_dir = resolved_home / ".obsidian-kb-skill" / "vendor"
    python_paths = [str(scripts_dir)]
    if vendor_dir.is_dir():
        python_paths.append(str(vendor_dir))
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    env["OBSIDIAN_KB_SKILL_ROOT"] = str(skill_root)
    return env


def parse_dispatch(argv: list[str] | None = None) -> tuple[str, list[str]]:
    """Parse only the helper token and preserve all child arguments verbatim."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description="Run a helper bundled with the Obsidian Knowledge Base Skill."
    )
    parser.add_argument("helper", choices=sorted(HELPERS))
    if not arguments or arguments[0] in {"-h", "--help"}:
        parser.parse_args(arguments)
        raise AssertionError("argparse help should exit")
    if arguments[0] in PEER_HELPERS:
        # It exists — just not here. Saying only "invalid choice" sends the
        # reader looking for a capability that is working fine one Skill over.
        print(
            f"error: `{arguments[0]}` is provided by the {PEER_SKILL} Skill, "
            f"not this one.\n"
            f"Run it through that Skill's run_helper.py. Invoking the module "
            f"directly will fail on dependencies: this runner is what puts the "
            f"vendored packages on the path.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if arguments[0] not in HELPERS:
        parser.parse_args(arguments[:1])
        raise AssertionError("argparse validation should exit")
    helper = arguments[0]
    forwarded = arguments[1:]
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    return helper, forwarded


def main(argv: list[str] | None = None) -> int:
    helper, forwarded = parse_dispatch(argv)
    skill_root = Path(__file__).resolve().parent.parent
    command = [sys.executable] if helper == "doctor" else None
    if command is None:
        try:
            command = python_command()
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3
    # Windows PowerShell 5.1 does not reliably preserve an inherited native
    # pipeline across this launcher and its child process.  When create-note
    # explicitly requests stdin, bridge the original bytes ourselves so UTF-8
    # frontmatter and content reach the helper unchanged.
    stdin_bytes = (
        sys.stdin.buffer.read()
        if helper == "create-note" and "--stdin" in forwarded
        else None
    )
    try:
        return subprocess.run(
            [*command, "-P", "-m", HELPERS[helper], *forwarded],
            env=helper_environment(skill_root),
            check=False,
            input=stdin_bytes,
        ).returncode
    except OSError as exc:
        print(f"error: helper runtime failed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
