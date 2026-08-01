# Review package: 55cf100..36e09a8

## Commits
36e09a8 fix: bind inbox reads to verified file descriptors
4049ccf fix: fail closed on unsafe inbox sources

## Files changed
 obsidian_kb_skill/scripts/inbox_plan.py | 225 ++++++++++++++++++++++++++
 tests/test_inbox_plan.py                | 273 ++++++++++++++++++++++++++++++++
 2 files changed, 498 insertions(+)

## Diff
diff --git a/obsidian_kb_skill/scripts/inbox_plan.py b/obsidian_kb_skill/scripts/inbox_plan.py
new file mode 100644
index 0000000..228ae9d
--- /dev/null
+++ b/obsidian_kb_skill/scripts/inbox_plan.py
@@ -0,0 +1,225 @@
+"""Read-only, immutable snapshots of Inbox source notes."""
+from __future__ import annotations
+
+import hashlib
+import os
+import stat
+from dataclasses import dataclass
+from pathlib import Path
+
+from obsidian_kb_skill.scripts.frontmatter import FrontmatterResult, parse_frontmatter
+from obsidian_kb_skill.scripts.vault_paths import (
+    VaultPathError,
+    resolve_target_within_vault,
+    validate_vault_root,
+)
+
+
+@dataclass(frozen=True)
+class InboxIssue:
+    code: str
+    message: str
+    line: int | None = None
+    column: int | None = None
+
+
+@dataclass(frozen=True)
+class SourceIdentity:
+    device: int
+    inode: int
+    size: int
+    mtime_ns: int
+
+
+@dataclass(frozen=True)
+class InboxSourceSnapshot:
+    source: Path
+    identity: SourceIdentity | None
+    raw: bytes | None
+    sha256: str | None
+    text: str | None
+    frontmatter: FrontmatterResult | None
+    issue: InboxIssue | None
+
+
+def sha256_bytes(payload: bytes) -> str:
+    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
+
+
+def _source_identity(result: os.stat_result) -> SourceIdentity:
+    return SourceIdentity(
+        device=result.st_dev,
+        inode=result.st_ino,
+        size=result.st_size,
+        mtime_ns=result.st_mtime_ns,
+    )
+
+
+def _blocked_snapshot(
+    source: Path,
+    code: str,
+    message: str,
+    *,
+    identity: SourceIdentity | None = None,
+    raw: bytes | None = None,
+    sha256: str | None = None,
+    text: str | None = None,
+    frontmatter: FrontmatterResult | None = None,
+    line: int | None = None,
+    column: int | None = None,
+) -> InboxSourceSnapshot:
+    return InboxSourceSnapshot(
+        source=source,
+        identity=identity,
+        raw=raw,
+        sha256=sha256,
+        text=text,
+        frontmatter=frontmatter,
+        issue=InboxIssue(code, message, line=line, column=column),
+    )
+
+
+def _snapshot_entry(
+    entry: os.DirEntry[str], source: Path
+) -> InboxSourceSnapshot:
+    try:
+        status = entry.stat(follow_symlinks=False)
+    except OSError:
+        return _blocked_snapshot(
+            source,
+            "unreadable-source",
+            "source metadata could not be read",
+        )
+
+    identity = _source_identity(status)
+    if stat.S_ISLNK(status.st_mode):
+        return _blocked_snapshot(
+            source,
+            "symlink-source",
+            "source is a symbolic link",
+            identity=identity,
+        )
+    if not stat.S_ISREG(status.st_mode):
+        return _blocked_snapshot(
+            source,
+            "non-regular-source",
+            "source is not a regular file",
+            identity=identity,
+        )
+
+    flags = os.O_RDONLY
+    flags |= getattr(os, "O_NOFOLLOW", 0)
+    flags |= getattr(os, "O_CLOEXEC", 0)
+    flags |= getattr(os, "O_BINARY", 0)
+    fd: int | None = None
+    try:
+        fd = os.open(entry.path, flags)
+        opened_status = os.fstat(fd)
+        opened_identity = _source_identity(opened_status)
+        if (
+            not stat.S_ISREG(opened_status.st_mode)
+            or opened_identity.device != identity.device
+            or opened_identity.inode != identity.inode
+        ):
+            return _blocked_snapshot(
+                source,
+                "unreadable-source",
+                "source changed before it could be read",
+                identity=identity,
+            )
+
+        stream = os.fdopen(fd, "rb", closefd=True)
+        fd = None
+        with stream:
+            raw = stream.read()
+    except OSError:
+        return _blocked_snapshot(
+            source,
+            "unreadable-source",
+            "source bytes could not be read",
+            identity=identity,
+        )
+    finally:
+        if fd is not None:
+            try:
+                os.close(fd)
+            except OSError:
+                pass
+
+    digest = sha256_bytes(raw)
+    try:
+        text = raw.decode("utf-8")
+    except UnicodeDecodeError:
+        return _blocked_snapshot(
+            source,
+            "invalid-utf8",
+            "source is not valid UTF-8",
+            identity=identity,
+            raw=raw,
+            sha256=digest,
+        )
+
+    frontmatter = parse_frontmatter(text, source=source.as_posix())
+    if frontmatter.issue is not None:
+        issue = frontmatter.issue
+        return _blocked_snapshot(
+            source,
+            issue.code,
+            issue.message,
+            identity=identity,
+            raw=raw,
+            sha256=digest,
+            text=text,
+            frontmatter=frontmatter,
+            line=issue.line,
+            column=issue.column,
+        )
+
+    return InboxSourceSnapshot(
+        source=source,
+        identity=identity,
+        raw=raw,
+        sha256=digest,
+        text=text,
+        frontmatter=frontmatter,
+        issue=None,
+    )
+
+
+def snapshot_inbox_sources(
+    vault: Path, inbox_name: str = "00-Inbox"
+) -> tuple[InboxSourceSnapshot, ...]:
+    """Snapshot every Markdown source without following or modifying entries."""
+    requested_inbox = Path(inbox_name)
+    try:
+        root = validate_vault_root(vault)
+        inbox = resolve_target_within_vault(root, inbox_name, label="Inbox")
+    except VaultPathError:
+        return (
+            _blocked_snapshot(
+                requested_inbox,
+                "unsafe-inbox-path",
+                "Inbox path could not be resolved safely",
+            ),
+        )
+
+    try:
+        with os.scandir(inbox) as entries:
+            markdown_entries = sorted(
+                (entry for entry in entries if entry.name.endswith(".md")),
+                key=lambda entry: entry.name,
+            )
+    except OSError:
+        return (
+            _blocked_snapshot(
+                requested_inbox,
+                "unreadable-inbox",
+                "Inbox directory could not be scanned",
+            ),
+        )
+
+    source_root = inbox.relative_to(root)
+    return tuple(
+        _snapshot_entry(entry, source_root / entry.name)
+        for entry in markdown_entries
+    )
diff --git a/tests/test_inbox_plan.py b/tests/test_inbox_plan.py
new file mode 100644
index 0000000..98fff2a
--- /dev/null
+++ b/tests/test_inbox_plan.py
@@ -0,0 +1,273 @@
+from __future__ import annotations
+
+import os
+from pathlib import Path
+
+import pytest
+
+from obsidian_kb_skill.scripts.inbox_plan import (
+    sha256_bytes,
+    snapshot_inbox_sources,
+)
+
+
+def make_vault(tmp_path: Path) -> Path:
+    vault = tmp_path / "vault"
+    vault.mkdir()
+    (vault / ".obsidian").mkdir()
+    (vault / "00-Inbox").mkdir()
+    return vault
+
+
+def make_symlink(target: Path, link: Path) -> None:
+    try:
+        link.symlink_to(target)
+    except (OSError, NotImplementedError) as exc:
+        pytest.skip(f"symlink creation unavailable: {exc}")
+
+
+@pytest.mark.parametrize(
+    ("payload", "code"),
+    [
+        (b"---\na: [\n---\nbody\n", "invalid-frontmatter"),
+        (b"---\na: 1\nbody\n", "unclosed-frontmatter"),
+        (b"---\nnull\n---\nbody\n", "frontmatter-not-mapping"),
+        (b"---\n- one\n---\nbody\n", "frontmatter-not-mapping"),
+        (b"---\nscalar\n---\nbody\n", "frontmatter-not-mapping"),
+    ],
+)
+def test_snapshot_blocks_frontmatter_issue_without_changing_bytes(
+    tmp_path: Path, payload: bytes, code: str
+) -> None:
+    vault = make_vault(tmp_path)
+    note = vault / "00-Inbox" / "bad.md"
+    note.write_bytes(payload)
+
+    item = snapshot_inbox_sources(vault)[0]
+
+    assert item.issue is not None
+    assert item.issue.code == code
+    assert item.raw == payload
+    assert item.sha256 == sha256_bytes(payload)
+    assert item.text == payload.decode("utf-8")
+    assert item.frontmatter is not None
+    assert item.issue.line == item.frontmatter.issue.line
+    assert item.issue.column == item.frontmatter.issue.column
+    assert note.read_bytes() == payload
+
+
+def test_snapshot_valid_source_freezes_identity_bytes_hash_and_parse(
+    tmp_path: Path,
+) -> None:
+    vault = make_vault(tmp_path)
+    note = vault / "00-Inbox" / "good.md"
+    payload = b"\xef\xbb\xbf---\r\ntype: note\r\n---\r\nbody\r\n"
+    note.write_bytes(payload)
+    before = note.stat()
+
+    item = snapshot_inbox_sources(vault)[0]
+
+    assert item.source == Path("00-Inbox/good.md")
+    assert item.identity is not None
+    assert item.identity.device == before.st_dev
+    assert item.identity.inode == before.st_ino
+    assert item.identity.size == before.st_size
+    assert item.identity.mtime_ns == before.st_mtime_ns
+    assert item.raw == payload
+    assert item.sha256 == sha256_bytes(payload)
+    assert item.text == payload.decode("utf-8")
+    assert item.frontmatter is not None
+    assert item.frontmatter.issue is None
+    assert item.frontmatter.metadata == {"type": "note"}
+    assert item.issue is None
+    assert note.read_bytes() == payload
+
+
+def test_snapshot_sorts_by_filename_and_has_no_item_limit(tmp_path: Path) -> None:
+    vault = make_vault(tmp_path)
+    inbox = vault / "00-Inbox"
+    names = [f"note-{number:02d}.md" for number in range(10, -1, -1)]
+    for name in names:
+        (inbox / name).write_bytes(name.encode("utf-8"))
+    (inbox / "ignored.txt").write_bytes(b"ignored")
+
+    items = snapshot_inbox_sources(vault)
+
+    assert [item.source.name for item in items] == sorted(names)
+    assert len(items) == 11
+
+
+def test_snapshot_blocks_invalid_utf8_without_changing_bytes(tmp_path: Path) -> None:
+    vault = make_vault(tmp_path)
+    note = vault / "00-Inbox" / "bad.md"
+    payload = b"front\xffmatter"
+    note.write_bytes(payload)
+
+    item = snapshot_inbox_sources(vault)[0]
+
+    assert item.issue is not None
+    assert item.issue.code == "invalid-utf8"
+    assert item.raw == payload
+    assert item.sha256 == sha256_bytes(payload)
+    assert item.text is None
+    assert item.frontmatter is None
+    assert note.read_bytes() == payload
+
+
+@pytest.mark.parametrize("target_location", ["internal", "external"])
+def test_snapshot_rejects_symlink_without_reading_target(
+    tmp_path: Path, target_location: str
+) -> None:
+    vault = make_vault(tmp_path)
+    inbox = vault / "00-Inbox"
+    if target_location == "internal":
+        target = inbox / "target.txt"
+    else:
+        target = tmp_path / "outside.md"
+    payload = b"secret source bytes\n"
+    target.write_bytes(payload)
+    link = inbox / "linked.md"
+    make_symlink(target, link)
+    before = target.read_bytes()
+
+    item = snapshot_inbox_sources(vault)[0]
+
+    assert item.source == Path("00-Inbox/linked.md")
+    assert item.issue is not None
+    assert item.issue.code == "symlink-source"
+    assert item.raw is None
+    assert item.sha256 is None
+    assert item.text is None
+    assert item.frontmatter is None
+    assert target.read_bytes() == before
+
+
+def test_snapshot_rejects_source_swapped_to_symlink_after_stat(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = make_vault(tmp_path)
+    source = vault / "00-Inbox" / "swapped.md"
+    source.write_bytes(b"safe source\n")
+    outside = tmp_path / "outside-secret.md"
+    secret = b"outside secret\n"
+    outside.write_bytes(secret)
+    original_read_bytes = Path.read_bytes
+    original_open = os.open
+    swapped = False
+
+    def swap_source() -> None:
+        nonlocal swapped
+        if not swapped:
+            source.unlink()
+            make_symlink(outside, source)
+            swapped = True
+
+    def swapping_read_bytes(path: Path) -> bytes:
+        if path == source:
+            swap_source()
+        return original_read_bytes(path)
+
+    def swapping_open(
+        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
+        flags: int,
+        mode: int = 0o777,
+        *,
+        dir_fd: int | None = None,
+    ) -> int:
+        if Path(path) == source:
+            swap_source()
+        return original_open(path, flags, mode, dir_fd=dir_fd)
+
+    monkeypatch.setattr(Path, "read_bytes", swapping_read_bytes)
+    monkeypatch.setattr(os, "open", swapping_open)
+
+    item = snapshot_inbox_sources(vault)[0]
+
+    assert swapped is True
+    assert item.issue is not None
+    assert item.issue.code == "unreadable-source"
+    assert item.raw is None
+    assert item.sha256 is None
+    assert item.text is None
+    assert item.frontmatter is None
+    assert source.is_symlink()
+    assert outside.read_bytes() == secret
+
+
+def test_snapshot_rejects_fifo_without_opening_it(tmp_path: Path) -> None:
+    if not hasattr(os, "mkfifo"):
+        pytest.skip("FIFO creation unavailable")
+    vault = make_vault(tmp_path)
+    fifo = vault / "00-Inbox" / "pipe.md"
+    try:
+        os.mkfifo(fifo)
+    except OSError as exc:
+        pytest.skip(f"FIFO creation unavailable: {exc}")
+
+    item = snapshot_inbox_sources(vault)[0]
+
+    assert item.issue is not None
+    assert item.issue.code == "non-regular-source"
+    assert item.raw is None
+    assert item.sha256 is None
+    assert item.text is None
+    assert item.frontmatter is None
+
+
+def test_snapshot_blocks_unreadable_source_without_changing_bytes(
+    tmp_path: Path,
+) -> None:
+    vault = make_vault(tmp_path)
+    note = vault / "00-Inbox" / "private.md"
+    payload = b"private\n"
+    note.write_bytes(payload)
+    note.chmod(0)
+    try:
+        try:
+            note.read_bytes()
+        except PermissionError:
+            pass
+        else:
+            pytest.skip("filesystem does not enforce unreadable file permissions")
+
+        item = snapshot_inbox_sources(vault)[0]
+
+        assert item.issue is not None
+        assert item.issue.code == "unreadable-source"
+        assert item.raw is None
+        assert item.sha256 is None
+        assert item.text is None
+        assert item.frontmatter is None
+    finally:
+        note.chmod(0o600)
+    assert note.read_bytes() == payload
+
+
+def test_snapshot_returns_stable_issue_for_inbox_path_escape(tmp_path: Path) -> None:
+    vault = make_vault(tmp_path)
+    outside = tmp_path / "outside"
+    outside.mkdir()
+    alias = vault / "external-inbox"
+    make_symlink(outside, alias)
+
+    items = snapshot_inbox_sources(vault, "external-inbox")
+
+    assert len(items) == 1
+    assert items[0].source == Path("external-inbox")
+    assert items[0].issue is not None
+    assert items[0].issue.code == "unsafe-inbox-path"
+    assert items[0].raw is None
+
+
+def test_snapshot_returns_stable_issue_when_inbox_cannot_be_scanned(
+    tmp_path: Path,
+) -> None:
+    vault = make_vault(tmp_path)
+
+    items = snapshot_inbox_sources(vault, "missing-inbox")
+
+    assert len(items) == 1
+    assert items[0].source == Path("missing-inbox")
+    assert items[0].issue is not None
+    assert items[0].issue.code == "unreadable-inbox"
+    assert items[0].raw is None
