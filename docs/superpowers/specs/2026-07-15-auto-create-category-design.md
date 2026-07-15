# Automatic Category Creation Design

## Goal

Allow a note-capture agent to propose and safely initialize a missing Vault
category without adding work to the ordinary path for existing categories.
The user keeps control of the category name and separately decides whether the
new route becomes persistent Vault governance.

## Scope and principles

This first version supports one new child category beneath an existing,
governed note folder, for example `20-Learning/Rust`. It adds a dedicated
`create-category` helper and a short exceptional-path instruction to the note
creation workflow. Existing `create-note` preflight, write, audit, routing, and
index behavior remain unchanged when the target folder already exists.

Category creation is never inferred and applied silently. The agent may infer a
candidate from a clear content theme, but the user must approve the proposed
path before mutation. A user can accept the proposed name, provide another
name, use an existing folder, or decline category creation.

Arbitrary governance prose is not parsed by the helper. The agent reads the
applicable Vault governance and performs any approved minimal prose edits.

## Decision flow

1. Run the ordinary `vault-info --json` discovery and read applicable root and
   target-path governance.
2. Route directly when a matching governed category already exists. This path
   receives no new prompt or helper call.
3. When a clear topic lacks a category, propose one full relative path and tell
   the user that they may rename it. Ask independently whether the route should
   be added to `AGENTS.md`.
4. Do not create anything until the user confirms the category path.
5. Run `create-category --preflight-json` for the confirmed path, inspect its
   planned mutations and warnings, then run `--apply --confirmed
   --compact-json` with the same path.
6. If the user approved route persistence, minimally add the route to the
   applicable `AGENTS.md`. If they declined, leave governance unchanged and
   treat the directory as a one-off category; a later capture must ask again
   unless governance has since changed.
7. Apply any other Vault-mandated structural maintenance, such as the current
   Vault's README directory tree and category section. This obligation is
   independent of route persistence.
8. Continue through the unchanged `create-note` preflight, apply, and audit
   path for the first note.
9. Run the category structure audit reported by the new helper. Do not add a
   second manual file read merely to prove creation.

The confirmation can be presented in one conversational prompt, but it must
capture two independent answers: the final category path and whether to update
the route governance.

## Helper contract

The new helper is invoked through the packaged runner:

```bash
python <skill-root>/scripts/run_helper.py create-category <vault> \
  --folder "20-Learning/Rust" --preflight-json

python <skill-root>/scripts/run_helper.py create-category <vault> \
  --folder "20-Learning/Rust" --apply --confirmed --compact-json
```

`--folder` is a Vault-relative full category path. The final component is the
category name. The helper derives the parent rather than accepting separate
parent and name values, preventing disagreement between them.

The preflight result contains at least:

```json
{
  "vault": "/vault",
  "folder": "20-Learning/Rust",
  "parent": "20-Learning",
  "category": "Rust",
  "exists": false,
  "applied": false,
  "index": {
    "mode": "folder-index",
    "path": "20-Learning/Rust/Rust.md"
  },
  "planned_changes": [
    {"kind": "directory", "path": "20-Learning/Rust"},
    {"kind": "index", "path": "20-Learning/Rust/Rust.md"}
  ],
  "governance_reminders": ["AGENTS.md", "README.md"],
  "warnings": []
}
```

Full JSON is used for preflight because the planned mutations are the review
surface. Compact apply output retains `folder`, `applied`, the created paths,
warnings, and audit status. Human-readable output conveys the same decisions.

`--apply` requires `--confirmed`. This is a mechanical guard that proves the
agent crossed the user-confirmation gate; it does not replace the conversational
confirmation. Dry-run and preflight never require the flag.

If the folder already exists, the helper makes no changes and reports
`already-exists`; normal note creation may continue. It never overwrites or
repairs an existing index as a side effect. Explicit index repair remains a
separate maintenance task.

## Validation and safety

The helper reuses the existing Vault-root and containment validators. It rejects:

- an invalid Vault;
- an absolute path or path that escapes through `..` or a symlink;
- the Vault root as a category;
- a missing or non-directory parent;
- more than one new path component;
- an empty, dot-only, control-character, or filesystem-invalid category name;
- a reserved/control directory such as `.obsidian`, `Templates`, Attachments,
  `.git`, `.obsidian-kb-backups`, or `docs/superpowers`;
- a destination occupied by a file or symlink;
- apply without `--confirmed`.

The parent must already be a note-bearing, governed location. In the first
version this means it has a recognized index strategy or is one of the standard
note folders reported by `vault-info`. A new category cannot recursively create
its missing parent.

