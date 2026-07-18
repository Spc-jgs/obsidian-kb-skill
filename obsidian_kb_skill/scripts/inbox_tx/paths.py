"""Descriptor-bound path capabilities for Inbox transactions.

All public filesystem operations in this module are relative to an already
bound directory descriptor.  Passing a verified, free-floating absolute path
to a later mutation is deliberately avoided.
"""
from __future__ import annotations

import errno
import hashlib
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from obsidian_kb_skill.scripts.inbox_tx.models import (
    FileIdentity,
    FileMetadata,
    InboxFailure,
    InboxTransactionError,
)
from obsidian_kb_skill.scripts.vault_paths import validate_vault_root


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


def _unsupported_mutation(message: str) -> CapabilitySupport:
    return CapabilitySupport(False, "unsupported-inbox-mutation", message)


def _unsupported_preview(message: str) -> PreviewCapabilitySupport:
    return PreviewCapabilitySupport(False, "unsupported-inbox-preview", message, None)


def _nofollow_available() -> bool:
    return bool(getattr(os, "O_NOFOLLOW", 0) and getattr(os, "O_DIRECTORY", 0))


def _required_dir_fd_support() -> bool:
    required = (os.open, os.stat, os.mkdir, os.unlink, os.link)
    return all(function in os.supports_dir_fd for function in required)


def _secure_binding_support() -> bool:
    return _nofollow_available() and all(
        function in os.supports_dir_fd for function in (os.open, os.stat)
    )


def _hard_link_available() -> bool:
    return callable(getattr(os, "link", None)) and os.link in os.supports_dir_fd


def _flock_available() -> bool:
    try:
        import fcntl
    except ImportError:
        return False
    return callable(getattr(fcntl, "flock", None))


class LocalMutationCapabilityProbe:
    def probe(self, vault: Path) -> CapabilitySupport:
        if sys.version_info < (3, 11):
            return _unsupported_mutation("Inbox mutation requires CPython 3.11 or newer")
        if sys.platform not in {"linux", "darwin"}:
            return _unsupported_mutation("Inbox mutation is supported only on Linux and macOS")
        if not _required_dir_fd_support():
            return _unsupported_mutation("Required descriptor-relative operations are unavailable")
        if not _nofollow_available():
            return _unsupported_mutation("Safe no-follow directory traversal is unavailable")
        if not _hard_link_available():
            return _unsupported_mutation("Descriptor-relative hard links are unavailable")
        if not _flock_available():
            return _unsupported_mutation("Advisory file locking is unavailable")

        # This is intentionally read-only.  A successful probe says that the
        # local primitives exist; network-mount semantics remain outside the
        # guarantee and the real publication link is still authoritative.
        try:
            with VaultCapability.open(vault) as capability:
                os.fsync(capability.fd)
        except (InboxTransactionError, OSError):
            return _unsupported_mutation("The Vault root cannot provide directory durability")
        return CapabilitySupport(True, None, None)


class LocalPreviewCapabilityProbe:
    def probe(self, vault: Path) -> PreviewCapabilitySupport:
        if not _secure_binding_support():
            return _unsupported_preview("Safe no-follow Vault traversal is unavailable")
        try:
            with VaultCapability.open(vault):
                pass
        except InboxTransactionError:
            return _unsupported_preview("The Vault root cannot be safely bound")
        serialization: Literal["shared-lock", "double-read"]
        serialization = "shared-lock" if _flock_available() else "double-read"
        return PreviewCapabilitySupport(True, None, None, serialization)


@dataclass(frozen=True)
class CapabilityProviders:
    mutation: MutationCapabilityProbe
    preview: PreviewCapabilityProbe


def default_capability_providers() -> CapabilityProviders:
    return CapabilityProviders(LocalMutationCapabilityProbe(), LocalPreviewCapabilityProbe())


@dataclass(frozen=True)
class DirectoryBinding:
    relative: Path
    identity: FileIdentity


def _failure(code: str, message: str) -> InboxTransactionError:
    return InboxTransactionError(
        InboxFailure(
            code=code,
            message=message,
            restore_id=None,
            recovery_location=None,
            warnings=(),
            recovery_debris=None,
            business_mutation_started=False,
        )
    )


def _raise_os(code: str, message: str, error: OSError) -> None:
    raise _failure(code, message) from error


