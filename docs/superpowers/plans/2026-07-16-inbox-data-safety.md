# Inbox Data Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Inbox note apply fail closed, no-overwrite,
transactional, backed up, automatically reversible when safe, and explicitly
recoverable when exact rollback cannot be proved.

**Architecture:** A pure `inbox_plan.py` freezes raw source bytes, hashes,
mechanical frontmatter additions, destination, and static-index pre/post state.
`inbox_transaction.py` applies one frozen item through an in-Vault backup and
journal, installs destination/index bytes safely, audits, removes the source
last, and owns guarded restore. `process_inbox.py` becomes a compatibility CLI
adapter; it keeps today's discovery/routing UX while returning actual results.

**Tech Stack:** Python 3.10+, stdlib dataclasses/pathlib/hashlib/json/os/tempfile,
PyYAML through the existing shared parser, pytest, uv, existing Vault path,
catalog, audit, backup-policy, and Folder Index modules.

## Global Constraints

- Work only on `fix/inbox-data-safety` in
  `/Users/shaopc/playground/obsidian-kb-skill/.worktrees/inbox-data-safety`.
- Never merge, push, switch, or commit on `master`.
- Follow `docs/superpowers/specs/2026-07-16-inbox-data-safety-design.md`.
- Preserve current Inbox folder name, routing order, inferred type/tag values,
  default read-only behavior, legacy text plan, and top-level JSON plan list.
- Do not add the ten-item limit, reviewed plan artifacts, public plan/item IDs,
  confidence, evidence, `inbox-note`, semantic enrichment, or Skill routing.
- Never read through an Inbox symlink or write through a destination, index,
  backup, lock, or temp path that resolves outside the Vault.
- No existing destination or unknown concurrent bytes may be overwritten.
- Existing valid frontmatter/body bytes, BOM, and LF/CRLF style are preserved;
  only missing `date`, `type`, and `tags` entries may be inserted.
- `date`, `type`, or `tags` present with an empty/ambiguous value blocks apply;
  do not replace it or insert a duplicate key.
- Every business-file mutation occurs after a durable backup manifest and is
  either committed, exactly rolled back, or reported `recovery_required`.
- A test failure injector is passed as a Python protocol; do not expose a CLI or
  environment-variable failure backdoor.
- Keep canonical Python and the generated standard Skill payload synchronized
  through `uv run --locked --extra dev python build.py`.
- Every task follows RED → focused GREEN → relevant regression → commit, and a
  fresh reviewer must approve the task before the next task begins.

---

## File Responsibility Map

- `obsidian_kb_skill/scripts/inbox_plan.py`: immutable Inbox source snapshots,
  issues, proposals and plans; strict discovery; byte-preserving render; hashes;
  legacy-dict conversion. No writes.
- `obsidian_kb_skill/scripts/inbox_transaction.py`: locks, backup store,
  manifest/journal, mutation checkpoints, atomic/exclusive installation,
  rollback, restore, and typed results.
- `obsidian_kb_skill/scripts/folder_index_policy.py`: pure static-index plan in
  addition to the existing append compatibility API.
- `obsidian_kb_skill/scripts/process_inbox.py`: argparse, text/JSON adapters,
  orchestration, exact counts, exit codes, and legacy callable adapters.
- `obsidian_kb_skill/scripts/backup_policy.py`: preserve the owned `inbox/`
  transaction namespace during ordinary backup retention.
- `tests/test_inbox_plan.py`: pure discovery/parse/render/hash contracts.
- `tests/test_inbox_transaction.py`: backup, journal, commit, rollback, restore,
  idempotency, race, and failure-injection contracts.
- Existing Inbox, JSON, CLI, Folder Index, backup, path-safety, build, packaging,
  and runtime tests: compatibility and distribution gates.

---

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

### Task 2: Byte-Preserving Typed Inbox Plans

**Files:**
- Modify: `obsidian_kb_skill/scripts/inbox_plan.py`
- Modify: `tests/test_inbox_plan.py`

