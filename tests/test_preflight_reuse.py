"""Apply must be able to reference preflighted content instead of resending it.

The create contract validates and then writes the same document, so a long
article crossed the process boundary twice. These tests pin the shortcut and,
more importantly, the guarantees it must not weaken: the reference is bound to
the Vault, the note, and the exact rendered bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from obsidian_kb_skill.scripts import preflight_cache

ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONPATH": str(ROOT)}
BODY = "# 标题\n\n## Custom section\n\n正文足够长，重复传输一次就是一次浪费。\n"


def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.create_note", *args],
        cwd=str(ROOT),
        env=ENV,
        input=stdin,
        capture_output=True,
        text=True,
        # Windows would otherwise encode CJK stdin with the locale codec.
        encoding="utf-8",
    )


def _make_vault(tmp_path: Path, name: str = "vault") -> Path:
    vault = tmp_path / name
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "30-Insights").mkdir()
    (vault / "Templates" / "Insight Note.md").write_text(
        "---\ntype: insight-note\ntags: [insight]\n---\n"
        "# {{title}}\n\n## Custom section\n",
        encoding="utf-8",
    )
    return vault


def _preflight(vault: Path, *, title: str = "复用测试") -> dict:
    result = _run(
        str(vault), "--type", "insight-note", "--title", title,
        "--date", "2026-07-14", "--stdin", "--preflight-json", stdin=BODY,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_preflight_stages_content_outside_the_vault(tmp_path: Path):
    vault = _make_vault(tmp_path)
    before = sorted(path.name for path in vault.rglob("*"))

    payload = _preflight(vault)

    assert payload["content"]["reusable"] is True
    assert sorted(path.name for path in vault.rglob("*")) == before


def test_apply_by_reference_writes_what_preflight_validated(tmp_path: Path):
    vault = _make_vault(tmp_path)
    sha256 = _preflight(vault)["content"]["sha256"]

    result = _run(
        str(vault), "--type", "insight-note", "--title", "复用测试",
        "--date", "2026-07-14", "--from-preflight", sha256,
        "--apply", "--compact-json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    written = Path(json.loads(result.stdout)["path"])
    assert hashlib.sha256(written.read_bytes()).hexdigest() == sha256


def test_reference_is_refused_for_another_note(tmp_path: Path):
    vault = _make_vault(tmp_path)
    sha256 = _preflight(vault)["content"]["sha256"]

    result = _run(
        str(vault), "--type", "insight-note", "--title", "另一篇",
        "--date", "2026-07-14", "--from-preflight", sha256,
        "--apply", "--compact-json",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "preflight-context-mismatch"
    assert not list((vault / "30-Insights").glob("*另一篇*.md"))


def test_reference_is_refused_for_another_vault(tmp_path: Path):
    source = _make_vault(tmp_path, "source")
    other = _make_vault(tmp_path, "other")
    sha256 = _preflight(source)["content"]["sha256"]

    result = _run(
        str(other), "--type", "insight-note", "--title", "复用测试",
        "--date", "2026-07-14", "--from-preflight", sha256,
        "--apply", "--compact-json",
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "preflight-vault-mismatch"


def test_reference_is_refused_when_the_render_would_differ(tmp_path: Path):
    vault = _make_vault(tmp_path)
    sha256 = _preflight(vault)["content"]["sha256"]
    # The Vault template contributes frontmatter, so editing it changes what
    # apply would write even though the staged body is untouched.
    (vault / "Templates" / "Insight Note.md").write_text(
        "---\ntype: insight-note\ntags: [insight]\nstatus: draft\n---\n"
        "# {{title}}\n\n## Custom section\n",
        encoding="utf-8",
    )

    result = _run(
        str(vault), "--type", "insight-note", "--title", "复用测试",
        "--date", "2026-07-14", "--from-preflight", sha256,
        "--apply", "--compact-json",
    )

    assert result.returncode == 2
    error = json.loads(result.stdout)["error"]
    assert error["code"] == "preflight-content-changed"
    assert error["expected_sha256"] == sha256
    assert not list((vault / "30-Insights").glob("*.md"))


def test_unknown_reference_names_the_recovery(tmp_path: Path):
    vault = _make_vault(tmp_path)
    never_staged = hashlib.sha256(b"never preflighted").hexdigest()

    result = _run(
        str(vault), "--type", "insight-note", "--title", "复用测试",
        "--from-preflight", never_staged, "--apply", "--compact-json",
    )

    assert result.returncode == 2
    error = json.loads(result.stdout)["error"]
    assert error["code"] == "unknown-preflight-content"
    assert "rerun preflight" in error["message"]


def test_reference_and_body_cannot_be_supplied_together(tmp_path: Path):
    vault = _make_vault(tmp_path)
    sha256 = _preflight(vault)["content"]["sha256"]

    result = _run(
        str(vault), "--type", "insight-note", "--title", "复用测试",
        "--from-preflight", sha256, "--stdin", "--preflight-json", stdin=BODY,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == "conflicting-content-source"


def test_expired_entries_are_pruned(tmp_path: Path):
    vault = _make_vault(tmp_path)
    sha256 = hashlib.sha256(b"stale").hexdigest()
    preflight_cache.stage(
        vault, sha256, "# stale\n", note_type="insight-note", title="t"
    )
    entry = preflight_cache.cache_dir() / f"{sha256}.json"
    assert entry.is_file()
    os.utime(entry, (0, 0))

    preflight_cache.prune(preflight_cache.cache_dir())

    assert not entry.exists()


def test_retention_keeps_the_newest_entries(tmp_path: Path):
    vault = _make_vault(tmp_path)
    directory = preflight_cache.cache_dir()
    now = time.time()
    surplus = 5
    for index in range(preflight_cache.MAX_ENTRIES + surplus):
        sha256 = hashlib.sha256(str(index).encode()).hexdigest()
        preflight_cache.stage(
            vault, sha256, f"# {index}\n", note_type="insight-note", title="t"
        )
        stamp = now - (preflight_cache.MAX_ENTRIES + surplus - index)
        os.utime(directory / f"{sha256}.json", (stamp, stamp))

    preflight_cache.prune(directory)

    kept = {path.stem for path in directory.glob("*.json")}
    last = preflight_cache.MAX_ENTRIES + surplus - 1
    assert len(kept) == preflight_cache.MAX_ENTRIES
    assert hashlib.sha256(b"0").hexdigest() not in kept
    assert hashlib.sha256(str(last).encode()).hexdigest() in kept


def test_an_interrupted_write_is_not_mistaken_for_an_entry(tmp_path: Path):
    vault = _make_vault(tmp_path)
    directory = preflight_cache.cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256(b"debris").hexdigest()
    (directory / f"{sha256}.1234.tmp").write_text("{}", encoding="utf-8")

    preflight_cache.prune(directory)

    # Swept on age, not on sight: a concurrent stage may be about to rename it.
    assert list(directory.glob("*.tmp"))
    result = _run(
        str(vault), "--type", "insight-note", "--title", "复用测试",
        "--from-preflight", sha256, "--apply", "--compact-json",
    )
    assert json.loads(result.stdout)["error"]["code"] == "unknown-preflight-content"
