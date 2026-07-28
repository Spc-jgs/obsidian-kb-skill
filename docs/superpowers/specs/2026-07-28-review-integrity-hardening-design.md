# Review Integrity Hardening Design

## Status

- Target release: `v1.22.1`
- Base release: `v1.22.0`
- Source reviews: PR #21 and PR #22
- Scope: repair every review finding that still reproduces on `master`
- Non-goal: redesign the complete capture taxonomy or migrate historical notes

## Problem

The v1.21 and v1.22 releases introduced semantic and mechanical gates for
finished source-backed articles. Post-merge Codex review found two classes of
defect:

1. complete gate bypasses, where a note can be written or accepted without the
   reader-facing evidence promised by the contract; and
2. bounded coverage or compatibility gaps, where a common valid input is either
   skipped or rejected incorrectly.

The findings were reproduced against v1.22.0 in disposable Vaults. In
particular:

- `00-Inbox/../20-Learning` writes outside Inbox without a receipt;
- every semantic anchor can point at frontmatter while the visible body is
  empty;
- a resource survey can give compatibility and limitation evidence for only one
  of several named resources;
- a receipt-only inference label passes even when the note does not label the
  inference;
- heredoc-first `SKILL.md` creation, common English measurements, English
  template comments, and valid non-triple fences bypass their intended checks;
- fresh Task Memory initialization has no working helper path after ordinary
  note creation stopped creating directories.

One PR #21 finding, material rewrites bypassing the deep gate, is already fixed
by v1.22. It needs regression coverage and a review-thread response, not another
behavior change.

## Decision

Ship one patch release that fixes all currently reproducible findings. Treat the
two P1 findings as release blockers. Do not leave known deterministic failures
behind a monitoring flag.

The patch keeps the existing progressive-disclosure architecture:

- ordinary notes do not load deep-capture instructions;
- finished source-backed articles use `web-clip` and the conditional
  `deep-capture.md`;
- resource-level receipt detail remains transient and bounded;
- Task Memory receives a narrow operational-directory exception without
  reopening silent category creation for ordinary notes.

## Design

### 1. Canonical destination owns receipt routing

`create-note` already resolves the destination directory inside the Vault before
writing. Receipt routing will use that canonical resolved directory, relative
to the canonical Vault root, rather than the raw `--folder` spelling.

After resolution, the helper will also replace the displayed and written folder
with the canonical Vault-relative path. Thus:

- `00-Inbox/../20-Learning` becomes `20-Learning` and requires a receipt;
- an Inbox child symlink resolving to `20-Learning` requires a receipt;
- a symlink resolving to a real Inbox descendant remains exempt;
- output paths do not preserve misleading `..` or symlink spellings.

Containment remains owned by `vault_paths.py`.

### 2. Semantic anchors must be reader-facing

Receipt anchors will search a reader-facing Markdown projection:

- YAML frontmatter is excluded;
- HTML comments outside fenced code are excluded;
- fenced code remains visible because rendered code examples are reader-facing;
- inline code, links, headings, tables, and ordinary prose remain eligible.

The same projection will feed measurement detection before code, inline-code,
and URL masking. Hidden comments therefore cannot create evidence or create
spurious measurement requirements.

### 3. Inference labels bind to their excerpts

An inference `label` must be meaningful and occur inside its exact
`note_excerpt`. A label appearing only in the receipt or elsewhere in the note
does not distinguish the claimed sentence from source fact.

### 4. Resource evidence is per concrete resource

A `resource-survey` receipt will include a non-empty `resources` array:

```json
{
  "resources": [
    {
      "id": "spring-ai-agent-utils",
      "name": "Spring AI Agent Utils",
      "canonical_url": "https://github.com/example/project"
    }
  ]
}
```

Each resource must have unique, meaningful identity and a canonical URL visible
in the candidate. Material items of kinds `canonical-link`, `compatibility`, and
`limitation` must declare `resource_id`. Every declared resource must have all
three kinds. Profile-wide `selection-criteria` and `starting-example` remain
allowed because they may compare or start from the survey as a whole.

This tightens schema version 1 rather than accepting old weak receipts. Receipts
are transient preflight artifacts, not stored Vault data, and preflight/apply
already require exact receipt identity.

### 5. Finished source-backed articles use `web-clip`

