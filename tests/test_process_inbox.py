"""Tests for the Inbox Processor (scripts/process_inbox.py)."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

import obsidian_kb_skill.scripts.process_inbox as process_inbox
from obsidian_kb_skill.scripts.process_inbox import process_vault


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    (vault / "00-Inbox").mkdir()
    (vault / "30-Insights").mkdir()
    return vault


def test_routes_insight_by_keyword(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\ninteresting idea\n", encoding="utf-8"
    )

    plans = process_vault(vault, apply=False)

    assert len(plans) == 1
    assert plans[0]["target"] == "30-Insights"
    # read-only: nothing moved
    assert (vault / "00-Inbox" / "Note.md").is_file()
    assert not (vault / "30-Insights" / "Note.md").exists()


def test_routes_by_type(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Clip.md").write_text(
        '---\ndate: "2026-07-07"\ntype: web-clip\n'
        'tags: [web-clip]\nsource: ""\nauthor: ""\npublished: ""\n---\n# Clip\n',
        encoding="utf-8",
    )

    plans = process_vault(vault, apply=False)

    assert plans[0]["target"] == "20-Learning"


def test_apply_moves_and_fills_frontmatter(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    moved = vault / "30-Insights" / "Note.md"
    assert moved.is_file()
    assert not (vault / "00-Inbox" / "Note.md").exists()
    text = moved.read_text(encoding="utf-8")
    assert "type: insight-note" in text
    assert "tags:" in text
    assert "date:" in text


def test_apply_updates_static_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    class FixedDate(datetime.date):
        @classmethod
        def today(cls) -> datetime.date:
            return cls(2042, 3, 4)

    monkeypatch.setattr(process_inbox.datetime, "date", FixedDate)
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "INDEX.md").write_text(
        "# Insights\n\n## Recent\n", encoding="utf-8"
    )
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    index_text = (vault / "30-Insights" / "INDEX.md").read_text(encoding="utf-8")
    assert index_text == (
        "# Insights\n\n## Recent\n"
        "- [[30-Insights/Note|Some Insight]] (2042-03-04)\n"
    )


def test_skips_when_target_unknown(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Misc.md").write_text(
        "# Misc\nuncategorized capture\n", encoding="utf-8"
    )

    plans = process_vault(vault, apply=True)

    assert plans[0].get("skip")
    # left in the inbox
    assert (vault / "00-Inbox" / "Misc.md").is_file()


def test_apply_skips_existing_target(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "Note.md").write_text("existing\n", encoding="utf-8")
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    assert (vault / "00-Inbox" / "Note.md").is_file()
    assert (vault / "30-Insights" / "Note.md").read_text(encoding="utf-8") == "existing\n"


def test_apply_does_not_touch_folder_index_listings(tmp_path):
    vault = make_vault(tmp_path)
    obsidian = vault / ".obsidian"
    plugin = obsidian / "plugins" / "obsidian-folder-index"
    plugin.mkdir(parents=True)
    (obsidian / "community-plugins.json").write_text(
        json.dumps(["obsidian-folder-index"]), encoding="utf-8"
    )
    (vault / "30-Insights" / "INDEX.md").write_text(
        "---\ntype: folder-index\ntags: [moc]\n---\n```folder-index-content\n```\n",
        encoding="utf-8",
    )
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    index_text = (vault / "30-Insights" / "INDEX.md").read_text(encoding="utf-8")
    # Folder Index owns the listing; the processor must not append a manual link.
    assert "[[" not in index_text


MALFORMED_NOTE = (
    "---\n"
    "title: 重要笔记\n"
    "tags: [a, b\n"
    "date: 2026-07-01\n"
    "custom_field: 我的原始数据\n"
    "---\n"
    "\n"
    "# 一个 insight\n"
    "\n"
    "正文内容，非常重要。\n"
)

UNCLOSED_NOTE = "---\ntitle: 重要笔记\ntype: insight-note\n\n# 一个 insight\n"

NOT_MAPPING_NOTE = "---\n- insight\n- idea\n---\n\n# 一个 insight\n"


@pytest.mark.parametrize(
    "content",
    [MALFORMED_NOTE, UNCLOSED_NOTE, NOT_MAPPING_NOTE],
    ids=["invalid-yaml", "unclosed", "not-mapping"],
)
def test_plan_refuses_unreadable_frontmatter(tmp_path, content):
    """Preview must surface the defect before the user ever reaches --apply."""
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Bad.md").write_text(content, encoding="utf-8")

    plans = process_vault(vault, apply=False)

    assert plans[0]["skip_code"] == "unreadable-frontmatter"
    assert plans[0].get("skip")
    assert plans[0].get("target") is None


@pytest.mark.parametrize(
    "content",
    [MALFORMED_NOTE, UNCLOSED_NOTE, NOT_MAPPING_NOTE],
    ids=["invalid-yaml", "unclosed", "not-mapping"],
)
def test_apply_never_rewrites_unreadable_frontmatter(tmp_path, content):
    """Fail closed: unparseable frontmatter is preserved byte-for-byte in place.

    Regression for silent data loss — the note used to be moved with its
    original frontmatter replaced by inferred defaults and the source deleted.
    """
    vault = make_vault(tmp_path)
    source = vault / "00-Inbox" / "Bad.md"
    source.write_text(content, encoding="utf-8")
    original = source.read_bytes()

    process_vault(vault, apply=True)

    assert source.is_file(), "source must not be deleted"
    assert source.read_bytes() == original, "source must not be rewritten"
    assert not (vault / "30-Insights" / "Bad.md").exists()


def test_apply_still_fills_notes_without_frontmatter(tmp_path):
    """A note with no frontmatter at all is not a defect and stays fillable."""
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    plans = process_vault(vault, apply=True)

    assert not plans[0].get("skip")
    assert (vault / "30-Insights" / "Note.md").is_file()


def _refuse_unlink_for(monkeypatch: pytest.MonkeyPatch, *blocked: Path) -> None:
    """Make unlink fail only for the given paths, leaving others real."""
    real_unlink = Path.unlink
    targets = {path.resolve() for path in blocked}

    def guarded_unlink(self: Path, *args, **kwargs):
        if self.resolve() in targets:
            raise OSError("permission denied")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", guarded_unlink)


def test_apply_leaves_no_duplicate_when_source_removal_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """A failed source unlink must not leave the note in two places."""
    vault = make_vault(tmp_path)
    source = vault / "00-Inbox" / "Note.md"
    source.write_text("# Some Insight\nidea\n", encoding="utf-8")
    _refuse_unlink_for(monkeypatch, source)

    process_vault(vault, apply=True)

    assert source.is_file(), "source is retained when it cannot be removed"
    assert not (vault / "30-Insights" / "Note.md").exists(), (
        "the half-written destination must be rolled back"
    )


def test_apply_warns_when_rollback_also_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
):
    """If the rollback cannot run either, say so instead of staying silent."""
    vault = make_vault(tmp_path)
    source = vault / "00-Inbox" / "Note.md"
    source.write_text("# Some Insight\nidea\n", encoding="utf-8")
    dest = vault / "30-Insights" / "Note.md"
    _refuse_unlink_for(monkeypatch, source, dest)

    process_vault(vault, apply=True)

    stderr = capsys.readouterr().err
    assert "cannot remove source" in stderr
    assert "could not roll back" in stderr
    assert source.is_file()


def test_apply_summary_does_not_claim_refused_notes_were_applied(tmp_path, capsys):
    """The summary must count commits, not inspected files."""
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Bad.md").write_text(MALFORMED_NOTE, encoding="utf-8")
    (vault / "00-Inbox" / "Good.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    exit_code = process_inbox.main([str(vault), "--apply"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "1 Inbox note(s) applied." in captured.out
    assert "1 Inbox note(s) left in place" in captured.out
    assert "unreadable frontmatter" in captured.err
    assert (vault / "00-Inbox" / "Bad.md").is_file()
    assert (vault / "30-Insights" / "Good.md").is_file()


def test_unreadable_frontmatter_is_reported_in_json(tmp_path, capsys):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Bad.md").write_text(MALFORMED_NOTE, encoding="utf-8")

    exit_code = process_inbox.main([str(vault), "--apply", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload[0]["skip_code"] == "unreadable-frontmatter"
    assert payload[0]["frontmatter_issue"]["code"] == "invalid-frontmatter"
    assert payload[0]["frontmatter_issue"]["line"] == 4


def test_apply_preserves_existing_frontmatter_bytes(tmp_path):
    """Only the missing keys are inserted; the rest of the block is untouched.

    The old renderer re-dumped the whole mapping through yaml.safe_dump, which
    silently discarded comments and rewrote indentation and quoting.
    """
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Note.md").write_text(
        "---\n"
        "title: 我的笔记  # 保留我\n"
        "aliases:\n"
        "  - 别名一\n"
        "  - 别名二\n"
        'custom: "带引号"\n'
        "type: insight-note\n"
        "---\n"
        "\n# 正文\n",
        encoding="utf-8",
    )

    process_vault(vault, apply=True)

    text = (vault / "30-Insights" / "Note.md").read_text(encoding="utf-8")
    assert "# 保留我" in text, "YAML comments must survive"
    assert "  - 别名一" in text, "indentation style must survive"
    assert 'custom: "带引号"' in text, "quoting style must survive"
    # the missing keys are still filled in
    assert "date:" in text and "tags:" in text


def test_apply_still_prepends_a_block_when_frontmatter_is_absent(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    text = (vault / "30-Insights" / "Note.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert text.count("---\n") == 2, "exactly one frontmatter block"
    assert text.rstrip().endswith("idea")


def test_apply_fills_an_empty_frontmatter_block_without_duplicating_it(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "Note.md").write_text(
        "---\n---\n\n# Some Insight\nidea\n", encoding="utf-8"
    )

    process_vault(vault, apply=True)

    text = (vault / "30-Insights" / "Note.md").read_text(encoding="utf-8")
    assert text.count("---\n") == 2
    assert "type: insight-note" in text


def test_inbox_discovery_refuses_symlinked_entries(tmp_path):
    """A symlink in the Inbox must not import content from outside the Vault.

    process_inbox states that reading from an external directory is rejected
    so that outside files are never silently imported, but discovery used
    glob() and is_file(), both of which follow symlinks.
    """
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.md"
    secret.write_text("# A stray analysis idea\n\nsecret\n", encoding="utf-8")
    link = vault / "00-Inbox" / "link.md"
    try:
        link.symlink_to(secret)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    plans = process_vault(vault, apply=True)

    assert plans[0]["skip_code"] == "unsafe-inbox-entry"
    assert not (vault / "30-Insights" / "link.md").exists()
    assert link.is_symlink(), "the entry is left in place, not consumed"
    assert secret.read_text(encoding="utf-8").endswith("secret\n")


def test_inbox_discovery_reports_unsafe_entries_in_plan_mode(tmp_path):
    vault = make_vault(tmp_path)
    target = vault / "30-Insights"
    link = vault / "00-Inbox" / "dir-link.md"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    plans = process_vault(vault, apply=False)

    assert [p["skip_code"] for p in plans] == ["unsafe-inbox-entry"]


# --- Apply-phase refusals must reach the plan, not only stderr (#92) ---------
#
# Plan-phase refusals carry `skip`/`skip_code` on the plan entry. Apply-phase
# refusals printed to stderr and set nothing, so a JSON consumer saw
# `applied: false` with no reason at all and could report *that* a note did not
# move but never *why*.


def test_apply_records_why_an_occupied_target_was_refused(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "Note.md").write_text("existing\n", encoding="utf-8")
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    plans = process_vault(vault, apply=True, silent=True)

    assert plans[0]["applied"] is False
    assert plans[0]["skip_code"] == "target-exists"
    assert plans[0].get("skip"), "a refusal code without a readable reason"


def test_apply_records_a_write_time_frontmatter_failure(tmp_path):
    """The plan was sound when shown; the file changed before it was applied.

    This is the real window between showing a user their filing plan and their
    confirming it — the re-check exists for exactly that, and its refusal has
    to be as visible as the plan-phase one.
    """
    vault = make_vault(tmp_path)
    source = vault / "00-Inbox" / "Note.md"
    source.write_text("# Some Insight\nidea\n", encoding="utf-8")
    plan = process_inbox.plan_note(source, vault)
    source.write_text(MALFORMED_NOTE, encoding="utf-8")

    applied = process_inbox.apply_plan(plan, vault, silent=True)

    assert applied is False
    assert plan["skip_code"] == "unreadable-frontmatter"
    assert plan.get("skip")


def test_apply_records_why_a_failed_source_removal_refused_the_note(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    vault = make_vault(tmp_path)
    source = vault / "00-Inbox" / "Note.md"
    source.write_text("# Some Insight\nidea\n", encoding="utf-8")
    _refuse_unlink_for(monkeypatch, source)

    plans = process_vault(vault, apply=True, silent=True)

    assert plans[0]["applied"] is False
    assert plans[0]["skip_code"] == "source-removal-failed"
    assert not (vault / "30-Insights" / "Note.md").exists()


def test_partial_apply_is_reported_as_its_own_state(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Two copies on disk is not the same outcome as 'nothing happened'.

    Every other refusal leaves the Vault untouched. This one leaves a copy the
    user has to remove by hand, so it cannot share their code — an Agent that
    cannot tell the two apart will report a clean skip over a split note.
    """
    vault = make_vault(tmp_path)
    source = vault / "00-Inbox" / "Note.md"
    source.write_text("# Some Insight\nidea\n", encoding="utf-8")
    dest = vault / "30-Insights" / "Note.md"
    _refuse_unlink_for(monkeypatch, source, dest)

    plans = process_vault(vault, apply=True, silent=True)

    assert plans[0]["applied"] is False
    assert plans[0]["skip_code"] == "partial-apply"
    assert dest.is_file(), "the copy survives when rollback also fails"
    assert source.is_file()


def test_every_unapplied_note_carries_a_machine_readable_reason(tmp_path, capsys):
    """The contract the Agent depends on: no silent `applied: false`."""
    vault = make_vault(tmp_path)
    (vault / "30-Insights" / "Occupied.md").write_text("existing\n", encoding="utf-8")
    (vault / "00-Inbox" / "Occupied.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )
    (vault / "00-Inbox" / "Bad.md").write_text(MALFORMED_NOTE, encoding="utf-8")
    (vault / "00-Inbox" / "Good.md").write_text(
        "# Some Insight\nidea\n", encoding="utf-8"
    )

    exit_code = process_inbox.main([str(vault), "--apply", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    unapplied = [entry for entry in payload if not entry.get("applied")]
    assert len(unapplied) == 2
    for entry in unapplied:
        assert entry.get("skip_code"), f"no machine-readable reason: {entry['path']}"
        assert entry.get("skip"), f"no readable reason: {entry['path']}"