def _identity(result: os.stat_result) -> FileIdentity:
    return FileIdentity(
        device=result.st_dev,
        inode=result.st_ino,
        size=result.st_size,
        mtime_ns=result.st_mtime_ns,
    )


def _same_directory(left: FileIdentity, right: FileIdentity) -> bool:
    return left.device == right.device and left.inode == right.inode


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )


def _regular_flags(*, writable: bool) -> int:
    access = os.O_RDWR if writable else os.O_RDONLY
    return access | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


def _foreign_windows_path(relative: Path) -> bool:
    if os.name == "nt":
        return False
    text = str(relative)
    return text.startswith("\\\\") or (
        len(text) >= 2 and text[0].isalpha() and text[1] == ":"
    )


def _validate_relative(relative: Path, *, label: str, code: str) -> Path:
    path = Path(relative)
    if (
        path.is_absolute()
        or _foreign_windows_path(path)
        or not path.parts
        or str(path) in {"", "."}
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise _failure(code, f"{label} must be a safe nonempty Vault-relative path")
    return path


def validate_business_relative(relative: Path, *, label: str) -> Path:
    path = _validate_relative(
        relative, label=label, code="unsafe-inbox-business-path"
    )
    if path.parts[0] == ".obsidian-kb-backups":
        raise _failure(
            "unsafe-inbox-business-path",
            f"{label} cannot use the Inbox recovery namespace",
        )
    return path


def validate_recovery_relative(relative: Path, *, label: str) -> Path:
    return _validate_relative(relative, label=label, code="unsafe-inbox-recovery-path")


def _validate_directory_relative(relative: Path) -> Path:
    path = Path(relative)
    if str(path) == ".":
        return path
    return _validate_relative(path, label="Directory", code="unsafe-inbox-path")


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise _failure("unsafe-inbox-path", "Entry name must be one safe component")
    if os.sep in name or (os.altsep is not None and os.altsep in name):
        raise _failure("unsafe-inbox-path", "Entry name must be one safe component")
    return name


@dataclass
class BoundDirectory:
    fd: int
    relative: Path
    identity: FileIdentity
    chain: tuple[DirectoryBinding, ...]
    _closed: bool = field(default=False, init=False, repr=False)

    def _require_open(self) -> None:
        if self._closed:
            raise _failure(
                "inbox-capability-closed",
                f"Directory capability {self.relative} is closed",
            )

    def fileno(self) -> int:
        self._require_open()
        return self.fd

    def __enter__(self) -> "BoundDirectory":
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> tuple[str, ...]:
        if self._closed:
            return ()
        self._closed = True
        try:
            os.close(self.fd)
        except OSError:
            return (f"Could not close directory capability {self.relative}",)
        return ()


@dataclass
class VaultCapability:
    root: Path
    fd: int
    identity: FileIdentity
    _closed: bool = field(default=False, init=False, repr=False)

    @classmethod
    def open(cls, vault: Path) -> "VaultCapability":
        opened: list[int] = []
        try:
            root = validate_vault_root(vault)
            fd = os.open(root, _directory_flags())
            opened.append(fd)
            result = os.fstat(fd)
            if not stat.S_ISDIR(result.st_mode):
                raise _failure("unsafe-inbox-path", "Vault root is not a directory")
            capability = cls(root=root, fd=fd, identity=_identity(result))
        except InboxTransactionError:
            for local_fd in reversed(opened):
                try:
                    os.close(local_fd)
                except OSError:
                    pass
            raise
        except OSError as error:
            for local_fd in reversed(opened):
                try:
                    os.close(local_fd)
                except OSError:
                    pass
            _raise_os("inbox-path-operation-failed", "Could not bind the Vault root", error)
        except Exception as error:
            for local_fd in reversed(opened):
                try:
                    os.close(local_fd)
                except OSError:
                    pass
            cause = error.__cause__ if isinstance(error.__cause__, OSError) else error
            raise _failure("unsafe-inbox-path", "Vault root cannot be safely resolved") from cause
        opened.clear()
        return capability

    def _require_open(self) -> None:
        if self._closed:
            raise _failure("inbox-capability-closed", "Vault capability is closed")

    def __enter__(self) -> "VaultCapability":
        self._require_open()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _open_component(self, parent_fd: int, name: str, relative: Path) -> int:
        try:
            fd = os.open(name, _directory_flags(), dir_fd=parent_fd)
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                _raise_os("unsafe-inbox-path", f"Directory {relative} is unsafe", error)
            _raise_os(
                "inbox-path-operation-failed",
                f"Could not open directory {relative}",
                error,
            )
        try:
            result = os.fstat(fd)
            if not stat.S_ISDIR(result.st_mode):
                raise _failure("unsafe-inbox-path", f"Directory {relative} is unsafe")
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            raise
        return fd

    def open_directory(self, relative: Path) -> BoundDirectory:
        self._require_open()
        path = _validate_directory_relative(relative)
        current_fd: int | None = None
        bindings = [DirectoryBinding(Path("."), self.identity)]
        try:
            current_fd = self._open_component(self.fd, ".", Path("."))
            current_identity = _identity(os.fstat(current_fd))
            if not _same_directory(current_identity, self.identity):
                raise _failure("inbox-path-changed", "Vault root identity changed")
            cumulative = Path()
            if path != Path("."):
                for component in path.parts:
                    cumulative = cumulative / component
                    next_fd = self._open_component(current_fd, component, cumulative)
                    try:
                        next_identity = _identity(os.fstat(next_fd))
                    except BaseException:
                        try:
                            os.close(next_fd)
                        except OSError:
                            pass
                        raise
                    try:
                        os.close(current_fd)
                    except BaseException:
                        try:
                            os.close(next_fd)
                        except OSError:
                            pass
                        raise
                    current_fd = next_fd
                    current_identity = next_identity
                    bindings.append(DirectoryBinding(cumulative, current_identity))
            assert current_fd is not None
            bound = BoundDirectory(
                fd=current_fd,
                relative=path,
                identity=current_identity,
                chain=tuple(bindings),
            )
        except InboxTransactionError:
            if current_fd is not None:
                try:
                    os.close(current_fd)
                except OSError:
                    pass
            raise
        except OSError as error:
            if current_fd is not None:
                try:
                    os.close(current_fd)
                except OSError:
                    pass
            _raise_os(
                "inbox-path-operation-failed",
                f"Could not bind directory {path}",
                error,
            )
        current_fd = None
        return bound

    def open_parent(self, relative: Path) -> BoundDirectory:
        self._require_open()
        path = _validate_relative(relative, label="File", code="unsafe-inbox-path")
        parent = path.parent
        return self.open_directory(parent if str(parent) != "." else Path("."))

    def ensure_directory(self, relative: Path, *, mode: int = 0o700) -> BoundDirectory:
        self._require_open()
        path = _validate_relative(relative, label="Directory", code="unsafe-inbox-path")
        with self.open_directory(Path(".")) as root_bound:
            current_fd = os.dup(root_bound.fd)
        bindings = [DirectoryBinding(Path("."), self.identity)]
        cumulative = Path()
        current_identity = self.identity
        try:
            for component in path.parts:
                cumulative = cumulative / component
                try:
                    next_fd = self._open_component(current_fd, component, cumulative)
                except InboxTransactionError as error:
                    cause = error.__cause__
                    if not isinstance(cause, OSError) or cause.errno != errno.ENOENT:
                        raise
                    try:
                        os.mkdir(component, mode=mode, dir_fd=current_fd)
                    except FileExistsError:
                        pass
                    except OSError as mkdir_error:
                        _raise_os(
                            "inbox-path-operation-failed",
                            f"Could not create directory {cumulative}",
                            mkdir_error,
                        )
                    else:
                        try:
                            os.fsync(current_fd)
                        except OSError as fsync_error:
                            _raise_os(
                                "inbox-path-durability-failed",
                                f"Could not make directory {cumulative} durable",
                                fsync_error,
                            )
                    next_fd = self._open_component(current_fd, component, cumulative)
                try:
                    next_identity = _identity(os.fstat(next_fd))
                except BaseException:
                    try:
                        os.close(next_fd)
                    except OSError:
                        pass
                    raise
                try:
                    os.close(current_fd)
                except BaseException:
                    try:
                        os.close(next_fd)
                    except OSError:
                        pass
                    raise
                current_fd = next_fd
                current_identity = next_identity
                bindings.append(DirectoryBinding(cumulative, current_identity))
            bound = BoundDirectory(current_fd, path, current_identity, tuple(bindings))
        except InboxTransactionError:
            try:
                os.close(current_fd)
            except OSError:
                pass
            raise
        except OSError as error:
            try:
                os.close(current_fd)
            except OSError:
                pass
            _raise_os(
                "inbox-path-operation-failed", f"Could not ensure directory {path}", error
            )
        return bound

    def create_directory(self, relative: Path, *, mode: int = 0o700) -> BoundDirectory:
        self._require_open()
        path = _validate_relative(relative, label="Directory", code="unsafe-inbox-path")
        name = _validate_name(path.name)
        with self.open_parent(path) as parent:
            try:
                os.mkdir(name, mode=mode, dir_fd=parent.fd)
            except FileExistsError as error:
                _raise_os(
                    "inbox-path-occupied", f"Directory {path} already exists", error
                )
            except OSError as error:
                _raise_os(
                    "inbox-path-operation-failed",
                    f"Could not create directory {path}",
                    error,
                )
            try:
                os.fsync(parent.fd)
            except OSError as error:
                _raise_os(
                    "inbox-path-durability-failed",
                    f"Could not make directory {path} durable",
                    error,
                )
        return self.open_directory(path)

    def revalidate_public_chain(self, bound: BoundDirectory) -> None:
        self._require_open()
        bound._require_open()
        temporary: list[int] = []
        try:
            root_fd = os.open(self.root, _directory_flags())
            temporary.append(root_fd)
            root_identity = _identity(os.fstat(root_fd))
            if not _same_directory(root_identity, self.identity):
                raise _failure("inbox-path-changed", "Vault root identity changed")
            if not bound.chain or bound.chain[0].relative != Path("."):
                raise _failure("inbox-path-changed", "Directory binding chain is invalid")
            if not _same_directory(root_identity, bound.chain[0].identity):
                raise _failure("inbox-path-changed", "Directory binding chain changed")
            current_fd = root_fd
            for expected in bound.chain[1:]:
                component = expected.relative.name
                next_fd = self._open_component(current_fd, component, expected.relative)
                temporary.append(next_fd)
                actual = _identity(os.fstat(next_fd))
                if not _same_directory(actual, expected.identity):
                    raise _failure(
                        "inbox-path-changed", f"Directory {expected.relative} changed"
                    )
                current_fd = next_fd
        except InboxTransactionError:
            raise
        except OSError as error:
            _raise_os(
                "inbox-path-operation-failed", "Could not revalidate directory chain", error
            )
        finally:
            for fd in reversed(temporary):
                try:
                    os.close(fd)
                except OSError:
                    pass

    def close(self) -> tuple[str, ...]:
        if self._closed:
            return ()
        self._closed = True
        try:
            os.close(self.fd)
        except OSError:
            return ("Could not close Vault capability",)
        return ()


def _require_parent(parent: BoundDirectory) -> None:
    if not isinstance(parent, BoundDirectory):
        raise TypeError("parent must be a BoundDirectory")
    parent._require_open()


def _metadata(result: os.stat_result) -> FileMetadata:
    return FileMetadata(mode=result.st_mode, mtime_ns=result.st_mtime_ns)


def create_regular_at(
    parent: BoundDirectory, name: str, *, mode: int = 0o600
) -> tuple[int, FileIdentity]:
    _require_parent(parent)
    name = _validate_name(name)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    try:
        fd = os.open(name, flags, mode, dir_fd=parent.fd)
    except FileExistsError as error:
        _raise_os("inbox-path-occupied", f"Entry {parent.relative / name} exists", error)
    except OSError as error:
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not create entry {parent.relative / name}",
            error,
        )
    try:
        result = os.fstat(fd)
        if not stat.S_ISREG(result.st_mode):
            raise _failure(
                "unsafe-inbox-path", f"Entry {parent.relative / name} is not regular"
            )
        return fd, _identity(result)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _lexical_regular_stat(parent: BoundDirectory, name: str) -> os.stat_result:
    try:
        result = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    except OSError as error:
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not inspect entry {parent.relative / name}",
            error,
        )
    if not stat.S_ISREG(result.st_mode):
        raise _failure(
            "unsafe-inbox-path", f"Entry {parent.relative / name} is not a regular file"
        )
    return result


