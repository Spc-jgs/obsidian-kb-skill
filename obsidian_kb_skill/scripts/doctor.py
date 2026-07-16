#!/usr/bin/env python3
"""Read-only diagnostics for an installed standard Skill payload."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


HOUSEKEEPING = {".DS_Store", "__pycache__"}
REQUIRED_RESOURCES = (
    "SKILL.md",
    "references/note-creation.md",
    "references/rules-and-errors.md",
    "assets/templates/daily-note.md",
    "scripts/run_helper.py",
)
HELPER_MODULES = (
    "audit_vault",
    "process_inbox",
    "suggest_links",
    "template_contract",
    "create_category",
    "create_note",
    "update_note",
    "vault_info",
    "detect_index",
    "scaffold_templates",
    "doctor",
)


def _check(name: str, ok: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details}


def _excluded(relative: PurePosixPath) -> bool:
    return (
        relative == PurePosixPath("header.md")
        or relative == PurePosixPath("manifest.json")
        or any(part in HOUSEKEEPING for part in relative.parts)
        or relative.suffix in {".pyc", ".pyo"}
    )


def _safe_manifest_path(raw: str) -> bool:
    relative = PurePosixPath(raw)
    return (
        bool(raw)
        and "\\" not in raw
        and not relative.is_absolute()
        and raw == relative.as_posix()
        and all(part not in {"", ".", ".."} for part in relative.parts)
        and ":" not in relative.parts[0]
        and not _excluded(relative)
    )


def _actual_files(skill_root: Path) -> set[str]:
    result: set[str] = set()
    if not skill_root.is_dir():
        return result
    for directory, names, filenames in os.walk(skill_root, followlinks=False):
        parent = Path(directory)
        for name in list(names):
            path = parent / name
            if path.is_symlink():
                relative = PurePosixPath(path.relative_to(skill_root).as_posix())
                if not _excluded(relative):
                    result.add(relative.as_posix())
                names.remove(name)
        for name in filenames:
            path = parent / name
            relative = PurePosixPath(path.relative_to(skill_root).as_posix())
            if not _excluded(relative):
                result.add(relative.as_posix())
    return result


def _read_manifest(root: Path) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    manifest: dict[str, Any] = {}
    files: dict[str, str] = {}
    error = "unsupported manifest"
    try:
        payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("manifest must be an object")
        manifest = payload
        candidate_files = payload.get("files")
        valid = (
            payload.get("schema_version") == 1
            and payload.get("product") == "obsidian-kb-skill"
            and isinstance(payload.get("version"), str)
            and re.fullmatch(r"\d+\.\d+\.\d+", payload["version"]) is not None
            and isinstance(candidate_files, dict)
            and all(
                isinstance(path, str)
                and _safe_manifest_path(path)
                and isinstance(digest, str)
                and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                for path, digest in candidate_files.items()
            )
        )
        if valid:
            files = dict(candidate_files)
        else:
            error = "unsupported manifest schema, version, path, or digest"
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        valid = False
        error = str(exc)
    return manifest, files, _check("manifest", valid, error=None if valid else error)


def _runtime(home: Path) -> tuple[list[str] | None, dict[str, Any]]:
    runtime_file = home / ".obsidian-kb-skill" / "runtime.json"
    try:
        payload = json.loads(runtime_file.read_text(encoding="utf-8"))
        command = payload["python"]
        valid = (
            payload.get("schema_version") == 1
            and isinstance(command, list)
            and bool(command)
            and all(isinstance(part, str) and part for part in command)
            and Path(command[0]).is_file()
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return None, _check("runtime", False, error=str(exc))
    if not valid:
        return None, _check("runtime", False, error="invalid runtime command")
    try:
        probe = subprocess.run(
            [
                *command,
                "-B",
                "-c",
                "import sys; print('.'.join(map(str, sys.version_info[:3])))",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, _check("runtime", False, command=command, error=str(exc))
    try:
        parsed_version = tuple(
            int(part) for part in probe.stdout.strip().split(".")[:2]
        )
    except ValueError:
        parsed_version = ()
    ok = probe.returncode == 0 and parsed_version >= (3, 11)
    return command if ok else None, _check(
        "runtime",
        ok,
        command=command,
        version=probe.stdout.strip(),
        error=probe.stderr.strip() or None,
    )


def _dependencies(
    root: Path, home: Path, command: list[str] | None
) -> dict[str, Any]:
    if command is None:
        return _check("dependencies", False, error="runtime check failed")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(root / "scripts"), str(home / ".obsidian-kb-skill" / "vendor")]
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    code = "import yaml;" + ";".join(
        f"import obsidian_kb_skill.scripts.{name}" for name in HELPER_MODULES
    )
    try:
        probe = subprocess.run(
            [*command, "-B", "-c", code],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _check("dependencies", False, error=str(exc))
    return _check(
        "dependencies",
        probe.returncode == 0,
        error=probe.stderr.strip() or None,
    )


def inspect_installation(
    skill_root: Path, home: Path | None = None
) -> dict[str, Any]:
    """Inspect an installed Skill without writing, repairing, or deleting files."""
    root = skill_root.expanduser().resolve()
    resolved_home = (home or Path.home()).expanduser().resolve()
    manifest, files, manifest_check = _read_manifest(root)
    checks = [manifest_check]

    actual = _actual_files(root)
    expected = set(files)
    changed: list[str] = []
    unreadable: dict[str, str] = {}
    for relative in sorted(actual & expected):
        path = root / relative
        if path.is_symlink() or not path.is_file():
            changed.append(relative)
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            unreadable[relative] = str(exc)
            continue
        if digest != files[relative]:
            changed.append(relative)
    checks.append(
        _check(
            "payload",
            manifest_check["ok"]
            and not (expected - actual)
            and not (actual - expected)
            and not changed
            and not unreadable,
            missing=sorted(expected - actual),
            extra=sorted(actual - expected),
            changed=changed,
            unreadable=unreadable,
        )
    )

    command, runtime_check = _runtime(resolved_home)
    checks.append(runtime_check)
    checks.append(_dependencies(root, resolved_home, command))
    missing_resources = [
        relative
        for relative in REQUIRED_RESOURCES
        if not (root / relative).is_file() or (root / relative).is_symlink()
    ]
    checks.append(_check("resources", not missing_resources, missing=missing_resources))
    return {
        "schema_version": "1.0",
        "ok": all(check["ok"] for check in checks),
        "version": manifest.get("version"),
        "skill_root": str(root),
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose an installed Obsidian Knowledge Base Skill."
    )
    parser.add_argument("--skill-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = args.skill_root
    if root is None:
        raw_root = os.environ.get("OBSIDIAN_KB_SKILL_ROOT")
        if not raw_root:
            parser.error("--skill-root or OBSIDIAN_KB_SKILL_ROOT is required")
        root = Path(raw_root)
    result = inspect_installation(root)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Obsidian Knowledge Base Skill {result['version'] or 'unknown'}")
        for check in result["checks"]:
            print(f"{'PASS' if check['ok'] else 'FAIL'}  {check['name']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
