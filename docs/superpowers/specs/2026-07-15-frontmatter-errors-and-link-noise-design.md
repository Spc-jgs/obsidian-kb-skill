# Frontmatter Errors and Link Noise Design

## Goal

Make invalid input frontmatter fail with actionable location data and suppress link suggestions whose only title evidence is generic wording.

## Scope

This patch changes two existing helper behaviors only:

1. `create-note` and other callers of the shared frontmatter parser must not silently replace malformed YAML with empty metadata.
2. `suggest-links` must not award title-overlap points for generic Chinese or English article words.

Automatic folder creation, governance-prose parsing, and date semantics are explicitly out of scope.

## Invalid frontmatter contract

`split_frontmatter` raises `InvalidFrontmatterError` when a leading, closed frontmatter block contains invalid YAML. The error carries:

- a stable `invalid-frontmatter` code;
- a concise PyYAML problem message;
- 1-based line and column coordinates relative to the complete Markdown input, including the opening `---` line.

For `create-note`, all JSON output modes return one error object and exit 2 before preview, preflight, apply, audit, or index mutation:

```json
{
  "error": {
    "code": "invalid-frontmatter",
    "source": "stdin",
    "line": 3,
    "column": 17,
    "message": "expected <block end>, but found '<scalar>'"
  }
}
```

Human-readable mode prints the same source, line, column, and message to stderr. `--content-file` identifies the validated file path as the source. Invalid Vault templates and invalid existing task-memory notes also fail explicitly rather than continuing with defaults.

Valid YAML, BOM/CRLF normalization, metadata precedence, web-clip required-field validation, and output schemas for successful calls remain unchanged.

## Generic title-token contract

Title tokenization continues to support Latin runs and overlapping CJK bigrams. A small deterministic stop set removes generic article wording before folder relevance and pair scoring. Initial Chinese terms include `详解`, `指南`, `实践`, `教程`, `攻略`, `入门`, `解析`, `介绍`, `总结`, and `分享`; English equivalents include `guide`, `tutorial`, `overview`, `introduction`, `intro`, `practice`, and `explained`.

Filtered terms add no points and do not appear in reasons. A pair sharing only note type plus a filtered title term therefore remains below the existing confidence threshold. Specific technical title tokens and specific tags keep their current weights.

## Acceptance criteria

- The reported malformed author example fails at full-input line 3, column 17 and does not write a note.
- Text, full JSON, compact JSON, and preflight JSON expose the same stable error details.
- A malformed existing task-memory note is not overwritten.
- `Vibe Coding ... 详解` and `Hermes Agent ... 操作详解` do not match solely on `详解` and type.
- Existing CJK technical matches and real-Vault `spring-boot` suggestions still work.
- No new runtime dependency or network call is introduced.
