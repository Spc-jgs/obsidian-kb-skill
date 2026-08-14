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
RETRIEVAL_CORE_FILE = ROOT / "core" / "RETRIEVAL.md"
BODY_MARKER = "## Overview"

@dataclass(frozen=True)
class BuildTarget:
    """One generated instruction artifact."""

    name: str
    core: Path
    header: Path
    output: Path
    references: Path


REFERENCES_SRC = ROOT / "core" / "references"
RETRIEVAL_REFERENCES_SRC = ROOT / "core" / "retrieval-references"

# `vault_paths` and `frontmatter` ship in both Skill bundles, so both Agents can
# receive their refusals — but `core/references/` reaches only the write Skill.
# The write reference stays the single source (it is the main capability and its
# table must stay complete on its own); the marked block is fanned out to the
# retrieval Skill rather than maintained twice.
SHARED_ERRORS_SRC = REFERENCES_SRC / "rules-and-errors.md"
SHARED_ERRORS_OUT = RETRIEVAL_REFERENCES_SRC / "shared-errors.md"
SHARED_ERRORS_BEGIN = "<!-- BEGIN shared-refusals"
SHARED_ERRORS_END = "<!-- END shared-refusals -->"
SHARED_ERRORS_HEADING = """# Shared Refusal Codes

These come from the path and frontmatter guards both Skills bundle. With
`--json` a helper refuses through `{"error": {"code", "message"}}` and returns
nothing else; `search-vault` also reports frontmatter codes per note in its
bounded `issues` list. A refusal is the contract, not an obstacle: this Skill is
read-only and never repairs a note to make one go away.
"""


TARGETS = [
    BuildTarget(
        "standard-agent-skill",
        CORE_FILE,
        ROOT / "skills" / "obsidian-knowledge-base" / "header.md",
        ROOT / "skills" / "obsidian-knowledge-base" / "SKILL.md",
        REFERENCES_SRC,
    ),
    BuildTarget(
        "standard-retrieval-skill",
        RETRIEVAL_CORE_FILE,
        ROOT / "skills" / "obsidian-knowledge-retrieval" / "header.md",
        ROOT / "skills" / "obsidian-knowledge-retrieval" / "SKILL.md",
        RETRIEVAL_REFERENCES_SRC,
    ),
    BuildTarget(
        "qoderwork",
        CORE_FILE,
        ROOT / "skills" / "obsidian-knowledge-base" / "header.md",
        ROOT / "platforms" / "qoderwork" / "SKILL.md",
        REFERENCES_SRC,
    ),
    BuildTarget(
        "claude-code",
        CORE_FILE,
        ROOT / "platforms" / "claude-code" / "header.md",
        ROOT / "platforms" / "claude-code" / "CLAUDE.md",
        REFERENCES_SRC,
    ),
    BuildTarget(
        "codex",
        CORE_FILE,
        ROOT / "platforms" / "codex" / "header.md",
        ROOT / "platforms" / "codex" / "AGENTS.md",
        REFERENCES_SRC,
    ),
    BuildTarget(
        "cursor",
        CORE_FILE,
        ROOT / "platforms" / "cursor" / "header.md",
        ROOT / "platforms" / "cursor" / "obsidian-kb.mdc",
        REFERENCES_SRC,
    ),
]