def open_regular_at(
    parent: BoundDirectory, name: str, *, writable: bool = False
) -> tuple[int, FileIdentity, FileMetadata]:
    _require_parent(parent)
    name = _validate_name(name)
    lexical = _lexical_regular_stat(parent, name)
    try:
        fd = os.open(name, _regular_flags(writable=writable), dir_fd=parent.fd)
    except OSError as error:
        code = "unsafe-inbox-path" if error.errno in {errno.ELOOP, errno.ENXIO} else "inbox-path-operation-failed"
        _raise_os(code, f"Could not safely open entry {parent.relative / name}", error)
    try:
        result = os.fstat(fd)
        if not stat.S_ISREG(result.st_mode):
            raise _failure(
                "unsafe-inbox-path", f"Entry {parent.relative / name} is not regular"
            )
        identity = _identity(result)
        if identity != _identity(lexical):
            raise _failure("inbox-path-changed", f"Entry {parent.relative / name} changed")
        return fd, identity, _metadata(result)
    except OSError as error:
        try:
            os.close(fd)
        except OSError:
            pass
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not inspect open entry {parent.relative / name}",
            error,
        )
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def read_all_fd(fd: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while True:
        try:
            chunk = os.pread(fd, 1024 * 1024, offset)
        except InterruptedError:
            continue
        except OSError as error:
            _raise_os("inbox-path-operation-failed", "Could not read bound file", error)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        offset += len(chunk)


def write_all_fd(fd: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        try:
            written = os.write(fd, remaining)
        except InterruptedError:
            continue
        except OSError as error:
            _raise_os("inbox-path-operation-failed", "Could not write bound file", error)
        if written <= 0:
            error = OSError(errno.EIO, "write returned no progress")
            _raise_os("inbox-path-operation-failed", "Could not write bound file", error)
        remaining = remaining[written:]


def fsync_fd(fd: int) -> None:
    try:
        os.fsync(fd)
    except OSError as error:
        _raise_os("inbox-path-durability-failed", "Could not fsync bound file", error)


def fsync_directory(parent: BoundDirectory) -> None:
    _require_parent(parent)
    try:
        os.fsync(parent.fd)
    except OSError as error:
        _raise_os(
            "inbox-path-durability-failed",
            f"Could not fsync directory {parent.relative}",
            error,
        )


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def entry_exists_at(parent: BoundDirectory, name: str) -> bool:
    _require_parent(parent)
    name = _validate_name(name)
    try:
        os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not inspect entry {parent.relative / name}",
            error,
        )
    return True


def verify_regular_binding_at(
    parent: BoundDirectory, name: str, fd: int
) -> FileIdentity:
    _require_parent(parent)
    name = _validate_name(name)
    lexical = _lexical_regular_stat(parent, name)
    try:
        opened = os.fstat(fd)
    except OSError as error:
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not inspect bound entry {parent.relative / name}",
            error,
        )
    if not stat.S_ISREG(opened.st_mode):
        raise _failure(
            "unsafe-inbox-path", f"Entry {parent.relative / name} is not regular"
        )
    opened_identity = _identity(opened)
    if opened_identity != _identity(lexical):
        raise _failure("inbox-path-changed", f"Entry {parent.relative / name} changed")
    return opened_identity