The routing contract will explicitly say:

- use `web-clip` for a finished source-backed article unless Vault governance
  selects a more specific source-backed article template;
- do not choose `learning-note` merely because the destination is
  `20-Learning`;
- reserve `learning-note` for learning material that is not a reconstructed
  source article.

This closes the instruction-level escape from the runtime receipt gate.

### 6. Markdown fences use a line-aware parser

Instruction-comment filtering and copyable-example inspection will recognize
CommonMark-style backtick or tilde fences of length three or greater. A closing
fence must use the same character and at least the opening length.

This supports:

- `~~~markdown`;
- four-backtick fences containing triple-backtick examples;
- longer fences;
- unclosed fences extending to end of input.

HTML comments inside fenced examples remain reader-facing literal examples and
are not treated as hidden comments.

### 7. Copyable `SKILL.md` commands include heredoc-first forms

Shell detection will recognize both:

```bash
cat > path/SKILL.md <<'EOF'
cat <<'EOF' > path/SKILL.md
```

It will retain `tee`, `Set-Content`, and `Out-File` support and continue to
ignore directory-tree illustrations that do not execute a write command.

### 8. Measurement coverage includes common units

Measurement detection will add:

- English `month(s)` and `year(s)`;
- abbreviated `B` counts in addition to K/M;
- English `thousand`, `million`, and `billion`;
- Chinese `万` and `亿`.

Dates remain excluded, and code, URLs, inline code, and hidden comments remain
masked. Long-tail units remain a monitored compatibility surface rather than a
claim of universal natural-language measurement parsing.

### 9. Task Memory gets a narrow initialization exception

Missing directories remain a hard failure for every ordinary note and article.
For explicit `--type task-memory`, the helper may initialize only a normalized
`Tasks/<slug>` path:

- exactly two path components;
- top-level component exactly `Tasks`;
- portable lowercase task slug;
- no absolute path, dot component, traversal, or symlink escape.

Preflight reports the prospective path without mutation. Apply creates the
operational parent and task directory immediately before the exclusive note
write. If the write fails, helper-created empty directories are cleaned up.
This is an operational Task Memory exception, not category creation, and does
not use `create-category`.

### 10. English template markers match shipped templates

The auditor will retain old marker variants for customized/older templates and
add the exact shipped English phrases:

- `state success criteria`;
- `link only to existing vault notes`.

### 11. Existing material rewrite routing remains covered

Regression tests will require `update-note.md` to route material source-backed
rewrites through `deep-capture.md` and `capture-receipt`. No runtime behavior
change is needed for this already-fixed PR #21 finding.

## Failure and Compatibility Boundaries

- A receipt created under v1.22.0 for a resource survey without `resources`
  will fail under v1.22.1 and must be regenerated. It cannot be reused across
  versions safely anyway because candidate and receipt hashes are exact.
- The reader-facing projection deliberately keeps fenced code. A procedure may
  use a visible command or code excerpt as evidence.
- Task Memory initialization does not create indexes, governance files, or
  arbitrary nested directories.
- Historical notes are not revalidated or rewritten during installation.
- No token cost is added to the always-loaded Skill body beyond the concise
  finished-article type rule; detailed receipt changes stay in the conditional
  deep-capture reference and helper.

## Verification

Required regression tests:

1. traversal and in-Vault symlink routes use canonical destination semantics;
2. frontmatter and hidden-comment anchors fail while visible code anchors pass;
3. inference labels absent from their excerpt fail;
4. every resource needs canonical-link, compatibility, and limitation evidence;
5. heredoc-first malformed `SKILL.md` YAML fails;
6. months, years, B counts, word counts, 万, and 亿 require provenance;
7. tilde and variable-length fences do not leak instructional comments;
8. exact English template comments are detected;
9. fresh Task Memory preflight is read-only and apply initializes only
   `Tasks/<slug>`;
10. ordinary missing destinations still fail;
11. material rewrite routing remains present.

Release verification:

- full pytest suite;
- generated-artifact check;
- lockfile and diff checks;
- Skill Creator validation;
- sdist/wheel build and isolated installation;
- Python 3.11, Python 3.14, and Windows CI;
- disposable installed-runtime regressions;
- real Vault read-only audit and installed `doctor --json`.