# Reference docs are lazy-loaded: an agent reads them only when needed, so they
# are NOT part of the always-loaded body. build.py ships them next to each
# generated artifact so the relative path in the pointer resolves for every agent.

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
RETRIEVAL_SKILL_ROOT = ROOT / "skills" / "obsidian-knowledge-retrieval"
STANDARD_ASSETS_DST = STANDARD_SKILL_ROOT / "assets" / "templates"
STANDARD_HELPER_SRC = ROOT / "obsidian_kb_skill"
STANDARD_HELPER_DST = STANDARD_SKILL_ROOT / "scripts" / "obsidian_kb_skill"
RETRIEVAL_HELPER_DST = RETRIEVAL_SKILL_ROOT / "scripts" / "obsidian_kb_skill"
RETRIEVAL_HELPER_FILES = (
    Path("__init__.py"),
    Path("scripts/__init__.py"),
    Path("scripts/console.py"),
    Path("scripts/doctor.py"),
    Path("scripts/frontmatter.py"),
    # Resolving a wikilink the way Obsidian does, extracted from `audit_vault`
    # so `explore-neighborhood` can reach it without dragging the write-side
    # closure into this bundle (#121). Depends on `frontmatter` and nothing else.
    Path("scripts/link_graph.py"),
    # Shared note domain: retrieval needs the same judgement about what is
    # a note as the write Skill, and the same tag identity rules.
    Path("scripts/note_catalog.py"),
    # The bilingual lexicon and the one tokenizer both sides of a match must
    # share. Ship them or `search_vault` cannot import, and a lexicon tokenized
    # differently from the index would silently match nothing.
    Path("scripts/query_expansion.py"),
    # `resume_project` derives the digest section names from this contract
    # rather than restating them, so the contract travels with it. Zero further
    # dependencies and ~2 KB, which is what makes deriving cheaper than copying.
    Path("scripts/conversation_digest_contract.py"),
    Path("scripts/explore_neighborhood.py"),
    Path("scripts/resume_project.py"),
    Path("scripts/retrieval_vault_info.py"),
    Path("scripts/review_projects.py"),
    Path("scripts/search_vault.py"),
    Path("scripts/text_tokens.py"),
    Path("scripts/vault_paths.py"),
)
RETRIEVAL_RUNNER_SRC = ROOT / "core" / "retrieval-run-helper.py"
RETRIEVAL_RUNNER_DST = RETRIEVAL_SKILL_ROOT / "scripts" / "run_helper.py"
PYPROJECT = ROOT / "pyproject.toml"
STANDARD_MANIFEST = STANDARD_SKILL_ROOT / "manifest.json"
RETRIEVAL_MANIFEST = RETRIEVAL_SKILL_ROOT / "manifest.json"


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


def selected_tree_drift(
    src: Path,
    dst: Path,
    relative_files: tuple[Path, ...],
) -> list[str]:
    expected = {path.as_posix() for path in relative_files}
    actual = set(_file_map(dst, exclude=_exclude_housekeeping))
    drift: list[str] = []
    for relative in sorted(expected | actual):
        source = src / relative
        target = dst / relative
        if relative not in actual:
            drift.append(f"missing: {relative}")
        elif relative not in expected:
            drift.append(f"extra: {relative}")
        elif not source.is_file():
            drift.append(f"missing source: {relative}")
        elif source.read_bytes() != target.read_bytes():
            drift.append(f"changed: {relative}")
    return drift


def sync_selected_tree(
    src: Path,
    dst: Path,
    relative_files: tuple[Path, ...],
) -> None:
    expected = {path.as_posix() for path in relative_files}
    for relative, path in _file_map(dst, exclude=_exclude_housekeeping).items():
        if relative not in expected:
            path.unlink()
    for relative in relative_files:
        source = src / relative
        if not source.is_file():
            raise SystemExit(f"Missing retrieval helper source: {source}")
        target = dst / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
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


