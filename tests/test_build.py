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
        result = build.build_adapter(self.YAML_HEADER, self.BODY, "qoderwork")
        # Frontmatter must remain the first thing in the file (some agent loaders parse line 1).
        assert result.startswith("---\nname: obsidian-knowledge-base\n")

    def test_yaml_header_inserts_banner_after_closing_fence(self):
        result = build.build_adapter(self.YAML_HEADER, self.BODY, "qoderwork")
        # Banner must come AFTER the closing `---` of the frontmatter, BEFORE the H1.
        closing_fence_idx = result.find("\n---\n") + len("\n---\n")
        banner_idx = result.find("AUTO-GENERATED")
        h1_idx = result.find("# Skill Title")
        assert 0 < closing_fence_idx < banner_idx < h1_idx

    def test_plain_header_puts_banner_at_top(self):
        result = build.build_adapter(self.PLAIN_HEADER, self.BODY, "claude-code")
        assert result.startswith("<!-- AUTO-GENERATED")
        assert "platforms/claude-code/header.md" in result

    def test_body_is_appended_verbatim(self):
        result = build.build_adapter(self.PLAIN_HEADER, self.BODY, "codex")
        assert result.endswith(self.BODY)

    def test_banner_names_the_correct_platform(self):
        result = build.build_adapter(self.PLAIN_HEADER, self.BODY, "cursor")
        assert "platforms/cursor/header.md" in result


# ---------- end-to-end against the real repo ----------

class TestEndToEnd:
    def test_check_mode_reports_in_sync_after_clean_build(self, tmp_path, monkeypatch):
        """Running build then build --check must succeed against the real repo state."""
        # Just call extract_body + build_adapter for each declared target and compare to the
        # on-disk file. This catches any uncommitted drift.
        core_text = (ROOT / "core" / "OBSIDIAN_KB.md").read_text(encoding="utf-8")
        body = build.extract_body(core_text)

        for platform_name, output_name in build.TARGETS:
            header_path = ROOT / "platforms" / platform_name / "header.md"
            output_path = ROOT / "platforms" / platform_name / output_name
            assert header_path.exists(), f"missing header: {header_path}"
            assert output_path.exists(), f"missing generated adapter: {output_path}"
            header = header_path.read_text(encoding="utf-8")
            expected = build.build_adapter(header, body, platform_name)
            actual = output_path.read_text(encoding="utf-8")
            assert actual == expected, (
                f"{output_path.relative_to(ROOT)} is out of sync with source. "
                "Run: python build.py"
            )
