# Read-Only Knowledge Retrieval v1.23.0 Evaluation

Date: 2026-07-29

## Acceptance result

The independent `obsidian-knowledge-retrieval` Skill passes the v1 acceptance
gate. It provides bounded, deterministic lexical retrieval without embedding,
network access, persistent indexes, caches, or Vault mutation. Its installed
payload contains only `doctor`, `vault-info`, and `search-vault`; write helpers
are absent.

## Versioned synthetic retrieval set

Fixture: `tests/fixtures/retrieval_eval_cases.json`

The fixture contains four notes and four representative mixed Chinese/English
queries covering:

- title and alias retrieval for MCP;
- the decision to defer local embedding;
- the two-Skill responsibility boundary;
- field-weight explanation for lexical ranking.

Result:

| Metric | Result |
|---|---:|
| Queries | 4 |
| Hit@1 | 1.00 |
| Hit@5 | 1.00 |
| MRR | 1.00 |
| Fixture file mutations | 0 |

This is a regression gate, not a claim that four synthetic cases predict
production recall. Future releases should expand the fixture before changing
tokenization, weights, or query expansion.

## Real Vault read-only acceptance

Vault: `/Users/shaopc/Documents/my-knowledge-base`

Three representative queries were run against the source implementation:

- `本地 embedding 知识库检索`
- `Superpowers skill 管理`
- `知识库痛点 检索`

Each run scanned 143 searchable Markdown notes, indexed all 143, skipped zero,
returned at most three results, and reported deterministic evidence fields.
Before and after the searches, SHA-256 snapshots covered 978 regular files in
the Vault. The snapshots were byte-for-byte identical.

This verifies no mutation by the exercised retrieval path. It does not claim
that the Vault already contains a note answering every query; for example, the
first query returned general knowledge-base notes because the newly approved
local-embedding decision had not been saved into that Vault.

## Release verification

Executed locally:

```text
uv run --locked --extra dev pytest
643 passed in 54.18s

uv run python build.py --check
All generated artifacts are up to date.

uv lock --check
Resolved 10 packages

python -m compileall
bash -n install.sh
git diff --check
all passed
```

The full suite includes source, generated payload, installed runner, clean-wheel
installation, Bash lifecycle, symlink, hostile-working-directory, manifest,
read-only, query-boundary, and malformed-note coverage. PowerShell was not
available on the development Mac; Windows installer parsing and runtime smoke
remain a required GitHub Actions check before merge.

## Known v1 limits

- Lexical matching cannot reliably recover synonyms absent from note metadata
  or body text.
- Ranking scores are ordering signals, not confidence or factuality.
- Search is in-memory and rescans the bounded scope on each invocation.
- Returned snippets may be sent to the hosting Agent's cloud model provider.
- Local embedding is intentionally not shipped in v1. A future provider must be
  optional, local, disabled by default, and evaluated against the lexical
  baseline before release.
