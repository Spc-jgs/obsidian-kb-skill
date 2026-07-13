# Web Clip Create-Note Hardening Design

**Status:** Approved in conversation on 2026-07-13

## Goal

Make `create-note` create valid `web-clip` notes in one pass, preserve the Vault path boundary, and define a reliable UTF-8 stdin contract on Windows without expanding the always-loaded Skill hub.

## Scope

This change covers four related failures observed during a QoderWork web-clip capture:

1. Required `source`, `author`, and `published` metadata is difficult to discover when content is supplied through stdin.
2. `create-note --apply` writes a web clip with empty required metadata and reports the problem only after the write.
3. An unquoted YAML value such as `published: 2026-07-13` is parsed as `datetime.date` and then rejected by the audit as if it were missing.
4. The helper does not define or test UTF-8 stdin behavior on Windows.

The Vault-local `--content-file` boundary, optional Git workflow, and hub-plus-references architecture remain unchanged.

## Considered Approaches

### Dedicated web-clip flags

Add `--source`, `--author`, and `--published`. This is easy to discover but makes the generic note creator grow one flag per type-specific field and still leaves `related` and future custom template metadata unresolved.

### Generic metadata flags

Add `--meta key=value` or `--frontmatter-json`. This is flexible, but duplicates the complete Markdown frontmatter merge that stdin and content files already provide. It also introduces quoting and type-coercion rules that agents must learn.

### Complete Markdown input with preflight validation — selected

Keep stdin and content files as the single generic metadata interface. Clarify that they accept complete Markdown with optional YAML frontmatter, demonstrate a web-clip example, normalize supported YAML scalar types, and validate required metadata before writing. This is the smallest interface that supports built-in and Vault-defined fields.

## Design

### Metadata input and precedence

`--stdin` and `--content-file` accept complete Markdown. A leading YAML frontmatter block is parsed and merged using this precedence:

`type defaults < Vault template < input frontmatter < explicit CLI fields`

The explicit CLI fields remain `--type`, `--date`, and `--tags`. No web-clip-only flags are added.

The note-creation reference will include a complete web-clip stdin example with quoted URL, author, and published date. It will continue to state that `--content-file` must resolve inside the Vault and that external or transient content must use stdin.

### Scalar normalization

Before rendering YAML, metadata values that PyYAML resolves as `datetime.date` or `datetime.datetime` are converted to ISO-8601 strings. Normalization is recursive so the renderer produces portable Obsidian properties for nested lists and dictionaries as well as top-level fields.

This makes both of these inputs valid and renders them consistently as strings:

```yaml
published: 2026-07-13
published: "2026-07-13"
```

### Preflight validation

After merging and normalizing metadata but before creating directories, writing the note, or updating an index, `create-note --apply` validates non-empty `source`, `author`, and `published` values for `web-clip` notes.

If a required value is missing:

- no note or index change is made;
- human-readable mode prints a concise error naming every missing field to stderr;
- JSON mode returns a structured error containing a stable code and the missing field list;
- the process exits with status 2.

Dry-run mode remains useful for inspection: it renders the preview and includes the same preflight result without writing. A failed dry run exits with status 2 so automation cannot mistake an invalid preview for success.

Post-write audit remains enabled because it covers template headings, placeholders, wikilinks, and other rules that cannot all be evaluated as simple required metadata.

### UTF-8 stdin contract

All helper CLIs define stdin, stdout, and stderr as UTF-8. The shared console configuration applies UTF-8 to stdin in addition to stdout and stderr when the stream supports `reconfigure`.

Windows CI will execute `create-note` with UTF-8 bytes containing Chinese text and an emoji, then verify the resulting Markdown contains the exact characters. Invalid Unicode containing an unpaired surrogate is rejected with a clear input-encoding error; the helper does not emit invalid UTF-8 with `surrogatepass`.

### Generated artifacts

Source changes are made only in the canonical Python package and `core/references`. `python build.py` regenerates bundled helper copies and platform references. Generated `SKILL.md`, platform adapters, and bundled runtime files are not edited directly.

## Testing

Tests will be added before production changes for these behaviors:

- unquoted YAML `published` dates normalize to ISO strings and pass web-clip audit;
- complete web-clip frontmatter supplied through stdin creates a valid note;
- missing required web-clip metadata exits 2 and performs no write or index mutation;
- JSON preflight errors have a stable machine-readable shape;
- UTF-8 Chinese and emoji stdin round-trip exactly;
- the Windows smoke workflow exercises the UTF-8 stdin path;
- generated artifacts remain synchronized with canonical sources.

Targeted tests and the full suite must pass before completion.

## Non-Goals

- Allowing `--content-file` outside the Vault.
- Automatically committing or pushing Vault changes.
- Adding metadata flags for every note type.
- Moving Vault governance rules into the always-loaded hub.
- Replacing post-write audit with preflight validation.
