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
    "process-inbox": "obsidian_kb_skill.scripts.process_inbox",
    "suggest-links": "obsidian_kb_skill.scripts.suggest_links",
    "create-note": "obsidian_kb_skill.scripts.create_note",
    "update-note": "obsidian_kb_skill.scripts.update_note",
    "vault-info": "obsidian_kb_skill.scripts.vault_info",
    "detect-index": "obsidian_kb_skill.scripts.detect_index",
    "scaffold-templates": "obsidian_kb_skill.scripts.scaffold_templates",
}


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
    existing = os.environ.get("PYTHONPATH")
    if existing:
        python_paths.append(existing)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    env["OBSIDIAN_KB_SKILL_ROOT"] = str(skill_root)
    return env


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a helper bundled with the Obsidian Knowledge Base Skill."
    )
    parser.add_argument("helper", choices=sorted(HELPERS))
    args, forwarded = parser.parse_known_args(argv)
    skill_root = Path(__file__).resolve().parent.parent
    try:
        command = python_command()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    return subprocess.run(
        [*command, "-m", HELPERS[args.helper], *forwarded],
        env=helper_environment(skill_root),
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
