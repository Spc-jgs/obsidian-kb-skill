# Cost Limits, Important Rules & Error Handling (reference)

Budgets, non-negotiable rules, and failure handling. The always-loaded skill body points here.

## Cost Limits (Per Invocation)

To prevent runaway token usage on a single save request, respect these caps:

| Operation | Hard Cap |
|---|---|
| Files scanned (directory listing or read) | 10 |
| Content notes read in full | 3 |
| Notes written or edited | 1 (the target note) |
| Index files updated | 2 (Static mode only: target folder + parent if subfolder) |
| Wikilinks inserted per note | 5 |

Short control-plane files — Vault-local governance, templates, plugin manifests, and plugin configuration — still count toward the 10-file scan cap, but do not count as content notes read in full. INDEX files and existing notes are content files. Reading only the first ~20 lines of a candidate note is a small read, not a full read.

If a task genuinely needs to exceed these caps (e.g. bulk import of 20 notes), **ask the user first** and proceed only on explicit confirmation.


## Important Rules

1. **UTF-8 encoding** for all file writes (no BOM)
2. **Use current date** (from system), never hardcode
3. **Decide Create vs Update first** — use the Update Existing Note Workflow when appropriate; do not always create new notes
4. **Use `[[wikilinks]]`** for internal links (not markdown links) — and respect the bounded-search caps in Step 6
5. **One topic per note** — keep notes focused
6. **Match user's language** — write in whatever language the user uses
7. **Never overwrite** — if filename exists, add a numeric suffix (e.g. `-2`, `-3`) or ask user
8. **Validate the vault** before writing — refuse to write to a path that is not a real Obsidian vault
9. **Validate the result** after writing — re-read the target and fix metadata, placeholder, link, or index violations before reporting success
10. **Respect cost limits** — do not scan the entire vault for a single save
11. **One index owner** — let Folder Index or Dataview own generated listings; update subfolder and parent indexes only in Static mode
12. **Bounded capture** — Default to one target note per invocation. Multiple solutions inside one source can stay in one focused note. If the source contains multiple independently reusable topics, ask the user before creating multiple notes; without confirmation, create one aggregate note and suggest later extraction.
13. **Use the provided write helper** — if your environment lacks a native file-write tool, call `python <skill-root>/scripts/run_helper.py create-note` instead of writing your own ad-hoc script to save the note.


## Structured Error Codes

Every helper refusal carries a machine-readable `code`. Match on the code, not
on the message text. Two envelope shapes are in use:

```jsonc
// path and security refusals, plus update-note backup failures — exit 3 (path) / 2
{"schema_version": "1.0", "ok": false, "command": "...", "error": {"code": "...", "message": "...", "details": {}}}

// all other helper refusals — exit 2
{"error": {"code": "...", "message": "...", ...}}
```

`SCREAMING_SNAKE` codes use the first shape; `kebab-case` codes use the second.
Both nest the code at `error.code`, so reading that path works for either
envelope. Read it there rather than matching on the code's spelling.

### Convention For New Codes

Every new code is `kebab-case` and uses the second envelope. Four codes predate
this convention and are grandfathered exactly as they are:

`PATH_OUTSIDE_VAULT`, `PATH_NOT_FOUND`, `INVALID_VAULT_ROOT`, `BACKUP_FAILED`

They are not renamed. Three of them are the Vault containment boundary, which
is the most safety-sensitive code in the project, and their spelling is pinned
by existing output tests. Renaming them would buy nothing that reading
`error.code` does not already provide.

`tests/test_error_code_contract.py` enforces this: a new code outside the
grandfathered set must be `kebab-case`, so the split cannot grow.

### Refusal Codes

Every refusal leaves the Vault unchanged. Never work around one by writing the
file yourself with a native tool — the refusal is the contract, not an obstacle.