**Interfaces:**
- Consumes: `InboxSourceSnapshot` and catalog route mappings. Preserve the
  current H1-or-filename title behavior with an Inbox-local private helper; do
  not create a new cross-module dependency on `audit_vault._note_title()`.
  `StaticIndexPlan` is forward-referenced and remains `None` until Task 3.
- Produces:

```python
InboxStatus = Literal["ready", "skipped", "blocked"]

@dataclass(frozen=True)
class InboxProposal:
    destination: Path
    target: str
    note_type: str
    tags: tuple[str, ...]
    metadata_updates: tuple[tuple[str, object], ...]
    rendered_bytes: bytes
    rendered_sha256: str
    index: StaticIndexPlan | None

@dataclass(frozen=True)
class InboxPlanItem:
    source: Path
    identity: SourceIdentity | None
    source_sha256: str | None
    title: str | None
    status: InboxStatus
    proposal: InboxProposal | None
    issue: InboxIssue | None

@dataclass(frozen=True)
class InboxPlan:
    effective_date: str
    items: tuple[InboxPlanItem, ...]

def render_frontmatter_updates(
    snapshot: InboxSourceSnapshot,
    updates: Mapping[str, object],
) -> bytes: ...

def plan_inbox(
    vault: Path,
    inbox_name: str = "00-Inbox",
    *,
    effective_date: str | None = None,
) -> InboxPlan: ...

def legacy_plan_dict(vault: Path, item: InboxPlanItem) -> dict[str, Any]: ...
```

- [ ] **Step 1: Write rendering and proposal RED tests**

Cover no frontmatter, valid LF, valid CRLF, UTF-8 BOM, comments, quoted values,
missing one or three keys, existing scalar/list tags, and empty/null existing
`date/type/tags`. Assert the original body slice appears byte-for-byte in the
rendered output and no existing frontmatter line changes.

```python
def test_render_inserts_missing_keys_without_rewriting_frontmatter(tmp_path: Path):
    original = (
        b"\xef\xbb\xbf---\r\n"
        b'title: "Keep quoting" # keep comment\r\n'
        b"---\r\n# Body\r\nexact  \r\n"
    )
    item = snapshot_one(tmp_path, original)

    rendered = render_frontmatter_updates(
        item,
        {"date": "2042-03-04", "type": "insight-note", "tags": ["insight"]},
    )

    assert b'title: "Keep quoting" # keep comment\r\n' in rendered
    assert rendered.endswith(b"# Body\r\nexact  \r\n")
    assert parse_frontmatter(rendered.decode("utf-8-sig")).issue is None
```

Assert that changing raw bytes, route, update values, destination, or effective
date changes the relevant hashes/proposal. Assert `legacy_plan_dict()` retains
the existing `path`, `target`, `title`, `tags`, `type`, `related_suggestion`, and
`skip` meanings.

- [ ] **Step 2: Run focused RED tests**

```bash
uv run --locked --extra dev pytest tests/test_inbox_plan.py -q
```

Expected: failures for missing plan/render APIs.

- [ ] **Step 3: Implement the raw-byte renderer and typed planning**

Locate the raw frontmatter delimiter without reserializing existing YAML. Detect
the BOM and newline convention, insert only serialized lines for absent keys,
and reparse the rendered candidate. Use `yaml.safe_dump()` only on each new
value, never on the existing mapping. Reject a multi-line serialization that is
not an indented valid mapping entry.

An existing key with `None`, empty string, or empty list produces
`InboxIssue(code="ambiguous-empty-metadata", ...)`. An absent frontmatter block
may receive all three defaults. Freeze `effective_date` exactly once in
`plan_inbox()`.

Resolve both target directory and destination with shared Vault resolvers;
reject a destination that exists lexically, including a dangling symlink.

- [ ] **Step 4: Run focused and current Inbox regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_process_inbox.py \
  tests/test_cli_integration.py tests/test_json_output.py -q
