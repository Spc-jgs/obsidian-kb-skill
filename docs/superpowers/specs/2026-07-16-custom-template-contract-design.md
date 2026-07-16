# Custom Template Contract Design

## Goal

Make user-edited Vault templates influence the semantic quality of generated notes, including instructions written below headings, without adding a template read or template-body tokens to the unchanged built-in path.

## Current Behavior

The Vault template already owns frontmatter defaults and required heading order. When an agent supplies complete Markdown through stdin, that explicit body wins over the template body. Preflight can therefore prove that headings match, but the agent may never see prose such as “include risk level, impact, and rollback plan” below a heading.

This design closes that semantic gap. It does not replace deterministic validation with a semantic service. The model already writing the note receives the custom template and applies its instructions; helpers continue to validate facts they can prove mechanically.

## Scope

This release will:

1. Detect whether each conventional Vault template differs from either shipped Chinese or English starter template.
2. Expose only the changed template types in compact Vault discovery.
3. Load the complete template contract for the selected note type only when it is customized.
4. Require the writing model to treat frontmatter, structure, prose instructions, examples, lists, and tables as parts of that contract.
5. Detect a template change between contract retrieval, preflight, and apply.

The ordinary path for an unchanged template retains its current helper calls and does not load template content.

## Non-Goals

- Do not support renamed template files in this release.
- Do not introduce template-specific markup, comments, or a DSL.
- Do not add a second semantic model or claim that deterministic code can judge prose quality.
- Do not expand custom placeholders beyond `{{date}}` and `{{title}}`.
- Do not weaken YAML, heading-order, placeholder, tag, web-clip metadata, preflight, apply, audit, or Git checks.

## Customization Detection

Add a shared template-inspection module used by discovery, the contract helper, and create-note.

For each entry in the existing `TYPE_TO_TEMPLATE` mapping:

1. Read the conventional Vault template file.
2. Normalize transport-only differences: remove a UTF-8 BOM, convert CRLF/CR to LF, and ensure one final newline.
3. Compute SHA-256 over the normalized UTF-8 content.
4. Compare it with the normalized hashes of both shipped starter variants.

Matching either shipped Chinese or English template means `standard`. Any other content means `custom`. Content whitespace is otherwise preserved and remains significant; only encoding and line-ending transport differences are ignored.

Missing conventional templates retain the existing missing-template behavior and are not reported as custom.

Compact `vault-info` adds one bounded field:

```json
{
  "custom_templates": ["web-clip", "meeting-note"]
}
```

An empty list is returned for a standard installation. No template body, heading list, or frontmatter is added to discovery output.

## Template Contract Helper

Add a focused read-only helper:

```bash
python <skill-root>/scripts/run_helper.py template-contract <vault> \
  --type web-clip --json
```

It uses the fixed filename mapping already used by create-note and returns:

```json
{
  "type": "web-clip",
  "path": "Templates/Web Clip.md",
  "customized": true,
  "sha256": "...",
  "frontmatter": {},
  "body": "# ...",
  "supported_placeholders": ["date", "title"],
  "unknown_placeholders": []
}
```

The helper returns the complete body because arbitrary natural-language guidance cannot be safely summarized without losing user intent. It returns only one selected template, and it is called only when compact discovery marks that type as custom.

Malformed template YAML fails with the existing precise source, line, and column shape. Unknown placeholders return a structured contract error before generation; the agent asks the user to replace them or defers the note rather than guessing values.

## Model Interpretation Contract

No special user syntax is required. The note-creation reference instructs the writing model to interpret a custom template as follows:

- Frontmatter fields are defaults and schema hints, subject to existing merge precedence and mandatory runtime overrides.
- Headings and their order define the note structure.
- Imperative or explanatory prose below a heading defines content requirements; apply it without copying meta-instructions into the finished note.
- Lists, tables, labels, and placeholder-shaped fields are body scaffolds; preserve their useful structure and fill them.
- Examples define expected format or depth unless the template clearly identifies them as literal content.
- When a line is ambiguous, preserve its useful information rather than silently discarding it.

Before preflight, the model performs an internal coverage pass against the custom template. This checklist is not written to the Vault and does not create a second note.

## Runtime Flow

The ordinary flow becomes:

1. Run compact Vault discovery.
2. Apply Vault governance and required Git preflight.
3. Determine the note type and destination from the request and source.
4. If the type is absent from `custom_templates`, continue the existing fast path.
5. If present, read exactly one `template-contract` and generate the note against it.
6. Run structured create-note preflight.
7. Apply the identical validated input with automatic audit.

The custom path adds one bounded helper call and one relevant template body. The default path adds only the small `custom_templates` discovery field.

## Template Change Safety

`template-contract` returns the normalized template SHA-256. The custom path passes it to create-note as:

```bash
--expect-template-sha256 <sha256>
```

Both preflight and apply compare the expected hash with the current template. A mismatch returns a structured `template-changed` error before mutation and tells the agent to reload the contract. This prevents applying content against instructions that changed after generation.

The flag is optional for compatibility and is required by the reference only on the custom-template path.

## Error Handling

- Invalid template YAML: fail before note mutation with template path and line/column.
- Unknown note type: keep existing type validation.
- Missing conventional template: keep current fallback and warning behavior.
- Unknown placeholder: fail contract loading before generation and report every unsupported name.
- Template hash mismatch: fail with `template-changed`, expected hash, and actual hash.
- Semantic ambiguity: preserve useful content when safe; if different interpretations would materially change the note, pause before apply and ask the user.

## Testing

Tests will prove:

- shipped Chinese and English templates are classified as standard;
- BOM and newline transport differences do not create false customization;
- a changed heading, instruction, list, table, or frontmatter field marks only that type as custom;
- compact discovery exposes type slugs without template bodies;
- the contract helper returns one complete custom template and stable hash;
- standard note creation makes no contract call;
- custom-template instructions are present in forward-test input and reflected in the resulting note;
- malformed YAML, unknown placeholders, and stale hashes fail before mutation;
- installer upgrades without `--force` continue preserving Vault template edits;
- the full default capture path retains preflight, apply, audit, and current token optimizations.

## Deferred Backlog

Support renamed templates by falling back from conventional filenames to a unique `Templates/*.md` frontmatter `type` match, with an explicit conflict error when multiple files claim the same type. This is a valid future optimization but is intentionally outside the current quality goal.
