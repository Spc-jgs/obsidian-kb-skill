"""Tests for build.py — adapter generator from core/OBSIDIAN_KB.md + per-platform header.md."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_repository_enforces_lf_payload_checkouts():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "* text=auto eol=lf" in attributes.splitlines()


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
    @pytest.mark.parametrize(
        "skill_name",
        ["obsidian-knowledge-base", "obsidian-knowledge-retrieval"],
    )
    def test_skill_manifest_covers_every_installable_payload_file(self, skill_name):
        root = ROOT / "skills" / skill_name
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

    def test_skill_manifest_never_follows_payload_symlinks(self, tmp_path):
        root = tmp_path / "skill"
        outside = tmp_path / "outside"
        root.mkdir()
        outside.mkdir()
        (root / "SKILL.md").write_text("owned", encoding="utf-8")
        secret = outside / "secret.md"
        secret.write_text("outside", encoding="utf-8")
        try:
            (root / "linked-file.md").symlink_to(secret)
            (root / "linked-dir").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unavailable")

        payload = build.skill_payload_files(root)

        assert set(payload) == {"SKILL.md"}
        assert all(path.is_relative_to(root) for path in payload.values())

    def test_project_version_reads_pyproject(self):
        assert build.project_version() == "1.36.0"

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
        assert (
            root
            / "scripts"
            / "obsidian_kb_skill"
            / "scripts"
            / "create_category.py"
        ).is_file()
        assert (root / "assets" / "templates" / "digest-note.md").is_file()

    def test_retrieval_skill_is_read_only_and_self_contained(self):
        root = ROOT / "skills" / "obsidian-knowledge-retrieval"
        helper_root = root / "scripts" / "obsidian_kb_skill" / "scripts"

        assert (root / "SKILL.md").is_file()
        assert (root / "agents" / "openai.yaml").is_file()
        assert (root / "references" / "search.md").is_file()
        assert (root / "scripts" / "run_helper.py").is_file()
        assert (helper_root / "search_vault.py").is_file()
        assert (helper_root / "review_projects.py").is_file()
        assert (helper_root / "retrieval_vault_info.py").is_file()
        for forbidden in (
            "create_note.py",
            "update_note.py",
            "process_inbox.py",
            "scaffold_templates.py",
        ):
            assert not (helper_root / forbidden).exists()

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
        assert "skills/obsidian-knowledge-retrieval/SKILL.md" in outputs

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
        for target in build.TARGETS:
            assert target.header.exists(), f"missing header: {target.header}"
            assert target.output.exists(), f"missing generated adapter: {target.output}"
            core_text = target.core.read_text(encoding="utf-8")
            body = build.extract_body(core_text)
            header = target.header.read_text(encoding="utf-8")
            header_path = target.header.relative_to(ROOT).as_posix()
            core_path = target.core.relative_to(ROOT).as_posix()
            expected = build.build_adapter(header, body, header_path, core_path)
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

    def test_web_clip_defines_deep_capture(self):
        assert "## 理解与启发" in self.web_clip
        assert "## 具体做法与示例" in self.web_clip
        assert "## 验证、风险与限制" in self.web_clip
        assert "不限制篇幅" in self.web_clip
        assert "足以复现" in self.web_clip
        assert "不要代替用户表达个人立场" in self.web_clip

    def test_native_folder_index_graph_contract(self):
        assert "Folder Index 1.0.30" in self.skill
        assert "folder-named indexes" in self.skill
        # Link suggestion used to be described as listing the target folder's
        # filenames, which handed the Agent raw material for a link the helper
        # never proposed. What the contract must guarantee is the bound and the
        # empty answer, not a filename dump.
        assert "name-relevant sibling" in self.skill
        assert "Zero candidates is an answer" in self.skill
        assert "Proximity is not a relationship" in self.skill
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
    assert "skills/obsidian-knowledge-retrieval/SKILL.md" in readme
    assert "obsidian-knowledge-retrieval" in readme


def test_user_documentation_is_linked_and_keeps_the_readmes_focused():
    expected_docs = {
        "README.md": "# Obsidian Knowledge Base Skill 使用文档",
        "getting-started.md": "# 快速开始",
        "feature-guide.md": "# 完整功能指南",
        "retrieval.md": "# 只读知识检索",
        "capture-and-governance.md": "# 知识沉淀与治理",
        "platforms-and-installation.md": "# 平台与安装",
        "troubleshooting.md": "# 故障排查",
    }
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")

    for filename, title in expected_docs.items():
        document = ROOT / "docs" / filename
        assert document.is_file()
        assert title in document.read_text(encoding="utf-8")
        if filename != "README.md":
            assert f"({filename})" in docs_index

    assert "(docs/README.md)" in readme
    assert "(docs/README.md)" in readme_en
    hero = ROOT / "docs" / "assets" / "obsidian-kb-hero.webp"
    assert hero.is_file()
    assert hero.stat().st_size < 100_000
    assert hero.read_bytes()[:4] == b"RIFF"
    assert 'src="docs/assets/obsidian-kb-hero.webp"' in readme
    assert 'src="docs/assets/obsidian-kb-hero.webp"' in readme_en
    assert "img.shields.io/github/v/release/Spc-jgs/obsidian-kb-skill" in readme
    assert "img.shields.io/github/v/release/Spc-jgs/obsidian-kb-skill" in readme_en
    assert "```mermaid" in readme
    assert "```mermaid" in readme_en
    assert sum(
        path.read_text(encoding="utf-8").count("```mermaid")
        for path in (ROOT / "docs").glob("*.md")
    ) >= 3
    assert len(readme.splitlines()) < 350
    assert len(readme_en.splitlines()) < 350

    user_documents = [
        ROOT / "README.md",
        ROOT / "README_EN.md",
        *(ROOT / "docs").glob("*.md"),
    ]
    for document in user_documents:
        content = document.read_text(encoding="utf-8")
        targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", content)
        targets.extend(re.findall(r'(?:href|src)="([^"]+)"', content))
        for target in targets:
            local_target = target.split("#", 1)[0]
            if (
                not local_target
                or local_target.startswith("#")
                or "://" in local_target
                or local_target.startswith("mailto:")
            ):
                continue
            assert (document.parent / local_target).resolve().exists(), (
                f"{document.relative_to(ROOT)} links to missing {target}"
            )


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


def test_readmes_use_agent_first_installation_and_changelog_owns_history():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")

    assert "## 让 Agent 安装（推荐）" in readme
    assert "## Install with Your Agent (Recommended)" in readme_en
    assert readme.index("## 让 Agent 安装（推荐）") < readme.index(
        "## 手动安装与下载"
    )
    assert readme_en.index("## Install with Your Agent (Recommended)") < (
        readme_en.index("## Manual Installation and Downloads")
    )
    assert "doctor --json" in readme
    assert "doctor --json" in readme_en
    assert "CHANGELOG.md" in readme
    assert "CHANGELOG.md" in readme_en
    assert "## v1.19 新增的能力" not in readme
    assert "## v1.12 新增的能力" not in readme
    assert "## What's New in v1.19" not in readme_en
    assert "## What's New in v1.12" not in readme_en


def test_lockfile_records_the_current_project_version():
    """A release bump must reach `uv.lock`, or CI cannot install the project.

    Version-agnostic on purpose: the per-release contract below is rewritten
    every time, but this one has to keep holding for every future bump. The
    1.28.0 release shipped with a stale lock and `uv sync --locked` refused on
    every CI job, while a local run against an already-built venv passed.
    """
    version = build.project_version()
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    entry = lock.index('name = "obsidian-kb-skill"')

    assert f'version = "{version}"' in lock[entry : entry + 200], (
        f"uv.lock does not record version {version}; run `uv lock`"
    )


def test_v1_36_0_release_contract_is_consistent():
    # Renamed with the bump. The previous release left this named for v1.31.0
    # while it asserted v1.32.0 throughout, so the one place a reader looks to
    # ask "which release does this guard?" gave the wrong answer.
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    core = (ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")
    retrieval_core = (ROOT / "core" / "RETRIEVAL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_en = (ROOT / "README_EN.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert 'version = "1.36.0"' in pyproject
    assert "**Version**: 1.36.0" in core
    # The retrieval header is its own file and was missed by earlier bumps'
    # assertions, which only ever read the write Skill's core.
    assert "**Version**: 1.36.0" in retrieval_core
    assert "**v1.36.0**" in readme
    assert "**v1.36.0**" in readme_en
    assert "## [1.36.0] - 2026-08-24" in changelog
    # Unique to this release: the audit finding and its floor, the named BM25
    # parameters, and the design that records the floor's distribution.
    assert "web-clip-captured-nothing" in changelog
    assert "WEB_CLIP_MIN_CONTENT_CHARS" in changelog
    assert "BM25_B" in changelog
    assert "2026-08-24-shell-capture-detection-design.md" in changelog
    assert "## [1.35.0] - 2026-08-21" in changelog
    assert "review-captures" in changelog
    assert "unfinished-template-body" in changelog
    assert "stopped_after_case" in changelog
    assert "adv-dilution-06" in changelog
    # The three hypotheses this release tested and rejected. A blanket rewrite
    # of the section would drop the losing side, which is the part that stops
    # the next reader re-deriving it.
    assert "2026-08-21-rejected-hypotheses.md" in changelog
    assert "## [1.34.0] - 2026-08-17" in changelog
    assert "suggest-directed-links" in changelog
    assert "material-not-inspected" in changelog
    assert "fact_form_provenance" in changelog
    assert "next_action_heading" in changelog
    assert "## [1.33.0] - 2026-08-14" in changelog
    assert "explore-neighborhood" in changelog
    assert "run-retrieval-view" in changelog
    assert "index-note-excluded" in changelog
    assert "invalid-view-scope" in changelog
    assert "link_graph" in changelog
    assert "## [1.32.0] - 2026-08-12" in changelog
    assert "duplicate-project-note" in changelog
    assert "entity-instance-unknown" in changelog
    assert "resume-project" in changelog
    assert "dismissed-required-material" in changelog
    assert "## [1.30.0] - 2026-08-09" in changelog
    assert "obsidian-archive-source" in changelog
    assert "## [1.29.1] - 2026-08-07" in changelog
    assert "CLUSTER_MIN_NOTES" in changelog
    assert "## [1.29.0] - 2026-08-07" in changelog
    assert "archive-source" in changelog
    assert "disconnected-note" in changelog
    assert "undecodable-source-content" in changelog
    assert "## [1.28.0] - 2026-08-06" in changelog
    assert "tag_vocabulary" in changelog
    assert "near-duplicate tag detection" in changelog.lower()
    assert "## [1.27.0] - 2026-08-04" in changelog
    assert "--from-preflight" in changelog
    assert "required_references" in changelog
    assert "## [1.26.4] - 2026-08-02" in changelog
    assert "--min-severity" in changelog
    assert "## [1.26.3] - 2026-08-02" in changelog
    assert "conversation-digest-missing-resume-field" in changelog
    assert "## [1.26.2] - 2026-08-02" in changelog
    assert "unsafe-inbox-entry" in changelog
    assert "## [1.26.1] - 2026-08-01" in changelog
    assert "invalid-folder-index-config" in changelog
    assert "## [1.26.0] - 2026-08-01" in changelog
    assert "obsidian-knowledge-base" in changelog
    # Earlier history stays intact under the new section.
    assert "## [1.25.1] - 2026-08-01" in changelog
    assert "unreadable-frontmatter" in changelog
    assert "## [1.25.0] - 2026-07-31" in changelog
    assert "web acquisition contract" in changelog
    assert "`capture_depth: standard`" in changelog
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


def test_only_the_release_contract_hardcodes_the_version():
    """A version literal outside this file silently joins the release checklist.

    v1.35.0 found three of them — `test_doctor.py` twice and
    `test_installers.py` once — none of which was on the checklist. They cost a
    round of red CI after the CHANGELOG was already written, and they bought
    nothing: what they assert is that the installed artifact carries the same
    version the repository declares, which reads stronger from
    `build.project_version()` than from a literal somebody has to remember.

    This file keeps its two on purpose: `test_project_version_reads_pyproject`
    is where the value is anchored, and the per-release contract test exists to
    be updated by hand.
    """
    version = build.project_version()

    offenders = sorted(
        path.name
        for path in (ROOT / "tests").glob("test_*.py")
        if path.name != "test_build.py" and f'"{version}"' in path.read_text(
            encoding="utf-8"
        )
    )

    assert not offenders, (
        f"these test files hardcode version {version}: {offenders}. Read "
        "`build.project_version()` instead, or the next bump has to find them "
        "by running the suite."
    )
