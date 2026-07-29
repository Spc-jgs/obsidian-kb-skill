"""Conversation Digest v2: keep layered context recovery lazy and in sync.

The digest is a 30-second resume card plus the details needed for safe context
recovery. The spec lives in
core/references/conversation-digest.md (lazy-loaded); the always-loaded body
only points to it, so generated artifacts must NOT inline the digest details.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "core" / "references" / "conversation-digest.md"
GENERATED = [
    ROOT / "skills" / "obsidian-knowledge-base" / "SKILL.md",
]

# Markers that define layered context recovery.
MARKERS = [
    "30-second Resume Card",
    "Scope and Constraints",
    "Decisions and Rationale",
    "Evidence and Artifacts",
    "Open Questions and Next Actions",
]

# Phrases from superseded formats that must NOT survive.
FORBIDDEN = [
    "confirmed conclusions",
    "250 words",
    "Frontmatter carries the load",
]


def test_reference_doc_has_agent_friendly_digest_markers():
    text = REFERENCE.read_text(encoding="utf-8")
    for m in MARKERS:
        assert m in text, f"references/conversation-digest.md missing digest marker: {m!r}"


def test_reference_doc_dropped_narrative_digest_format():
    text = REFERENCE.read_text(encoding="utf-8")
    for bad in FORBIDDEN:
        assert bad not in text, f"references/conversation-digest.md still has old digest phrase: {bad!r}"


def test_generated_artifacts_do_not_inline_digest_spec():
    # The tiny always-loaded body may *mention* the digest (e.g. "decision-dense
    # note"); what must stay lazy is the full spec. Assert the structural spec
    # phrases are absent from the generated artifact.
    for path in GENERATED:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "30-second Resume Card" not in text, (
            f"{path.name} inlines digest spec (should be lazy-loaded)"
        )
        assert "## Conversation Digest Workflow" not in text, (
            f"{path.name} inlines digest spec (should be lazy-loaded)"
        )
