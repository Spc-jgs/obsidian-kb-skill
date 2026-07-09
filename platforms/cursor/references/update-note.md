# Update Existing Note Workflow (reference)

Loaded only when the user asks to append/edit an existing note. The always-loaded skill body points here.

## Update Existing Note Workflow

When the user wants to append to or edit an existing note (project, person, daily, etc.):

### Step 1: Resolve & Validate Vault Path

Same as Create workflow.

### Step 2: Locate the Target Note

1. If the user named the file, resolve its path directly
2. Otherwise, read the relevant folder's detected index file and pick the best match
3. If multiple candidates exist, **ask the user** which one — do not guess

### Step 3: Read the Existing Note in Full

Always read the complete file before editing. Note the YAML frontmatter, section headings, and current content.

### Step 4: Decide the Insertion Point

Match the new content to the most appropriate section:
- `project-note`: append to `## Updates` / `## Decisions` / `## Tasks` as appropriate
- `person-note`: append to `## Interactions` (newest first or chronological — match existing style)
- `daily-note`: append to the time-block section matching the current time
- If no obvious section exists, append a new `## YYYY-MM-DD Update` subsection at the end

### Step 5: Backup, Then Apply the Edit

1. **Always back up first.** Copy the original file (as bytes — preserve content exactly) to:
   ```
   {VAULT}/.obsidian-kb-backups/YYYY-MM-DD-HHMMSS/{original-relative-path}
   ```
   Example: editing `40-Projects/2026-Q3-OKR.md` at 14:32:07 creates `{VAULT}/.obsidian-kb-backups/2026-06-11-143207/40-Projects/2026-Q3-OKR.md`. The folder structure under the timestamp mirrors the vault so multiple files in one session stay organized. Create parent directories as needed.
2. **Preserve** YAML frontmatter (only bump `updated:` field if present)
3. **Insert** new content at the chosen point — do not rewrite unrelated sections
4. Re-emit the file with **UTF-8 (no BOM)** encoding
5. If the edit removes or rewrites more than a few lines, ask the user to confirm first
6. **Tell the user** where the backup landed so they can roll back manually if needed

### Step 6: Refresh a Static Index (Only If Needed)

Skip index changes in Folder Index and Dataview modes. In Static mode, update an index line only if the note's title, date, or summary blurb changed.

### Step 7: Validate Result

Re-read the updated note and any changed static index. Apply the same metadata, placeholder, wikilink, index-ownership, and encoding checks from Create Step 9. If a reusable Vault auditor is available, run it in strict/read-only mode. Fix validation failures before reporting or performing version-control actions.

### Step 8: Report Diff Summary

Tell the user:
- Which file was edited (full path)
- Which section(s) received new content
- A 1–2 sentence summary of what was added
