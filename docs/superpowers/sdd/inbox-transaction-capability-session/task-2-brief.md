### Task 2: Bound Path Capabilities and Platform Probes

**Files:**
- Create: `obsidian_kb_skill/scripts/inbox_tx/paths.py`
- Create: `tests/test_inbox_tx_paths.py`

**Interfaces:**
- Consumes: `FileIdentity`, `FileMetadata`, `InboxFailure`,
  `InboxTransactionError`, existing `validate_vault_root()` policy.
- Produces:

```python
@dataclass(frozen=True)
class CapabilitySupport:
    supported: bool
    code: str | None
    message: str | None

@dataclass(frozen=True)
class PreviewCapabilitySupport:
    supported: bool
    code: str | None
    message: str | None
    serialization: Literal["shared-lock", "double-read"] | None

    def __post_init__(self) -> None:
        if self.supported != (self.serialization is not None):
            raise ValueError("preview support and serialization must agree")

class MutationCapabilityProbe(Protocol):
    def probe(self, vault: Path) -> CapabilitySupport: ...

class PreviewCapabilityProbe(Protocol):
    def probe(self, vault: Path) -> PreviewCapabilitySupport: ...

class LocalMutationCapabilityProbe:
    def probe(self, vault: Path) -> CapabilitySupport: ...

class LocalPreviewCapabilityProbe:
    def probe(self, vault: Path) -> PreviewCapabilitySupport: ...

@dataclass(frozen=True)
class CapabilityProviders:
    mutation: MutationCapabilityProbe
    preview: PreviewCapabilityProbe

def default_capability_providers() -> CapabilityProviders: ...

@dataclass(frozen=True)
class DirectoryBinding:
    relative: Path
    identity: FileIdentity

@dataclass
class BoundDirectory:
    fd: int
    relative: Path
    identity: FileIdentity
    chain: tuple[DirectoryBinding, ...]
    _closed: bool = field(default=False, init=False, repr=False)

    def fileno(self) -> int: ...
    def __enter__(self) -> "BoundDirectory": ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...
    def close(self) -> tuple[str, ...]: ...

@dataclass
class VaultCapability:
    root: Path
    fd: int
    identity: FileIdentity
    _closed: bool = field(default=False, init=False, repr=False)

    @classmethod
    def open(cls, vault: Path) -> "VaultCapability": ...
    def __enter__(self) -> "VaultCapability": ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...
    def open_directory(self, relative: Path) -> BoundDirectory: ...
    def open_parent(self, relative: Path) -> "BoundDirectory": ...
    def ensure_directory(self, relative: Path, *, mode: int = 0o700) \
            -> BoundDirectory: ...
    def create_directory(self, relative: Path, *, mode: int = 0o700) \
            -> BoundDirectory: ...
    def revalidate_public_chain(self, bound: BoundDirectory) -> None: ...
    def close(self) -> tuple[str, ...]: ...

def validate_business_relative(relative: Path, *, label: str) -> Path: ...
def validate_recovery_relative(relative: Path, *, label: str) -> Path: ...
def create_regular_at(parent: BoundDirectory, name: str, *, mode: int = 0o600) \
        -> tuple[int, FileIdentity]: ...
def open_regular_at(parent: BoundDirectory, name: str, *, writable: bool = False) \
        -> tuple[int, FileIdentity, FileMetadata]: ...
def read_all_fd(fd: int) -> bytes: ...
def write_all_fd(fd: int, payload: bytes) -> None: ...
def fsync_fd(fd: int) -> None: ...
def fsync_directory(parent: BoundDirectory) -> None: ...
def sha256_bytes(payload: bytes) -> str: ...
def entry_exists_at(parent: BoundDirectory, name: str) -> bool: ...
def verify_regular_binding_at(
    parent: BoundDirectory,
    name: str,
    fd: int,
) -> FileIdentity: ...
def read_regular_at(parent: "BoundDirectory", name: str) \
        -> tuple[int, bytes, FileIdentity, FileMetadata]: ...
def write_new_durable_at(parent: "BoundDirectory", name: str, payload: bytes) \
        -> tuple[int, FileIdentity]: ...
def link_no_overwrite_at(
    source_parent: "BoundDirectory",
    source_name: str,
    destination_parent: "BoundDirectory",
    destination_name: str,
) -> FileIdentity: ...
def unlink_expected_at(
    parent: BoundDirectory,
    name: str,
    *,
    expected_identity: FileIdentity,
    expected_sha256: str,
) -> None: ...
def replace_expected_at(
    parent: BoundDirectory,
    source_name: str,
    destination_name: str,
    *,
    expected_source_identity: FileIdentity,
    expected_source_sha256: str,
    expected_destination_identity: FileIdentity,
    expected_destination_sha256: str,
) -> FileIdentity: ...
```