```

Expected: new typed-plan tests pass and old production behavior remains green
because the CLI has not switched adapters yet.

- [ ] **Step 5: Commit typed planning**

```bash
git add obsidian_kb_skill/scripts/inbox_plan.py tests/test_inbox_plan.py
git commit -m "refactor: model immutable inbox plans"
```

---

### Task 3: Pure Static-Index Plans

**Files:**
- Modify: `obsidian_kb_skill/scripts/folder_index_policy.py`
- Modify: `obsidian_kb_skill/scripts/inbox_plan.py`
- Modify: `tests/test_folder_index_policy.py`
- Modify: `tests/test_inbox_plan.py`

**Interfaces:**
- Consumes: `StaticIndexEntry`, existing Folder Index config and exclusion
  rules, `sha256_bytes()`.
- Produces:

```python
StaticIndexAction = Literal["append", "unchanged", "missing", "unmanaged"]

@dataclass(frozen=True)
class StaticIndexPlan:
    action: StaticIndexAction
    index: Path | None
    before: bytes | None
    after: bytes | None
    before_sha256: str | None
    after_sha256: str | None
    line: str | None

def plan_static_index_entry(
    vault: Path,
    entry: StaticIndexEntry,
) -> StaticIndexPlan: ...
```

- [ ] **Step 1: Write pure-plan RED tests**

Test missing index, Folder Index-managed, Dataview-managed, append, already
present, invalid plugin JSON, malicious plugin filenames, internal folder
symlink, external symlink, BOM/CRLF, and exact before/after bytes.

```python
def test_static_index_plan_is_read_only_and_byte_exact(tmp_path: Path):
    vault = make_vault(tmp_path)
    index = vault / "30-Insights" / "INDEX.md"
    before = b"# Insights\r\n"
    index.write_bytes(before)

    plan = plan_static_index_entry(
        vault,
        StaticIndexEntry(Path("30-Insights/Idea.md"), "Idea", "2042-03-04"),
    )

    assert plan.action == "append"
    assert plan.before == before
    assert plan.after == before + b"- [[30-Insights/Idea|Idea]] (2042-03-04)\r\n"
    assert index.read_bytes() == before
```

- [ ] **Step 2: Run RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py -q
```

Expected: import/API failures for `StaticIndexPlan` and
`plan_static_index_entry()`.

- [ ] **Step 3: Implement the pure policy**

Refactor the current append decision into the pure function. Preserve the
existing `append_static_index_entry()` signature and `StaticIndexResult`; have
it call the pure planner and append only for `action == "append"`.

Read bytes and preserve the existing index newline convention. Escape or reject
titles that would create a multi-line index entry. Treat invalid enabled-plugin
configuration as a policy error for the pure Inbox plan, while keeping existing
consumer compatibility through the current non-strict config API.

Update `plan_inbox()` to attach `StaticIndexPlan` and block the item when index
ownership/path cannot be proved.

- [ ] **Step 4: Run Folder Index consumer regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py \
  tests/test_create_note.py tests/test_create_category.py \
  tests/test_process_inbox.py tests/test_detect_index.py \
  tests/test_audit_vault.py tests/test_vault_info.py -q
```

Expected: all selected tests pass with unchanged existing-consumer outputs.

- [ ] **Step 5: Commit pure index planning**

```bash
git add obsidian_kb_skill/scripts/folder_index_policy.py \
  obsidian_kb_skill/scripts/inbox_plan.py \
  tests/test_folder_index_policy.py tests/test_inbox_plan.py
git commit -m "refactor: plan inbox index updates without writes"
```

---

### Task 4: Backup Store, Manifest, Journal, and Locks

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_transaction.py`
- Create: `tests/test_inbox_transaction.py`
- Modify: `obsidian_kb_skill/scripts/backup_policy.py`
- Modify: `tests/test_backup_policy.py`

**Interfaces:**
- Consumes: ready `InboxPlanItem`, Vault resolvers, `sha256_bytes()`.
- Produces:

