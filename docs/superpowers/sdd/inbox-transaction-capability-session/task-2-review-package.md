# Review package: 6361e64..HEAD

## Commits
792c023 fix: bind inbox transaction paths to descriptors

## Files changed
 obsidian_kb_skill/scripts/inbox_tx/paths.py | 991 ++++++++++++++++++++++++++++
 tests/test_inbox_tx_paths.py                | 841 +++++++++++++++++++++++
 2 files changed, 1832 insertions(+)

## Diff
diff --git a/obsidian_kb_skill/scripts/inbox_tx/paths.py b/obsidian_kb_skill/scripts/inbox_tx/paths.py
new file mode 100644
index 0000000..630877d
--- /dev/null
+++ b/obsidian_kb_skill/scripts/inbox_tx/paths.py
@@ -0,0 +1,991 @@
+"""Descriptor-bound path capabilities for Inbox transactions.
+
+All public filesystem operations in this module are relative to an already
+bound directory descriptor.  Passing a verified, free-floating absolute path
+to a later mutation is deliberately avoided.
+"""
+from __future__ import annotations
+
+import errno
+import hashlib
+import os
+import stat
+import sys
+from dataclasses import dataclass, field
+from pathlib import Path
+from typing import Literal, Protocol
+
+from obsidian_kb_skill.scripts.inbox_tx.models import (
+    FileIdentity,
+    FileMetadata,
+    InboxFailure,
+    InboxTransactionError,
+)
+from obsidian_kb_skill.scripts.vault_paths import validate_vault_root
+
+
+@dataclass(frozen=True)
+class CapabilitySupport:
+    supported: bool
+    code: str | None
+    message: str | None
+
+
+@dataclass(frozen=True)
+class PreviewCapabilitySupport:
+    supported: bool
+    code: str | None
+    message: str | None
+    serialization: Literal["shared-lock", "double-read"] | None
+
+    def __post_init__(self) -> None:
+        if self.supported != (self.serialization is not None):
+            raise ValueError("preview support and serialization must agree")
+
+
+class MutationCapabilityProbe(Protocol):
+    def probe(self, vault: Path) -> CapabilitySupport: ...
+
+
+class PreviewCapabilityProbe(Protocol):
+    def probe(self, vault: Path) -> PreviewCapabilitySupport: ...
+
+
+def _unsupported_mutation(message: str) -> CapabilitySupport:
+    return CapabilitySupport(False, "unsupported-inbox-mutation", message)
+
+
+def _unsupported_preview(message: str) -> PreviewCapabilitySupport:
+    return PreviewCapabilitySupport(False, "unsupported-inbox-preview", message, None)
+
+
+def _nofollow_available() -> bool:
+    return bool(getattr(os, "O_NOFOLLOW", 0) and getattr(os, "O_DIRECTORY", 0))
+
+
+def _required_dir_fd_support() -> bool:
+    required = (os.open, os.stat, os.mkdir, os.unlink, os.link)
+    return all(function in os.supports_dir_fd for function in required)
+
+
+def _secure_binding_support() -> bool:
+    return _nofollow_available() and all(
+        function in os.supports_dir_fd for function in (os.open, os.stat)
+    )
+
+
+def _hard_link_available() -> bool:
+    return callable(getattr(os, "link", None)) and os.link in os.supports_dir_fd
+
+
+def _flock_available() -> bool:
+    try:
+        import fcntl
+    except ImportError:
+        return False
+    return callable(getattr(fcntl, "flock", None))
+
+
+class LocalMutationCapabilityProbe:
+    def probe(self, vault: Path) -> CapabilitySupport:
+        if sys.version_info < (3, 11):
+            return _unsupported_mutation("Inbox mutation requires CPython 3.11 or newer")
+        if sys.platform not in {"linux", "darwin"}:
+            return _unsupported_mutation("Inbox mutation is supported only on Linux and macOS")
+        if not _required_dir_fd_support():
+            return _unsupported_mutation("Required descriptor-relative operations are unavailable")
+        if not _nofollow_available():
+            return _unsupported_mutation("Safe no-follow directory traversal is unavailable")
+        if not _hard_link_available():
+            return _unsupported_mutation("Descriptor-relative hard links are unavailable")
+        if not _flock_available():
+            return _unsupported_mutation("Advisory file locking is unavailable")
+
+        # This is intentionally read-only.  A successful probe says that the
+        # local primitives exist; network-mount semantics remain outside the
+        # guarantee and the real publication link is still authoritative.
+        try:
+            with VaultCapability.open(vault) as capability:
+                os.fsync(capability.fd)
+        except (InboxTransactionError, OSError):
+            return _unsupported_mutation("The Vault root cannot provide directory durability")
+        return CapabilitySupport(True, None, None)
+
+
+class LocalPreviewCapabilityProbe:
+    def probe(self, vault: Path) -> PreviewCapabilitySupport:
+        if not _secure_binding_support():
+            return _unsupported_preview("Safe no-follow Vault traversal is unavailable")
+        try:
+            with VaultCapability.open(vault):
+                pass
+        except InboxTransactionError:
+            return _unsupported_preview("The Vault root cannot be safely bound")
+        serialization: Literal["shared-lock", "double-read"]
+        serialization = "shared-lock" if _flock_available() else "double-read"
+        return PreviewCapabilitySupport(True, None, None, serialization)
+
+
+@dataclass(frozen=True)
+class CapabilityProviders:
+    mutation: MutationCapabilityProbe
+    preview: PreviewCapabilityProbe
+
+
+def default_capability_providers() -> CapabilityProviders:
+    return CapabilityProviders(LocalMutationCapabilityProbe(), LocalPreviewCapabilityProbe())
+
+
+@dataclass(frozen=True)
+class DirectoryBinding:
+    relative: Path
+    identity: FileIdentity
+
+
+def _failure(code: str, message: str) -> InboxTransactionError:
+    return InboxTransactionError(
+        InboxFailure(
+            code=code,
+            message=message,
+            restore_id=None,
+            recovery_location=None,
+            warnings=(),
+            recovery_debris=None,
+            business_mutation_started=False,
+        )
+    )
+
+
+def _raise_os(code: str, message: str, error: OSError) -> None:
+    raise _failure(code, message) from error
+
+
+def _identity(result: os.stat_result) -> FileIdentity:
+    return FileIdentity(
+        device=result.st_dev,
+        inode=result.st_ino,
+        size=result.st_size,
+        mtime_ns=result.st_mtime_ns,
+    )
+
+
+def _same_directory(left: FileIdentity, right: FileIdentity) -> bool:
+    return left.device == right.device and left.inode == right.inode
+
+
+def _directory_flags() -> int:
+    return (
+        os.O_RDONLY
+        | getattr(os, "O_DIRECTORY", 0)
+        | getattr(os, "O_NOFOLLOW", 0)
+        | getattr(os, "O_CLOEXEC", 0)
+    )
+
+
+def _regular_flags(*, writable: bool) -> int:
+    access = os.O_RDWR if writable else os.O_RDONLY
+    return access | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
+
+
+def _foreign_windows_path(relative: Path) -> bool:
+    if os.name == "nt":
+        return False
+    text = str(relative)
+    return text.startswith("\\\\") or (
+        len(text) >= 2 and text[0].isalpha() and text[1] == ":"
+    )
+
+
+def _validate_relative(relative: Path, *, label: str, code: str) -> Path:
+    path = Path(relative)
+    if (
+        path.is_absolute()
+        or _foreign_windows_path(path)
+        or not path.parts
+        or str(path) in {"", "."}
+        or any(part in {"", ".", ".."} for part in path.parts)
+    ):
+        raise _failure(code, f"{label} must be a safe nonempty Vault-relative path")
+    return path
+
+
+def validate_business_relative(relative: Path, *, label: str) -> Path:
+    path = _validate_relative(
+        relative, label=label, code="unsafe-inbox-business-path"
+    )
+    if path.parts[0] == ".obsidian-kb-backups":
+        raise _failure(
+            "unsafe-inbox-business-path",
+            f"{label} cannot use the Inbox recovery namespace",
+        )
+    return path
+
+
+def validate_recovery_relative(relative: Path, *, label: str) -> Path:
+    return _validate_relative(relative, label=label, code="unsafe-inbox-recovery-path")
+
+
+def _validate_directory_relative(relative: Path) -> Path:
+    path = Path(relative)
+    if str(path) == ".":
+        return path
+    return _validate_relative(path, label="Directory", code="unsafe-inbox-path")
+
+
+def _validate_name(name: str) -> str:
+    if not isinstance(name, str) or not name or name in {".", ".."}:
+        raise _failure("unsafe-inbox-path", "Entry name must be one safe component")
+    if os.sep in name or (os.altsep is not None and os.altsep in name):
+        raise _failure("unsafe-inbox-path", "Entry name must be one safe component")
+    return name
+
+
+@dataclass
+class BoundDirectory:
+    fd: int
+    relative: Path
+    identity: FileIdentity
+    chain: tuple[DirectoryBinding, ...]
+    _closed: bool = field(default=False, init=False, repr=False)
+
+    def _require_open(self) -> None:
+        if self._closed:
+            raise _failure(
+                "inbox-capability-closed",
+                f"Directory capability {self.relative} is closed",
+            )
+
+    def fileno(self) -> int:
+        self._require_open()
+        return self.fd
+
+    def __enter__(self) -> "BoundDirectory":
+        self._require_open()
+        return self
+
+    def __exit__(self, exc_type, exc, traceback) -> None:
+        self.close()
+
+    def close(self) -> tuple[str, ...]:
+        if self._closed:
+            return ()
+        self._closed = True
+        try:
+            os.close(self.fd)
+        except OSError:
+            return (f"Could not close directory capability {self.relative}",)
+        return ()
+
+
+@dataclass
+class VaultCapability:
+    root: Path
+    fd: int
+    identity: FileIdentity
+    _closed: bool = field(default=False, init=False, repr=False)
+
+    @classmethod
+    def open(cls, vault: Path) -> "VaultCapability":
+        opened: list[int] = []
+        try:
+            root = validate_vault_root(vault)
+            fd = os.open(root, _directory_flags())
+            opened.append(fd)
+            result = os.fstat(fd)
+            if not stat.S_ISDIR(result.st_mode):
+                raise _failure("unsafe-inbox-path", "Vault root is not a directory")
+            capability = cls(root=root, fd=fd, identity=_identity(result))
+        except InboxTransactionError:
+            for local_fd in reversed(opened):
+                try:
+                    os.close(local_fd)
+                except OSError:
+                    pass
+            raise
+        except OSError as error:
+            for local_fd in reversed(opened):
+                try:
+                    os.close(local_fd)
+                except OSError:
+                    pass
+            _raise_os("inbox-path-operation-failed", "Could not bind the Vault root", error)
+        except Exception as error:
+            for local_fd in reversed(opened):
+                try:
+                    os.close(local_fd)
+                except OSError:
+                    pass
+            cause = error.__cause__ if isinstance(error.__cause__, OSError) else error
+            raise _failure("unsafe-inbox-path", "Vault root cannot be safely resolved") from cause
+        opened.clear()
+        return capability
+
+    def _require_open(self) -> None:
+        if self._closed:
+            raise _failure("inbox-capability-closed", "Vault capability is closed")
+
+    def __enter__(self) -> "VaultCapability":
+        self._require_open()
+        return self
+
+    def __exit__(self, exc_type, exc, traceback) -> None:
+        self.close()
+
+    def _open_component(self, parent_fd: int, name: str, relative: Path) -> int:
+        try:
+            fd = os.open(name, _directory_flags(), dir_fd=parent_fd)
+        except OSError as error:
+            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
+                _raise_os("unsafe-inbox-path", f"Directory {relative} is unsafe", error)
+            _raise_os(
+                "inbox-path-operation-failed",
+                f"Could not open directory {relative}",
+                error,
+            )
+        try:
+            result = os.fstat(fd)
+            if not stat.S_ISDIR(result.st_mode):
+                raise _failure("unsafe-inbox-path", f"Directory {relative} is unsafe")
+        except BaseException:
+            try:
+                os.close(fd)
+            except OSError:
+                pass
+            raise
+        return fd
+
+    def open_directory(self, relative: Path) -> BoundDirectory:
+        self._require_open()
+        path = _validate_directory_relative(relative)
+        current_fd: int | None = None
+        bindings = [DirectoryBinding(Path("."), self.identity)]
+        try:
+            current_fd = self._open_component(self.fd, ".", Path("."))
+            current_identity = _identity(os.fstat(current_fd))
+            if not _same_directory(current_identity, self.identity):
+                raise _failure("inbox-path-changed", "Vault root identity changed")
+            cumulative = Path()
+            if path != Path("."):
+                for component in path.parts:
+                    cumulative = cumulative / component
+                    next_fd = self._open_component(current_fd, component, cumulative)
+                    try:
+                        next_identity = _identity(os.fstat(next_fd))
+                    except BaseException:
+                        try:
+                            os.close(next_fd)
+                        except OSError:
+                            pass
+                        raise
+                    try:
+                        os.close(current_fd)
+                    except BaseException:
+                        try:
+                            os.close(next_fd)
+                        except OSError:
+                            pass
+                        raise
+                    current_fd = next_fd
+                    current_identity = next_identity
+                    bindings.append(DirectoryBinding(cumulative, current_identity))
+            assert current_fd is not None
+            bound = BoundDirectory(
+                fd=current_fd,
+                relative=path,
+                identity=current_identity,
+                chain=tuple(bindings),
+            )
+        except InboxTransactionError:
+            if current_fd is not None:
+                try:
+                    os.close(current_fd)
+                except OSError:
+                    pass
+            raise
+        except OSError as error:
+            if current_fd is not None:
+                try:
+                    os.close(current_fd)
+                except OSError:
+                    pass
+            _raise_os(
+                "inbox-path-operation-failed",
+                f"Could not bind directory {path}",
+                error,
+            )
+        current_fd = None
+        return bound
+
+    def open_parent(self, relative: Path) -> BoundDirectory:
+        self._require_open()
+        path = _validate_relative(relative, label="File", code="unsafe-inbox-path")
+        parent = path.parent
+        return self.open_directory(parent if str(parent) != "." else Path("."))
+
+    def ensure_directory(self, relative: Path, *, mode: int = 0o700) -> BoundDirectory:
+        self._require_open()
+        path = _validate_relative(relative, label="Directory", code="unsafe-inbox-path")
+        with self.open_directory(Path(".")) as root_bound:
+            current_fd = os.dup(root_bound.fd)
+        bindings = [DirectoryBinding(Path("."), self.identity)]
+        cumulative = Path()
+        current_identity = self.identity
+        try:
+            for component in path.parts:
+                cumulative = cumulative / component
+                try:
+                    next_fd = self._open_component(current_fd, component, cumulative)
+                except InboxTransactionError as error:
+                    cause = error.__cause__
+                    if not isinstance(cause, OSError) or cause.errno != errno.ENOENT:
+                        raise
+                    try:
+                        os.mkdir(component, mode=mode, dir_fd=current_fd)
+                    except FileExistsError:
+                        pass
+                    except OSError as mkdir_error:
+                        _raise_os(
+                            "inbox-path-operation-failed",
+                            f"Could not create directory {cumulative}",
+                            mkdir_error,
+                        )
+                    else:
+                        try:
+                            os.fsync(current_fd)
+                        except OSError as fsync_error:
+                            _raise_os(
+                                "inbox-path-durability-failed",
+                                f"Could not make directory {cumulative} durable",
+                                fsync_error,
+                            )
+                    next_fd = self._open_component(current_fd, component, cumulative)
+                try:
+                    next_identity = _identity(os.fstat(next_fd))
+                except BaseException:
+                    try:
+                        os.close(next_fd)
+                    except OSError:
+                        pass
+                    raise
+                try:
+                    os.close(current_fd)
+                except BaseException:
+                    try:
+                        os.close(next_fd)
+                    except OSError:
+                        pass
+                    raise
+                current_fd = next_fd
+                current_identity = next_identity
+                bindings.append(DirectoryBinding(cumulative, current_identity))
+            bound = BoundDirectory(current_fd, path, current_identity, tuple(bindings))
+        except InboxTransactionError:
+            try:
+                os.close(current_fd)
+            except OSError:
+                pass
+            raise
+        except OSError as error:
+            try:
+                os.close(current_fd)
+            except OSError:
+                pass
+            _raise_os(
+                "inbox-path-operation-failed", f"Could not ensure directory {path}", error
+            )
+        return bound
+
+    def create_directory(self, relative: Path, *, mode: int = 0o700) -> BoundDirectory:
+        self._require_open()
+        path = _validate_relative(relative, label="Directory", code="unsafe-inbox-path")
+        name = _validate_name(path.name)
+        with self.open_parent(path) as parent:
+            try:
+                os.mkdir(name, mode=mode, dir_fd=parent.fd)
+            except FileExistsError as error:
+                _raise_os(
+                    "inbox-path-occupied", f"Directory {path} already exists", error
+                )
+            except OSError as error:
+                _raise_os(
+                    "inbox-path-operation-failed",
+                    f"Could not create directory {path}",
+                    error,
+                )
+            try:
+                os.fsync(parent.fd)
+            except OSError as error:
+                _raise_os(
+                    "inbox-path-durability-failed",
+                    f"Could not make directory {path} durable",
+                    error,
+                )
+        return self.open_directory(path)
+
+    def revalidate_public_chain(self, bound: BoundDirectory) -> None:
+        self._require_open()
+        bound._require_open()
+        temporary: list[int] = []
+        try:
+            root_fd = os.open(self.root, _directory_flags())
+            temporary.append(root_fd)
+            root_identity = _identity(os.fstat(root_fd))
+            if not _same_directory(root_identity, self.identity):
+                raise _failure("inbox-path-changed", "Vault root identity changed")
+            if not bound.chain or bound.chain[0].relative != Path("."):
+                raise _failure("inbox-path-changed", "Directory binding chain is invalid")
+            if not _same_directory(root_identity, bound.chain[0].identity):
+                raise _failure("inbox-path-changed", "Directory binding chain changed")
+            current_fd = root_fd
+            for expected in bound.chain[1:]:
+                component = expected.relative.name
+                next_fd = self._open_component(current_fd, component, expected.relative)
+                temporary.append(next_fd)
+                actual = _identity(os.fstat(next_fd))
+                if not _same_directory(actual, expected.identity):
+                    raise _failure(
+                        "inbox-path-changed", f"Directory {expected.relative} changed"
+                    )
+                current_fd = next_fd
+        except InboxTransactionError:
+            raise
+        except OSError as error:
+            _raise_os(
+                "inbox-path-operation-failed", "Could not revalidate directory chain", error
+            )
+        finally:
+            for fd in reversed(temporary):
+                try:
+                    os.close(fd)
+                except OSError:
+                    pass
+
+    def close(self) -> tuple[str, ...]:
+        if self._closed:
+            return ()
+        self._closed = True
+        try:
+            os.close(self.fd)
+        except OSError:
+            return ("Could not close Vault capability",)
+        return ()
+
+
+def _require_parent(parent: BoundDirectory) -> None:
+    if not isinstance(parent, BoundDirectory):
+        raise TypeError("parent must be a BoundDirectory")
+    parent._require_open()
+
+
+def _metadata(result: os.stat_result) -> FileMetadata:
+    return FileMetadata(mode=result.st_mode, mtime_ns=result.st_mtime_ns)
+
+
+def create_regular_at(
+    parent: BoundDirectory, name: str, *, mode: int = 0o600
+) -> tuple[int, FileIdentity]:
+    _require_parent(parent)
+    name = _validate_name(name)
+    flags = (
+        os.O_WRONLY
+        | os.O_CREAT
+        | os.O_EXCL
+        | getattr(os, "O_NOFOLLOW", 0)
+        | getattr(os, "O_CLOEXEC", 0)
+    )
+    try:
+        fd = os.open(name, flags, mode, dir_fd=parent.fd)
+    except FileExistsError as error:
+        _raise_os("inbox-path-occupied", f"Entry {parent.relative / name} exists", error)
+    except OSError as error:
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not create entry {parent.relative / name}",
+            error,
+        )
+    try:
+        result = os.fstat(fd)
+        if not stat.S_ISREG(result.st_mode):
+            raise _failure(
+                "unsafe-inbox-path", f"Entry {parent.relative / name} is not regular"
+            )
+        return fd, _identity(result)
+    except BaseException:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        raise
+
+
+def _lexical_regular_stat(parent: BoundDirectory, name: str) -> os.stat_result:
+    try:
+        result = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
+    except OSError as error:
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not inspect entry {parent.relative / name}",
+            error,
+        )
+    if not stat.S_ISREG(result.st_mode):
+        raise _failure(
+            "unsafe-inbox-path", f"Entry {parent.relative / name} is not a regular file"
+        )
+    return result
+
+
+def open_regular_at(
+    parent: BoundDirectory, name: str, *, writable: bool = False
+) -> tuple[int, FileIdentity, FileMetadata]:
+    _require_parent(parent)
+    name = _validate_name(name)
+    lexical = _lexical_regular_stat(parent, name)
+    try:
+        fd = os.open(name, _regular_flags(writable=writable), dir_fd=parent.fd)
+    except OSError as error:
+        code = "unsafe-inbox-path" if error.errno in {errno.ELOOP, errno.ENXIO} else "inbox-path-operation-failed"
+        _raise_os(code, f"Could not safely open entry {parent.relative / name}", error)
+    try:
+        result = os.fstat(fd)
+        if not stat.S_ISREG(result.st_mode):
+            raise _failure(
+                "unsafe-inbox-path", f"Entry {parent.relative / name} is not regular"
+            )
+        identity = _identity(result)
+        if identity != _identity(lexical):
+            raise _failure("inbox-path-changed", f"Entry {parent.relative / name} changed")
+        return fd, identity, _metadata(result)
+    except OSError as error:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not inspect open entry {parent.relative / name}",
+            error,
+        )
+    except BaseException:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        raise
+
+
+def read_all_fd(fd: int) -> bytes:
+    chunks: list[bytes] = []
+    offset = 0
+    while True:
+        try:
+            chunk = os.pread(fd, 1024 * 1024, offset)
+        except InterruptedError:
+            continue
+        except OSError as error:
+            _raise_os("inbox-path-operation-failed", "Could not read bound file", error)
+        if not chunk:
+            return b"".join(chunks)
+        chunks.append(chunk)
+        offset += len(chunk)
+
+
+def write_all_fd(fd: int, payload: bytes) -> None:
+    remaining = memoryview(payload)
+    while remaining:
+        try:
+            written = os.write(fd, remaining)
+        except InterruptedError:
+            continue
+        except OSError as error:
+            _raise_os("inbox-path-operation-failed", "Could not write bound file", error)
+        if written <= 0:
+            error = OSError(errno.EIO, "write returned no progress")
+            _raise_os("inbox-path-operation-failed", "Could not write bound file", error)
+        remaining = remaining[written:]
+
+
+def fsync_fd(fd: int) -> None:
+    try:
+        os.fsync(fd)
+    except OSError as error:
+        _raise_os("inbox-path-durability-failed", "Could not fsync bound file", error)
+
+
+def fsync_directory(parent: BoundDirectory) -> None:
+    _require_parent(parent)
+    try:
+        os.fsync(parent.fd)
+    except OSError as error:
+        _raise_os(
+            "inbox-path-durability-failed",
+            f"Could not fsync directory {parent.relative}",
+            error,
+        )
+
+
+def sha256_bytes(payload: bytes) -> str:
+    return "sha256:" + hashlib.sha256(payload).hexdigest()
+
+
+def entry_exists_at(parent: BoundDirectory, name: str) -> bool:
+    _require_parent(parent)
+    name = _validate_name(name)
+    try:
+        os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
+    except FileNotFoundError:
+        return False
+    except OSError as error:
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not inspect entry {parent.relative / name}",
+            error,
+        )
+    return True
+
+
+def verify_regular_binding_at(
+    parent: BoundDirectory, name: str, fd: int
+) -> FileIdentity:
+    _require_parent(parent)
+    name = _validate_name(name)
+    lexical = _lexical_regular_stat(parent, name)
+    try:
+        opened = os.fstat(fd)
+    except OSError as error:
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not inspect bound entry {parent.relative / name}",
+            error,
+        )
+    if not stat.S_ISREG(opened.st_mode):
+        raise _failure(
+            "unsafe-inbox-path", f"Entry {parent.relative / name} is not regular"
+        )
+    opened_identity = _identity(opened)
+    if opened_identity != _identity(lexical):
+        raise _failure("inbox-path-changed", f"Entry {parent.relative / name} changed")
+    return opened_identity
+
+
+def read_regular_at(
+    parent: BoundDirectory, name: str
+) -> tuple[int, bytes, FileIdentity, FileMetadata]:
+    fd, identity, metadata = open_regular_at(parent, name)
+    try:
+        payload = read_all_fd(fd)
+        os.lseek(fd, 0, os.SEEK_SET)
+        return fd, payload, identity, metadata
+    except InboxTransactionError:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        raise
+    except OSError as error:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not reset entry {parent.relative / name}",
+            error,
+        )
+
+
+def write_new_durable_at(
+    parent: BoundDirectory, name: str, payload: bytes
+) -> tuple[int, FileIdentity]:
+    fd, _ = create_regular_at(parent, name)
+    try:
+        write_all_fd(fd, payload)
+        fsync_fd(fd)
+        identity = verify_regular_binding_at(parent, name, fd)
+        fsync_directory(parent)
+        return fd, identity
+    except InboxTransactionError:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        raise
+    except OSError as error:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not write entry {parent.relative / name}",
+            error,
+        )
+
+
+def link_no_overwrite_at(
+    source_parent: BoundDirectory,
+    source_name: str,
+    destination_parent: BoundDirectory,
+    destination_name: str,
+) -> FileIdentity:
+    _require_parent(source_parent)
+    _require_parent(destination_parent)
+    source_name = _validate_name(source_name)
+    destination_name = _validate_name(destination_name)
+    source = _lexical_regular_stat(source_parent, source_name)
+    source_identity = _identity(source)
+    try:
+        os.link(
+            source_name,
+            destination_name,
+            src_dir_fd=source_parent.fd,
+            dst_dir_fd=destination_parent.fd,
+            follow_symlinks=False,
+        )
+    except FileExistsError as error:
+        _raise_os(
+            "inbox-path-occupied",
+            f"Entry {destination_parent.relative / destination_name} exists",
+            error,
+        )
+    except OSError as error:
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not publish entry {destination_parent.relative / destination_name}",
+            error,
+        )
+    installed = _lexical_regular_stat(destination_parent, destination_name)
+    installed_identity = _identity(installed)
+    if installed_identity != source_identity:
+        raise _failure(
+            "inbox-path-changed",
+            f"Published entry {destination_parent.relative / destination_name} changed",
+        )
+    return installed_identity
+
+
+def _valid_expected_hash(expected_sha256: str) -> bool:
+    if not expected_sha256.startswith("sha256:") or len(expected_sha256) != 71:
+        return False
+    digest = expected_sha256[7:]
+    return digest == digest.lower() and all(c in "0123456789abcdef" for c in digest)
+
+
+def _read_expected(
+    parent: BoundDirectory,
+    name: str,
+    expected_identity: FileIdentity,
+    expected_sha256: str,
+) -> int:
+    if not _valid_expected_hash(expected_sha256):
+        raise _failure("inbox-path-changed", f"Entry {parent.relative / name} hash changed")
+    fd, payload, identity, _ = read_regular_at(parent, name)
+    if identity != expected_identity or sha256_bytes(payload) != expected_sha256:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        raise _failure("inbox-path-changed", f"Entry {parent.relative / name} changed")
+    try:
+        verify_regular_binding_at(parent, name, fd)
+    except BaseException:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+        raise
+    return fd
+
+
+def unlink_expected_at(
+    parent: BoundDirectory,
+    name: str,
+    *,
+    expected_identity: FileIdentity,
+    expected_sha256: str,
+) -> None:
+    _require_parent(parent)
+    name = _validate_name(name)
+    fd = _read_expected(parent, name, expected_identity, expected_sha256)
+    try:
+        os.unlink(name, dir_fd=parent.fd)
+        if entry_exists_at(parent, name):
+            raise _failure("inbox-path-changed", f"Entry {parent.relative / name} remains")
+    except FileNotFoundError as error:
+        _raise_os("inbox-path-changed", f"Entry {parent.relative / name} changed", error)
+    except InboxTransactionError:
+        raise
+    except OSError as error:
+        _raise_os(
+            "inbox-path-operation-failed",
+            f"Could not unlink entry {parent.relative / name}",
+            error,
+        )
+    finally:
+        try:
+            os.close(fd)
+        except OSError:
+            pass
+
+
+def replace_expected_at(
+    parent: BoundDirectory,
+    source_name: str,
+    destination_name: str,
+    *,
+    expected_source_identity: FileIdentity,
+    expected_source_sha256: str,
+    expected_destination_identity: FileIdentity,
+    expected_destination_sha256: str,
+) -> FileIdentity:
+    _require_parent(parent)
+    source_name = _validate_name(source_name)
+    destination_name = _validate_name(destination_name)
+    source_fd = _read_expected(
+        parent, source_name, expected_source_identity, expected_source_sha256
+    )
+    destination_fd: int | None = None
+    try:
+        destination_fd = _read_expected(
+            parent,
+            destination_name,
+            expected_destination_identity,
+            expected_destination_sha256,
+        )
+        verify_regular_binding_at(parent, source_name, source_fd)
+        verify_regular_binding_at(parent, destination_name, destination_fd)
+        try:
+            os.replace(
+                source_name,
+                destination_name,
+                src_dir_fd=parent.fd,
+                dst_dir_fd=parent.fd,
+            )
+        except FileNotFoundError as error:
+            _raise_os("inbox-path-changed", "Replace entries changed", error)
+        except OSError as error:
+            _raise_os(
+                "inbox-path-operation-failed",
+                f"Could not replace entry {parent.relative / destination_name}",
+                error,
+            )
+        if entry_exists_at(parent, source_name):
+            raise _failure(
+                "inbox-path-changed", f"Entry {parent.relative / source_name} remains"
+            )
+        installed = verify_regular_binding_at(parent, destination_name, source_fd)
+        if installed != expected_source_identity:
+            raise _failure(
+                "inbox-path-changed",
+                f"Entry {parent.relative / destination_name} changed",
+            )
+        return installed
+    finally:
+        if destination_fd is not None:
+            try:
+                os.close(destination_fd)
+            except OSError:
+                pass
+        try:
+            os.close(source_fd)
+        except OSError:
+            pass
diff --git a/tests/test_inbox_tx_paths.py b/tests/test_inbox_tx_paths.py
new file mode 100644
index 0000000..c83687b
--- /dev/null
+++ b/tests/test_inbox_tx_paths.py
@@ -0,0 +1,841 @@
+from __future__ import annotations
+
+import dataclasses
+import os
+import stat
+from collections import Counter
+from pathlib import Path
+
+import pytest
+
+from obsidian_kb_skill.scripts.inbox_tx.models import FileIdentity, InboxTransactionError
+from obsidian_kb_skill.scripts.inbox_tx.paths import (
+    BoundDirectory,
+    CapabilityProviders,
+    CapabilitySupport,
+    LocalMutationCapabilityProbe,
+    LocalPreviewCapabilityProbe,
+    PreviewCapabilitySupport,
+    VaultCapability,
+    create_regular_at,
+    default_capability_providers,
+    entry_exists_at,
+    fsync_directory,
+    fsync_fd,
+    link_no_overwrite_at,
+    open_regular_at,
+    read_all_fd,
+    read_regular_at,
+    replace_expected_at,
+    sha256_bytes,
+    unlink_expected_at,
+    validate_business_relative,
+    validate_recovery_relative,
+    verify_regular_binding_at,
+    write_all_fd,
+    write_new_durable_at,
+)
+
+
+def _vault(tmp_path: Path) -> Path:
+    vault = tmp_path / "vault"
+    (vault / "00-Inbox" / "nested").mkdir(parents=True)
+    (vault / "30-Insights").mkdir()
+    (vault / ".obsidian-kb-backups").mkdir()
+    return vault
+
+
+def _assert_code(caught: pytest.ExceptionInfo[InboxTransactionError], code: str) -> None:
+    failure = caught.value.failure
+    assert failure.code == code
+    assert failure.restore_id is None
+    assert failure.recovery_location is None
+    assert failure.warnings == ()
+    assert failure.recovery_debris is None
+    assert failure.business_mutation_started is False
+
+
+@pytest.mark.parametrize(
+    "relative",
+    [
+        Path("."),
+        Path("../outside.md"),
+        Path("00-Inbox/../outside.md"),
+        Path("/absolute.md"),
+        Path("C:\\outside\\note.md"),
+        Path("\\\\server\\share\\note.md"),
+        Path(".obsidian-kb-backups/x.md"),
+        Path(".obsidian-kb-backups/x/y.md"),
+    ],
+)
+def test_business_validator_rejects_unsafe_or_control_paths(relative: Path) -> None:
+    with pytest.raises(InboxTransactionError) as caught:
+        validate_business_relative(relative, label="Inbox source")
+    _assert_code(caught, "unsafe-inbox-business-path")
+
+
+@pytest.mark.parametrize(
+    "relative",
+    [
+        Path("."),
+        Path("../outside.md"),
+        Path("records/../outside.md"),
+        Path("/absolute.md"),
+        Path("D:\\outside\\record.json"),
+        Path("\\\\server\\share\\record.json"),
+    ],
+)
+def test_recovery_validator_rejects_unsafe_paths(relative: Path) -> None:
+    with pytest.raises(InboxTransactionError) as caught:
+        validate_recovery_relative(relative, label="Recovery record")
+    _assert_code(caught, "unsafe-inbox-recovery-path")
+
+
+def test_validators_accept_nested_paths_and_posix_literal_backslash() -> None:
+    assert validate_business_relative(Path("00-Inbox/nested/A.md"), label="source") == Path(
+        "00-Inbox/nested/A.md"
+    )
+    assert validate_recovery_relative(
+        Path(".obsidian-kb-backups/records/r.json"), label="record"
+    ) == Path(".obsidian-kb-backups/records/r.json")
+    if os.name != "nt":
+        assert validate_business_relative(Path(r"00-Inbox/A\B.md"), label="source") == Path(
+            r"00-Inbox/A\B.md"
+        )
+
+
+@pytest.mark.parametrize(
+    ("supported", "serialization"),
+    [(False, None), (True, "shared-lock"), (True, "double-read")],
+)
+def test_preview_support_accepts_exact_consistent_combinations(
+    supported: bool, serialization: str | None
+) -> None:
+    value = PreviewCapabilitySupport(supported, None, None, serialization)  # type: ignore[arg-type]
+    assert value.supported is supported
+    assert value.serialization == serialization
+
+
+@pytest.mark.parametrize(
+    ("supported", "serialization"),
+    [(True, None), (False, "shared-lock"), (False, "double-read")],
+)
+def test_preview_support_rejects_inconsistent_combinations(
+    supported: bool, serialization: str | None
+) -> None:
+    with pytest.raises(ValueError, match="preview support and serialization must agree"):
+        PreviewCapabilitySupport(supported, None, None, serialization)  # type: ignore[arg-type]
+
+
+def test_capability_provider_bundle_is_frozen_and_accepts_fakes(tmp_path: Path) -> None:
+    class Mutation:
+        def probe(self, vault: Path) -> CapabilitySupport:
+            return CapabilitySupport(True, None, None)
+
+    class Preview:
+        def probe(self, vault: Path) -> PreviewCapabilitySupport:
+            return PreviewCapabilitySupport(True, None, None, "double-read")
+
+    providers = CapabilityProviders(Mutation(), Preview())
+    assert providers.mutation.probe(tmp_path).supported
+    assert providers.preview.probe(tmp_path).serialization == "double-read"
+    with pytest.raises(dataclasses.FrozenInstanceError):
+        providers.mutation = Mutation()  # type: ignore[misc]
+
+
+def test_default_capability_providers_returns_new_stateless_adapters() -> None:
+    first = default_capability_providers()
+    second = default_capability_providers()
+    assert isinstance(first.mutation, LocalMutationCapabilityProbe)
+    assert isinstance(first.preview, LocalPreviewCapabilityProbe)
+    assert first is not second
+    assert first.mutation is not second.mutation
+    assert first.preview is not second.preview
+
+
+def test_preview_probe_uses_shared_lock_or_double_read_without_mutation(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    before = sorted(p.relative_to(vault) for p in vault.rglob("*"))
+    result = LocalPreviewCapabilityProbe().probe(vault)
+    after = sorted(p.relative_to(vault) for p in vault.rglob("*"))
+    assert result.supported
+    assert result.serialization in {"shared-lock", "double-read"}
+    assert before == after
+
+    monkeypatch.setattr("obsidian_kb_skill.scripts.inbox_tx.paths._flock_available", lambda: False)
+    fallback = LocalPreviewCapabilityProbe().probe(vault)
+    assert fallback == PreviewCapabilitySupport(True, None, None, "double-read")
+
+
+def test_probes_are_distinct_and_preview_fails_before_record_open_when_binding_missing(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    monkeypatch.setattr("obsidian_kb_skill.scripts.inbox_tx.paths._secure_binding_support", lambda: False)
+    preview = LocalPreviewCapabilityProbe().probe(vault)
+    mutation = LocalMutationCapabilityProbe().probe(vault)
+    assert preview.code == "unsupported-inbox-preview"
+    assert preview.serialization is None
+    assert mutation.supported
+
+
+def test_mutation_probe_is_read_only_and_checks_root_fsync(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    calls: list[int] = []
+    real_fsync = os.fsync
+
+    def tracing_fsync(fd: int) -> None:
+        calls.append(fd)
+        real_fsync(fd)
+
+    monkeypatch.setattr(os, "fsync", tracing_fsync)
+    before = sorted(p.relative_to(vault) for p in vault.rglob("*"))
+    result = LocalMutationCapabilityProbe().probe(vault)
+    assert result.supported
+    assert calls
+    assert sorted(p.relative_to(vault) for p in vault.rglob("*")) == before
+
+
+@pytest.mark.parametrize("feature", ["dir_fd", "nofollow", "directory_fsync", "hard_link"])
+def test_mutation_probe_reports_each_missing_required_primitive(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, feature: str
+) -> None:
+    vault = _vault(tmp_path)
+    module = "obsidian_kb_skill.scripts.inbox_tx.paths"
+    if feature == "dir_fd":
+        monkeypatch.setattr(f"{module}._required_dir_fd_support", lambda: False)
+    elif feature == "nofollow":
+        monkeypatch.setattr(f"{module}._nofollow_available", lambda: False)
+    elif feature == "directory_fsync":
+        monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("no dir fsync")))
+    else:
+        monkeypatch.setattr(f"{module}._hard_link_available", lambda: False)
+    result = LocalMutationCapabilityProbe().probe(vault)
+    assert result.supported is False
+    assert result.code == "unsupported-inbox-mutation"
+
+
+def test_preview_probe_does_not_require_flock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    vault = _vault(tmp_path)
+    monkeypatch.setattr("obsidian_kb_skill.scripts.inbox_tx.paths._flock_available", lambda: False)
+    assert LocalPreviewCapabilityProbe().probe(vault).serialization == "double-read"
+    mutation = LocalMutationCapabilityProbe().probe(vault)
+    assert mutation == CapabilitySupport(
+        False,
+        "unsupported-inbox-mutation",
+        "Advisory file locking is unavailable",
+    )
+
+
+def test_vault_open_preserves_root_resolution_oserror_as_cause(tmp_path: Path) -> None:
+    with pytest.raises(InboxTransactionError) as caught:
+        VaultCapability.open(tmp_path / "missing-vault")
+    assert isinstance(caught.value.__cause__, OSError)
+
+
+def test_vault_open_failure_closes_locally_opened_fd(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    opened: list[int] = []
+    closed: list[int] = []
+    real_open = os.open
+    real_close = os.close
+
+    def tracing_open(*args: object, **kwargs: object) -> int:
+        fd = real_open(*args, **kwargs)  # type: ignore[arg-type]
+        opened.append(fd)
+        return fd
+
+    def tracing_close(fd: int) -> None:
+        closed.append(fd)
+        real_close(fd)
+
+    monkeypatch.setattr(os, "open", tracing_open)
+    monkeypatch.setattr(os, "close", tracing_close)
+    monkeypatch.setattr(os, "fstat", lambda fd: (_ for _ in ()).throw(OSError("fstat failed")))
+    with pytest.raises(InboxTransactionError) as caught:
+        VaultCapability.open(vault)
+    _assert_code(caught, "inbox-path-operation-failed")
+    assert closed == list(reversed(opened))
+
+
+def test_root_and_nested_bound_directories_have_distinct_owned_fds_and_chains(
+    tmp_path: Path,
+) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability:
+        with capability.open_directory(Path(".")) as root, capability.open_directory(
+            Path("00-Inbox/nested")
+        ) as nested:
+            assert len({capability.fd, root.fd, nested.fd}) == 3
+            assert root.relative == Path(".")
+            assert [item.relative for item in root.chain] == [Path(".")]
+            assert [item.relative for item in nested.chain] == [
+                Path("."),
+                Path("00-Inbox"),
+                Path("00-Inbox/nested"),
+            ]
+            with pytest.raises((AttributeError, TypeError)):
+                nested.chain[0].relative = Path("changed")  # type: ignore[misc]
+
+
+def test_open_directory_closes_new_child_before_parent_when_local_close_fails(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability:
+        acquired: list[int] = []
+        closed: list[int] = []
+        real_open = os.open
+        real_close = os.close
+        injected = False
+
+        def trace_open(*args: object, **kwargs: object) -> int:
+            fd = real_open(*args, **kwargs)  # type: ignore[arg-type]
+            acquired.append(fd)
+            return fd
+
+        def fail_once(fd: int) -> None:
+            nonlocal injected
+            if not injected:
+                injected = True
+                raise OSError("injected local close failure")
+            closed.append(fd)
+            real_close(fd)
+
+        monkeypatch.setattr(os, "open", trace_open)
+        monkeypatch.setattr(os, "close", fail_once)
+        try:
+            with pytest.raises(InboxTransactionError):
+                capability.open_directory(Path("00-Inbox"))
+            assert closed == list(reversed(acquired))
+        finally:
+            for fd in acquired:
+                try:
+                    real_close(fd)
+                except OSError:
+                    pass
+
+
+@pytest.mark.parametrize("symlink_depth", [0, 1])
+def test_open_directory_rejects_symlink_at_every_ancestor_depth(
+    tmp_path: Path, symlink_depth: int
+) -> None:
+    vault = _vault(tmp_path)
+    outside = tmp_path / "outside"
+    (outside / "nested").mkdir(parents=True)
+    if symlink_depth == 0:
+        (vault / "link").symlink_to(outside, target_is_directory=True)
+        relative = Path("link/nested")
+    else:
+        (vault / "00-Inbox" / "link").symlink_to(outside, target_is_directory=True)
+        relative = Path("00-Inbox/link/nested")
+    with VaultCapability.open(vault) as capability:
+        with pytest.raises(InboxTransactionError) as caught:
+            capability.open_directory(relative)
+    _assert_code(caught, "unsafe-inbox-path")
+
+
+def test_open_directory_rejects_non_directory_and_public_chain_replacement(
+    tmp_path: Path,
+) -> None:
+    vault = _vault(tmp_path)
+    (vault / "not-dir").write_text("x", encoding="utf-8")
+    with VaultCapability.open(vault) as capability:
+        with pytest.raises(InboxTransactionError) as caught:
+            capability.open_directory(Path("not-dir"))
+        _assert_code(caught, "unsafe-inbox-path")
+
+        bound = capability.open_directory(Path("00-Inbox/nested"))
+        (vault / "00-Inbox" / "nested").rename(vault / "00-Inbox" / "old")
+        (vault / "00-Inbox" / "nested").mkdir()
+        try:
+            with pytest.raises(InboxTransactionError) as changed:
+                capability.revalidate_public_chain(bound)
+            _assert_code(changed, "inbox-path-changed")
+        finally:
+            bound.close()
+
+
+def test_public_chain_revalidation_compares_only_directory_device_and_inode(
+    tmp_path: Path,
+) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox/nested")
+    ) as bound:
+        (vault / "00-Inbox" / "sibling.md").write_text("metadata change", encoding="utf-8")
+        capability.revalidate_public_chain(bound)
+
+
+def test_ensure_and_create_directory_are_durable_and_exclusive(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    real_fsync = os.fsync
+    fsyncs: list[int] = []
+
+    def trace(fd: int) -> None:
+        fsyncs.append(fd)
+        real_fsync(fd)
+
+    monkeypatch.setattr(os, "fsync", trace)
+    with VaultCapability.open(vault) as capability:
+        with capability.ensure_directory(Path("new/a/b")) as made:
+            assert made.relative == Path("new/a/b")
+            assert stat.S_ISDIR(os.fstat(made.fd).st_mode)
+        assert len(fsyncs) == 3
+
+        with capability.create_directory(Path("single")) as made:
+            assert made.relative == Path("single")
+        assert len(fsyncs) == 4
+        with pytest.raises(InboxTransactionError) as occupied:
+            capability.create_directory(Path("single"))
+        _assert_code(occupied, "inbox-path-occupied")
+
+
+def test_ensure_directory_closes_every_local_fd_when_child_fstat_fails(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability:
+        acquired: list[int] = []
+        closed: list[int] = []
+        real_open = os.open
+        real_dup = os.dup
+        real_close = os.close
+        real_fstat = os.fstat
+        fstat_calls = 0
+
+        def trace_open(*args: object, **kwargs: object) -> int:
+            fd = real_open(*args, **kwargs)  # type: ignore[arg-type]
+            acquired.append(fd)
+            return fd
+
+        def trace_dup(fd: int) -> int:
+            duplicate = real_dup(fd)
+            acquired.append(duplicate)
+            return duplicate
+
+        def trace_close(fd: int) -> None:
+            closed.append(fd)
+            real_close(fd)
+
+        def fail_child_identity(fd: int) -> os.stat_result:
+            nonlocal fstat_calls
+            fstat_calls += 1
+            if fstat_calls == 4:
+                raise OSError("injected child fstat failure")
+            return real_fstat(fd)
+
+        monkeypatch.setattr(os, "open", trace_open)
+        monkeypatch.setattr(os, "dup", trace_dup)
+        monkeypatch.setattr(os, "close", trace_close)
+        monkeypatch.setattr(os, "fstat", fail_child_identity)
+        with pytest.raises(InboxTransactionError):
+            capability.ensure_directory(Path("00-Inbox"))
+        assert Counter(closed) == Counter(acquired)
+
+
+def test_capability_close_is_idempotent_and_owner_independent(tmp_path: Path) -> None:
+    vault = _vault(tmp_path)
+    capability = VaultCapability.open(vault)
+    child = capability.open_directory(Path("00-Inbox"))
+    root_fd = capability.fd
+    child_fd = child.fd
+    assert capability.close() == ()
+    assert capability.close() == ()
+    with pytest.raises(OSError):
+        os.fstat(root_fd)
+    assert os.fstat(child_fd)
+    with pytest.raises(InboxTransactionError) as caught:
+        capability.open_directory(Path("00-Inbox"))
+    _assert_code(caught, "inbox-capability-closed")
+    assert child.fileno() == child_fd
+    assert child.close() == ()
+    assert child.close() == ()
+    with pytest.raises(InboxTransactionError) as child_closed:
+        child.fileno()
+    _assert_code(child_closed, "inbox-capability-closed")
+
+
+def test_close_errors_return_relative_warnings_without_leaking_root(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    capability = VaultCapability.open(vault)
+    child = capability.open_directory(Path("00-Inbox"))
+    real_close = os.close
+    doomed = {capability.fd, child.fd}
+
+    def fail_selected(fd: int) -> None:
+        if fd in doomed:
+            doomed.remove(fd)
+            real_close(fd)
+            raise OSError("injected close failure")
+        real_close(fd)
+
+    monkeypatch.setattr(os, "close", fail_selected)
+    child_warnings = child.close()
+    root_warnings = capability.close()
+    assert child_warnings and root_warnings
+    assert str(vault) not in " ".join(child_warnings + root_warnings)
+    assert child.close() == ()
+    assert capability.close() == ()
+
+
+def test_create_open_read_and_verify_regular_fd_ownership(tmp_path: Path) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as parent:
+        fd, created_identity = create_regular_at(parent, "note.md")
+        try:
+            write_all_fd(fd, b"payload")
+            fsync_fd(fd)
+            assert os.fstat(fd)
+        finally:
+            os.close(fd)
+        fsync_directory(parent)
+
+        read_fd, identity, metadata = open_regular_at(parent, "note.md")
+        try:
+            assert identity.device == created_identity.device
+            assert stat.S_ISREG(metadata.mode)
+            assert verify_regular_binding_at(parent, "note.md", read_fd) == identity
+        finally:
+            os.close(read_fd)
+
+        returned_fd, payload, read_identity, read_metadata = read_regular_at(parent, "note.md")
+        try:
+            assert payload == b"payload"
+            assert os.lseek(returned_fd, 0, os.SEEK_CUR) == 0
+            assert read_identity == identity
+            assert read_metadata == metadata
+        finally:
+            os.close(returned_fd)
+
+
+def test_regular_helpers_reject_dangling_symlink_fifo_and_bad_names(tmp_path: Path) -> None:
+    vault = _vault(tmp_path)
+    (vault / "00-Inbox" / "dangling").symlink_to(vault / "missing")
+    fifo = vault / "00-Inbox" / "pipe"
+    try:
+        os.mkfifo(fifo)
+    except (AttributeError, OSError):
+        pytest.skip("FIFO unavailable")
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as parent:
+        assert entry_exists_at(parent, "dangling") is True
+        assert entry_exists_at(parent, "missing") is False
+        for name in ("dangling", "pipe"):
+            with pytest.raises(InboxTransactionError) as caught:
+                open_regular_at(parent, name)
+            _assert_code(caught, "unsafe-inbox-path")
+        for name in ("", ".", "..", f"a{os.sep}b"):
+            with pytest.raises(InboxTransactionError) as caught:
+                create_regular_at(parent, name)
+            _assert_code(caught, "unsafe-inbox-path")
+        if os.name != "nt":
+            fd, _ = create_regular_at(parent, r"literal\backslash.md")
+            os.close(fd)
+
+
+def test_exclusive_create_and_open_failure_do_not_transfer_fd(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as parent:
+        fd, _ = create_regular_at(parent, "existing.md")
+        os.close(fd)
+        with pytest.raises(InboxTransactionError) as occupied:
+            create_regular_at(parent, "existing.md")
+        _assert_code(occupied, "inbox-path-occupied")
+
+        closed: list[int] = []
+        real_close = os.close
+        real_fstat = os.fstat
+
+        def close(fd: int) -> None:
+            closed.append(fd)
+            real_close(fd)
+
+        def fail_file_fstat(fd: int) -> os.stat_result:
+            result = real_fstat(fd)
+            if stat.S_ISREG(result.st_mode):
+                raise OSError("injected")
+            return result
+
+        monkeypatch.setattr(os, "close", close)
+        monkeypatch.setattr(os, "fstat", fail_file_fstat)
+        with pytest.raises(InboxTransactionError):
+            open_regular_at(parent, "existing.md")
+        assert closed
+
+
+def test_read_all_fd_handles_short_reads_without_changing_offset(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    file = tmp_path / "short-read"
+    file.write_bytes(b"abcdefgh")
+    fd = os.open(file, os.O_RDONLY)
+    real_pread = os.pread
+
+    def short_pread(target_fd: int, amount: int, offset: int) -> bytes:
+        return real_pread(target_fd, min(amount, 2), offset)
+
+    monkeypatch.setattr(os, "pread", short_pread)
+    try:
+        os.lseek(fd, 3, os.SEEK_SET)
+        assert read_all_fd(fd) == b"abcdefgh"
+        assert os.lseek(fd, 0, os.SEEK_CUR) == 3
+    finally:
+        os.close(fd)
+
+
+def test_write_all_fd_handles_short_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    file = tmp_path / "short-write"
+    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
+    real_write = os.write
+
+    def short_write(target_fd: int, payload: bytes | memoryview) -> int:
+        return real_write(target_fd, payload[:2])
+
+    monkeypatch.setattr(os, "write", short_write)
+    try:
+        write_all_fd(fd, b"abcdefgh")
+    finally:
+        os.close(fd)
+    assert file.read_bytes() == b"abcdefgh"
+
+
+def test_write_new_durable_orders_create_write_file_and_parent_fsync(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    events: list[str] = []
+    module = "obsidian_kb_skill.scripts.inbox_tx.paths"
+    import obsidian_kb_skill.scripts.inbox_tx.paths as paths
+
+    real_create = paths.create_regular_at
+    real_write = paths.write_all_fd
+    real_fsync_fd = paths.fsync_fd
+    real_fsync_directory = paths.fsync_directory
+    monkeypatch.setattr(module + ".create_regular_at", lambda *a, **k: (events.append("create"), real_create(*a, **k))[1])
+    monkeypatch.setattr(module + ".write_all_fd", lambda *a, **k: (events.append("write"), real_write(*a, **k))[1])
+    monkeypatch.setattr(module + ".fsync_fd", lambda *a, **k: (events.append("file-fsync"), real_fsync_fd(*a, **k))[1])
+    monkeypatch.setattr(module + ".fsync_directory", lambda *a, **k: (events.append("parent-fsync"), real_fsync_directory(*a, **k))[1])
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as parent:
+        fd, identity = write_new_durable_at(parent, "durable.md", b"payload")
+        try:
+            assert os.fstat(fd).st_ino == identity.inode
+        finally:
+            os.close(fd)
+    assert events == ["create", "write", "file-fsync", "parent-fsync"]
+
+
+def test_write_new_durable_closes_local_fd_on_failure(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    closed: list[int] = []
+    real_close = os.close
+    monkeypatch.setattr(
+        "obsidian_kb_skill.scripts.inbox_tx.paths.write_all_fd",
+        lambda fd, payload: (_ for _ in ()).throw(OSError("injected short write failure")),
+    )
+
+    def trace_close(fd: int) -> None:
+        closed.append(fd)
+        real_close(fd)
+
+    monkeypatch.setattr(os, "close", trace_close)
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as parent:
+        with pytest.raises(InboxTransactionError) as caught:
+            write_new_durable_at(parent, "failure.md", b"payload")
+        _assert_code(caught, "inbox-path-operation-failed")
+        assert closed
+
+
+def test_link_is_no_overwrite_and_exposes_parent_fsync_boundary(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as source_parent, capability.open_directory(Path("30-Insights")) as destination_parent:
+        source_fd, source_identity = write_new_durable_at(source_parent, "source.md", b"source")
+        os.close(source_fd)
+        fsyncs: list[int] = []
+        real_fsync = os.fsync
+        monkeypatch.setattr(
+            os,
+            "fsync",
+            lambda target_fd: (fsyncs.append(target_fd), real_fsync(target_fd))[1],
+        )
+        linked = link_no_overwrite_at(source_parent, "source.md", destination_parent, "public.md")
+        assert linked == source_identity
+        assert (vault / "30-Insights" / "public.md").read_bytes() == b"source"
+        assert fsyncs == []
+        fsync_directory(destination_parent)
+        assert fsyncs == [destination_parent.fd]
+        with pytest.raises(InboxTransactionError) as occupied:
+            link_no_overwrite_at(source_parent, "source.md", destination_parent, "public.md")
+        _assert_code(occupied, "inbox-path-occupied")
+
+
+def test_unlink_requires_identity_and_hash_and_preserves_mismatch(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    payload = b"expected"
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as parent:
+        fd, identity = write_new_durable_at(parent, "note.md", payload)
+        os.close(fd)
+        wrong_identity = dataclasses.replace(identity, size=identity.size + 1)
+        with pytest.raises(InboxTransactionError) as changed:
+            unlink_expected_at(
+                parent,
+                "note.md",
+                expected_identity=wrong_identity,
+                expected_sha256=sha256_bytes(payload),
+            )
+        _assert_code(changed, "inbox-path-changed")
+        assert (vault / "00-Inbox" / "note.md").read_bytes() == payload
+
+        with pytest.raises(InboxTransactionError) as hash_changed:
+            unlink_expected_at(
+                parent,
+                "note.md",
+                expected_identity=identity,
+                expected_sha256=sha256_bytes(b"wrong"),
+            )
+        _assert_code(hash_changed, "inbox-path-changed")
+        assert (vault / "00-Inbox" / "note.md").read_bytes() == payload
+
+        fsyncs: list[int] = []
+        real_fsync = os.fsync
+        monkeypatch.setattr(os, "fsync", lambda target_fd: (fsyncs.append(target_fd), real_fsync(target_fd))[1])
+        unlink_expected_at(
+            parent,
+            "note.md",
+            expected_identity=identity,
+            expected_sha256=sha256_bytes(payload),
+        )
+        assert not entry_exists_at(parent, "note.md")
+        assert fsyncs == []
+        fsync_directory(parent)
+        assert fsyncs == [parent.fd]
+
+
+def test_replace_requires_both_identities_and_hashes_and_preserves_mismatch(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as parent:
+        source_fd, source_identity = write_new_durable_at(parent, "source.md", b"new")
+        destination_fd, destination_identity = write_new_durable_at(parent, "destination.md", b"old")
+        os.close(source_fd)
+        os.close(destination_fd)
+
+        mismatches = [
+            {
+                "expected_source_identity": dataclasses.replace(
+                    source_identity, inode=source_identity.inode + 1
+                ),
+                "expected_source_sha256": sha256_bytes(b"new"),
+                "expected_destination_identity": destination_identity,
+                "expected_destination_sha256": sha256_bytes(b"old"),
+            },
+            {
+                "expected_source_identity": source_identity,
+                "expected_source_sha256": sha256_bytes(b"wrong"),
+                "expected_destination_identity": destination_identity,
+                "expected_destination_sha256": sha256_bytes(b"old"),
+            },
+            {
+                "expected_source_identity": source_identity,
+                "expected_source_sha256": sha256_bytes(b"new"),
+                "expected_destination_identity": dataclasses.replace(
+                    destination_identity, size=destination_identity.size + 1
+                ),
+                "expected_destination_sha256": sha256_bytes(b"old"),
+            },
+            {
+                "expected_source_identity": source_identity,
+                "expected_source_sha256": sha256_bytes(b"new"),
+                "expected_destination_identity": destination_identity,
+                "expected_destination_sha256": sha256_bytes(b"wrong"),
+            },
+        ]
+        for mismatch in mismatches:
+            with pytest.raises(InboxTransactionError) as changed:
+                replace_expected_at(parent, "source.md", "destination.md", **mismatch)
+            _assert_code(changed, "inbox-path-changed")
+            assert (vault / "00-Inbox/source.md").read_bytes() == b"new"
+            assert (vault / "00-Inbox/destination.md").read_bytes() == b"old"
+
+        fsyncs: list[int] = []
+        real_fsync = os.fsync
+        monkeypatch.setattr(
+            os,
+            "fsync",
+            lambda target_fd: (fsyncs.append(target_fd), real_fsync(target_fd))[1],
+        )
+        installed = replace_expected_at(
+            parent,
+            "source.md",
+            "destination.md",
+            expected_source_identity=source_identity,
+            expected_source_sha256=sha256_bytes(b"new"),
+            expected_destination_identity=destination_identity,
+            expected_destination_sha256=sha256_bytes(b"old"),
+        )
+        assert installed == source_identity
+        assert not entry_exists_at(parent, "source.md")
+        assert (vault / "00-Inbox/destination.md").read_bytes() == b"new"
+        assert fsyncs == []
+        fsync_directory(parent)
+        assert fsyncs == [parent.fd]
+
+
+def test_identity_guards_require_sha256_scheme(tmp_path: Path) -> None:
+    vault = _vault(tmp_path)
+    with VaultCapability.open(vault) as capability, capability.open_directory(
+        Path("00-Inbox")
+    ) as parent:
+        fd, identity = write_new_durable_at(parent, "note.md", b"payload")
+        os.close(fd)
+        with pytest.raises(InboxTransactionError) as changed:
+            unlink_expected_at(
+                parent,
+                "note.md",
+                expected_identity=identity,
+                expected_sha256="not-a-sha256",
+            )
+        _assert_code(changed, "inbox-path-changed")
+        assert entry_exists_at(parent, "note.md")
+
+
+def test_sha256_format_is_exact() -> None:
+    digest = sha256_bytes(b"payload")
+    assert digest.startswith("sha256:")
+    assert len(digest) == len("sha256:") + 64
+    assert digest.removeprefix("sha256:") == digest.removeprefix("sha256:").lower()
+    int(digest.removeprefix("sha256:"), 16)