`DirectoryBinding.relative` is relative to the bound Vault; only the first
internal root binding may use `Path(".")`. A `BoundDirectory` owns exactly one
fd plus the immutable root-to-directory identity chain. `close()` is idempotent,
closes only that fd, returns warning strings instead of raising close errors,
and every other method/helper rejects a closed capability. Warnings contain
only Vault-relative diagnostics, never `VaultCapability.root`. Every
`BoundDirectory`, including one for the Vault root, owns a distinct fd from the
Vault capability. Returned regular-file fds are owned by the caller; every
helper closes locally opened fds on failure before ownership can transfer.
`VaultCapability` owns only its root fd; its `close()` has the same idempotent,
warning-returning behavior, and every method rejects use after close. Closing a
Vault capability does not close independently owned `BoundDirectory` or file
fds; the session closes those children first in reverse ownership order.
Directory bindings require a directory at every step and compare only
`device`/`inode` when revalidating; directory size/mtime may change because of
legitimate sibling entry updates. Regular-file identity guards compare the full
`FileIdentity` plus the separately required content hash.

Both relative validators reject native absolute paths, Windows drive/UNC-shaped
paths on non-Windows hosts, empty paths, and dot/parent/empty components.
Every `name` argument is exactly one nonempty native lexical component: it
rejects `.`, `..`, `os.sep`, and `os.altsep` when `os.altsep` exists. Thus POSIX
accepts an ordinary relative filename containing a literal backslash, matching
the existing Vault policy, while Windows rejects both native separators.
Callers cannot smuggle traversal through a final name.
`sha256_bytes()` returns exactly `sha256:` followed by 64 lowercase hexadecimal
characters.

`open_directory()` binds an existing directory. `open_parent(file_relative)`
binds `file_relative.parent`. `ensure_directory()` opens or creates each missing
directory component with no-follow semantics and fsyncs every newly changed
parent. `create_directory()` requires the final component to be absent, creates
it once, fsyncs its parent, and returns the bound new directory. Neither method
accepts an absolute/dot/parent/empty component.

`create_regular_at()` performs exclusive no-follow creation but no write or
fsync, so later tasks can inject distinct open/write/fsync failures.
`open_regular_at()` and `read_regular_at()` reject every symlink and non-regular
entry; `read_regular_at()` leaves its returned fd positioned at offset zero.
`entry_exists_at()` uses a no-follow lexical stat and returns true for every
entry type, including dangling symlinks; only true `ENOENT` returns false.
`read_all_fd()` uses positional descriptor reads without closing, changing the
file offset, or changing the caller's logical ownership. `write_all_fd()`
handles short writes. `fsync_fd()` and
`fsync_directory()` are separate explicit durability boundaries.