```python
ApplyStatus = Literal[
    "applied", "skipped", "blocked", "rolled_back", "recovery_required"
]

class InboxFailureInjector(Protocol):
    def checkpoint(self, name: str) -> None: ...

@dataclass(frozen=True)
class InboxApplyResult:
    source: Path
    destination: Path | None
    status: ApplyStatus
    applied: bool
    restore_id: str | None
    backup: Path | None
    issue: InboxIssue | None
    warnings: tuple[str, ...] = ()
    rollback_actions: tuple[str, ...] = ()

@dataclass(frozen=True)
class PreparedInboxOperation:
    vault: Path
    item: InboxPlanItem
    restore_id: str
    operation_root: Path
    manifest: Mapping[str, Any]
    held_locks: tuple[Path, ...]

def prepare_inbox_operation(
    vault: Path,
    item: InboxPlanItem,
    *,
    injector: InboxFailureInjector | None = None,
) -> PreparedInboxOperation: ...
```

- [ ] **Step 1: Write RED tests for zero-mutation preparation failures**

Create a `FailAt` injector:

```python
class FailAt:
    def __init__(self, checkpoint: str) -> None:
        self.checkpoint_name = checkpoint

    def checkpoint(self, name: str) -> None:
        if name == self.checkpoint_name:
            raise OSError(f"injected:{name}")
```

Parametrize `lock-source`, `lock-index`, `backup-root`, `backup-source-write`,
`backup-source-fsync`, `backup-index-write`, `manifest-write`,
`manifest-fsync`, and `journal-backup-ready`. At every point assert source and
index bytes unchanged, destination absent, Vault outside path empty, and any
created lock released unless it represents a durable recovery record.

Test concurrent preparation of the same source and shared index. Assert the
second operation returns a stable busy/blocked result without stealing the
first lock. Test symlinked backup root and lock root fail closed.

- [ ] **Step 2: Run RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py -q
```

Expected: missing module/API failures.

- [ ] **Step 3: Implement contained durable operation preparation**

Use `.obsidian-kb-backups/inbox/<restore-id>/` with an ASCII UTC timestamp and
random hex suffix. Create the operation directory with `exist_ok=False`. Store
only Vault-relative POSIX paths in `manifest.json`. Write JSON with sorted keys,
UTF-8, and a final newline.

Provide these internal primitives with exact responsibilities:

```python
def _checkpoint(injector: InboxFailureInjector | None, name: str) -> None: ...
def _write_new_durable(path: Path, payload: bytes) -> None: ...
def _append_event(operation: PreparedInboxOperation, phase: str, **data: Any) -> None: ...
def _acquire_lock(vault: Path, key: str, restore_id: str) -> Path: ...
def _release_locks(paths: Iterable[Path]) -> tuple[str, ...]: ...
```

`_write_new_durable()` must use exclusive creation, flush, and `os.fsync()`.
Acquire source and optional index locks in sorted hash-key order. Back up exact
source/index bytes, verify their hashes after reading the backup, persist the
manifest, then append `backup-ready` before returning.

Update backup retention so the exact top-level `inbox` namespace is preserved
silently. It must not hide similarly named ordinary timestamp directories.

- [ ] **Step 4: Run preparation, backup, and path regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_backup_policy.py \
  tests/test_vault_paths.py tests/test_path_safety_e2e.py -q
```

Expected: all pass; no injected preparation failure changes a business file.

- [ ] **Step 5: Commit the recovery store**

```bash
git add obsidian_kb_skill/scripts/inbox_transaction.py \
  obsidian_kb_skill/scripts/backup_policy.py \
  tests/test_inbox_transaction.py tests/test_backup_policy.py
git commit -m "feat: add inbox transaction recovery store"
```

---

### Task 5: Transactional Destination, Index, Audit, and Rollback

**Files:**
- Modify: `obsidian_kb_skill/scripts/inbox_transaction.py`
- Modify: `tests/test_inbox_transaction.py`

