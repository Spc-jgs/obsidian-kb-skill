# Web Capture Resilience Implementation Plan

## Release Target

Ship the approved first-stage behavior as `v1.25.0` through a feature branch,
ready pull request, required GitHub checks, merge to `master`, annotated tag,
and published GitHub Release.

## Task 1: Capture-depth domain contract

1. Add failing tests for Web Clip `capture_depth` defaults, accepted values,
   invalid-value zero-write behavior, and historical audit compatibility.
2. Add `capture_depth: standard` to both canonical Web Clip templates and the
   helper fallback metadata.
3. Validate `standard|verified` on new Web Clip candidates without flagging
   historical notes that omit the field.
4. Make capture-receipt routing depend on canonical destination and persisted
   `capture_depth`.
5. Reject receipts on standard Web Clips and retain receipt identity binding for
   verified applies.

## Task 2: Lazy acquisition-resilience workflow

1. Add contract tests for conditional reference loading and the agreed
   acquisition, privacy, media, verification, self-check, and zero-write rules.
2. Add `core/references/web-capture.md`.
3. Route finished source-backed captures through the new reference and load
   `deep-capture.md` only for verified work.
4. Narrow the deep-capture introduction and completion language to verified
   captures without weakening its receipt or coverage semantics.
5. Update material-rewrite instructions to select and persist depth before
   editing.

## Task 3: Cross-Agent forward evaluation

1. Add tool-neutral JSON fixtures for direct success, safe fallback, private URL
   refusal, image materiality, terminal failure, standard routing, numerical
   self-report, and verified routing.
2. Add deterministic tests that every expected contract decision is represented
   in the lazy reference set.
3. Record a read-only evaluation of the motivating Juejin URL, including
   retrieval representations and structural coverage.

## Task 4: User documentation and generated artifacts

1. Update the knowledge-capture guide, feature guide, YAML reference, README
   feature summary where appropriate, and CHANGELOG Unreleased section.
2. Run `python build.py` so every platform adapter, standard Skill, packaged
   resource, and manifest matches canonical sources.
3. Verify `python build.py --check`.

## Task 5: Local release gates

Run:

```bash
uv sync --locked --extra dev
uv run --no-sync python -m pytest
uv run --no-sync python build.py --check
uv lock --check
git diff --check
```

Also build sdist and wheel, install the wheel into an isolated environment, run
the installed doctor, and verify shell syntax and generated payload parity.

## Task 6: Delivery and release

1. Commit design and implementation in reviewable Conventional Commits with
   Chinese subjects.
2. Push `feature/web-capture-resilience` and open a ready PR.
3. Wait for all required GitHub checks and inspect mergeability.
4. Merge through the normal PR path and synchronize local `master`.
5. Prepare the `v1.25.0` release commit: version sources, manifests, tests,
   lockfile, READMEs, and CHANGELOG.
6. Re-run release gates, push the release update through the PR, and merge.
7. Create and push annotated tag `v1.25.0`.
8. Publish a non-draft, non-prerelease GitHub Release with compatibility and
   verification notes.
9. Verify the public release, tag target, final `master` HEAD, GitHub Actions,
   and installed package doctor output.