def build_adapter(
    header: str,
    body: str,
    header_path: str,
    core_path: str = "core/OBSIDIAN_KB.md",
) -> str:
    banner = (
        f"<!-- AUTO-GENERATED by build.py from {core_path} + "
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


def build_shared_errors(reference_text: str) -> str:
    """Return the retrieval Skill's copy of the shared refusal table."""
    start = reference_text.find(SHARED_ERRORS_BEGIN)
    end = reference_text.find(SHARED_ERRORS_END)
    if start == -1 or end == -1 or end < start:
        raise SystemExit(
            f"{SHARED_ERRORS_SRC.relative_to(ROOT).as_posix()} is missing the "
            f"'{SHARED_ERRORS_BEGIN}' / '{SHARED_ERRORS_END}' markers around the "
            "codes both Skills can emit. Restore them or update build.py."
        )
    block = reference_text[reference_text.index("-->", start) + 3 : end].strip("\n")
    source = SHARED_ERRORS_SRC.relative_to(ROOT).as_posix()
    banner = (
        f"<!-- AUTO-GENERATED by build.py from the shared-refusals block in "
        f"{source}. DO NOT EDIT DIRECTLY. -->\n\n"
    )
    return banner + SHARED_ERRORS_HEADING + "\n" + block + "\n"


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

    drift = []
    # Generate before the reference trees are synced, so the retrieval bundle
    # picks the fresh copy up in the same run.
    shared_errors = build_shared_errors(read_text(SHARED_ERRORS_SRC))
    if args.check:
        if (
            not SHARED_ERRORS_OUT.exists()
            or read_text(SHARED_ERRORS_OUT) != shared_errors
        ):
            drift.append(str(SHARED_ERRORS_OUT.relative_to(ROOT)))
    else:
        write_text(SHARED_ERRORS_OUT, shared_errors)
        print(f"  wrote {SHARED_ERRORS_OUT.relative_to(ROOT)}")

    for target in TARGETS:
        if not target.core.exists():
            raise SystemExit(f"Missing core: {target.core}")
        if not target.header.exists():
            raise SystemExit(f"Missing header: {target.header}")
        body = extract_body(read_text(target.core))
        header = read_text(target.header)
        header_path = target.header.relative_to(ROOT).as_posix()
        core_path = target.core.relative_to(ROOT).as_posix()
        adapter = build_adapter(header, body, header_path, core_path)

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
                src=target.references,
                dst=references_dst,
                exclude=_exclude_housekeeping,
            )
        else:
            sync_exact_tree(
                target.references,
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

    if args.check:
        for item in selected_tree_drift(
            STANDARD_HELPER_SRC,
            RETRIEVAL_HELPER_DST,
            RETRIEVAL_HELPER_FILES,
        ):
            drift.append(
                f"{RETRIEVAL_HELPER_DST.relative_to(ROOT).as_posix()}: {item}"
            )
    else:
        sync_selected_tree(
            STANDARD_HELPER_SRC,
            RETRIEVAL_HELPER_DST,
            RETRIEVAL_HELPER_FILES,
        )
        print(f"  synced {RETRIEVAL_HELPER_DST.relative_to(ROOT)}")

    if args.check:
        if (
            not RETRIEVAL_RUNNER_DST.is_file()
            or RETRIEVAL_RUNNER_DST.read_bytes() != RETRIEVAL_RUNNER_SRC.read_bytes()
        ):
            drift.append(RETRIEVAL_RUNNER_DST.relative_to(ROOT).as_posix())
    else:
        RETRIEVAL_RUNNER_DST.write_bytes(RETRIEVAL_RUNNER_SRC.read_bytes())
        print(f"  wrote {RETRIEVAL_RUNNER_DST.relative_to(ROOT)}")

    for skill_root, manifest in (
        (STANDARD_SKILL_ROOT, STANDARD_MANIFEST),
        (RETRIEVAL_SKILL_ROOT, RETRIEVAL_MANIFEST),
    ):
        manifest_text = render_skill_manifest(
            build_skill_manifest(skill_root, project_version())
        )
        if args.check:
            if not manifest.is_file() or read_text(manifest) != manifest_text:
                drift.append(manifest.relative_to(ROOT).as_posix())
        else:
            write_text(manifest, manifest_text)
            print(f"  wrote {manifest.relative_to(ROOT)}")

    if args.check:
        if drift:
            print("Out of sync:", file=sys.stderr)
            for f in drift:
                print(f"  - {f}", file=sys.stderr)
            print("\nRun: python build.py", file=sys.stderr)
            return 1
        print("All generated artifacts are up to date.")
        return 0

    print(f"\nBuilt {len(TARGETS)} instruction artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