`write_new_durable_at()` is the create/write/file-fsync/parent-fsync composite.
`link_no_overwrite_at()` uses `follow_symlinks=False`, never replaces an entry,
and returns the verified public identity without fsyncing so Task 6 can set
`business_mutation_started=True` before the explicit destination-parent
`fsync_directory()` boundary. `unlink_expected_at()` and
`replace_expected_at()` first require every supplied identity **and** `sha256:`
hash, perform the single fd-relative mutation, and then verify absence or the
installed source identity; they likewise leave the parent fsync as the caller's
next explicit operation. They preserve a mismatching object and raise instead
of retrying. These are generic compare-and-mutate primitives; Task 6 owns the
required immediate fsync/revalidation, rollback policy, and the decision whether
a mismatch means abort, rollback, or recovery-required.

Path-layer failures use `InboxTransactionError(InboxFailure(...))` with
`restore_id=None`, `recovery_location=None`, empty warnings/debris, and
`business_mutation_started=False`; later session code enriches failures after
it owns a restore ID or starts mutation. Messages and issue paths are
Vault-relative and never contain `VaultCapability.root`. Use these exact codes:

| Condition | Code |
|---|---|
| invalid business lexical path/control namespace | `unsafe-inbox-business-path` |
| invalid recovery lexical path | `unsafe-inbox-recovery-path` |
| symlink/non-regular/unsafe directory or file | `unsafe-inbox-path` |
| existing entry blocks exclusive create/link | `inbox-path-occupied` |
| chain, identity, or hash no longer matches | `inbox-path-changed` |
| operation attempted after capability close | `inbox-capability-closed` |
| open/read/write/link/unlink/replace OS failure | `inbox-path-operation-failed` |
| file or directory fsync failure | `inbox-path-durability-failed` |

Preserve an underlying `OSError` as `__cause__`. Mutation/preview probe failures
are returned—not raised—with exact codes `unsupported-inbox-mutation` and
`unsupported-inbox-preview`.

- [ ] **Step 1: Write traversal, namespace, and capability RED tests**

Cover real nested paths, a symlink at every ancestor depth, dangling final
symlink, FIFO/non-regular objects, parent traversal, absolute paths, and source/
destination/index paths under `.obsidian-kb-backups`. Inject missing `dir_fd`,
`O_NOFOLLOW`, directory fsync, hard-link, and `flock` support. Assert mutation
and preview probes are distinct and preview fails before opening a record when
safe no-follow traversal is absent. Assert `CapabilityProviders` is frozen,
`default_capability_providers()` returns stateless production adapters, and
fake mutation/preview adapters can be supplied without monkeypatching globals.
Parametrize preview support as unsupported/`None`, supported/`shared-lock`, and
supported/`double-read`; reject every inconsistent combination such as
supported/`None` or unsupported/non-`None`. This return value, not a later
global `fcntl` lookup, is the complete orchestration decision.
Fault-inject `VaultCapability.open()` after each local descriptor acquisition;
assert every pre-return failure closes the exact opened fds in reverse order and
that no `VaultCapability` ownership escapes. Cover root and nested
`BoundDirectory` ownership, distinct fds, immutable chain contents, and public-
chain replacement detection. For both `VaultCapability` and `BoundDirectory`,
cover idempotent close/warnings, rejection after close, and proof that closing
one owner does not close independently owned child fds.
Exercise every named primitive's ownership contract: caller-owned returned fds,
local close on failure, short reads/writes, unchanged `read_all_fd()` offset,
exclusive create, file/parent fsync order, lexical dangling-symlink occupancy,
no-overwrite link, identity-and-hash mismatch preservation, and verified
unlink/replace success.

```python
@pytest.mark.parametrize(
    "relative",
    [Path(".obsidian-kb-backups/x.md"), Path("../outside.md")],
)
def test_business_path_rejects_control_or_parent_namespace(relative: Path) -> None:
    with pytest.raises(InboxTransactionError) as caught:
        validate_business_relative(relative, label="Inbox source")
    assert caught.value.failure.code == "unsafe-inbox-business-path"
```

