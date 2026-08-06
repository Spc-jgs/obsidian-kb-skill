"""A captured source is kept beside the note, verbatim, and linked both ways.

The note that prompted this carried 35 KB of an author's prose around a 7.6 KB
digest — 82% of the file — and a quarter of its search citations landed in that
prose rather than in the user's own knowledge.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from obsidian_kb_skill.scripts.audit_vault import audit_vault
from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter
from obsidian_kb_skill.scripts.source_archive import (
    archive_stem,
    archived_body,
    link_note_to_archive,
    render_archive,
    source_sha256,
)

ROOT = Path(__file__).resolve().parent.parent
# Everything an archiver could be tempted to normalize away.
AWKWARD = (
    "### 原文的三级标题\r\n"
    "\r\n"
    "---\r\n"
    "\r\n"
    "front: matter-looking line\r\n"
    "\r\n"
    "```zig\r\n"
    "const x = 1;\r\n"
    "```\r\n"
    "\r\n"
    "尾部没有换行"
)


def _run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    # Bytes on stdin, decoded output. In text mode Windows translates the `\n`
    # in what the *parent* writes, turning this fixture's `\r\n` into `\r\r\n`
    # before the helper ever sees it — the test would then be measuring the
    # harness rather than whether the archive preserves what it was given.
    result = subprocess.run(
        [sys.executable, "-m", "obsidian_kb_skill.scripts.archive_source", *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        input=None if stdin is None else stdin.encode("utf-8"),
        capture_output=True,
    )
    return subprocess.CompletedProcess(
        result.args,
        result.returncode,
        result.stdout.decode("utf-8"),
        result.stderr.decode("utf-8", errors="replace"),
    )


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Templates").mkdir()
    (vault / "20-Learning").mkdir()
    (vault / "20-Learning" / "violin.md").write_text(
        '---\ndate: "2026-08-06"\ntype: web-clip\ntags: [learning]\n'
        "source: https://example.com/a\n---\n"
        "# Violin 架构\n\n## 来源与结论\n\n结论正文。\n\n## 核心知识\n\n正文。\n",
        encoding="utf-8",
    )
    return vault


def _hashes(vault: Path) -> dict[str, str]:
    return {
        path.relative_to(vault).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(vault.rglob("*"))
        if path.is_file()
    }


def test_the_source_survives_byte_for_byte():
    rendered = render_archive(
        AWKWARD, source="https://example.com/a", note="violin.md",
        captured="2026-08-06",
    )

    assert archived_body(rendered) == AWKWARD


def test_the_hash_covers_the_source_and_not_the_frontmatter():
    """Frontmatter is metadata about the capture, not part of the evidence."""
    one = render_archive(
        AWKWARD, source="https://example.com/a", note="violin.md",
        captured="2026-08-06",
    )
    two = render_archive(
        AWKWARD, source="https://example.com/a", note="violin.md",
        captured="2026-08-06", author="酒米", published="2026-08-06",
    )

    assert source_sha256(AWKWARD) in one
    assert source_sha256(AWKWARD) in two
    assert archived_body(one) == archived_body(two)


def test_linking_leaves_the_rest_of_the_note_alone():
    note = (
        '---\ndate: "2026-08-06"\ntype: web-clip\n---\n'
        "# Violin\n\n## 来源与结论\n\n结论。\n\n## 核心知识\n\n正文。\n"
    )

    linked = link_note_to_archive(note, "2026-08-06 violin·原文")

    assert "source_archive: '[[2026-08-06 violin·原文]]'" in linked
    assert "原文存档：[[2026-08-06 violin·原文]]" in linked
    # Every original body line is still present, in order.
    for line in ("# Violin", "## 来源与结论", "结论。", "## 核心知识", "正文。"):
        assert line in linked
    assert linked.index("## 来源与结论") < linked.index("原文存档：")
    assert linked.index("原文存档：") < linked.index("## 核心知识")
    # The rewritten frontmatter must still be readable, or the note is broken.
    reparsed = parse_frontmatter(linked)
    assert reparsed.metadata is not None
    assert reparsed.metadata["type"] == "web-clip"


def test_preflight_writes_nothing(tmp_path: Path):
    vault = _vault(tmp_path)
    before = _hashes(vault)

    result = _run(
        str(vault), "--note", "20-Learning/violin.md",
        "--source-url", "https://example.com/a",
        "--stdin", "--preflight-json", stdin=AWKWARD,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["archive"]["path"].startswith("95-Sources/2026-")
    assert payload["archive"]["sha256"] == source_sha256(AWKWARD)
    assert payload["archive"]["already_archived"] is None
    assert _hashes(vault) == before


def test_apply_writes_the_archive_and_links_it_both_ways(tmp_path: Path):
    vault = _vault(tmp_path)

    result = _run(
        str(vault), "--note", "20-Learning/violin.md",
        "--source-url", "https://example.com/a", "--author", "酒米",
        "--stdin", "--apply", "--compact-json", stdin=AWKWARD,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    archive = vault / payload["archive"]["path"]
    assert archived_body(archive.read_bytes().decode("utf-8")) == AWKWARD
    note = (vault / "20-Learning" / "violin.md").read_text(encoding="utf-8")
    assert archive.stem in note
    assert "[[violin]]" in archive.read_bytes().decode("utf-8")


def test_the_archived_note_link_resolves_and_breaks_loudly(tmp_path: Path):
    vault = _vault(tmp_path)
    _run(
        str(vault), "--note", "20-Learning/violin.md",
        "--source-url", "https://example.com/a",
        "--stdin", "--apply", "--compact-json", stdin=AWKWARD,
    )

    assert "broken-wikilink" not in {f.code for f in audit_vault(vault)}

    next(vault.joinpath("95-Sources").rglob("*.md")).unlink()

    assert "broken-wikilink" in {f.code for f in audit_vault(vault)}


def test_archiving_twice_is_refused_unless_replacing(tmp_path: Path):
    vault = _vault(tmp_path)
    args = (
        str(vault), "--note", "20-Learning/violin.md",
        "--source-url", "https://example.com/a", "--stdin", "--apply",
        "--compact-json",
    )
    _run(*args, stdin=AWKWARD)
    before = _hashes(vault)

    refused = _run(*args, stdin=AWKWARD)

    assert refused.returncode == 2
    assert json.loads(refused.stdout)["error"]["code"] == "note-already-archived"
    assert _hashes(vault) == before

    allowed = _run(*args, "--replace", stdin=AWKWARD)
    assert allowed.returncode == 0, allowed.stderr


def test_refusals_leave_the_vault_untouched(tmp_path: Path):
    vault = _vault(tmp_path)
    before = _hashes(vault)

    missing = _run(
        str(vault), "--note", "20-Learning/nope.md",
        "--source-url", "https://example.com/a",
        "--stdin", "--apply", "--compact-json", stdin=AWKWARD,
    )
    empty = _run(
        str(vault), "--note", "20-Learning/violin.md",
        "--source-url", "https://example.com/a",
        "--stdin", "--apply", "--compact-json", stdin="   \n",
    )

    assert json.loads(missing.stdout)["error"]["code"] == "invalid-note"
    assert json.loads(empty.stdout)["error"]["code"] == "empty-source-content"
    assert missing.returncode == empty.returncode == 2
    assert _hashes(vault) == before


def test_a_dated_note_title_is_not_dated_twice():
    """Notes here are named `YYYY-MM-DD Title`; the first real archive read
    `2026-08-06 2026-08-06 …·原文`."""
    dated = archive_stem("2026-08-06 从零构建Coding Agent", captured="2026-08-06")
    undated = archive_stem("Violin 架构", captured="2026-08-06")

    assert dated == "2026-08-06 从零构建Coding Agent·原文"
    assert undated == "2026-08-06 Violin 架构·原文"
