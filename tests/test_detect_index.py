"""Tests for scripts/detect_index.py — single source for index-strategy detection."""
import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import detect_index  # noqa: E402


def _make_vault(tmp_path, *, folder_index=False, dataview=False):
    obs = tmp_path / ".obsidian"
    obs.mkdir()
    (tmp_path / "Templates").mkdir()
    # community-plugins.json
    plugins = ["obsidian-folder-index"] if folder_index else ["some-other-plugin"]
    (obs / "community-plugins.json").write_text(json.dumps(plugins), encoding="utf-8")
    if folder_index:
        data = {
            "graphOverwrite": False,
            "indexFileUserSpecified": False,
            "rootIndexFile": "INDEX.md",
            "indexFilename": "INDEX",
        }
        (obs / "plugins" / "obsidian-folder-index").mkdir(parents=True)
        (obs / "plugins" / "obsidian-folder-index" / "data.json").write_text(
            json.dumps(data), encoding="utf-8"
        )
    # a target folder with two notes + an index file
    folder = tmp_path / "30-Insights"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n")
    (folder / "b.md").write_text("# B\n")
    if dataview:
        (folder / "INDEX.md").write_text("```dataview\nLIST FROM ...\n```\n")
    else:
        (folder / "INDEX.md").write_text("- [[a]]\n")
    return tmp_path


def test_static_mode_lists_notes_and_allows_append(tmp_path):
    vault = _make_vault(tmp_path)
    out = detect_index.detect(vault, "30-Insights")
    assert out["mode"] == "static"
    assert out["index_file"] == "INDEX.md"
    assert out["can_append"] is True
    assert set(out["notes"]) == {"a.md", "b.md", "INDEX.md"}


def test_folder_index_mode_never_appendable(tmp_path):
    vault = _make_vault(tmp_path, folder_index=True)
    out = detect_index.detect(vault, "30-Insights")
    assert out["mode"] == "folder-index"
    assert out["can_append"] is False
    assert out["graph_compatible"] is False  # graphOverwrite off
    assert any("graphOverwrite" in w for w in out["warnings"])


def test_dataview_mode_detected(tmp_path):
    vault = _make_vault(tmp_path, dataview=True)
    out = detect_index.detect(vault, "30-Insights")
    assert out["mode"] == "dataview"
    assert out["can_append"] is False


def test_json_output_is_valid_and_machine_readable(tmp_path):
    vault = _make_vault(tmp_path)
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "detect_index.py"),
         str(vault), "--folder", "30-Insights"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed["mode"] == "static"
    assert parsed["can_append"] is True
