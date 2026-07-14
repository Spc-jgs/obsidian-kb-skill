# Create Note Compact JSON Design

## Goal

Reduce token-heavy `create-note` apply responses without breaking the existing
JSON contract used by agents, scripts, and tests.

## Context

`create-note --json` currently returns the complete `rendered` Markdown for
both dry-run and apply calls. The dry-run copy is necessary because it is the
preview. The apply copy is often redundant once the caller has approved the
preview, but existing consumers and regression tests rely on `rendered` being
present whenever `--json` is used.

Two of the four commonly observed copies of a long note are caller input: the
agent submits the Markdown once for dry-run and again for apply. This feature
does not attempt to hide or persist caller input between commands. It only
offers a compact apply response.

## Considered Approaches

### Remove `rendered` from apply `--json`

This produces the smallest default response, but it is a breaking API change.
Current tests explicitly require `rendered` in the apply JSON object, and other
agents may rely on the same field. Rejected.

### Use human-readable output for apply

The existing non-JSON apply output is already concise: it reports audit status
and the created path without echoing the note. This needs no code change, but
callers that need deterministic machine-readable audit data lose structured
output. Keep this as a supported immediate option, not the only solution.

### Add opt-in compact JSON

Add `--compact-json` as a backward-compatible apply mode. It emits structured
JSON but omits `rendered`. Existing `--json` behavior remains unchanged. This
is the selected approach.

## CLI Contract

`--compact-json`:

- implies JSON output; callers do not need to combine it with `--json`;
- is valid only together with `--apply`;
- returns the normal successful apply result with `rendered` omitted;
- preserves `vault`, `folder`, `path`, `applied`, `dry_run`, `audit`, and
  `suggested_links`;
- uses structured JSON for validation and runtime errors, just like `--json`;
- may be combined with `--suggest-links` and preserves those structured
  recommendations.

Using `--compact-json` without `--apply` returns exit status 2, emits a concise
JSON error, and writes nothing. Dry-run continues to use `--json` so the caller
can inspect `rendered`.

The legacy commands remain unchanged:

```bash
# Preview: full rendered Markdown remains available.
obsidian-create-note <vault> ... --json

# Legacy apply: still includes rendered Markdown.
obsidian-create-note <vault> ... --apply --json

# Compact apply: structured result without rendered Markdown.
obsidian-create-note <vault> ... --apply --compact-json
```

## Implementation

Add one parser flag in `obsidian_kb_skill/scripts/create_note.py` and derive a
single internal `json_mode` boolean from `args.json or args.compact_json`.
Every existing error path that checks `args.json` must use this combined mode
so compact callers never receive human-formatted errors.

Build the existing result object unchanged. Only immediately before the final
successful compact response, copy or filter the result to remove `rendered`.
This keeps write, index, audit, and link-suggestion behavior identical between
legacy and compact apply modes.

Do not add response hashes, persisted preview tokens, temporary draft files,
or a new output schema version. They do not contribute to the approved goal.

## Documentation

Update the canonical note-creation reference to recommend:

1. `--json` for dry-run preview;
2. `--apply --compact-json` for the real write.

Update the Chinese and English README CLI documentation. Regenerate all
platform adapters and the standard Skill payload through `build.py`; do not
edit generated copies directly.

## Testing

Use test-driven development:

1. Add a failing subprocess test proving compact apply returns valid JSON,
   writes the note, includes a successful audit, and omits `rendered`.
2. Add a failing test proving compact mode without `--apply` exits 2 and does
   not write a note.
3. Retain the existing apply `--json` assertion that `rendered` is present as
   the compatibility regression.
4. Run focused JSON tests, generated-artifact checks, the complete pytest
   suite, and installed-runtime smoke verification after rebuilding.

## Success Criteria

- A long note appears in full only in the dry-run JSON response when callers
  switch apply to `--compact-json`.
- Apply remains machine-readable and includes audit results.
- Existing `--json` consumers observe no field or behavior change.
- Generated Skill payloads are synchronized and all tests pass.
