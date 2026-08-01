# Task 1 Report: Strict Inbox Source Snapshots

Status: DONE

Commit: `4049ccf0afa815f6f8b56ca0f330f30054da2226`

## RED

Command:

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Expected and actual failure: pytest collection failed with
`ModuleNotFoundError: No module named 'obsidian_kb_skill.scripts.inbox_plan'`.
This was the required missing-production-module RED.

A second RED cycle covered stable Inbox-boundary errors. With the first GREEN
implementation present, the same focused command reported 12 passes and 2
failures: an external Inbox symlink leaked `PathOutsideVaultError`, and a
missing Inbox leaked `FileNotFoundError`. The subsequent minimal change converted
both into immutable blocked snapshots.

## GREEN and Regression

Focused command:

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Actual result after the final implementation: 14 passed, exit 0.

Required regression command:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_frontmatter.py tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py -q
```

Actual fresh result immediately before commit: 58 passed, exit 0. The run had
no skips, warnings, errors, or failures. `git diff --check` also exited 0.

## Self-review

- The commit contains exactly the two tracked files allowed by the brief.
- All public dataclasses use `@dataclass(frozen=True)` with the exact requested
  fields, and `sha256_bytes()` uses the exact requested representation.
- Discovery resolves the Inbox through the shared Vault resolver once, uses
  `os.scandir()`, sorts by filename, imposes no item limit, and filters to `.md`.
- Each entry is inspected with `entry.stat(follow_symlinks=False)`; symlinks and
  non-regular entries are rejected before any open/read operation.
- Regular sources are read with `read_bytes()`, hashed from the exact raw bytes,
  strictly decoded as UTF-8, and parsed through the shared frontmatter parser.
- Shared frontmatter issue code, message, line, and column are preserved in the
  snapshot issue. Expected `OSError`, `UnicodeDecodeError`, and `VaultPathError`
  cases become stable blocked snapshots. No `BaseException` catch exists.
- Tests cover malformed, unclosed, null/list/scalar frontmatter, invalid UTF-8,
  FIFO, internal/external symlinks, unreadable files, deterministic order,
  eleven-item discovery, exact hashes/identity, BOM parsing, and byte stability.
- The module has no mutation, routing, transaction, rendering, or CLI API.

## Concerns

None.

---

## Review Fix: Bind Reads to a Verified File Descriptor

Status: DONE

Commit: `36e09a8a8f37f40bf8d1f04fc67e5a8b10a4e4d0`

### Root Cause

`entry.stat(follow_symlinks=False)` validated the directory entry at one path
resolution point, but `Path(entry.path).read_bytes()` opened the same pathname
again later. A source replaced with an external symlink between those operations
was therefore followed by the second open, allowing outside bytes into the
snapshot.

### RED

Command:

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Actual result: 1 failed, 14 passed. The new
`test_snapshot_rejects_source_swapped_to_symlink_after_stat` deterministically
swapped the source after the preflight stat; the failure showed `item.issue` was
`None` and `item.raw`/parsed body contained `outside secret`.

### GREEN and Regression

Focused command:

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Actual final result: 15 passed, exit 0.

Required regression command:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_frontmatter.py tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py -q
```

Actual final result: 59 passed, exit 0. `git diff --check` exited 0.

### Self-review

- The fix is limited to `inbox_plan.py` and its existing focused test file.
- Opening now uses `os.open`; `O_NOFOLLOW`, `O_CLOEXEC`, and `O_BINARY` are
  included when the host exposes them.
- `os.fstat(fd)` runs before any read. The opened object must be regular and its
  device/inode must match the no-follow preflight identity.
- Bytes are read only through a binary stream wrapping that same verified fd;
  no second pathname-based read remains.
- Open/fstat failures and identity/type mismatches return a stable
  `unreadable-source` snapshot with `raw=None`.
- The fd is closed on mismatch, open/fstat/fdopen failure, read failure, and
  successful read paths. No `BaseException` catch was introduced.
- The regression test exercises both the prior `Path.read_bytes()` path and the
  fixed `os.open()` path so the swap occurs after preflight in either version;
  it asserts that no outside bytes are returned.

### Concerns

None.
