"""Runtime contract tests for user-customized Vault templates."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from obsidian_kb_skill.scripts.note_types import (
    TYPE_TO_TEMPLATE,
    TYPE_TO_TEMPLATE_ASSET,
)
from obsidian_kb_skill.scripts.template_contract import (
    custom_template_types,
    inspect_template,
    normalize_template_text,
    template_shape,
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
    path.write_bytes(("\ufeff" + content).encode("utf-8"))

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


def test_template_shape_returns_only_selected_ordered_level_two_headings(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    target = vault / "Templates" / "Web Clip.md"
    target.write_text(
        "---\n## Internal note\ntype: web-clip\ntags: [web-clip]\n---\n"
        "# {{title}}\n\n## First\n\nDo not leak this instruction.\n"
        "\n```markdown\n## Example\n```\n"
        "\n### Nested\n\n## Second\n",
        encoding="utf-8",
    )

    shape = template_shape(vault, "web-clip")

    assert shape == {
        "type": "web-clip",
        "path": "Templates/Web Clip.md",
        "headings": ["First", "Second"],
    }
    assert "instruction" not in json.dumps(shape)
    assert "frontmatter" not in shape


def test_template_shape_returns_none_for_missing_conventional_template(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    (vault / "Templates" / "Web Clip.md").unlink()

    assert template_shape(vault, "web-clip") is None


def test_normalization_changes_only_transport_details():
    source = "\ufeff---\r\ntype: web-clip\r\n---\r\n# Title"

    normalized = normalize_template_text(source)

    assert normalized == "---\ntype: web-clip\n---\n# Title\n"


def run_contract(vault: Path, note_type: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.template_contract",
            str(vault),
            "--type",
            note_type,
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_cli_returns_one_complete_custom_contract(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    target = vault / "Templates" / "Web Clip.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n必须评估风险。\n",
        encoding="utf-8",
    )

    result = run_contract(vault, "web-clip")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["type"] == "web-clip"
    assert payload["customized"] is True
    assert "必须评估风险" in payload["body"]
    assert len(payload["sha256"]) == 64


def test_cli_rejects_unsupported_template_type(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)

    result = run_contract(vault, "renamed-template")

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "unsupported-template-type"


def test_cli_reports_malformed_template_yaml_location(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    (vault / "Templates" / "Web Clip.md").write_text(
        '---\ntype: web-clip\nauthor: "broken: "value""\n---\n# Body\n',
        encoding="utf-8",
    )

    result = run_contract(vault, "web-clip")

    assert result.returncode == 2
    error = json.loads(result.stdout)["error"]
    assert error["code"] == "invalid-template-frontmatter"
    assert error["source"].endswith("Templates/Web Clip.md")
    assert error["line"] == 3
    assert isinstance(error["column"], int)
    assert error["message"] == "expected <block end>, but found '<scalar>'"


def test_cli_rejects_unknown_placeholders_before_generation(tmp_path: Path):
    vault = vault_with_shipped_templates(tmp_path)
    target = vault / "Templates" / "Web Clip.md"
    target.write_text(
        target.read_text(encoding="utf-8") + "\n项目：{{project}}，负责人：{{owner}}\n",
        encoding="utf-8",
    )

    result = run_contract(vault, "web-clip")

    assert result.returncode == 2
    error = json.loads(result.stdout)["error"]
    assert error == {
        "code": "unknown-template-placeholder",
        "placeholders": ["owner", "project"],
    }
