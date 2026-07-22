"""Real CLI coverage for invalid Folder Index filename configuration."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]


def _make_vault(tmp_path: Path, *, field: str) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    plugin = vault / ".obsidian/plugins/obsidian-folder-index"
    plugin.mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "00-Inbox").mkdir()
    (vault / "30-Insights").mkdir()
    (vault / ".obsidian/community-plugins.json").write_text(
        '["obsidian-folder-index"]', encoding="utf-8"
    )
    outside = tmp_path / "outside.md"
    settings: dict[str, object]
    if field == "root_index_file":
        settings = {"rootIndexFile": str(outside)}
    else:
        settings = {
            "indexFileUserSpecified": True,
            "indexFilename": str(outside.with_suffix("")),
        }
    (plugin / "data.json").write_text(json.dumps(settings), encoding="utf-8")
    return vault, outside


@pytest.mark.parametrize(
    ("module", "field", "extra", "json_error"),
    [
        ("audit_vault", "root_index_file", (), False),
        ("audit_vault", "root_index_file", ("--json",), True),
        ("detect_index", "index_filename", ("--folder", "30-Insights"), False),
        (
            "detect_index",
            "index_filename",
            ("--folder", "30-Insights", "--json"),
            True,
        ),
        ("vault_info", "index_filename", (), True),
        ("vault_info", "index_filename", ("--json",), True),
    ],
)
def test_invalid_folder_index_config_is_a_clean_cli_error(
    tmp_path: Path,
    module: str,
    field: str,
    extra: tuple[str, ...],
    json_error: bool,
):
    vault, outside = _make_vault(tmp_path, field=field)
    env = {**os.environ, "PYTHONPATH": str(REPO)}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            f"obsidian_kb_skill.scripts.{module}",
            str(vault),
            *extra,
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stdout + result.stderr
    if json_error:
        assert result.stderr == ""
        error = json.loads(result.stdout)["error"]
        assert error == {
            "code": "invalid-folder-index-config",
            "message": f"{field} must be a portable visible basename",
        }
    else:
        assert result.stdout == ""
        assert result.stderr == (
            "error: invalid-folder-index-config: "
            f"{field} must be a portable visible basename\n"
        )
    assert not outside.exists()
