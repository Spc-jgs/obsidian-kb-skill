### Task 1: Strict Inbox Source Snapshots

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_plan.py`
- Create: `tests/test_inbox_plan.py`

**Interfaces:**
- Consumes: `validate_vault_root()`, `resolve_target_within_vault()`,
  `parse_frontmatter()`.
- Produces:

```python
@dataclass(frozen=True)
class InboxIssue:
    code: str
    message: str
    line: int | None = None
    column: int | None = None

@dataclass(frozen=True)
class SourceIdentity:
    device: int
    inode: int
    size: int
    mtime_ns: int

@dataclass(frozen=True)
class InboxSourceSnapshot:
    source: Path
    identity: SourceIdentity | None
    raw: bytes | None
    sha256: str | None
    text: str | None
    frontmatter: FrontmatterResult | None
    issue: InboxIssue | None

def snapshot_inbox_sources(vault: Path, inbox_name: str = "00-Inbox") \
        -> tuple[InboxSourceSnapshot, ...]: ...
```

- [ ] **Step 1: Write failing discovery and parse tests**

Add parametrized tests that create malformed, unclosed, null, list, scalar,
invalid UTF-8, FIFO/non-regular where supported, internal symlink, external
symlink, and unreadable source fixtures. Use byte snapshots before and after.
The core assertion shape is:

```python
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
    assert note.read_bytes() == payload
```

Also assert deterministic filename order and that the function has no item
limit by planning 11 files.

- [ ] **Step 2: Run the new tests and confirm RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Expected: collection fails because `inbox_plan` does not exist.

- [ ] **Step 3: Implement immutable snapshots**

Use `os.scandir()` and `entry.stat(follow_symlinks=False)`. Reject symlinks and
non-regular entries before opening them. Resolve the Inbox once through the
shared resolver. Read every real `.md` with `read_bytes()`, hash raw bytes, then
strictly decode UTF-8 (accepting a UTF-8 BOM through the shared parser). Convert
`FrontmatterResult.issue` without discarding line/column.

Use this exact hash helper so every later task shares one representation:

```python
def sha256_bytes(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
```

Catch expected `OSError`, `UnicodeDecodeError`, and `VaultPathError` at the item
boundary and return a stable issue. Never catch `BaseException`.

- [ ] **Step 4: Run focused and shared-parser/path regressions**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_frontmatter.py tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py -q
```

Expected: all selected tests pass and every rejected source remains byte exact.

- [ ] **Step 5: Commit the strict snapshot boundary**

```bash
git add obsidian_kb_skill/scripts/inbox_plan.py tests/test_inbox_plan.py
git commit -m "fix: fail closed on unsafe inbox sources"
```

---