**Interfaces:**
- Consumes: `PreparedInboxOperation`, frozen destination/index bytes and hashes,
  `audit_note()`.
- Produces:

```python
def apply_inbox_item(
    vault: Path,
    item: InboxPlanItem,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxApplyResult: ...
```

- [ ] **Step 1: Write commit/rollback RED tests**

Start with one clean apply and assert:

```python
result = apply_inbox_item(vault, ready_item)
assert result.status == "applied"
assert result.applied is True
assert not (vault / ready_item.source).exists()
assert (vault / ready_item.proposal.destination).read_bytes() == (
    ready_item.proposal.rendered_bytes
)
assert load_events(vault, result.restore_id)[-1]["phase"] == "committed"
```

Then inject failures at destination temp create/write/flush/fsync/install,
index precondition/temp write/flush/fsync/replace, disk audit, source unlink,
post-unlink verification, journal append/fsync, destination cleanup, index
restore, and source restore. Assert either the exact original state plus
`rolled_back`, or preserved copies plus `recovery_required`.

Add races for source hash/identity changed, destination appeared, dangling
destination symlink, target parent external symlink, index hash changed, and a
second apply of the same item. Assert no overwrite and no duplicate index line.

- [ ] **Step 2: Run RED**

```bash
uv run --locked --extra dev pytest tests/test_inbox_transaction.py -q
```

Expected: failures because `apply_inbox_item()` does not yet commit.

- [ ] **Step 3: Implement precondition validation and exclusive destination installation**

Re-resolve and re-stat every path after locks. Re-read source bytes and require
identity and hash equality. Reject any lexical destination, including dangling
symlinks.

Write destination bytes to a contained sibling temp file with exclusive
creation and fsync. Prefer `os.link(temp, destination)` for atomic no-overwrite
installation on the same filesystem, then unlink temp. When hard links are not
supported, create an exclusive zero-byte reservation, verify its identity while
the source lock is held, replace only that reservation, and journal the fallback
before replacement. Never call `os.replace()` on an unverified user file.

- [ ] **Step 4: Implement index installation, audit, source removal, and final commit**

For `StaticIndexPlan.action == "append"`, recheck the before hash, write the
after bytes to a sibling temp file, fsync, recheck the before hash, replace, and
verify the after hash. Other actions do not mutate an index.

Verify destination/index hashes, call the existing note audit on the installed
destination, and record findings as warnings. Treat audit exceptions and
structural frontmatter findings as failures. Remove the source only after these
steps. Verify source absence and final hashes before appending `committed`.

- [ ] **Step 5: Implement hash-guarded rollback**

Before source deletion, leave the verified source in place, restore only an
index matching its expected post-hash, and remove only a destination matching
the rendered hash. After source deletion, restore the source first through an
exclusive contained temp/install path, then restore index and remove
destination. Any unknown hash or failed rollback step produces
`recovery_required`; do not keep trying destructive cleanup.

Always retain the backup/journal. Return Vault-relative paths and the exact
restore preview command in the issue details/message.

- [ ] **Step 6: Run transaction and shared-policy regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py tests/test_inbox_plan.py \
  tests/test_folder_index_policy.py tests/test_audit_vault.py \
  tests/test_backup_policy.py tests/test_path_safety_e2e.py -q
```

Expected: every checkpoint has an asserted terminal state; all selected tests
pass.

- [ ] **Step 7: Commit transactional apply**

```bash
git add obsidian_kb_skill/scripts/inbox_transaction.py \
  tests/test_inbox_transaction.py
git commit -m "fix: apply inbox notes transactionally"
```

---

### Task 6: Guarded Restore Preview and Apply

**Files:**
- Modify: `obsidian_kb_skill/scripts/inbox_transaction.py`
- Modify: `tests/test_inbox_transaction.py`

**Interfaces:**
- Consumes: persisted Inbox manifest, backups, events, and hash guards.
- Produces:

```python
RestoreStatus = Literal[
    "ready", "restored", "already_restored", "blocked", "recovery_required"
]

