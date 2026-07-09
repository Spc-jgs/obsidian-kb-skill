"""Checks for localized templates and index-strategy invariants."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_NAMES = {
    "daily-note.md",
    "meeting-note.md",
    "learning-note.md",
    "project-note.md",
    "web-clip.md",
    "insight-note.md",
    "person-note.md",
    "digest-note.md",
}


def test_chinese_and_english_template_sets_match():
    zh = {path.name for path in (ROOT / "core" / "templates").glob("*.md")}
    en = {path.name for path in (ROOT / "core" / "templates" / "en").glob("*.md")}
    assert zh == TEMPLATE_NAMES
    assert en == TEMPLATE_NAMES


def test_all_templates_have_required_metadata_and_related_links():
    paths = list((ROOT / "core" / "templates").glob("*.md"))
    paths += list((ROOT / "core" / "templates" / "en").glob("*.md"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert 'date: "{{date}}"' in text
        assert "type:" in text
        assert "tags:" in text
        assert "related: []" in text


def test_chinese_templates_are_actually_chinese():
    learning = (ROOT / "core" / "templates" / "learning-note.md").read_text(
        encoding="utf-8"
    )
    assert "## 今天学了什么" in learning
    assert "### WHY：为什么这样设计" in learning


def test_index_rules_have_single_owner():
    core = (ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")
    assert "## Index Strategy Detection" in core
    assert "Folder Index mode" in core
    assert "Never append links to plugin-managed indexes" in core
    assert "update both the subfolder INDEX and the parent folder INDEX" not in core
