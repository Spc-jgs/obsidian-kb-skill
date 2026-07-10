"""Tests for build.py — adapter generator from core/OBSIDIAN_KB.md + per-platform header.md."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_build_module():
    """Load build.py as a module without executing main()."""
    spec = importlib.util.spec_from_file_location("build", ROOT / "build.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build = _load_build_module()


# ---------- extract_body ----------

class TestExtractBody:
    def test_returns_text_from_marker_onward(self):
        core = "# Title\n\nIntro paragraph.\n\n## Overview\n\nBody starts here.\n"
        result = build.extract_body(core)
        assert result.startswith("## Overview\n")
        assert "Body starts here." in result

    def test_ignores_marker_inside_inline_text(self):
        # The marker phrase appears inside a quoted reference before the real heading.
        # The function MUST find the real heading (line-start), not the quoted occurrence.
        core = (
            "# Title\n\n"
            'Note: this body (starting from "## Overview").\n\n'
            "## Overview\n\n"
            "Real body.\n"
        )
        result = build.extract_body(core)
        assert result.startswith("## Overview\n")
        assert "Real body." in result
        # The intro line above the heading must NOT be in the body.
        assert "Note: this body" not in result

    def test_missing_marker_raises_systemexit(self):
        core = "# Title\n\nNo heading at all.\n"
        with pytest.raises(SystemExit) as excinfo:
            build.extract_body(core)
        assert "BODY_MARKER" in str(excinfo.value) or "## Overview" in str(excinfo.value)

    def test_marker_as_first_line_is_accepted(self):
        core = "## Overview\n\nBody.\n"
        result = build.extract_body(core)
        assert result == core


# ---------- build_adapter ----------

class TestBuildAdapter:
    YAML_HEADER = (
        "---\n"
        "name: obsidian-knowledge-base\n"
        'description: "Save notes."\n'
        "---\n"
        "\n"
        "# Skill Title\n"
        "\n"
    )

    PLAIN_HEADER = "# Skill Title\n\n"
    BODY = "## Overview\n\nThe shared body.\n"

    def test_yaml_header_keeps_frontmatter_first(self):
        result = build.build_adapter(
            self.YAML_HEADER,
            self.BODY,
            "platforms/qoderwork/header.md",
        )
        # Frontmatter must remain the first thing in the file (some agent loaders parse line 1).
        assert result.startswith("---\nname: obsidian-knowledge-base\n")

    def test_yaml_header_inserts_banner_after_closing_fence(self):
        result = build.build_adapter(
            self.YAML_HEADER,
            self.BODY,
            "platforms/qoderwork/header.md",
        )
        # Banner must come AFTER the closing `---` of the frontmatter, BEFORE the H1.
        closing_fence_idx = result.find("\n---\n") + len("\n---\n")
        banner_idx = result.find("AUTO-GENERATED")
        h1_idx = result.find("# Skill Title")
        assert 0 < closing_fence_idx < banner_idx < h1_idx

    def test_plain_header_puts_banner_at_top(self):
        result = build.build_adapter(
            self.PLAIN_HEADER,
            self.BODY,
            "platforms/claude-code/header.md",
        )
        assert result.startswith("<!-- AUTO-GENERATED")
        assert "platforms/claude-code/header.md" in result

    def test_body_is_appended_verbatim(self):
        result = build.build_adapter(
            self.PLAIN_HEADER,
            self.BODY,
            "platforms/codex/header.md",
        )
        assert result.endswith(self.BODY)

    def test_header_and_body_are_separated_by_blank_line(self):
        result = build.build_adapter(
            "# Skill Title\n",
            self.BODY,
            "platforms/codex/header.md",
        )

        assert "# Skill Title\n\n## Overview" in result

    def test_banner_names_the_correct_platform(self):
        result = build.build_adapter(
            self.PLAIN_HEADER,
            self.BODY,
            "platforms/cursor/header.md",
        )
        assert "platforms/cursor/header.md" in result

    def test_banner_uses_explicit_header_path(self):
        result = build.build_adapter(
            self.YAML_HEADER,
            self.BODY,
            "skills/obsidian-knowledge-base/header.md",
        )
        assert "skills/obsidian-knowledge-base/header.md" in result
        assert "platforms/skills/" not in result


# ---------- end-to-end against the real repo ----------

class TestEndToEnd:
    def test_skill_manifest_covers_every_installable_payload_file(self):
        root = ROOT / "skills" / "obsidian-knowledge-base"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        expected = {
            relative: hashlib.sha256(path.read_bytes()).hexdigest()
            for relative, path in build.skill_payload_files(root).items()
        }

        assert manifest == {
            "schema_version": 1,
            "product": "obsidian-kb-skill",
            "version": build.project_version(),
            "files": dict(sorted(expected.items())),
        }
        assert "agents/openai.yaml" in manifest["files"]
        assert "header.md" not in manifest["files"]
        assert "manifest.json" not in manifest["files"]

    def test_skill_manifest_is_deterministic_and_detects_hash_drift(self, tmp_path):
        root = tmp_path / "skill"
        shutil.copytree(ROOT / "skills" / "obsidian-knowledge-base", root)
        first = build.render_skill_manifest(
            build.build_skill_manifest(root, build.project_version())
        )
        second = build.render_skill_manifest(
            build.build_skill_manifest(root, build.project_version())
        )
        assert first == second

        (root / "SKILL.md").write_text("changed", encoding="utf-8")
        changed = build.render_skill_manifest(
            build.build_skill_manifest(root, build.project_version())
        )
        assert changed != first

    def test_project_version_reads_pyproject(self):
        assert build.project_version() == "1.12.0"

    def test_standard_skill_has_required_resource_directories(self):
        root = ROOT / "skills" / "obsidian-knowledge-base"

        assert (root / "SKILL.md").is_file()
        assert (root / "agents" / "openai.yaml").is_file()
        assert (root / "references" / "note-creation.md").is_file()
        assert (root / "scripts" / "run_helper.py").is_file()
        assert (
            root
            / "scripts"
            / "obsidian_kb_skill"
            / "scripts"
            / "create_note.py"
        ).is_file()
        assert (root / "assets" / "templates" / "digest-note.md").is_file()

    def test_generated_tree_drift_reports_missing_changed_and_extra(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "same.md").write_text("same", encoding="utf-8")
        (src / "changed.md").write_text("new", encoding="utf-8")
        (src / "missing.md").write_text("missing", encoding="utf-8")
        (dst / "same.md").write_text("same", encoding="utf-8")
        (dst / "changed.md").write_text("old", encoding="utf-8")
        (dst / "extra.md").write_text("extra", encoding="utf-8")

        assert build.tree_drift(src, dst, exclude=lambda _: False) == [
            "changed: changed.md",
            "extra: extra.md",
            "missing: missing.md",
        ]

    def test_standard_agent_skill_is_a_build_target(self):
        outputs = {
            target.output.relative_to(ROOT).as_posix()
            for target in build.TARGETS
        }
        assert "skills/obsidian-knowledge-base/SKILL.md" in outputs

    def test_standard_agent_skill_has_valid_frontmatter(self):
        skill = ROOT / "skills" / "obsidian-knowledge-base" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "name: obsidian-knowledge-base" in text
        assert "description:" in text

    def test_standard_agent_skill_description_is_trigger_only(self):
        header = ROOT / "skills" / "obsidian-knowledge-base" / "header.md"
        text = header.read_text(encoding="utf-8")

        assert 'description: "Use when ' in text

    def test_qoderwork_compatibility_target_reuses_standard_header(self):
        targets = {target.name: target for target in build.TARGETS}

        assert targets["qoderwork"].header == targets["standard-agent-skill"].header

    def test_check_mode_reports_in_sync_after_clean_build(self, tmp_path, monkeypatch):
        """Running build then build --check must succeed against the real repo state."""
        # Just call extract_body + build_adapter for each declared target and compare to the
        # on-disk file. This catches any uncommitted drift.
        core_text = (ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")
        body = build.extract_body(core_text)

        for target in build.TARGETS:
            assert target.header.exists(), f"missing header: {target.header}"
            assert target.output.exists(), f"missing generated adapter: {target.output}"
            header = target.header.read_text(encoding="utf-8")
            header_path = target.header.relative_to(ROOT).as_posix()
            expected = build.build_adapter(header, body, header_path)
            actual = target.output.read_text(encoding="utf-8")
            assert actual == expected, (
                f"{target.output.relative_to(ROOT)} is out of sync with source. "
                "Run: python build.py"
            )


class TestGovernanceContract:
    @classmethod
    def setup_class(cls):
        # The detailed contracts live in core/references/*.md (lazy-loaded); the
        # always-loaded body only points to them. Scan the union so the contract
        # tests still guard that each rule exists *somewhere* in the skill.
        core = (ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")
        ref_dir = ROOT / "core" / "references"
        parts = [core]
        if ref_dir.is_dir():
            for ref in sorted(ref_dir.iterdir()):
                if ref.is_file():
                    parts.append(ref.read_text(encoding="utf-8"))
        cls.skill = "\n".join(parts)
        cls.web_clip = (ROOT / "core" / "templates" / "web-clip.md").read_text(
            encoding="utf-8"
        )

    def test_local_vault_rules_precede_generic_defaults(self):
        assert "Vault-local governance" in self.skill
        assert "generic skill defaults" in self.skill

    def test_create_workflow_validates_before_confirmation(self):
        validate = self.skill.index("### Step 9: Validate Result")
        confirm = self.skill.index("### Step 10: Confirm to User")
        assert validate < confirm

    def test_batch_capture_requires_confirmation(self):
        assert "Default to one target note per invocation" in self.skill
        assert "ask the user before creating multiple notes" in self.skill

    def test_git_stops_on_divergence_or_conflict(self):
        assert "Stop on divergence or conflict" in self.skill
        assert "Never auto-resolve INDEX conflicts" in self.skill

    def test_web_clip_defines_bounded_interpretation(self):
        assert "## 理解与启发" in self.web_clip
        assert "2–4 句" in self.web_clip
        assert "不要代替用户表达个人立场" in self.web_clip

    def test_native_folder_index_graph_contract(self):
        assert "Folder Index 1.0.30" in self.skill
        assert "folder-named indexes" in self.skill
        assert "list the target folder's filenames" in self.skill
        assert "required template headings" in self.skill

    def test_metadata_relationship_contract(self):
        assert "canonical source URL" in self.skill
        assert "machine-readable source of truth" in self.skill

    def test_pre_write_git_sync_contract(self):
        assert "Pre-write Git synchronization" in self.skill
        assert "merge --ff-only" in self.skill


def test_readme_documents_standard_skill_entry():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "skills/obsidian-knowledge-base/SKILL.md" in readme
    assert "~/.agents/skills/obsidian-knowledge-base" in readme


def test_readmes_do_not_tell_users_to_edit_generated_platform_files():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")

    assert "编辑平台指令文件中的标签" not in readme
    assert "Edit the platform instruction file's tagging section" not in readme_en


def test_readmes_warn_that_one_instruction_file_is_not_a_complete_install():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")

    assert "单独复制一个指令文件既不是完整标准 Skill" in readme
    assert "Copying one instruction file is neither a complete standard Skill" in readme_en


def test_v1_12_0_release_contract_is_consistent():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    core = (ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert 'version = "1.12.0"' in pyproject
    assert "**Version**: 1.12.0" in core
    assert "**v1.12.0**" in readme
    assert "**v1.12.0**" in readme_en
    assert "## [1.12.0] - 2026-07-11" in changelog
    assert "~/.workbuddy/skills/obsidian-knowledge-base" in readme
    assert "run_helper.py doctor" in readme
    assert "WorkBuddy" in readme_en
    assert "only the product-owned WorkBuddy Skill directory" in readme_en


def test_backup_retention_is_documented_as_script_owned_global_policy():
    task_memory = (ROOT / "core" / "references" / "task-memory.md").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")

    for text in (task_memory, readme, readme_en):
        assert "~/.obsidian-kb-settings.json" in text
    assert "`backup.keep_per_note`" in task_memory
    assert "defaults to `1`" in task_memory
    assert "The helper, not the agent" in task_memory
    assert "never list or delete backup files" in task_memory
    assert "升级和默认卸载都会保留" in readme
    assert "explicit config purge removes it" in readme_en


def test_generated_skill_never_assigns_backup_cleanup_to_the_agent():
    reference = (
        ROOT
        / "skills"
        / "obsidian-knowledge-base"
        / "references"
        / "task-memory.md"
    ).read_text(encoding="utf-8")
    assert "The helper, not the agent" in reference
    assert "never list or delete backup files" in reference
    assert "find .obsidian-kb-backups" not in reference
    assert "rm -rf .obsidian-kb-backups" not in reference


def test_codex_compatibility_adapter_points_to_standard_skill():
    header = (ROOT / "platforms/codex/header.md").read_text(encoding="utf-8")

    assert "Compatibility adapter" in header
    assert "skills/obsidian-knowledge-base/SKILL.md" in header


def test_non_skill_compatibility_adapters_name_the_installed_support_root():
    for relative in (
        "platforms/claude-code/header.md",
        "platforms/cursor/header.md",
        "platforms/codex/header.md",
    ):
        header = (ROOT / relative).read_text(encoding="utf-8")
        assert "~/.obsidian-kb-skill/skill" in header