@dataclass(frozen=True)
class InboxRestoreResult:
    restore_id: str
    status: RestoreStatus
    applied: bool
    actions: tuple[str, ...]
    conflicts: tuple[InboxIssue, ...]
    warnings: tuple[str, ...] = ()

def preview_inbox_restore(vault: Path, restore_id: str) -> InboxRestoreResult: ...
def restore_inbox_operation(
    vault: Path,
    restore_id: str,
    *,
    injector: InboxFailureInjector | None = None,
) -> InboxRestoreResult: ...
```

- [ ] **Step 1: Write restore RED tests**

Cover clean preview, clean restore, repeated preview/restore, source already
original, destination edited, index edited, missing/corrupt manifest, missing or
corrupt backup, path traversal in manifest, symlinked operation root, and
failures during source install, index restore, destination removal, and journal
append.

Also construct persisted crash snapshots at `backup-ready`,
`destination-installed`, `index-installed`, and `source-removed`, including a
truncated final JSONL line. Preview/restore must derive safe actions from the
manifest and observed hashes rather than assuming the last journal phase is
complete.

```python
preview = preview_inbox_restore(vault, applied.restore_id)
assert preview.status == "ready"
assert preview.applied is False
assert preview.actions == (
    "restore source 00-Inbox/Idea.md",
    "restore index 30-Insights/INDEX.md",
    "remove destination 30-Insights/Idea.md",
)

restored = restore_inbox_operation(vault, applied.restore_id)
assert restored.status == "restored"
assert restored.applied is True
```

- [ ] **Step 2: Run RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py -k restore -q
```

Expected: missing restore API/behavior failures.

- [ ] **Step 3: Implement manifest validation and read-only preview**

Reject unknown schema versions, absolute paths, parent traversal, path type
mismatches, invalid hashes, missing required keys, and any contained-path
failure. Verify backup hashes before proposing actions. Compare current source,
destination, and index against only the manifest's known before/after hashes.
Preview performs no writes, lock creation, or journal append.

- [ ] **Step 4: Implement guarded restore and idempotency**

Acquire the same deterministic locks as apply. Restore the source first without
overwriting unknown bytes. Restore index only if it still matches the expected
post-image. Remove destination only if it still matches the rendered hash.
Journal `restored` after final verification. A repeated restore returns
`already_restored` without changing files.

If any state changes after preview or any injected step fails, preserve copies
and return `recovery_required`; never convert a concurrent edit into a rollback.

- [ ] **Step 5: Run all restore/transaction tests**

```bash
uv run --locked --extra dev pytest tests/test_inbox_transaction.py -q
```

Expected: all apply, rollback, and restore tests pass.

- [ ] **Step 6: Commit restore support**

```bash
git add obsidian_kb_skill/scripts/inbox_transaction.py \
  tests/test_inbox_transaction.py
git commit -m "feat: restore inbox transactions safely"
```

---

### Task 7: CLI Compatibility and Truthful Results

**Files:**
- Modify: `obsidian_kb_skill/scripts/process_inbox.py`
- Modify: `tests/test_process_inbox.py`
- Modify: `tests/test_json_output.py`
- Modify: `tests/test_cli_integration.py`
- Modify: `tests/test_path_safety_e2e.py`

**Interfaces:**
- Consumes: `plan_inbox()`, `legacy_plan_dict()`, `apply_inbox_item()`, restore
  preview/apply, typed result dataclasses.
- Produces: compatible `plan_note()`, `apply_plan()`, `process_vault()`, and
  `main()` adapters plus accurate text/JSON outcomes.

- [ ] **Step 1: Write end-to-end CLI RED tests**

Add subprocess tests proving:

