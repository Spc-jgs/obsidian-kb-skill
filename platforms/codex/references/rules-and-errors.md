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
13. **Use the provided write helper** — if your environment lacks a native file-write tool, call `scripts/create_note.py` instead of writing your own ad-hoc script to save the note.


## Error Handling

When things go wrong, follow these guidelines:

- **Vault not found / not an Obsidian vault**: Stop and report. Offer to (a) re-prompt for the correct path, or (b) initialize a new vault structure (folders + templates + INDEX) at the given location with explicit user confirmation.
- **Template missing**: Create the note using the base YAML frontmatter and standard sections. Warn the user that the template was missing and suggest re-running the installer.
- **Permission denied**: Report the error clearly and suggest checking file/directory permissions.
- **Index missing**: In Folder Index mode, create the configured minimal folder index; in Dataview mode, report the missing query page; in Static mode, create a basic `INDEX.md` before appending.
- **Filename conflict**: Append `-2` (or next available number). Inform the user of the actual filename used.
- **Encoding issues**: Always write files as UTF-8 without BOM. If the platform has encoding quirks (e.g. PowerShell 5.1), use appropriate workarounds (`[System.IO.File]::WriteAllText` with `UTF8Encoding $false`).
- **Cost cap hit**: Stop scanning, write the note with whatever wikilinks were already found, and note the truncation in the user-facing summary.
- **Post-write validation failed**: Do not confirm, commit, or push. Correct only the files from the current invocation, re-run validation, and report the unresolved finding if it cannot be fixed safely.
- **Git divergence or conflict**: Stop and report the branch state. Do not merge, rebase, or resolve INDEX content automatically.