def read_regular_at(
    parent: BoundDirectory, name: str
) -> tuple[int, bytes, FileIdentity, FileMetadata]:
    fd, identity, metadata = open_regular_at(parent, name)
    try:
        payload = read_all_fd(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        return fd, payload, identity, metadata
    except InboxTransactionError:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    except OSError as error:
        try:
            os.close(fd)
        except OSError:
            pass
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not reset entry {parent.relative / name}",
            error,
        )


def write_new_durable_at(
    parent: BoundDirectory, name: str, payload: bytes
) -> tuple[int, FileIdentity]:
    fd, _ = create_regular_at(parent, name)
    try:
        write_all_fd(fd, payload)
        fsync_fd(fd)
        identity = verify_regular_binding_at(parent, name, fd)
        fsync_directory(parent)
        return fd, identity
    except InboxTransactionError:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    except OSError as error:
        try:
            os.close(fd)
        except OSError:
            pass
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not write entry {parent.relative / name}",
            error,
        )


def link_no_overwrite_at(
    source_parent: BoundDirectory,
    source_name: str,
    destination_parent: BoundDirectory,
    destination_name: str,
) -> FileIdentity:
    _require_parent(source_parent)
    _require_parent(destination_parent)
    source_name = _validate_name(source_name)
    destination_name = _validate_name(destination_name)
    source = _lexical_regular_stat(source_parent, source_name)
    source_identity = _identity(source)
    try:
        os.link(
            source_name,
            destination_name,
            src_dir_fd=source_parent.fd,
            dst_dir_fd=destination_parent.fd,
            follow_symlinks=False,
        )
    except FileExistsError as error:
        _raise_os(
            "inbox-path-occupied",
            f"Entry {destination_parent.relative / destination_name} exists",
            error,
        )
    except OSError as error:
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not publish entry {destination_parent.relative / destination_name}",
            error,
        )
    installed = _lexical_regular_stat(destination_parent, destination_name)
    installed_identity = _identity(installed)
    if installed_identity != source_identity:
        raise _failure(
            "inbox-path-changed",
            f"Published entry {destination_parent.relative / destination_name} changed",
        )
    return installed_identity


