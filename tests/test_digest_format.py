"""Conversation Digest redesign: keep the agent-friendly format in sync.

The digest was redesigned from a narrative essay into a decision-dense,
link-rich, short context artifact. These tests guard the *intent* markers in
core/OBSIDIAN_KB.md and confirm the generated artifacts still carry them
(build.py must stay in sync).
"""

import pathlib

CORE = pathlib.Path(__file__).resolve().parents[1] / "core" / "OBSIDIAN_KB.md"
GENERATED = [
    pathlib.Path(__file__).resolve().parents[1] / "skills" / "obsidian-knowledge-base" / "SKILL.md",
]

# Markers that define the redesigned, agent-friendly digest format.
MARKERS = [
    "decision-dense",          # the core design intent
    "decisions",               # structured frontmatter list (primary field)
    "TL;DR",                   # short body anchor
    "250 words",               # explicit brevity cap
    "not",                     # paired with "a transcript or a narrative essay"
]

# Phrases from the OLD narrative format that must NOT survive.
FORBIDDEN = [
    "rejected/revised ideas",
    "confirmed conclusions",
]


def test_core_doc_has_agent_friendly_digest_markers():
    text = CORE.read_text(encoding="utf-8")
    for m in MARKERS:
        assert m in text, f"core/OBSIDIAN_KB.md missing digest marker: {m!r}"


def test_core_doc_dropped_narrative_digest_format():
    text = CORE.read_text(encoding="utf-8")
    for bad in FORBIDDEN:
        assert bad not in text, f"core/OBSIDIAN_KB.md still has old digest phrase: {bad!r}"


def test_generated_artifacts_carry_digest_markers():
    for path in GENERATED:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "decisions" in text, f"{path.name} missing 'decisions' (build out of sync?)"
        assert "TL;DR" in text, f"{path.name} missing 'TL;DR' (build out of sync?)"
