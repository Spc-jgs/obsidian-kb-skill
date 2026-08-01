# Task 4 Wave 3 Architecture Blocker

Date: 2026-07-19
Branch: `wip/inbox-task4-wave3-architecture`
Baseline: `f5ef1ec`
Status: `ARCHITECTURE_REASSESSMENT_REQUIRED`
Evidence-only WIP commit: `5f8d2df` (`wip: explore complete inbox state binding`)

This document freezes pre-commit evidence. The current Wave 3 tracked diff is
an explicitly non-accepted exploration. Do not cherry-pick it, start Task 5, or
attempt Wave 4 without a new architecture decision.

## Probe 1: final binding is not stable through return

The probe wrapped `_verify_recovery_file()`. Immediately after the second
successful `Inbox source backup` verification, it renamed the canonical public
restore-ID directory aside, created a new directory at the original name, and
wrote `unknown` into it. The remaining preamble checks continued through the
already-open old operation fd.

Assertion and command:

```python
with pytest.raises(InboxPreparationError):
    prepared = prepare_inbox_operation(vault, item)
```

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py::test_probe_final_operation_binding_is_stable_through_return -q
```

Actual result: exit 1, `Failed: DID NOT RAISE InboxPreparationError`.
`prepare_inbox_operation()` returned while `prepared.operation_root` resolved
to the unknown replacement directory. This also demonstrates the ancestor
variant: after any one path is verified, later sequential checks leave a window
to replace that earlier path while preserving its verified file inode elsewhere.

## Probe 2: journal exact read-to-append interleaving

After normal preparation, the probe wrapped `_write_all()`. When the
transaction attempted `later-phase`, the wrapper first wrote a complete unknown
JSONL event through the same append fd, then allowed the transaction's event.

Assertion and command:

```python
with pytest.raises(InboxPreparationError):
    _append_event(operation, "later-phase")
```

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py::test_probe_journal_exact_read_is_stable_through_append -q
```

Actual result: exit 1, `Failed: DID NOT RAISE InboxPreparationError`. The call
returned after accepting `expected-before + unknown + own-event`, while its
in-memory state advanced to `expected-before + own-event`. Exact comparison
before append therefore does not serialize the read/use interval.

## Probe 3: unavailable discarded namespace leaves a public operation

The probe intercepted the operation-parent directory fsync immediately after
successful operation mkdir. It renamed the bound `.discarded/` directory
aside, created a different real `.discarded/`, then raised the injected parent
fsync error. Quarantine correctly rejected the replacement namespace, but the
cleanup error was swallowed to preserve the triggering exception.

Assertion and command:

```python
with pytest.raises(OSError, match="injected-operation-parent-fsync"):
    prepare_inbox_operation(vault, item)
assert operation_directories(vault) == []
```

```bash
uv run --locked --extra dev pytest \
  tests/test_inbox_transaction.py::test_probe_discarded_replacement_cannot_leave_public_operation -q
```

Actual result: exit 1. `operation_directories(vault)` contained both the saved
`.discarded-owned` directory and the public restore-ID directory; the public
operation remained. Business source/index/destination bytes were untouched.

## Why another local patch is forbidden

An additional final pathname check only moves the verify/use race closer to
return. A post-append journal read has the same limitation. Falling back to an
unbound replacement `.discarded/` would violate the no-redirection invariant.
The next design must choose a kernel-backed publication/serialization model and
a quarantine fallback whose safety does not depend on a single mutable
namespace path.

The first two hardening commits remain ordered evidence:

1. `1cef079` — `fix: harden inbox recovery preparation`
2. `f5ef1ec` — `fix: bind inbox recovery identities`
3. Wave 3 accepted commit — **not created**

The WIP evidence commit `5f8d2df` is intentionally non-accepted and must not be
treated as the third integration commit or cherry-picked without a new design.
