"""Did what we captured earn its place?

Every other measurement in this project asks whether a capture is *faithful*.
None asks whether it was ever used. On the reference Vault, 66 of 152 dated
notes were written and never opened again — 40 of them web-clips, which is 74%
of every web-clip in the Vault. Revisit rate by type differs threefold:
learning-note 76%, insight-note 36%, web-clip 26%.

The literature named this in 2014. Christian Tietze, *The Collector's Fallacy*:
"having a text at hand does nothing to increase our knowledge". Andy Matuschak
sets the design requirement this module implements: an inbox "should encourage
lingering items to be removed (e.g. it should be obvious when one has been
passed over many times)".
"""
from __future__ import annotations

import datetime
import os
import runpy
import subprocess
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.review_captures import review_captures


ROOT = Path(__file__).resolve().parent.parent


def capture(vault: Path, relative: str, *, note_type: str, date: str, touched: str | None = None) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntype: {note_type}\ndate: '{date}'\ntags:\n- x\n---\n\n# {path.stem}\n\n正文。\n",
        encoding="utf-8",
    )
    stamp = datetime.date.fromisoformat(touched or date)
    when = datetime.datetime.combine(stamp, datetime.time(12, 0)).timestamp()
    os.utime(path, (when, when))
    return path


def test_a_capture_never_reopened_is_counted_and_named(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    capture(vault, "20-Learning/never.md", note_type="web-clip", date="2026-06-01")
    capture(vault, "20-Learning/revisited.md", note_type="web-clip", date="2026-06-01",
            touched="2026-07-15")

    report = review_captures(vault, as_of=datetime.date(2026, 8, 18))

    assert report["ok"] is True
    assert report["read_only"] is True
    assert report["summary"]["captures"] == 2
    assert report["summary"]["never_reopened"] == 1
    paths = [item["path"] for item in report["items"]]
    assert "20-Learning/never.md" in paths
    assert "20-Learning/revisited.md" not in paths


def test_the_report_says_which_evidence_it_used(tmp_path: Path):
    """A number whose provenance is unstated invites being quoted as precise.

    File mtime is perturbed by sync clients and by any git checkout. Git
    history is exact but only covers tracked files, and on the reference Vault
    that was 57 of 214. The report names its source rather than letting the
    reader assume the stronger one.
    """
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    capture(vault, "20-Learning/a.md", note_type="web-clip", date="2026-06-01")

    report = review_captures(vault, as_of=datetime.date(2026, 8, 18))

    assert report["evidence"] == "file-mtime"
    assert "mtime" in report["evidence_caveat"]


def test_git_history_is_preferred_and_declared_when_the_vault_is_a_repo(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=vault, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=vault, check=True)
    note = capture(vault, "20-Learning/tracked.md", note_type="web-clip", date="2026-06-01")
    subprocess.run(["git", "add", "-A"], cwd=vault, check=True)
    subprocess.run(["git", "commit", "-qm", "add"], cwd=vault, check=True)
    note.write_text(note.read_text(encoding="utf-8") + "\n补充。\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "revise"], cwd=vault, check=True)

    report = review_captures(vault, as_of=datetime.date(2026, 8, 18))

    assert report["evidence"] == "git-history"
    assert report["summary"]["never_reopened"] == 0, "two commits means it was revised"


def test_revisit_rate_is_broken_out_by_type(tmp_path: Path):
    """The threefold gap between types is the finding, not the total.

    A single number says "43% of notes are cold" and suggests nothing. The
    split says learning-notes get reopened and clips do not, which points at
    what to change.
    """
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for i in range(4):
        capture(vault, f"20-Learning/clip{i}.md", note_type="web-clip", date="2026-06-01")
    capture(vault, "20-Learning/learn.md", note_type="learning-note", date="2026-06-01",
            touched="2026-07-01")

    report = review_captures(vault, as_of=datetime.date(2026, 8, 18))
    by_type = {row["type"]: row for row in report["by_type"]}

    # Asserted on the list itself, not only on rows read out of it: a break
    # that emptied `by_type` left this test green, because a dict built from
    # no rows raises nothing until a key is read — and every key read below
    # was inside the same `assert` that would have failed anyway.
    assert len(report["by_type"]) == 2, report["by_type"]
    assert by_type["web-clip"]["never_reopened"] == 4
    assert by_type["web-clip"]["revisit_rate"] == 0.0
    assert by_type["learning-note"]["revisit_rate"] == 1.0


def test_the_coldest_captures_come_first(tmp_path: Path):
    """Matuschak's requirement: passed over many times must be obvious."""
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    # Named so that alphabetical order is the reverse of cold order: sorting by
    # path alone passed the first draft of this test, because `ancient` happens
    # to sort before `recent` and the assertion could not tell the two rules
    # apart.
    capture(vault, "20-Learning/aaa-recent.md", note_type="web-clip", date="2026-08-01")
    capture(vault, "20-Learning/zzz-ancient.md", note_type="web-clip", date="2026-01-05")

    report = review_captures(vault, as_of=datetime.date(2026, 8, 18))

    assert [item["path"] for item in report["items"]] == [
        "20-Learning/zzz-ancient.md",
        "20-Learning/aaa-recent.md",
    ]
    assert report["items"][0]["cold_days"] > report["items"][1]["cold_days"]


def test_a_capture_is_not_a_defect(tmp_path: Path):
    """This is feedback, not a verdict, and the module must not pretend otherwise.

    `similar-title` reported 115 findings on the reference Vault and 113 were
    normal practice; a per-note finding for each of 66 cold captures would
    repeat that mistake exactly. There is no severity here and no `findings`
    key — an aggregate with examples, which is what the reader can act on.
    """
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    capture(vault, "20-Learning/cold.md", note_type="web-clip", date="2026-06-01")

    report = review_captures(vault, as_of=datetime.date(2026, 8, 18))

    assert "findings" not in report
    assert "severity" not in report
    for item in report["items"]:
        assert "severity" not in item


def test_notes_that_are_not_captures_are_out_of_scope(tmp_path: Path):
    """A daily note is written once by design; counting it as cold is noise."""
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    capture(vault, "10-Work/日报/2026-06-01 日报.md", note_type="daily-report", date="2026-06-01")
    capture(vault, "00-Index/20-Learning.md", note_type="folder-index", date="2026-06-01")
    capture(vault, "20-Learning/clip.md", note_type="web-clip", date="2026-06-01")

    report = review_captures(vault, as_of=datetime.date(2026, 8, 18))

    assert report["summary"]["captures"] == 1
    assert [item["path"] for item in report["items"]] == ["20-Learning/clip.md"]


def test_the_helper_is_registered_in_both_skills():
    for skill in ("obsidian-knowledge-base", "obsidian-knowledge-retrieval"):
        runner = ROOT / "skills" / skill / "scripts" / "run_helper.py"
        assert "review-captures" in runner.read_text(encoding="utf-8"), skill
        assert (
            ROOT / "skills" / skill / "scripts" / "obsidian_kb_skill"
            / "scripts" / "review_captures.py"
        ).is_file(), skill


def test_a_backup_copy_is_not_a_capture(tmp_path):
    """`.obsidian-kb-backups/` holds tool-made copies, and they never get reopened.

    Counting them guarantees the answer: nobody opens a backup, so every one of
    them lands in `never_reopened` and drags the revisit rate down. On the
    reference Vault three backed-up web-clips were counted as captures and two
    of them were reported as never reopened — with `.obsidian-kb-backups/…` shown
    to the reader as a note worth revisiting.
    """
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    capture(vault, "20-Learning/Real.md", note_type="web-clip", date="2026-07-01")
    capture(
        vault,
        ".obsidian-kb-backups/2026-07-01-120000/20-Learning/Real.md",
        note_type="web-clip",
        date="2026-07-01",
    )

    report = review_captures(vault, as_of=datetime.date(2026, 8, 1))

    assert report["summary"]["captures"] == 1
    paths = [item["path"] for item in report["items"]]
    assert not [p for p in paths if ".obsidian-kb-backups" in p], paths


def test_every_helper_that_walks_the_vault_skips_the_backup_directory():
    """Three modules each keep their own exclusion list; nothing related them.

    `audit_vault.IGNORED_PARTS` and `search_vault.IGNORED_DIRECTORY_NAMES` both
    drop `.obsidian-kb-backups`; `review_captures.IGNORED_DIRECTORIES` did not,
    which is how backups became captures. The lists stay separate on purpose —
    they answer different questions — but a directory holding copies of notes is
    not a question any of them should differ on.
    """
    from obsidian_kb_skill.scripts.audit_vault import IGNORED_PARTS
    from obsidian_kb_skill.scripts.review_captures import IGNORED_DIRECTORIES
    from obsidian_kb_skill.scripts.search_vault import IGNORED_DIRECTORY_NAMES

    backups = ".obsidian-kb-backups"
    for name, listing in (
        ("audit_vault.IGNORED_PARTS", IGNORED_PARTS),
        ("search_vault.IGNORED_DIRECTORY_NAMES", IGNORED_DIRECTORY_NAMES),
        ("review_captures.IGNORED_DIRECTORIES", IGNORED_DIRECTORIES),
    ):
        assert backups in listing, f"{name} does not skip {backups}"
