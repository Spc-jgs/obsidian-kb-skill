from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

import obsidian_kb_skill.scripts.inbox_plan as inbox_plan
from obsidian_kb_skill.scripts.inbox_plan import (
    InboxPlanItem,
    legacy_plan_dict,
    plan_inbox,
    render_frontmatter_updates,
    sha256_bytes,
    snapshot_inbox_sources,
)
from obsidian_kb_skill.scripts.frontmatter import parse_frontmatter


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    (vault / "00-Inbox").mkdir()
    return vault


def make_symlink(target: Path, link: Path) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")


def snapshot_one(tmp_path: Path, payload: bytes, name: str = "Note.md"):
    vault = make_vault(tmp_path)
    note = vault / "00-Inbox" / name
    note.write_bytes(payload)
    return vault, note, snapshot_inbox_sources(vault)[0]


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"---\na: [\n---\nbody\n", "invalid-frontmatter"),
        (b"---\na: 1\nbody\n", "unclosed-frontmatter"),
        (b"---\nnull\n---\nbody\n", "frontmatter-not-mapping"),
        (b"---\n- one\n---\nbody\n", "frontmatter-not-mapping"),
        (b"---\nscalar\n---\nbody\n", "frontmatter-not-mapping"),
    ],
)
def test_snapshot_blocks_frontmatter_issue_without_changing_bytes(
    tmp_path: Path, payload: bytes, code: str
) -> None:
    vault = make_vault(tmp_path)
    note = vault / "00-Inbox" / "bad.md"
    note.write_bytes(payload)

    item = snapshot_inbox_sources(vault)[0]

    assert item.issue is not None
    assert item.issue.code == code
    assert item.raw == payload
    assert item.sha256 == sha256_bytes(payload)
    assert item.text == payload.decode("utf-8")
    assert item.frontmatter is not None
    assert item.issue.line == item.frontmatter.issue.line
    assert item.issue.column == item.frontmatter.issue.column
    assert note.read_bytes() == payload


