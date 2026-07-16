"""Runtime contract tests for user-customized Vault templates."""
from __future__ import annotations

import shutil
from pathlib import Path

from obsidian_kb_skill.scripts.note_types import (
    TYPE_TO_TEMPLATE,
    TYPE_TO_TEMPLATE_ASSET,
)
from obsidian_kb_skill.scripts.template_contract import (
    custom_template_types,
    inspect_template,
    normalize_template_text,
    template_sha256,
)


ROOT = Path(__file__).resolve().parents[1]


def vault_with_shipped_templates(tmp_path: Path, *, locale: str = "zh-CN") -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    templates = vault / "Templates"
    templates.mkdir()
    source = ROOT / "core" / "templates"
    if locale == "en":
        source = source / "en"
    for note_type, vault_name in TYPE_TO_TEMPLATE.items():
        shutil.copyfile(source / TYPE_TO_TEMPLATE_ASSET[note_type], templates / vault_name)
    return vault


def test_shipped_chinese_templates_are_standard(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)

    assert custom_template_types(vault) == []


def test_shipped_english_templates_are_standard(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path, locale="en")

    assert custom_template_types(vault) == []


def test_transport_only_template_differences_are_standard(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    path = vault / "Templates" / "Web Clip.md"
    content = path.read_text(encoding="utf-8").rstrip("\n").replace("\n", "\r\n")
    path.write_text("\ufeff" + content, encoding="utf-8")

    assert custom_template_types(vault) == []


def test_changed_instruction_marks_only_one_template_custom(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    target = vault / "Templates" / "Web Clip.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n必须给出风险等级与回滚方案。\n",
        encoding="utf-8",
    )

    assert custom_template_types(vault) == ["web-clip"]


def test_missing_conventional_template_is_not_custom(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    (vault / "Templates" / "Web Clip.md").unlink()

    assert "web-clip" not in custom_template_types(vault)


def test_contract_contains_complete_custom_body_and_stable_hash(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    target = vault / "Templates" / "Web Clip.md"
    target.write_text(
        target.read_text(encoding="utf-8")
        + "\n## 风险评估\n\n必须包含风险等级、影响范围和回滚方案。\n",
        encoding="utf-8",
    )

    contract = inspect_template(vault, "web-clip")

    assert contract is not None
    assert contract["type"] == "web-clip"
    assert contract["path"] == "Templates/Web Clip.md"
    assert contract["customized"] is True
    assert "必须包含风险等级" in contract["body"]
    assert contract["frontmatter"]["type"] == "web-clip"
    assert contract["supported_placeholders"] == ["date", "title"]
    assert contract["unknown_placeholders"] == []
    assert contract["sha256"] == template_sha256(target.read_text(encoding="utf-8"))


def test_contract_reports_unknown_placeholders(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    target = vault / "Templates" / "Web Clip.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n项目：{{project}}\n负责人：{{owner}}\n",
        encoding="utf-8",
    )

    contract = inspect_template(vault, "web-clip")

    assert contract is not None
    assert contract["unknown_placeholders"] == ["owner", "project"]


def test_normalization_changes_only_transport_details():
    source = "\ufeff---\r\ntype: web-clip\r\n---\r\n# Title"

    normalized = normalize_template_text(source)

    assert normalized == "---\ntype: web-clip\n---\n# Title\n"
