# Create Note Structured Preflight Design

## Goal

Reduce redundant note-body output without removing any quality or safety step.
The create workflow remains two-phase: preview first, then explicit apply. The
preview returns the final metadata, destination, content identity, and the same
per-note validation findings used after write, but it does not echo the complete
Markdown body that the caller just supplied.

This is the first incremental token optimization. It deliberately does not
persist previews or eliminate the second body submission.

## Quality Baseline

The release must retain all of the following:

- Vault discovery and validation;
- Vault-local governance and template precedence;
- final template/frontmatter merge;
- Vault path-boundary enforcement;
- note-type required metadata checks;
- template-heading, placeholder, wikilink, and note-schema validation;
- filename conflict protection without overwrite;
- explicit apply before mutation;
- index-strategy handling;
- independent post-write audit;
- machine-readable success and error results.

Token optimization may remove duplicate representation or duplicate discovery,
but it may not skip or weaken any item in this list.

## Scope

### Structured preflight output

Add `create-note --preflight-json`. It is a dry-run mode and therefore rejects
`--apply`. It accepts the same content, metadata, routing, and link-related
inputs as the current dry-run path.

On success it returns:

```json
{
  "vault": "/resolved/vault",
  "folder": "20-Learning",
  "path": "/resolved/vault/20-Learning/2026-07-14 Title.md",
  "applied": false,
  "dry_run": true,
  "frontmatter": {
    "type": "learning-note",
    "date": "2026-07-14",
    "tags": ["learning"]
  },
  "content": {
    "sha256": "<sha256-of-final-rendered-utf8-bytes>",
    "utf8_bytes": 1234,
    "line_count": 42
  },
  "validation": {
    "ok": true,
    "count": 0,
    "findings": []
  },
  "suggested_links": null
}
```

`frontmatter` is the final normalized and merged frontmatter, not the raw caller
input. `content.sha256` covers the exact final UTF-8 bytes that a corresponding
apply invocation would write under the same Vault state. The output never
contains `rendered` or the body text.

Validation findings use the existing audit finding shape: `code`, `path`, and
`message`. A validation failure returns structured output and exit status 2,
with no note or index mutation.

### Shared pre-write and post-write validation

Extract the per-note audit rules so they can validate `(vault, destination,
rendered_markdown)` before a file exists. Both structured preflight and the
existing post-write audit call the same rule engine. Post-write audit remains
mandatory by default and rereads the created file; preflight does not replace
it.

The preflight rule engine covers the current note-level checks, including final
frontmatter, required web-clip fields, template heading order, unresolved
placeholders, empty template content, and broken wikilinks. Vault-wide hygiene
findings that are unrelated to the candidate note are not added to preflight.

### Compatibility

Existing modes remain unchanged:

- `--json` dry-run still returns the complete `rendered` preview;
- `--apply --json` still returns the legacy complete apply object;
- `--apply --compact-json` still omits `rendered`;
- `--compact-json` without `--apply` still returns its existing error;
- human-readable preview and apply output remain available.

`--preflight-json` is mutually exclusive with `--json`, `--compact-json`, and
`--apply`. This avoids changing the v1.13.0 contract and gives callers an
explicit migration path.

### Correctness prerequisites

Include the four confirmed create-note corrections in the same release:

1. Save and read the canonical path returned by
   `resolve_existing_within_vault` for `--content-file`; never validate one path
   and read another relative to the process working directory.
2. Replace check-then-write destination creation with exclusive creation and a
   suffix retry loop so concurrent writers cannot overwrite one another.
3. Route invalid-Vault and other early failures through structured JSON whenever
   a JSON mode, including preflight, is active.
4. Base the empty-body warning on the final rendered body after template
   application, not only on raw stdin/content-file input.

These fixes are required for the quality baseline and are not counted as token
optimizations.

## Workflow

Recommended new-note flow:

1. Discover and validate the Vault as today.
2. Submit the complete Markdown once with `--preflight-json`.
3. Inspect final frontmatter, destination, content hash/size, and validation.
4. If validation is successful, repeat the same content with
   `--apply --compact-json`.
5. The helper independently rebuilds, writes exclusively, updates the index,
   rereads the file, and performs the post-write audit.
6. The agent compares the apply path/audit and reports the result.

The second content submission is intentionally retained in this release. A
future preview-token design may remove it only after this lower-risk release is
measured in real use.

## Token Acceptance Gate

Add a deterministic token/size regression fixture using a long Unicode note.
The test does not depend on a model-specific tokenizer; it asserts structural
properties that guarantee the saving:

- preflight stdout contains no `rendered` field and no complete body substring;
- preflight stdout grows by at most a small constant when the body grows from a
  short fixture to a long fixture;
- final frontmatter, SHA-256, byte count, line count, and all validation fields
  remain present;
- the SHA-256 matches the existing full dry-run `rendered` bytes;
- the long-note preflight response is at least 80% smaller than full dry-run
  JSON.

The release report will also record an `o200k_base` measurement for comparison
with the v1.13.0 baseline. The tokenizer measurement is informational; the
structural regression is the enforced test.

## Testing

Use test-driven development for:

- successful structured preflight and its exact schema;
- zero mutation of notes and indexes during preflight;
- final frontmatter and content-identity correctness;
- parity between preflight findings and post-write audit findings;
- invalid web-clip and invalid UTF-8 structured errors;
- invalid Vault structured errors in every JSON mode;
- relative `--content-file` resolution from a hostile working directory;
- concurrent same-title creation with exclusive suffix allocation;
- template-backed notes without a false empty-body warning;
- all v1.13.0 JSON compatibility contracts;
- source/generated Skill parity, wheel/install tests, hostile-cwd installed
  runtime tests, and Windows installer smoke coverage.

Run the complete local release gates and GitHub CI before publishing.

## Documentation and Release

Update the canonical note-creation reference and both READMEs to recommend:

```bash
# Structured preview without body echo
create-note ... --stdin --preflight-json

# Explicit write with compact result
create-note ... --stdin --apply --compact-json
```

Keep full `--json` documented for callers that explicitly need rendered output.
Regenerate all platform adapters and the standard Skill payload with `build.py`.

This is an additive feature plus correctness fixes, so publish it as v1.14.0.
Release only after local gates, installed-runtime verification, PR/CI review,
merge, tag/release creation, and local Codex/WorkBuddy synchronization all pass.

## Out of Scope

- preview IDs or persisted preview caches;
- eliminating the second body submission;
- single-shot apply without an observable preflight result;
- removing or weakening validation rules;
- broad reference-document compression;
- compact `vault-info` or merged index discovery;
- bulk note creation.

These remain candidates for later measured releases.
