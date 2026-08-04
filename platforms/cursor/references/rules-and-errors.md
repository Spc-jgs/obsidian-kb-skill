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
| `invalid-utf8-input` | Supplied content is not valid UTF-8 | Re-encode the content as UTF-8 without BOM and retry |
| `missing-required-metadata` | Required frontmatter fields are absent for this note type | Add the listed fields and re-run preflight; do not write a partial note |
| `template-changed` | The Vault template changed after its contract was read | Re-read the template contract, re-render, then retry |
| `unsupported-template-type` | No template exists for the requested note type | Pick a supported type, or create the category first |
| `missing-template` | The Vault has no template file for this type | Ask before bootstrapping with `scaffold-templates`; do not invent the structure |
| `invalid-template-frontmatter` | The Vault template's own YAML does not parse | Report the reported line/column. One broken template fails every note of that type |
| `unknown-template-placeholder` | The template uses a placeholder the helper cannot fill | Only `{{date}}` and `{{title}}` are supported. Ask the user to fix the template |
| `missing-destination-folder` | The routed folder does not exist | Do not create it implicitly; route elsewhere or use `create-category` |
| `invalid-destination-folder` | The destination is not an acceptable note folder | Re-route using the standard folder map |
| `invalid-task-memory-folder` | The Task Memory path is not the allowed `Tasks/<slug>` shape | Use the exact allowed shape; Task Memory cannot create arbitrary folders |
| `task-memory-initialization-failed` | Task Memory scaffolding could not be created | Report it; do not fall back to an ordinary note in that location |
| `invalid-capture-depth` | The requested `capture_depth` is not a known value | Use `standard` or `verified` |
| `capture-depth-route-mismatch` | The capture depth and the destination disagree | Re-read `web-capture.md` and pick a consistent depth and route |
| `invalid-content-file` | The supplied content file is missing or unreadable | Re-supply the content; do not fall back to inline guesses |
| `invalid-folder-index-config` | The Folder Index plugin config cannot be interpreted | Do not touch listings. Report the config problem |
| `confirmation-required` | `create-category` was applied without `--confirmed` | Show the proposed path, get the user's answer, then apply with `--confirmed` |
| `invalid-category-name` | The category name is not a portable visible directory name | Propose a plain durable subject name; no dots, separators, or hidden prefixes |
| `invalid-category-path` | The category path is not a normalized Vault-relative path | Pass one forward-slash path with no `.`, `..`, or absolute prefix |
| `reserved-category-path` | The target is a Vault control or resource directory | Never file notes under `Templates`, `Attachments`, or `.obsidian`. Re-route |
| `category-collision` | A file or symlink already occupies the destination | Stop and report what is there; do not remove or rename the existing entry |
| `missing-category-parent` | The parent folder does not exist, or is not a directory | Create or choose an existing governed parent first; nesting is at most two levels |
| `ungoverned-category-parent` | The parent is neither a standard note folder nor indexed | Pick a governed parent, or govern the current one with the user before filing under it |
| `category-apply-failed` | Category creation failed partway and was rolled back | Read the reported `created` and `cleaned` paths, report them, and do not retry blindly |
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

#### Capture receipt handshake

Verified capture only. These govern the receipt itself, not the article's
quality — see the next group for that.

| Code | Meaning | Do this |
|---|---|---|
| `missing-capture-receipt` | A finished verified clip arrived without a receipt | Expected on the first verified preflight: build the receipt against the returned content SHA-256 and rerun preflight. This is not a successful preflight; do not apply |
| `missing-capture-receipt-sha256` | Apply omitted the receipt hash preflight accepted | Pass `--expect-capture-receipt-sha256` with the `semantic_receipt.sha256` from preflight |
| `unexpected-capture-receipt` | A receipt was supplied where none applies | Receipts are only for verified web clips outside `00-Inbox`. Drop the receipt, or fix the depth and route |
| `capture-receipt-changed` | The receipt differs from the one preflight accepted | Re-run semantic preflight; never apply a receipt the gate has not seen |
| `capture-receipt-content-mismatch` | The receipt is not bound to the rendered candidate | Rebuild it against the current content SHA-256. A receipt for older bytes proves nothing |
| `capture-receipt-depth-mismatch` | The candidate is not `capture_depth: verified` | Either set verified depth deliberately, or drop to standard capture without a receipt |
| `invalid-capture-receipt-json` | The inline receipt is not valid JSON | Use `--capture-receipt-file` instead of fighting shell quoting |
| `invalid-capture-receipt-file` | The receipt file is missing, a symlink, or not a regular file | Supply a real readable file; the helper never follows a link for evidence |
| `capture-receipt-too-large` | The receipt file exceeds the 1 MiB limit | Cite material evidence, not the whole source. Trim to what the claims need |
| `missing-candidate-source` | The candidate frontmatter has no usable `source` | Fill real source metadata; a receipt cannot be validated against an unknown origin |
| `source-receipt-mismatch` | The candidate `source` is absent from `primary_sources` | List the article's own source as primary; do not reclassify it as supplemental |
| `invalid-capture-receipt` | A receipt field is missing, mistyped, or internally inconsistent | Read `message`: this one code covers every shape violation, so the message is the contract, not the code |

#### Semantic gate

Verified capture only. Each of these maps to a bullet in the "Semantic Hard
Failures" list in `deep-capture.md`; the fix is always to complete the reading
or the writing, never to weaken the receipt.

| Code | Meaning | Do this |
|---|---|---|
| `incomplete-source-access` | `source_access` is not `complete` | Finish acquiring the material sources, or fall back to the zero-write contract in `web-capture.md` |
| `unresolved-material-items` | A material inventory item is unresolved | Read the outstanding item and cover it, or state the limitation and drop the verified claim |
| `missing-receipt-anchor` | A cited anchor does not exist in reader-facing content | Quote text that is actually in the note; an anchor inside a comment or fence does not count |
| `incomplete-resource-evidence` | A resource survey lacks its inventory or per-resource evidence | Every declared resource needs a canonical link, compatibility, and limitation. Match the inventory to the declared set exactly |
| `incomplete-profile-evidence` | The selected profile is missing a required evidence kind | Supply the listed `missing_kinds`, or select the profile that matches what the source supports |
| `missing-practical-artifact` | The profile promises a usable path but the note has none | Add the command, procedure, decision rule, or comparison the profile requires, and match its kind |
| `missing-numeric-provenance` | A numeric claim has no supported provenance | Attribute each number to the source that states it; do not carry an unattributed figure |
| `uncovered-numeric-claim` | A measurement-shaped value is not declared in `numeric_claims` | Declare every measurement, or remove figures the source does not support |
| `missing-measurement-context` | A result is claimed without its measurement context | Report the conditions the source measured under; state honestly when the source omits them |
| `unlabeled-inference` | Source facts and your interpretation are not distinguishable | Label the inference inside the excerpt it belongs to, so a reader can tell claim from reading |
| `invalid-copyable-skill-frontmatter` | An embedded copyable `SKILL.md` has broken or empty frontmatter | Close the YAML block and give a meaningful name and description, or drop the example. A reader will paste this |

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

New category, reported by the create-category helper after it applies:
`missing-category-directory`, `missing-category-index`,
`unreadable-category-index`, `invalid-category-index`,
`invalid-folder-index-content`, `invalid-dataview-index`. These describe the
category the helper just created, so report them before filing the first note
into it — an index with the wrong declared type, or a missing query block, will
not list anything.


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
