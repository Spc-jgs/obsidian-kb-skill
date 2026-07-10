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


def _skill_union_text():
    # Detailed workflows live in core/references/*.md (lazy-loaded); the
    # always-loaded body only points to them. Union the two for invariants.
    parts = [(ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")]
    ref_dir = ROOT / "core" / "references"
    if ref_dir.is_dir():
        for ref in sorted(ref_dir.iterdir()):
            if ref.is_file():
                parts.append(ref.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_index_rules_have_single_owner():
    skill = _skill_union_text()
    assert "## Index Strategy Detection" in skill
    assert "Folder Index mode" in skill
    assert "Never append links to plugin-managed indexes" in skill
    assert "update both the subfolder INDEX and the parent folder INDEX" not in skill


def test_all_cli_helpers_use_portable_python_shebang():
    helpers = (
        "audit_vault.py",
        "process_inbox.py",
        "suggest_links.py",
        "create_note.py",
        "update_note.py",
        "vault_info.py",
        "detect_index.py",
        "scaffold_templates.py",
    )
    scripts = ROOT / "obsidian_kb_skill" / "scripts"

    for name in helpers:
        first_line = (scripts / name).read_text(encoding="utf-8").splitlines()[0]
        assert first_line == "#!/usr/bin/env python3", name
