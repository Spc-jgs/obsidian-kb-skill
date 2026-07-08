"""Tests for build.py — adapter generator from core/OBSIDIAN_KB.md + per-platform header.md."""
from __future__ import annotations

import importlib.util
import os
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
        cls.core = (ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")
        cls.web_clip = (ROOT / "core" / "templates" / "web-clip.md").read_text(
            encoding="utf-8"
        )

    def test_local_vault_rules_precede_generic_defaults(self):
        assert "Vault-local governance" in self.core
        assert "generic skill defaults" in self.core

    def test_create_workflow_validates_before_confirmation(self):
        validate = self.core.index("### Step 9: Validate Result")
        confirm = self.core.index("### Step 10: Confirm to User")
        assert validate < confirm

    def test_batch_capture_requires_confirmation(self):
        assert "Default to one target note per invocation" in self.core
        assert "ask the user before creating multiple notes" in self.core

    def test_git_stops_on_divergence_or_conflict(self):
        assert "Stop on divergence or conflict" in self.core
        assert "Never auto-resolve INDEX conflicts" in self.core

    def test_web_clip_defines_bounded_interpretation(self):
        assert "## 理解与启发" in self.web_clip
        assert "2–4 句" in self.web_clip
        assert "不要代替用户表达个人立场" in self.web_clip

    def test_native_folder_index_graph_contract(self):
        assert "Folder Index 1.0.30" in self.core
        assert "folder-named indexes" in self.core
        assert "list the target folder's filenames" in self.core
        assert "required template headings" in self.core

    def test_metadata_relationship_contract(self):
        assert "canonical source URL" in self.core
        assert "machine-readable source of truth" in self.core

    def test_pre_write_git_sync_contract(self):
        assert "Pre-write Git synchronization" in self.core
        assert "merge --ff-only" in self.core
