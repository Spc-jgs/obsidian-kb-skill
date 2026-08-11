#!/usr/bin/env python3
"""Launch one read-only helper bundled with the retrieval Skill."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


HELPERS = {
    "doctor": "obsidian_kb_skill.scripts.doctor",
    "review-projects": "obsidian_kb_skill.scripts.review_projects",
    "search-vault": "obsidian_kb_skill.scripts.search_vault",
    "vault-info": "obsidian_kb_skill.scripts.retrieval_vault_info",
}


def python_command(home: Path | None = None) -> list[str]:
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
    resolved_home = home or Path.home()
    python_paths = [str(skill_root / "scripts")]
    vendor = resolved_home / ".obsidian-kb-skill" / "vendor"
    if vendor.is_dir():
        python_paths.append(str(vendor))
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    env["OBSIDIAN_KB_SKILL_ROOT"] = str(skill_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def parse_dispatch(argv: list[str] | None = None) -> tuple[str, list[str]]:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description="Run a read-only helper bundled with Obsidian retrieval."
    )
    parser.add_argument("helper", choices=sorted(HELPERS))
    if not arguments or arguments[0] in {"-h", "--help"}:
        parser.parse_args(arguments)
        raise AssertionError("argparse help should exit")
    if arguments[0] not in HELPERS:
        parser.parse_args(arguments[:1])
        raise AssertionError("argparse validation should exit")
    forwarded = arguments[1:]
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    return arguments[0], forwarded


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
    try:
        return subprocess.run(
            [*command, "-P", "-m", HELPERS[helper], *forwarded],
            env=helper_environment(skill_root),
            check=False,
        ).returncode
    except OSError as exc:
        print(f"error: helper runtime failed: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