- [ ] **Step 2: Run path tests and confirm RED**

```bash
uv run --locked --extra dev pytest tests/test_inbox_tx_paths.py -q
```

Expected: missing module/API failures.

- [ ] **Step 3: Implement no-follow descriptor traversal**

Open the validated Vault root once. Traverse each component with
`os.open(component, O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC, dir_fd=fd)`,
validate with `fstat`, and close intermediate fds deterministically. Never
return a verified free-floating `Path` as a capability. Store the lexical root
only for relative diagnostics.

```python
def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )

def _identity(result: os.stat_result) -> FileIdentity:
    return FileIdentity(
        device=result.st_dev,
        inode=result.st_ino,
        size=result.st_size,
        mtime_ns=result.st_mtime_ns,
    )
```

`revalidate_public_chain()` must reopen from the bound Vault root and compare
the Vault identity plus every `DirectoryBinding` stored on the supplied
`BoundDirectory`, then close all temporary fds. It must never learn a new
identity or replace the expected chain during revalidation. Add
`validate_business_relative()` and a separate recovery-relative validator; both
reject absolute/dot/parent/empty components, while only business validation
rejects `.obsidian-kb-backups`.

- [ ] **Step 4: Implement durable fd-relative mutation primitives**

Implement the named create/open/read/write/verify helpers exactly as the
interface and ownership notes define. `write_new_durable_at()` and directory
creation are durable composites. Link/unlink/replace deliberately expose the
post-mutation, pre-parent-fsync boundary required by Task 6; their tests must
call `fsync_directory()` next and verify the resulting state. Exclusive
creation, regular-file checks, hard-link no-overwrite publication,
identity-and-hash unlink/replace, and reverse-order local close are mandatory.
Treat `FileExistsError` as occupied, not a retry signal, and never retry over an
unknown entry.

- [ ] **Step 5: Implement mutation and preview probes**

Mutation probe requires CPython 3.11+, Linux/macOS, required membership in
`os.supports_dir_fd`, `O_NOFOLLOW`, directory fsync, and importable
`fcntl.flock`. Preview probe requires only secure bound no-follow traversal and
identity, then returns `serialization="shared-lock"` when `flock` is available
or `serialization="double-read"` when safe path binding exists without it.
Unsupported preview returns `serialization=None`. Do not create a CLI/
environment bypass. Document in code that network mount semantics remain
outside the guarantee even if primitive checks pass.
`default_capability_providers()` returns new
`LocalMutationCapabilityProbe()`/`LocalPreviewCapabilityProbe()` instances;
later session/restore internals receive the frozen bundle explicitly while
public façades construct this default when no internal bundle is supplied.

Both production probes are read-only. The mutation probe validates and safely
binds the Vault root, checks the required callable/flag/`os.supports_dir_fd`
memberships, and actually fsyncs the open root directory; it does not create a
probe directory or file. Static hard-link support is only an API capability
check—the real recovery-stage-to-destination link in Task 6 remains the
authoritative filesystem test. The preview probe performs no create/fsync and
does not open a requested recovery record; Task 7 performs the actual bound
record traversal after supported preview capability is returned.

`VaultCapability.open()` keeps locally opened fds behind an `ExitStack` (or an
equivalent explicit `try/finally`) until the fully initialized object is ready.
Disarm that cleanup only on successful return; all earlier failures close in
reverse order.

- [ ] **Step 6: Run path and shared path-policy regressions**

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_tx_paths.py tests/test_vault_paths.py \
  tests/test_path_safety_e2e.py tests/test_environment_contract.py -q
```

Expected: all selected tests pass with no out-of-Vault reads/writes.

- [ ] **Step 7: Commit path capabilities**

```bash
git add obsidian_kb_skill/scripts/inbox_tx/paths.py \
  tests/test_inbox_tx_paths.py
git commit -m "fix: bind inbox transaction paths to descriptors"
```

---

