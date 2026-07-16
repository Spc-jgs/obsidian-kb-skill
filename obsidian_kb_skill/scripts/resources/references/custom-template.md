# Customized Template Contract (reference)

Load only when the selected type appears in compact discovery's
`custom_templates`. Read exactly one contract before drafting:

```bash
python <skill-root>/scripts/run_helper.py template-contract <vault> \
  --type <slug> --json
```

## Interpretation

Treat returned frontmatter and body as author instructions, not decoration:

- use frontmatter as defaults and schema hints under existing merge precedence;
- keep headings and their order as the note structure;
- execute prose instructions without copying instruction prose into the note;
- preserve and fill lists, tables, and labels as structural scaffolds;
- use examples to match requested depth and format.

Stop on unknown placeholders. If an instruction is materially ambiguous, ask
before apply. Before preflight, perform one internal coverage pass; do not write
that checklist or create a second note.

## Stale Contract Protection

Pass the returned digest to both create calls as
`--expect-template-sha256 <sha256>`. On `template-changed`, reread that one
contract, redraft as needed, and rerun preflight. Do not read the template file
directly.

Renamed template discovery is a deferred optimization. This release recognizes
only conventional template filenames and must not guess a fallback.