- default/`--plan` remains read-only and text records retain `FILE`/`SKIP`;
- `--plan --json` remains a top-level list with legacy keys;
- malformed/nonmapping/invalid UTF-8 `--apply` exits 2 with no mutation;
- mixed apply reports exact applied/skipped/blocked/failed/recovery counts;
- destination conflict is skipped and not counted applied;
- a fully rolled-back runtime failure exits 3;
- recovery required exits 4 and prints restore ID/preview command;
- `--restore ID` is read-only;
- `--restore ID --apply` restores;
- JSON stdout is one document and contains no absolute backup/result paths or
  traceback.

Keep this existing assertion valid for a one-item success:

```python
assert "1 Inbox note(s) applied." in result.stdout
```

Add a truthful breakdown assertion on the following line.

- [ ] **Step 2: Run CLI RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_process_inbox.py tests/test_json_output.py \
  tests/test_cli_integration.py tests/test_path_safety_e2e.py -q
```

Expected: new safety/result/restore assertions fail against the legacy CLI.

- [ ] **Step 3: Replace orchestration with typed APIs**

Make `process_vault()` call `plan_inbox()` once. For `apply=True`, pass those
exact items to `apply_inbox_item()`; never re-read for classification or compute
a second date. Convert typed plans/results at the outer adapter only.

Preserve import compatibility:

```python
def plan_note(path: Path, vault: Path) -> dict[str, Any]: ...
def apply_plan(
    plan: dict[str, Any], vault: Path, silent: bool = False
) -> InboxApplyResult: ...
def process_vault(
    vault: Path,
    apply: bool,
    inbox_name: str = "00-Inbox",
    silent: bool = False,
) -> list[dict[str, Any]]: ...
```

The legacy `apply_plan()` replans exactly the named in-Vault source at call time
and then uses the transaction. It must not restore unsafe direct-write behavior.

- [ ] **Step 4: Implement CLI result/exit serialization**

For plan JSON, emit the legacy list and add only `status`/structured `error` for
blocked items. For apply JSON, retain the list and add a `result` object to each
entry with `status`, `applied`, Vault-relative destination/backup, restore ID,
issue, and warnings.

Compute summary counts from result statuses. Use severity ordering 0 < 2 < 3 <
4, and return the highest encountered code. Keep diagnostics structured in JSON
mode and on stderr in text mode.

Change argparse so `--restore RESTORE_ID` selects restore mode while `--apply`
controls preview versus mutation:

```text
obsidian-process-inbox VAULT --restore <id>
obsidian-process-inbox VAULT --restore <id> --apply
```

- [ ] **Step 5: Run Inbox and JSON/CLI regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_plan.py tests/test_inbox_transaction.py \
  tests/test_process_inbox.py tests/test_json_output.py \
  tests/test_cli_integration.py tests/test_path_safety_e2e.py -q
```

Expected: all selected tests pass; no plan mode creates `.obsidian-kb-backups`.

- [ ] **Step 6: Commit the compatibility adapter**

```bash
git add obsidian_kb_skill/scripts/process_inbox.py \
  tests/test_process_inbox.py tests/test_json_output.py \
  tests/test_cli_integration.py tests/test_path_safety_e2e.py
git commit -m "fix: report actual inbox transaction outcomes"
```

---

### Task 8: Safety Documentation and Distribution Sync

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Modify: `obsidian_kb_skill/scripts/process_inbox.py` (`--help` strings only)
- Regenerate: `skills/obsidian-knowledge-base/`, platform adapters, packaged
  resources, and `skills/obsidian-knowledge-base/manifest.json` through
  `build.py`
- Modify: relevant documentation/build contract tests

**Interfaces:**
- Consumes: final CLI syntax, exit codes, backup layout, restore behavior.
- Produces: narrowly accurate user documentation and synchronized distribution
  artifacts. It does not perform the later README information-architecture work.

- [ ] **Step 1: Write documentation contract RED tests**

Assert both READMEs contain the exact two restore commands, state that malformed
frontmatter is never modified, identify the backup root, and distinguish
`rolled_back` from `recovery_required`. Assert they do not mention external plan
files, a ten-item limit, confidence, or automatic background processing.

Add `--help` snapshot/substring assertions for plan, apply, restore preview, and
restore apply.

