# Source Archive Implementation Plan

Design: `docs/superpowers/specs/2026-08-06-source-archive-design.md`

## Release Target

Minor on top of v1.28.0. A new helper, a new folder convention, and one new
excluded directory; no existing note changes shape and no migration runs.

Branched off `feat/retrieval-metadata-filters` rather than `master`, because
this touches `search_vault`'s ignored-directory set and `search.md`, both of
which that branch already modifies. It merges after PR #61.

Delivery rules as standing: RED tests before implementation, `python build.py`
before any doc assertion, `build.py --check` before the gate, and every CI job
green before merge.

## Task 1: The archive folder is not a note folder

Establish the convention before anything writes to it, so the audit never sees
an archive it wants to complain about.

- `SOURCE_ARCHIVE_FOLDER = "95-Sources"` and `SOURCE_ARCHIVE_TYPE =
  "source-archive"` in the shared note domain (`note_catalog`), which both
  bundles now ship.
- `95-Sources` is **not** added to `MANAGED_NOTE_FOLDERS`: it holds sources, not
  notes, and must not appear in crowded-folder analysis, cluster scans, or the
  tag vocabulary.
- `audit_vault` skips the folder for note contracts exactly as it skips
  `Templates/` — one guard, applied where the other already is.
- `source-archive` joins `VALID_NOTE_TYPES` so a `type:` on an archive is not
  itself a finding.

RED first: a Vault with an archive that violates every note contract (no
required headings, twelve tags, no date) produces no findings for it, while an
ordinary note in `20-Learning` still does.

## Task 2: Retrieval excludes the folder, `--scope` still reaches it

- Add `95-Sources` to `IGNORED_DIRECTORY_NAMES`.
- Nothing else. The walk applies that set to child directories reached from the
  scope root and never to the root, so a scoped search already descends into it.

RED first, and this is the important one: a Vault-wide search does not return
the archive, `--scope 95-Sources` does, and both assertions live in one test so
the pair cannot drift. The property is inherited rather than written, so it
needs a test that fails if the walk is ever refactored.

## Task 3: Archive domain

Pure functions, no CLI.

- `archive_path(vault, captured, title)` → `95-Sources/<YYYY-MM>/<slug>.md`,
  reusing the existing filename-safety helpers rather than inventing slugging.
- `render_archive(text, *, source, author, published, captured, note, sha256)`
  prepends the frontmatter block and leaves the body byte-identical.
- `source_sha256(text)` hashes the source text alone. The frontmatter is
  metadata about the capture, not part of the evidence, and must not move the
  hash.

RED first: round-trip a document containing YAML-looking lines, a `---` fence,
CRLF, and a trailing-newline-free ending; assert the body after the frontmatter
is byte-identical to the input and that the hash matches the input alone.

## Task 4: Linking both directions

- Apply adds `source_archive: "[[<archive stem>]]"` to the note's frontmatter
  and one visible line under its first `## ` section, so the link is clickable
  in Obsidian and not only present in metadata.
- The archive's frontmatter carries `note:` pointing back.
- The note edit is the only mutation to an existing file in this feature. It
  goes through the existing note-writing path with a backup, and it must not
  touch anything else in the note.

RED first: after apply, the note's body outside the inserted line is unchanged
byte-for-byte; `audit_vault` resolves the new wikilink; deleting the archive
turns it into `broken-wikilink`.

## Task 5: CLI, preflight, refusals

- `archive-source <vault> --note <path> --source-url <url> [--author]
  [--published] (--stdin | --content-file) (--preflight-json | --apply
  --compact-json)`.
- Preflight writes nothing and reports destination, byte count, `sha256`, and
  whether the note already declares an archive.
- Refusals: `invalid-note`, `note-already-archived` (unless `--replace`),
  `empty-source-content`, plus the shared path and frontmatter codes.
- Register in `run_helper` for the **write** bundle only — the retrieval Skill
  is read-only and must not gain a writing helper.
- Add the codes to `rules-and-errors.md`; the contract test will name them if
  this is missed.

RED first: one test per refusal asserting exit 2, the code, and that the Vault
is byte-for-byte unchanged.

## Task 6: Skill instructions

- `web-capture.md`: when the user wants the original kept, archive it — never
  append it to the note. State the reason in one line (the citation lands in the
  source's prose, and the digest is diluted).
- `deep-capture.md`: cross-reference, since verified capture is the case most
  likely to want evidence retained.
- `search.md`: `95-Sources/` exists, is excluded by default, and `--scope`
  reaches it when the user asks what the source actually said.
- `install.sh` folder list and the root index gain `95-Sources`.
- `python build.py`, then `build.py --check`.

## Verification gate

- Full suite green, `build.py --check` clean.
- Archive a real source into a scratch copy of the reference Vault, then re-run
  the twelve subject queries and confirm no citation lands in archived text.
- All CI jobs green before merge.

## Out of scope

Migrating the existing 680-line clipping out of the Violin note; that is a
follow-up using this tool. Source acquisition. Ranking changes. Issue #57.
