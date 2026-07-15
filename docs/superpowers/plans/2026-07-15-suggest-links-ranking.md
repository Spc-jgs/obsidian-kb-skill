# Suggest-links Ranking Implementation Plan

1. Add failing unit tests for CJK title overlap, weak-signal suppression, adaptive generic-tag weighting, relevant sibling selection, root-note scope, and single candidate reads.
2. Implement Unicode-aware tokenization and deterministic folder relevance selection.
3. Refactor candidate loading so each candidate body is read once and corpus tag frequencies can be computed before scoring.
4. Add confidence thresholding and reason filtering while preserving the CLI/JSON result shape.
5. Update the note-creation reference and module help text to describe the bounded confidence rules.
6. Run focused tests, full tests, build/manifest checks, and installed-artifact checks.
7. Prepare v1.15.0, open a separate PR, require green CI, merge, publish, reinstall Codex/WorkBuddy, and verify installed state.