| Code | Meaning | Do this |
|---|---|---|
| `PATH_OUTSIDE_VAULT` | The resolved path escapes the Vault, after following symlinks | Stop. Report the offending parameter. Never retry with a different spelling of the same path |
| `PATH_NOT_FOUND` | An existing-path argument does not exist | Re-resolve the target from the Vault; ask the user if still ambiguous |
| `INVALID_VAULT_ROOT` | The Vault root is not a usable, in-bounds directory | Stop and re-confirm the Vault path with the user |
| `invalid-vault` | The path is not a real Obsidian vault (`.obsidian/` missing) | Stop. Offer to re-prompt, or to initialize a vault only on explicit confirmation |
| `BACKUP_FAILED` | The pre-write backup could not be created | Stop. The note was not modified. Report the cause; do not retry the write without a backup |
| `invalid-frontmatter` | The frontmatter block exists but the YAML does not parse | Do not fill defaults over it. Show the user the reported line/column and let them fix it |
| `unclosed-frontmatter` | The opening fence has no closing fence | Do not treat the note as having no frontmatter. Report the unterminated block and let the user close it |
| `frontmatter-not-mapping` | Frontmatter parses but is not a YAML mapping (e.g. a list) | Report the actual shape found. Do not coerce it into a mapping or overwrite it with defaults |
| `unreadable-frontmatter` | Inbox processing refused a note whose frontmatter cannot be read | Leave the note in the Inbox untouched. Report the reported line and let the user repair the YAML |
| `unsafe-inbox-entry` | An Inbox entry is a symlink, a directory, or otherwise not a regular file | Leave it in place. Never resolve it: following the link would import content from outside the Vault. Tell the user what the entry is |
| `unreadable-note` | The note bytes could not be decoded | Report the path; do not guess an encoding and rewrite it |
| `invalid-utf8-input` | Supplied content is not valid UTF-8 | Re-encode the content as UTF-8 without BOM and retry |
| `missing-required-metadata` | Required frontmatter fields are absent for this note type | Add the listed fields and re-run preflight; do not write a partial note |
| `template-changed` | The Vault template changed after its contract was read | Re-read the template contract, re-render, then retry |
| `unsupported-template-type` | No template exists for the requested note type | Pick a supported type, or create the category first |
| `missing-destination-folder` | The routed folder does not exist | Do not create it implicitly; route elsewhere or use `create-category` |
| `invalid-destination-folder` | The destination is not an acceptable note folder | Re-route using the standard folder map |
| `invalid-task-memory-folder` | The Task Memory path is not the allowed `Tasks/<slug>` shape | Use the exact allowed shape; Task Memory cannot create arbitrary folders |
| `task-memory-initialization-failed` | Task Memory scaffolding could not be created | Report it; do not fall back to an ordinary note in that location |
| `invalid-capture-depth` | The requested `capture_depth` is not a known value | Use `standard` or `verified` |
| `capture-depth-route-mismatch` | The capture depth and the destination disagree | Re-read `web-capture.md` and pick a consistent depth and route |
| `invalid-content-file` | The supplied content file is missing or unreadable | Re-supply the content; do not fall back to inline guesses |
| `invalid-folder-index-config` | The Folder Index plugin config cannot be interpreted | Do not touch listings. Report the config problem |
| `invalid-output-mode` | Conflicting output flags were passed | Fix the invocation; `--preflight-json` cannot combine with `--apply` |
| `compact-json-requires-apply` | `--compact-json` was passed without `--apply` | Add `--apply`, or use `--preflight-json` for a dry run |
| `conflicting-content-source` | `--from-preflight` was combined with `--stdin` or `--content-file` | Keep one content source; the staged reference already carries the body |
| `fix-requires-preflight` | `--fix-heading-levels` was passed outside a preflight | Add `--preflight-json`; a repair is reviewed before it is applied |
| `invalid-preflight-reference` | `--from-preflight` was not a content SHA-256 | Pass the `content.sha256` value the preflight returned |
| `unknown-preflight-content` | Nothing is staged under that hash | The entry expired or was preflighted elsewhere; rerun preflight with the full body |
| `unreadable-preflight-content` | The staged entry could not be read | Rerun preflight with the full body; do not write from a partial copy |
| `preflight-vault-mismatch` | The staged content belongs to another Vault | Rerun preflight against this Vault |
| `preflight-context-mismatch` | The staged content was preflighted for another type or title | Rerun preflight for the note you are actually writing |
| `preflight-content-changed` | The staged content no longer renders to its hash | Something changed after preflight (date, tags, template); rerun preflight and apply the new hash |

### Audit Findings

The vault auditor reports findings rather than refusing. Fix only files from
the current invocation, re-run the audit, and report anything that cannot be
fixed safely. Never bulk-rewrite historical notes to clear a finding.

Frontmatter and content: `missing-frontmatter`, `invalid-frontmatter`,
`missing-date`, `missing-type`, `invalid-type`, `missing-tags`, `invalid-tag`,
`too-many-tags`, `near-duplicate-tags`, `invalid-related`,
`invalid-related-entry`, `duplicate-related-entry`, `unclosed-fence`.

Links and duplication: `broken-wikilink`, `ambiguous-wikilink`, `orphan-note`,
`duplicate-title`, `similar-title`.

Templates: `missing-template-heading`, `empty-template-note`,
`residual-template-instruction`, `unresolved-template-placeholder`,
`missing-deep-capture-heading`, `outdated-deep-capture-template`,
`web-clip-invalid-capture-depth`, `missing-conversation-digest-heading`,
`outdated-conversation-digest-template`,
`conversation-digest-missing-resume-field`,
`conversation-digest-resume-card-too-long`.

Folder index: `missing-folder-index`, `duplicate-folder-index`,
`misnamed-folder-index`, `missing-folder-index-content`,
`duplicate-folder-index-content`, `graph-incompatible-index-config`,
`broken-folder-graph-chain`.


### Finding Severity

Each finding carries a severity, and `--min-severity` filters by it:

| Severity | Meaning | Response |
|---|---|---|
| `defect` | Navigation, rendering, or tooling is already broken, or unfinished scaffolding shipped | Fix it |
| `hygiene` | Consistency or completeness worth improving | Fix when convenient |
| `informational` | Often perfectly fine — a standalone note, two similar titles | Report only if the user asks |

Report `defect` counts first. A long undifferentiated list is a list the user
will not read.

## Error Handling

Situations without a structured code:

- **Vault not found / not an Obsidian vault**: Stop and report. Offer to (a) re-prompt for the correct path, or (b) initialize a new vault structure (folders + templates + INDEX) at the given location with explicit user confirmation.
- **Template missing**: Create the note using the base YAML frontmatter and standard sections. Warn the user that the template was missing and suggest re-running the installer.
- **Permission denied**: Report the error clearly and suggest checking file/directory permissions.
- **Index missing**: In Folder Index mode, create the configured minimal folder index; in Dataview mode, report the missing query page; in Static mode, create a basic `INDEX.md` before appending.
- **Filename conflict**: Append `-2` (or next available number). Inform the user of the actual filename used.
- **Encoding issues**: Always write files as UTF-8 without BOM. If the platform has encoding quirks (e.g. PowerShell 5.1), use appropriate workarounds (`[System.IO.File]::WriteAllText` with `UTF8Encoding $false`).
- **Cost cap hit**: Stop scanning, write the note with whatever wikilinks were already found, and note the truncation in the user-facing summary.
- **Post-write validation failed**: Do not confirm, commit, or push. Correct only the files from the current invocation, re-run validation, and report the unresolved finding if it cannot be fixed safely.
- **Git divergence or conflict**: Stop and report the branch state. Do not merge, rebase, or resolve INDEX content automatically.
