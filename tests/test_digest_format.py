"""Conversation Digest redesign: keep the agent-friendly format in sync.

The digest was redesigned from a narrative essay into a decision-dense,
link-rich, short context artifact. The spec lives in
core/references/conversation-digest.md (lazy-loaded); the always-loaded body
only points to it, so generated artifacts must NOT inline the digest details.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "core" / "references" / "conversation-digest.md"
GENERATED = [
    ROOT / "skills" / "obsidian-knowledge-base" / "SKILL.md",
]

# Markers that define the redesigned, agent-friendly digest format.
MARKERS = [
    "decision-dense",          # the core design intent
    "decisions",               # structured frontmatter list (primary field)
    "TL;DR",                   # short body anchor
    "250 words",               # explicit brevity cap
]

# Phrases from the OLD narrative format that must NOT survive.
FORBIDDEN = [
    "confirmed conclusions",
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
        assert "250 words" not in text, f"{path.name} inlines digest spec (should be lazy-loaded)"
        assert "## Conversation Digest Workflow" not in text, (
            f"{path.name} inlines digest spec (should be lazy-loaded)"
        )
