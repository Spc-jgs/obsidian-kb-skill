#!/usr/bin/env python3
"""Build the standard Agent Skill and platform adapters from the shared core.

Single source of truth = core/OBSIDIAN_KB.md (body starting from "## Overview").
Each target contributes only its own header (YAML frontmatter, H1, trigger hint).
This script concatenates header + body and writes the adapter file.

Usage:
    python build.py            # build all adapters
    python build.py --check    # exit non-zero if any adapter is out of sync

Outputs are written with UTF-8 (no BOM) and LF line endings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent
CORE_FILE = ROOT / "core" / "OBSIDIAN_KB.md"
BODY_MARKER = "## Overview"

@dataclass(frozen=True)
class BuildTarget:
    """One generated instruction artifact."""

    name: str
    header: Path
    output: Path


TARGETS = [
    BuildTarget(
        "standard-agent-skill",
        ROOT / "skills" / "obsidian-knowledge-base" / "header.md",
        ROOT / "skills" / "obsidian-knowledge-base" / "SKILL.md",
    ),
    BuildTarget(
        "qoderwork",
        ROOT / "skills" / "obsidian-knowledge-base" / "header.md",
        ROOT / "platforms" / "qoderwork" / "SKILL.md",
    ),
    BuildTarget(
        "claude-code",
        ROOT / "platforms" / "claude-code" / "header.md",
        ROOT / "platforms" / "claude-code" / "CLAUDE.md",
    ),
    BuildTarget(
        "codex",
        ROOT / "platforms" / "codex" / "header.md",
        ROOT / "platforms" / "codex" / "AGENTS.md",
    ),
    BuildTarget(
        "cursor",
        ROOT / "platforms" / "cursor" / "header.md",
        ROOT / "platforms" / "cursor" / "obsidian-kb.mdc",
    ),
]

# Reference docs are lazy-loaded: an agent reads them only when needed, so they
# are NOT part of the always-loaded body. build.py ships them next to each
# generated artifact so the relative path in the pointer resolves for every agent.
REFERENCES_SRC = ROOT / "core" / "references"

# Bundled runtime templates/references that ship inside the wheel. They are kept
# in sync from core/ so the wheel carries the same single source of truth that
# the repo reads. This is the resource_locator's default (importlib.resources) path.
PACKAGED_RESOURCES = ROOT / "obsidian_kb_skill" / "scripts" / "resources"
PACKAGED_TEMPLATES_SRC = ROOT / "core" / "templates"
PACKAGED_REFERENCES_SRC = REFERENCES_SRC
PACKAGED_TEMPLATES_DST = PACKAGED_RESOURCES / "templates"
PACKAGED_REFERENCES_DST = PACKAGED_RESOURCES / "references"

# A standard Skill is a self-contained folder. Build its assets and bundled
# helper implementation from the same canonical sources as the wheel.
STANDARD_SKILL_ROOT = ROOT / "skills" / "obsidian-knowledge-base"
STANDARD_ASSETS_DST = STANDARD_SKILL_ROOT / "assets" / "templates"
STANDARD_HELPER_SRC = ROOT / "obsidian_kb_skill"
STANDARD_HELPER_DST = STANDARD_SKILL_ROOT / "scripts" / "obsidian_kb_skill"
PYPROJECT = ROOT / "pyproject.toml"
STANDARD_MANIFEST = STANDARD_SKILL_ROOT / "manifest.json"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _file_map(
    root: Path,
    *,
    exclude: Callable[[Path], bool],
) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if exclude(relative):
            continue
        files[relative.as_posix()] = path
    return files


def tree_drift(
    src: Path,
    dst: Path,
    *,
    exclude: Callable[[Path], bool],
) -> list[str]:
    """Return stable missing/changed/extra diagnostics for two file trees."""
    source = _file_map(src, exclude=exclude)
    target = _file_map(dst, exclude=exclude)
    drift: list[str] = []
    for relative in sorted(source.keys() | target.keys()):
        if relative not in target:
            drift.append(f"missing: {relative}")
        elif relative not in source:
            drift.append(f"extra: {relative}")
        elif source[relative].read_bytes() != target[relative].read_bytes():
            drift.append(f"changed: {relative}")
    return sorted(drift)


def sync_exact_tree(
    src: Path,
    dst: Path,
    *,
    exclude: Callable[[Path], bool],
) -> None:
    """Mirror the non-excluded files from ``src`` into ``dst`` exactly."""
    source = _file_map(src, exclude=exclude)
    target = _file_map(dst, exclude=exclude)
    for relative, path in target.items():
        if relative not in source:
            path.unlink()
    for relative, path in source.items():
        destination = dst / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    if dst.is_dir():
        for directory in sorted(
            (path for path in dst.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                directory.rmdir()


def _exclude_housekeeping(relative: Path) -> bool:
    return any(part in {".DS_Store", "__pycache__"} for part in relative.parts) or (
        relative.suffix in {".pyc", ".pyo"}
    )


def project_version(pyproject: Path = PYPROJECT) -> str:
    """Return the distribution version from ``pyproject.toml``."""
    with pyproject.open("rb") as handle:
        payload = tomllib.load(handle)
    return str(payload["project"]["version"])


def _exclude_manifest_file(relative: Path) -> bool:
    return (
        _exclude_housekeeping(relative)
        or relative == Path("header.md")
        or relative == Path("manifest.json")
    )


def skill_payload_files(root: Path) -> dict[str, Path]:
    """Return every regular installable Skill payload file in stable order."""
    return {
        relative: path
        for relative, path in sorted(
            _file_map(root, exclude=_exclude_manifest_file).items()
        )
        if not path.is_symlink()
    }


def build_skill_manifest(root: Path, version: str) -> dict[str, object]:
    files = {
        relative: hashlib.sha256(path.read_bytes()).hexdigest()
        for relative, path in skill_payload_files(root).items()
    }
    return {
        "schema_version": 1,
        "product": "obsidian-kb-skill",
        "version": version,
        "files": dict(sorted(files.items())),
    }


def render_skill_manifest(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _exclude_standard_helper(relative: Path) -> bool:
    if _exclude_housekeeping(relative):
        return True
    return relative.parts[:2] == ("scripts", "resources")


def _record_tree_drift(
    drift: list[str],
    *,
    src: Path,
    dst: Path,
    exclude: Callable[[Path], bool],
) -> None:
    for item in tree_drift(src, dst, exclude=exclude):
        drift.append(f"{dst.relative_to(ROOT).as_posix()}: {item}")


def write_text(path: Path, content: str) -> None:
    # UTF-8 without BOM, LF line endings.
    path.write_bytes(content.replace("\r\n", "\n").encode("utf-8"))


def extract_body(core_text: str) -> str:
    """Return everything from the BODY_MARKER heading onward.

    Only matches the marker when it appears at the start of a line
    (i.e. as a real markdown heading), not inside a quoted reference.
    """
    needle = "\n" + BODY_MARKER + "\n"
    idx = core_text.find(needle)
    if idx == -1:
        # Also accept the marker as the very first line of the file.
        if core_text.startswith(BODY_MARKER + "\n"):
            return core_text
        raise SystemExit(
            f"core/OBSIDIAN_KB.md is missing the body marker heading '{BODY_MARKER}'. "
            "Add the heading or update build.py."
        )
    return core_text[idx + 1 :]  # drop the leading newline


def build_adapter(header: str, body: str, header_path: str) -> str:
    banner = (
        "<!-- AUTO-GENERATED by build.py from core/OBSIDIAN_KB.md + "
        f"{header_path}. DO NOT EDIT DIRECTLY. -->\n\n"
    )
    # If header has YAML frontmatter, put banner AFTER the closing ---.
    if header.startswith("---\n"):
        end = header.find("\n---\n", 4)
        if end != -1:
            split_at = end + len("\n---\n")
            heading = header[split_at:].strip("\n")
            return header[:split_at] + "\n" + banner + heading + "\n\n" + body
    return banner + header.rstrip("\n") + "\n\n" + body


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the standard Skill and compatibility adapters."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated files match source; exit 1 if out of sync.",
    )
    args = parser.parse_args()

    core_text = read_text(CORE_FILE)
    body = extract_body(core_text)

    drift = []
    for target in TARGETS:
        if not target.header.exists():
            raise SystemExit(f"Missing header: {target.header}")
        header = read_text(target.header)
        header_path = target.header.relative_to(ROOT).as_posix()
        adapter = build_adapter(header, body, header_path)

        if args.check:
            if not target.output.exists() or read_text(target.output) != adapter:
                drift.append(str(target.output.relative_to(ROOT)))
        else:
            write_text(target.output, adapter)
            print(f"  wrote {target.output.relative_to(ROOT)}")

        # Ship lazy references next to every generated adapter.
        references_dst = target.output.parent / "references"
        if args.check:
            _record_tree_drift(
                drift,
                src=REFERENCES_SRC,
                dst=references_dst,
                exclude=_exclude_housekeeping,
            )
        else:
            sync_exact_tree(
                REFERENCES_SRC,
                references_dst,
                exclude=_exclude_housekeeping,
            )
            print(f"  synced {references_dst.relative_to(ROOT)}")

    generated_trees = [
        (PACKAGED_TEMPLATES_SRC, PACKAGED_TEMPLATES_DST, _exclude_housekeeping),
        (PACKAGED_REFERENCES_SRC, PACKAGED_REFERENCES_DST, _exclude_housekeeping),
        (PACKAGED_TEMPLATES_SRC, STANDARD_ASSETS_DST, _exclude_housekeeping),
        (STANDARD_HELPER_SRC, STANDARD_HELPER_DST, _exclude_standard_helper),
    ]
    for src, dst, exclude in generated_trees:
        if args.check:
            _record_tree_drift(drift, src=src, dst=dst, exclude=exclude)
        else:
            sync_exact_tree(src, dst, exclude=exclude)
            print(f"  synced {dst.relative_to(ROOT)}")

    manifest_text = render_skill_manifest(
        build_skill_manifest(STANDARD_SKILL_ROOT, project_version())
    )
    if args.check:
        if (
            not STANDARD_MANIFEST.is_file()
            or read_text(STANDARD_MANIFEST) != manifest_text
        ):
            drift.append(STANDARD_MANIFEST.relative_to(ROOT).as_posix())
    else:
        write_text(STANDARD_MANIFEST, manifest_text)
        print(f"  wrote {STANDARD_MANIFEST.relative_to(ROOT)}")

    if args.check:
        if drift:
            print("Out of sync:", file=sys.stderr)
            for f in drift:
                print(f"  - {f}", file=sys.stderr)
            print("\nRun: python build.py", file=sys.stderr)
            return 1
        print("All generated artifacts are up to date.")
        return 0

    print(f"\nBuilt {len(TARGETS)} artifacts from core/OBSIDIAN_KB.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