- [ ] **Step 2: Run documentation RED**

```bash
uv run --locked --extra dev pytest \
  tests/test_build.py tests/test_templates.py tests/test_skill_runtime.py -q
```

Expected: new documentation assertions fail.

- [ ] **Step 3: Update only the Inbox safety sections**

Document:

```text
obsidian-process-inbox VAULT --plan
obsidian-process-inbox VAULT --apply
obsidian-process-inbox VAULT --restore RESTORE_ID
obsidian-process-inbox VAULT --restore RESTORE_ID --apply
```

Explain default read-only operation, fail-closed parsing, per-note transactions,
backup location, exact rollback versus recovery-required, no-overwrite behavior,
and exit codes 0/2/3/4. Add the same semantic facts in Chinese and English.

- [ ] **Step 4: Regenerate and verify distribution artifacts**

```bash
uv run --locked --extra dev python build.py
uv run --locked --extra dev python build.py --check
```

Expected: build creates/synchronizes five artifacts, then check reports
`All generated artifacts are up to date.`

- [ ] **Step 5: Run documentation, packaging, and installed-runtime regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_build.py tests/test_templates.py tests/test_skill_runtime.py \
  tests/test_wheel_install.py tests/test_installers.py \
  tests/test_environment_contract.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit documentation and generated copies**

```bash
git add README.md README_EN.md CHANGELOG.md \
  obsidian_kb_skill/scripts/process_inbox.py \
  obsidian_kb_skill/scripts/resources skills platforms tests
git commit -m "docs: explain inbox recovery workflow"
```

Use `git status --short` before committing and stage only files actually changed
by this task; do not stage unrelated user files.

---

### Task 9: Branch Verification and Review Gate

**Files:**
- No production changes unless verification exposes a defect.
- Write ignored controller reports under `.superpowers/sdd/` only.

**Interfaces:**
- Consumes: all accepted task commits.
- Produces: fresh verification evidence and an independent final branch review.

- [ ] **Step 1: Run the full test and build gates from the feature worktree**

```bash
uv run --locked --extra dev python build.py --check
uv run --locked --extra dev pytest
uv run --locked --extra dev pytest \
  tests/test_wheel_install.py tests/test_installers.py \
  tests/test_environment_contract.py -q
```

Expected: build check passes; the full and packaging/environment suites have
zero failures.

- [ ] **Step 2: Run hostile-CWD, doctor, and source/mirror checks**

Use the existing hostile-working-directory and doctor tests discovered with:

```bash
rg -n "hostile|doctor" tests
```

Run the matching test files, then verify canonical/mirror bytes and manifest
with the existing build tests. Expected: all pass from a directory outside the
repository and the standard Skill mirror matches canonical sources.

- [ ] **Step 3: Check scope and repository cleanliness**

```bash
git diff --check 8132365..HEAD
git status --short
git log --oneline 8132365..HEAD
```

Expected: no diff-check errors, no tracked/untracked implementation debris, and
only Inbox safety/spec/plan/documentation/generated changes in the commit list.

- [ ] **Step 4: Generate a review package and dispatch an independent reviewer**

```bash
/Users/shaopc/.agents/superpowers/skills/subagent-driven-development/scripts/review-package \
  8132365 HEAD .superpowers/sdd/inbox-data-safety-final-review.md
```

The reviewer must inspect the spec, this plan, all commits, raw failure states,
Vault containment, backup/restore conflicts, CLI compatibility, generated
payload, and fresh test evidence. Critical or Important findings block branch
acceptance and return to one focused fixer with new RED tests.

- [ ] **Step 5: Freeze the accepted branch without touching master**

After a reviewer returns `Ready to merge: Yes`, use
`superpowers:finishing-a-development-branch`. Under the user's standing
instruction, keep the branch/worktree as-is (option 3), record its accepted HEAD
as the next clean base, and create the next independent worktree branch. Do not
merge or push unless the user later changes that instruction.