The agent should offer a new category only for a stable domain concept, not an
article title, task name, vendor feature, or incidental keyword. Ambiguous
content remains in the governed parent or `00-Inbox` according to existing
rules.

## Index initialization

Index ownership is determined inside the helper from the same Folder Index
configuration used by `detect-index` and Vault audit.

- With Folder Index enabled and the destination not excluded, create the path
  returned by `expected_folder_index`. Its frontmatter has `type:
  folder-index`, a `moc` tag, an H1 using the confirmed category name, and
  exactly one empty `folder-index-content` block. Custom index filenames are
  honored. Existing graph-compatibility warnings are surfaced without silently
  changing plugin configuration.
- Without Folder Index, create `INDEX.md` using the established Vault fallback.
  When the parent has a Dataview-managed index, initialize the matching
  Dataview category index; otherwise initialize a static MOC. The next ordinary
  `create-note` call may append the first note only to the static form.

The helper must reuse a shared renderer for index content rather than embedding
a second divergent template in the CLI. Installer/scaffolding behavior and
category creation must produce structurally equivalent indexes for the same
Vault mode.

The category directory and index are one logical mutation. Files are first
prepared in memory. If index creation fails after the helper created the empty
directory, the helper removes only that newly created empty directory. It never
rolls back or modifies pre-existing paths.

## Governance edits

The helper does not edit `AGENTS.md`, `CLAUDE.md`, README files, or arbitrary
Vault prose. It reports relevant governance reminders; the agent owns these
edits because their format and meaning are user-defined.

For an approved route update, the agent:

- edits the applicable routing table or section with the smallest possible
  patch;
- preserves unrelated wording and formatting;
- adds or adjusts a short category description only when the existing file has
  such a section;
- reviews the resulting diff and confirms that no unrelated governance changed.

Declining the route update means no governance edit. It does not waive other
explicit structural rules, such as updating the current Vault README when a
new subdirectory is introduced.

## Error and audit behavior

Validation failures return one stable structured error and exit 2 before any
mutation. Apply-time filesystem failures return an error, report any paths that
were created or removed during cleanup, and do not claim success.

After apply, the helper validates that the directory and expected index exist,
the index remains inside the Vault, and the index structure matches its mode.
Folder Index mode also verifies exactly one `folder-index-content` block. A
clean result reports an empty findings list; findings cause exit 2 while
preserving the created artifacts for diagnosis.

The subsequent `create-note` call keeps its existing exclusive-write and
per-note audit behavior. Category creation does not weaken frontmatter,
template, wikilink, or index ownership checks.

## Testing

Automated coverage includes:

- preflight is read-only and exposes the exact planned directory and index;
- apply without `--confirmed` fails without mutation;
- native Folder Index, custom Folder Index filename, Dataview fallback, and
  static fallback create the expected index content;
- the same renderer is exercised by category creation and scaffolding;
- existing category is an idempotent no-op and no existing index is rewritten;
- missing parent, nested missing parents, traversal, symlink escape, reserved
  paths, invalid names, and file collisions fail before mutation;
- an index-write failure cleans up only a newly created empty directory;
- JSON, compact JSON, human output, packaging, and hostile-working-directory
  runner behavior remain valid;
- the ordinary existing-category `create-note` integration test has unchanged
  calls and output;
- instruction tests require user naming confirmation, the independent
  `AGENTS.md` choice, README/local-governance compliance, and no repeat prompt
  for existing governed routes.

A real installed-skill smoke test creates a disposable category in a temporary
Vault, writes its first note, verifies the category audit, and confirms that a
second note uses the ordinary path without another category helper call.

## Non-goals for the first version

- Semantic models or network calls for classification.
- Automatic parsing and rewriting of arbitrary governance prose.
- Recursive category trees or creation outside an existing governed parent.
- Automatic renaming, merging, deletion, or repair of categories.
- Inferring permanent routing from an unpersisted one-off directory.
- Changing date semantics, link-ranking behavior, templates, or normal
  `create-note` output.

## Acceptance criteria

- A novel, clear topic causes a user-visible proposed path and naming choice
  before any write.
- Route persistence is a separate user choice; declining it leaves
  `AGENTS.md` unchanged.
- After confirmation, one helper initializes a structurally valid category and
  index for the current Vault mode, then existing note creation handles the
  first note normally.
- Vault-required README or other structural maintenance still occurs even when
  route persistence is declined.
- Existing governed categories incur no extra prompt, helper call, or token
  surface.
- No helper silently creates a category from a keyword or overwrites existing
  governance/index content.