def test_snapshot_valid_source_freezes_identity_bytes_hash_and_parse(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    note = vault / "00-Inbox" / "good.md"
    payload = b"\xef\xbb\xbf---\r\ntype: note\r\n---\r\nbody\r\n"
    note.write_bytes(payload)
    before = note.stat()

    item = snapshot_inbox_sources(vault)[0]

    assert item.source == Path("00-Inbox/good.md")
    assert item.identity is not None
    assert item.identity.device == before.st_dev
    assert item.identity.inode == before.st_ino
    assert item.identity.size == before.st_size
    assert item.identity.mtime_ns == before.st_mtime_ns
    assert item.raw == payload
    assert item.sha256 == sha256_bytes(payload)
    assert item.text == payload.decode("utf-8")
    assert item.frontmatter is not None
    assert item.frontmatter.issue is None
    assert item.frontmatter.metadata == {"type": "note"}
    assert item.issue is None
    assert note.read_bytes() == payload


def test_snapshot_sorts_by_filename_and_has_no_item_limit(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    inbox = vault / "00-Inbox"
    names = [f"note-{number:02d}.md" for number in range(10, -1, -1)]
    for name in names:
        (inbox / name).write_bytes(name.encode("utf-8"))
    (inbox / "ignored.txt").write_bytes(b"ignored")

    items = snapshot_inbox_sources(vault)

    assert [item.source.name for item in items] == sorted(names)
    assert len(items) == 11


def test_snapshot_blocks_invalid_utf8_without_changing_bytes(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    note = vault / "00-Inbox" / "bad.md"
    payload = b"front\xffmatter"
    note.write_bytes(payload)

    item = snapshot_inbox_sources(vault)[0]

    assert item.issue is not None
    assert item.issue.code == "invalid-utf8"
    assert item.raw == payload
    assert item.sha256 == sha256_bytes(payload)
    assert item.text is None
    assert item.frontmatter is None
    assert note.read_bytes() == payload


@pytest.mark.parametrize("target_location", ["internal", "external"])
def test_snapshot_rejects_symlink_without_reading_target(
    tmp_path: Path, target_location: str
) -> None:
    vault = make_vault(tmp_path)
    inbox = vault / "00-Inbox"
    if target_location == "internal":
        target = inbox / "target.txt"
    else:
        target = tmp_path / "outside.md"
    payload = b"secret source bytes\n"
    target.write_bytes(payload)
    link = inbox / "linked.md"
    make_symlink(target, link)
    before = target.read_bytes()

    item = snapshot_inbox_sources(vault)[0]

    assert item.source == Path("00-Inbox/linked.md")
    assert item.issue is not None
    assert item.issue.code == "symlink-source"
    assert item.raw is None
    assert item.sha256 is None
    assert item.text is None
    assert item.frontmatter is None
    assert target.read_bytes() == before


def test_snapshot_rejects_source_swapped_to_symlink_after_stat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = make_vault(tmp_path)
    source = vault / "00-Inbox" / "swapped.md"
    source.write_bytes(b"safe source\n")
    outside = tmp_path / "outside-secret.md"
    secret = b"outside secret\n"
    outside.write_bytes(secret)
    original_read_bytes = Path.read_bytes
    original_open = os.open
    swapped = False

    def swap_source() -> None:
        nonlocal swapped
        if not swapped:
            source.unlink()
            make_symlink(outside, source)
            swapped = True

    def swapping_read_bytes(path: Path) -> bytes:
        if path == source:
            swap_source()
        return original_read_bytes(path)

    def swapping_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if Path(path) == source:
            swap_source()
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(Path, "read_bytes", swapping_read_bytes)
    monkeypatch.setattr(os, "open", swapping_open)

    item = snapshot_inbox_sources(vault)[0]

    assert swapped is True
    assert item.issue is not None
    assert item.issue.code == "unreadable-source"
    assert item.raw is None
    assert item.sha256 is None
    assert item.text is None
    assert item.frontmatter is None
    assert source.is_symlink()
    assert outside.read_bytes() == secret


def test_snapshot_rejects_fifo_without_opening_it(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation unavailable")
    vault = make_vault(tmp_path)
    fifo = vault / "00-Inbox" / "pipe.md"
    try:
        os.mkfifo(fifo)
    except OSError as exc:
        pytest.skip(f"FIFO creation unavailable: {exc}")

    item = snapshot_inbox_sources(vault)[0]

    assert item.issue is not None
    assert item.issue.code == "non-regular-source"
    assert item.raw is None
    assert item.sha256 is None
    assert item.text is None
    assert item.frontmatter is None


def test_snapshot_blocks_unreadable_source_without_changing_bytes(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    note = vault / "00-Inbox" / "private.md"
    payload = b"private\n"
    note.write_bytes(payload)
    note.chmod(0)
    try:
        try:
            note.read_bytes()
        except PermissionError:
            pass
        else:
            pytest.skip("filesystem does not enforce unreadable file permissions")

        item = snapshot_inbox_sources(vault)[0]

        assert item.issue is not None
        assert item.issue.code == "unreadable-source"
        assert item.raw is None
        assert item.sha256 is None
        assert item.text is None
        assert item.frontmatter is None
    finally:
        note.chmod(0o600)
    assert note.read_bytes() == payload


def test_snapshot_returns_stable_issue_for_inbox_path_escape(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = vault / "external-inbox"
    make_symlink(outside, alias)

    items = snapshot_inbox_sources(vault, "external-inbox")

    assert len(items) == 1
    assert items[0].source == Path("external-inbox")
    assert items[0].issue is not None
    assert items[0].issue.code == "unsafe-inbox-path"
    assert items[0].raw is None


def test_snapshot_returns_stable_issue_when_inbox_cannot_be_scanned(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)

    items = snapshot_inbox_sources(vault, "missing-inbox")

    assert len(items) == 1
    assert items[0].source == Path("missing-inbox")
    assert items[0].issue is not None
    assert items[0].issue.code == "unreadable-inbox"
    assert items[0].raw is None


@pytest.mark.parametrize(
    ("original", "updates", "unchanged_slices"),
    [
        (
            b"# Body\nexact  \n",
            {"date": "2042-03-04", "type": "insight-note", "tags": ("insight",)},
            (b"# Body\nexact  \n",),
        ),
        (
            b"---\ntitle: Keep\n---\n# Body\nexact  \n",
            {"date": "2042-03-04", "type": "insight-note", "tags": ("insight",)},
            (b"title: Keep\n", b"# Body\nexact  \n"),
        ),
        (
            b"---\ndate: 2040-01-02\ntype: insight-note\n---\nbody",
            {"tags": ("insight",)},
            (b"date: 2040-01-02\ntype: insight-note\n", b"body"),
        ),
        (
            b"---\ntype: insight-note\ntags: insight\n---\nbody\n",
            {"date": "2042-03-04"},
            (b"type: insight-note\ntags: insight\n", b"body\n"),
        ),
        (
            b"---\ntype: insight-note\ntags: [insight, python]\n---\nbody\n",
            {"date": "2042-03-04"},
            (b"type: insight-note\ntags: [insight, python]\n", b"body\n"),
        ),
    ],
)
def test_render_inserts_only_missing_keys_without_rewriting_source_slices(
    tmp_path: Path,
    original: bytes,
    updates: dict[str, object],
    unchanged_slices: tuple[bytes, ...],
) -> None:
    _vault, note, snapshot = snapshot_one(tmp_path, original)

    rendered = render_frontmatter_updates(snapshot, updates)

    assert rendered != original
    for unchanged in unchanged_slices:
        assert unchanged in rendered
    assert parse_frontmatter(rendered.decode("utf-8-sig")).issue is None
    assert note.read_bytes() == original


def test_render_preserves_bom_crlf_comments_quotes_and_body_bytes(
    tmp_path: Path,
) -> None:
    original = (
        b"\xef\xbb\xbf---\r\n"
        b'title: "Keep quoting" # keep comment\r\n'
        b"type: insight-note\r\n"
        b"---\r\n# Body\r\nexact  \r\n"
    )
    _vault, note, snapshot = snapshot_one(tmp_path, original)

    rendered = render_frontmatter_updates(
        snapshot,
        {"date": "2042-03-04", "type": "ignored", "tags": ("insight",)},
    )

    assert rendered.startswith(b"\xef\xbb\xbf---\r\n")
    assert b'title: "Keep quoting" # keep comment\r\n' in rendered
    assert rendered.count(b"type:") == 1
    assert b"type: insight-note\r\n" in rendered
    assert b"date: '2042-03-04'\r\n" in rendered
    assert b"tags:\r\n  - insight\r\n" in rendered
    assert rendered.endswith(b"# Body\r\nexact  \r\n")
    assert b"\n" not in rendered.replace(b"\r\n", b"")
    assert parse_frontmatter(rendered.decode("utf-8-sig")).issue is None
    assert note.read_bytes() == original


def test_render_without_frontmatter_preserves_bom_and_crlf_body(tmp_path: Path) -> None:
    original = b"\xef\xbb\xbf# Body\r\nexact  \r\n"
    _vault, _note, snapshot = snapshot_one(tmp_path, original)

    rendered = render_frontmatter_updates(
        snapshot,
        {"date": "2042-03-04", "type": "insight-note", "tags": ("insight",)},
    )

    assert rendered.startswith(b"\xef\xbb\xbf---\r\n")
    assert rendered.endswith(b"# Body\r\nexact  \r\n")
    assert rendered.count(b"\xef\xbb\xbf") == 1
    assert parse_frontmatter(rendered.decode("utf-8-sig")).issue is None


@pytest.mark.parametrize(
    ("key", "yaml_value"),
    [
        ("date", "null"),
        ("date", "''"),
        ("type", "null"),
        ("type", "''"),
        ("tags", "null"),
        ("tags", "[]"),
    ],
)
def test_plan_blocks_ambiguous_empty_existing_metadata(
    tmp_path: Path, key: str, yaml_value: str
) -> None:
    vault = make_vault(tmp_path)
    (vault / "30-Insights").mkdir()
    (vault / "00-Inbox" / "Note.md").write_text(
        f"---\n{key}: {yaml_value}\n---\n# Insight\nidea\n", encoding="utf-8"
    )

    item = plan_inbox(vault, effective_date="2042-03-04").items[0]

    assert item.status == "blocked"
    assert item.issue is not None
    assert item.issue.code == "ambiguous-empty-metadata"
    assert item.proposal is None


def test_plan_builds_frozen_ready_proposal_without_writing(tmp_path: Path) -> None:
    original = (
        b"---\n"
        b'title: "Keep" # comment\n'
        b"tags: [existing, python]\n"
        b"---\n"
        b"# Planned Insight\nidea body  \n"
    )
    vault, note, snapshot = snapshot_one(tmp_path, original, "2040-Old.md")
    (vault / "30-Insights").mkdir()

    plan = plan_inbox(vault, effective_date="2042-03-04")

    assert plan.effective_date == "2042-03-04"
    assert len(plan.items) == 1
    item = plan.items[0]
    assert isinstance(item, InboxPlanItem)
    assert item.source == Path("00-Inbox/2040-Old.md")
    assert item.identity == snapshot.identity
    assert item.source_sha256 == sha256_bytes(original)
    assert item.title == "Planned Insight"
    assert item.status == "ready"
    assert item.issue is None
    assert item.proposal is not None
    assert item.proposal.destination == Path("30-Insights/2040-Old.md")
    assert item.proposal.target == "30-Insights"
    assert item.proposal.note_type == "insight-note"
    assert item.proposal.tags == ("existing", "python")
    assert item.proposal.metadata_updates == (
        ("date", "2042-03-04"),
        ("type", "insight-note"),
    )
    assert item.proposal.rendered_sha256 == sha256_bytes(
        item.proposal.rendered_bytes
    )
    assert item.proposal.rendered_bytes.endswith(b"# Planned Insight\nidea body  \n")
    assert item.proposal.index is None
    assert note.read_bytes() == original
    assert not (vault / item.proposal.destination).exists()


def test_plan_preserves_existing_scalar_tags_and_type(tmp_path: Path) -> None:
    original = (
        b"---\n"
        b"date: 2040-01-02\n"
        b"type: web-clip\n"
        b"tags: web-clip\n"
        b"---\n# Clip\n"
    )
    vault, _note, _snapshot = snapshot_one(tmp_path, original)
    (vault / "20-Learning").mkdir()

    item = plan_inbox(vault, effective_date="2042-03-04").items[0]

    assert item.status == "ready"
    assert item.proposal is not None
    assert item.proposal.target == "20-Learning"
    assert item.proposal.note_type == "web-clip"
    assert item.proposal.tags == ("web-clip",)
    assert item.proposal.metadata_updates == ()
    assert item.proposal.rendered_bytes == original


def test_plan_statuses_propagate_snapshot_issue_and_unknown_route(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    (vault / "00-Inbox" / "bad.md").write_bytes(b"---\na: [\n---\nbody\n")
    (vault / "00-Inbox" / "unknown.md").write_text(
        "# Unclassified\nplain capture\n", encoding="utf-8"
    )

    items = plan_inbox(vault, effective_date="2042-03-04").items

    assert [item.status for item in items] == ["blocked", "skipped"]
    assert items[0].issue is not None
    assert items[0].issue.code == "invalid-frontmatter"
    assert items[0].source_sha256 == sha256_bytes(b"---\na: [\n---\nbody\n")
    assert items[1].title == "Unclassified"
    assert items[1].issue is not None
    assert items[1].issue.code == "no-target"
    assert all(item.proposal is None for item in items)


def test_plan_existing_and_dangling_destinations_never_become_ready(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    target = vault / "30-Insights"
    target.mkdir()
    existing = target / "existing.md"
    existing.write_bytes(b"existing\n")
    (vault / "00-Inbox" / "existing.md").write_text("# Insight\nidea\n")
    outside = tmp_path / "missing.md"
    dangling = target / "dangling.md"
    make_symlink(outside, dangling)
    (vault / "00-Inbox" / "dangling.md").write_text("# Insight\nidea\n")

    items = plan_inbox(vault, effective_date="2042-03-04").items

    assert [item.status for item in items] == ["skipped", "skipped"]
    assert all(item.issue is not None for item in items)
    assert all(item.issue.code == "destination-exists" for item in items if item.issue)
    assert all(item.proposal is None for item in items)
    assert existing.read_bytes() == b"existing\n"
    assert dangling.is_symlink()


def test_plan_blocks_target_symlink_escape(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    make_symlink(outside, vault / "30-Insights")
    (vault / "00-Inbox" / "Note.md").write_text("# Insight\nidea\n")

    item = plan_inbox(vault, effective_date="2042-03-04").items[0]

    assert item.status == "blocked"
    assert item.issue is not None
    assert item.issue.code == "unsafe-destination-path"
    assert item.proposal is None
    assert not list(outside.iterdir())


def test_plan_changes_proposal_and_hashes_for_inputs(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    (vault / "20-Learning").mkdir()
    (vault / "30-Insights").mkdir()
    note = vault / "00-Inbox" / "Note.md"
    note.write_text("# Insight\nidea\n", encoding="utf-8")
    first = plan_inbox(vault, effective_date="2042-03-04").items[0]
    second_date = plan_inbox(vault, effective_date="2042-03-05").items[0]
    note.write_text("# Learning\narticle\n", encoding="utf-8")
    second_route = plan_inbox(vault, effective_date="2042-03-04").items[0]

    assert first.proposal is not None
    assert second_date.proposal is not None
    assert second_route.proposal is not None
    assert first.source_sha256 != second_route.source_sha256
    assert first.proposal.rendered_sha256 != second_date.proposal.rendered_sha256
    assert first.proposal != second_date.proposal
    assert first.proposal.target != second_route.proposal.target
    assert first.proposal.destination != second_route.proposal.destination
    assert first.proposal.rendered_sha256 != second_route.proposal.rendered_sha256


def test_legacy_plan_dict_retains_current_ready_and_skip_meanings(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    target = vault / "30-Insights"
    target.mkdir()
    (target / "INDEX.md").write_text("# Index\n", encoding="utf-8")
    (vault / "00-Inbox" / "ready.md").write_text(
        "# Ready Insight\nidea\n", encoding="utf-8"
    )
    (vault / "00-Inbox" / "skip.md").write_text(
        "# Skip\nplain capture\n", encoding="utf-8"
    )

    ready, skipped = plan_inbox(vault, effective_date="2042-03-04").items
    ready_dict = legacy_plan_dict(vault, ready)
    skipped_dict = legacy_plan_dict(vault, skipped)

    assert ready_dict == {
        "path": vault / "00-Inbox" / "ready.md",
        "target": "30-Insights",
        "title": "Ready Insight",
        "tags": ["insight"],
        "type": "insight-note",
        "related_suggestion": "INDEX",
    }
    assert skipped_dict["path"] == vault / "00-Inbox" / "skip.md"
    assert skipped_dict["target"] is None
    assert skipped_dict["title"] == "Skip"
    assert skipped_dict["skip"] == "could not infer a target folder"


@pytest.mark.parametrize(
    ("frontmatter", "duplicate_line", "duplicate_column"),
    [
        (
            "type: web-clip\ntype: insight-note\ntags: [insight]\n",
            3,
            1,
        ),
        (
            "type: insight-note\ntags: [one]\ntags: [two]\n",
            4,
            1,
        ),
        (
            "extra:\n  nested: one\n  nested: two\n",
            4,
            3,
        ),
    ],
)
def test_plan_blocks_duplicate_frontmatter_keys_at_any_mapping_depth(
    tmp_path: Path,
    frontmatter: str,
    duplicate_line: int,
    duplicate_column: int,
) -> None:
    vault = make_vault(tmp_path)
    (vault / "30-Insights").mkdir()
    (vault / "00-Inbox" / "duplicate.md").write_text(
        f"---\n{frontmatter}---\n# Insight\nidea\n", encoding="utf-8"
    )

    item = plan_inbox(vault, effective_date="2042-03-04").items[0]

    assert item.status == "blocked"
    assert item.proposal is None
    assert item.issue is not None
    assert item.issue.code == "duplicate-frontmatter-key"
    assert item.issue.line == duplicate_line
    assert item.issue.column == duplicate_column


def test_plan_blocks_target_replaced_with_file_between_resolver_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = make_vault(tmp_path)
    target = vault / "30-Insights"
    target.mkdir()
    (vault / "00-Inbox" / "Note.md").write_text(
        "# Insight\nidea\n", encoding="utf-8"
    )
    original_resolver = inbox_plan.resolve_target_within_vault
    resolver_calls = 0

    def replace_target_before_destination_resolution(
        resolver_vault: Path,
        user_path: str | Path,
        *,
        label: str = "path",
    ) -> Path:
        nonlocal resolver_calls
        resolver_calls += 1
        if label == "Inbox destination":
            target.rmdir()
            target.write_bytes(b"ordinary file\n")
        return original_resolver(resolver_vault, user_path, label=label)

    monkeypatch.setattr(
        inbox_plan,
        "resolve_target_within_vault",
        replace_target_before_destination_resolution,
    )

    item = plan_inbox(vault, effective_date="2042-03-04").items[0]

    assert resolver_calls >= 4
    assert item.status == "blocked"
    assert item.proposal is None
    assert item.issue is not None
    assert item.issue.code == "unsafe-destination-path"
    assert target.read_bytes() == b"ordinary file\n"


@pytest.mark.parametrize(
    "invalid_raw",
    [
        b"\xff",
        b"---\nnull\n---\n",
    ],
)
def test_render_revalidates_raw_candidate_when_no_updates_are_missing(
    tmp_path: Path, invalid_raw: bytes
) -> None:
    original = (
        b"---\n"
        b"date: 2040-01-02\n"
        b"type: insight-note\n"
        b"tags: [insight]\n"
        b"---\n# Insight\n"
    )
    _vault, _note, snapshot = snapshot_one(tmp_path, original)
    forged = replace(snapshot, raw=invalid_raw)

    with pytest.raises(ValueError):
        render_frontmatter_updates(
            forged,
            {
                "date": "2042-03-04",
                "type": "insight-note",
                "tags": ("insight",),
            },
        )
