Implementation base: e3d96b3a5f0bc4db016ffe9f25ca266f182545e1
Master base: 8785da8f98a7f111ed68b8964418c0c63658ba2a
Task 1: complete (commits 9751447..d0d4284, review clean)
Task 2: implemented, NOT accepted (commits d0d4284..91cbdda)
  - Delivers `inbox_tx/paths.py` (991 lines) and `tests/test_inbox_tx_paths.py`
    (841 lines). Those 55 tests were re-run on 2026-08-01 and still pass.
  - Self-report is complete in `task-2-report.md`; independent review is not.
    That report states: "The internal self-review agent was stopped to avoid
    delaying controller-owned independent Task review; no reviewer findings
    were received."
  - Open concerns recorded by the report: generated installable payloads are
    out of sync and now also lack this module (the brief prohibited touching
    them; integration must regenerate); runtime behaviour was exercised only on
    macOS / Python 3.14.6, with foreign-Windows semantics and missing-platform
    primitives fault-injected rather than run natively.
  - Do not treat this as accepted. Task 3 stays blocked on an independent
    review of the exact `d0d4284..91cbdda` range.
Task 3: pending
Task 4: pending
Task 5: pending
Task 6: pending
Task 7: pending
Task 8: pending
Task 9: pending
Task 10: pending