def _valid_expected_hash(expected_sha256: str) -> bool:
    if not expected_sha256.startswith("sha256:") or len(expected_sha256) != 71:
        return False
    digest = expected_sha256[7:]
    return digest == digest.lower() and all(c in "0123456789abcdef" for c in digest)


def _read_expected(
    parent: BoundDirectory,
    name: str,
    expected_identity: FileIdentity,
    expected_sha256: str,
) -> int:
    if not _valid_expected_hash(expected_sha256):
        raise _failure("inbox-path-changed", f"Entry {parent.relative / name} hash changed")
    fd, payload, identity, _ = read_regular_at(parent, name)
    if identity != expected_identity or sha256_bytes(payload) != expected_sha256:
        try:
            os.close(fd)
        except OSError:
            pass
        raise _failure("inbox-path-changed", f"Entry {parent.relative / name} changed")
    try:
        verify_regular_binding_at(parent, name, fd)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    return fd


def unlink_expected_at(
    parent: BoundDirectory,
    name: str,
    *,
    expected_identity: FileIdentity,
    expected_sha256: str,
) -> None:
    _require_parent(parent)
    name = _validate_name(name)
    fd = _read_expected(parent, name, expected_identity, expected_sha256)
    try:
        os.unlink(name, dir_fd=parent.fd)
        if entry_exists_at(parent, name):
            raise _failure("inbox-path-changed", f"Entry {parent.relative / name} remains")
    except FileNotFoundError as error:
        _raise_os("inbox-path-changed", f"Entry {parent.relative / name} changed", error)
    except InboxTransactionError:
        raise
    except OSError as error:
        _raise_os(
            "inbox-path-operation-failed",
            f"Could not unlink entry {parent.relative / name}",
            error,
        )
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def replace_expected_at(
    parent: BoundDirectory,
    source_name: str,
    destination_name: str,
    *,
    expected_source_identity: FileIdentity,
    expected_source_sha256: str,
    expected_destination_identity: FileIdentity,
    expected_destination_sha256: str,
) -> FileIdentity:
    _require_parent(parent)
    source_name = _validate_name(source_name)
    destination_name = _validate_name(destination_name)
    source_fd = _read_expected(
        parent, source_name, expected_source_identity, expected_source_sha256
    )
    destination_fd: int | None = None
    try:
        destination_fd = _read_expected(
            parent,
            destination_name,
            expected_destination_identity,
            expected_destination_sha256,
        )
        verify_regular_binding_at(parent, source_name, source_fd)
        verify_regular_binding_at(parent, destination_name, destination_fd)
        try:
            os.replace(
                source_name,
                destination_name,
                src_dir_fd=parent.fd,
                dst_dir_fd=parent.fd,
            )
        except FileNotFoundError as error:
            _raise_os("inbox-path-changed", "Replace entries changed", error)
        except OSError as error:
            _raise_os(
                "inbox-path-operation-failed",
                f"Could not replace entry {parent.relative / destination_name}",
                error,
            )
        if entry_exists_at(parent, source_name):
            raise _failure(
                "inbox-path-changed", f"Entry {parent.relative / source_name} remains"
            )
        installed = verify_regular_binding_at(parent, destination_name, source_fd)
        if installed != expected_source_identity:
            raise _failure(
                "inbox-path-changed",
                f"Entry {parent.relative / destination_name} changed",
            )
        return installed
    finally:
        if destination_fd is not None:
            try:
                os.close(destination_fd)
            except OSError:
                pass
        try:
            os.close(source_fd)
        except OSError:
            pass
