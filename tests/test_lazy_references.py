"""Task Memory spec must be lazy-loaded, not in the always-read body.

The full handoff spec lives in core/references/task-memory.md so agents never
pay to load it unless the user enables task memory. The main body keeps only a
short pointer whose heading states the feature is OFF by default.
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "core" / "OBSIDIAN_KB.md"
REFERENCE = ROOT / "core" / "references" / "task-memory.md"

# Every generated artifact carries the same body (build.py concatenates header+body).
GENERATED = [
    ROOT / "skills" / "obsidian-knowledge-base" / "SKILL.md",
    ROOT / "platforms" / "qoderwork" / "SKILL.md",
    ROOT / "platforms" / "claude-code" / "CLAUDE.md",
    ROOT / "platforms" / "codex" / "AGENTS.md",
    ROOT / "platforms" / "cursor" / "obsidian-kb.mdc",
]

# Pointer markers that MUST stay in the always-loaded body.
POINTER_MARKERS = [
    "OFF by default",           # discoverable from the heading itself
    "references/task-memory.md",  # where the full spec lives
    "Only read that file when the user actually turns task memory on",
]

# Phrases that belong ONLY in the reference doc, never in the always-loaded body.
BODY_FORBIDDEN = [
    "Handoff protocol",
    "Outgoing agent (before yielding)",
    "Incoming agent (first action)",
]


def test_core_has_compact_pointer_with_off_by_default():
    text = CORE.read_text(encoding="utf-8")
    for m in POINTER_MARKERS:
        assert m in text, f"core body missing pointer marker: {m!r}"


def test_core_body_does_not_inline_full_handoff_spec():
    text = CORE.read_text(encoding="utf-8")
    for bad in BODY_FORBIDDEN:
        assert bad not in text, f"core body still inlines the heavy spec: {bad!r}"


def test_reference_file_carries_full_spec():
    assert REFERENCE.exists(), "core/references/task-memory.md is missing"
    text = REFERENCE.read_text(encoding="utf-8")
    for need in BODY_FORBIDDEN:
        assert need in text, f"reference missing spec section: {need!r}"
    assert "obsidian-update-note" in text, "reference missing the updater reference"


def test_generated_artifacts_match_pointer_and_not_full_spec():
    for path in GENERATED:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in POINTER_MARKERS:
            assert m in text, f"{path.name} missing pointer marker {m!r} (build out of sync?)"
        for bad in BODY_FORBIDDEN:
            assert bad not in text, f"{path.name} inlines heavy spec {bad!r} (build out of sync?)"


def test_build_check_still_passes():
    """build --check must pass after the reference-shipping change."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "build.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"build --check failed:\n{result.stdout}\n{result.stderr}"
    )
