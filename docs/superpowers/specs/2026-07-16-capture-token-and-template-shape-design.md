# Capture Token and Template Shape Design

## Goal

Reduce ordinary note-capture instruction tokens and prevent avoidable first-preflight heading failures without weakening Vault governance, template quality, structured preflight, exclusive apply, automatic audit, Git safety, or custom-template hash protection.

## Scope and Repository Boundary

This change has two independently reviewable deliverables:

1. `/Users/shaopc/Documents/my-knowledge-base` removes duplicated root governance and moves Python-only rules to the Python subtree.
2. `/Users/shaopc/playground/obsidian-kb-skill` exposes the selected standard template's heading shape through the existing compact discovery call and lazy-loads exceptional workflow details.

Each repository uses its own feature branch, verification, commit history, and pull request. Neither repository is released or merged merely because the other passes.

## Vault Governance Design

`AGENTS.md` remains the authoritative cross-agent Vault policy. It keeps:

- type and topic routing, including governed learning subfolders;
- filename and required metadata rules;
- high-confidence wikilink policy;
- Git commit/publication requirements;
- Folder Index ownership and no-manual-list constraints;
- deletion/overwrite restrictions;
- the compact README update decision.

The root file stops duplicating template bodies and Python automation details. Template structure is delegated to `Templates/<Name>.md`. Python-only automation, learning style, tutorial progress, and enterprise-WeChat output rules move to `20-Learning/Python/AGENTS.md`, where they apply only to that subtree.

`CLAUDE.md` becomes a short platform entrypoint. It identifies the Vault and delegates all write governance to `AGENTS.md` instead of repeating routes, indexes, tags, and restrictions. It must not contradict or partially shadow `AGENTS.md`.

Success criteria:

- root `AGENTS.md` plus `CLAUDE.md` drops materially below the current 3,531 `o200k_base` tokens;
- all current routes, Git requirements, prohibited operations, Folder Index ownership, and README decisions remain discoverable;
- Python-specific rules remain complete when operating below `20-Learning/Python/`;
- an existing-category Web Clip does not need Python rules or duplicated Claude context.

## Selected Template Shape Interface

Extend compact discovery with an optional selected note type:

```bash
vault-info <vault> --json --compact --type web-clip
```

The existing response remains backward compatible. When `--type` is supplied and supported, add exactly one bounded field:

```json
{
  "template_shape": {
    "type": "web-clip",
    "path": "Templates/Web Clip.md",
    "headings": [
      "来源信息",
      "一句话摘要",
      "核心观点",
      "重要摘录",
      "理解与启发",
      "后续行动",
      "关联笔记"
    ]
  }
}
```

Rules:

- return only the selected conventional template's ordered level-two headings;
- never return template prose, examples, frontmatter, labels, lists, or tables in this field;
- preserve `custom_templates`; when the selected type is custom, the agent still loads the existing full `template-contract` and uses its SHA-256 gate;
- missing selected templates return `template_shape: null` and retain existing missing-template behavior during create;
- unsupported `--type` values exit with a stable structured error and no Vault mutation;
- omitting `--type` preserves the current response shape and behavior.

The ordinary workflow should infer a type from the explicit request before discovery when confidence is high, such as URL capture becoming `web-clip`. If type is genuinely unclear, discovery runs without `--type` and current preflight diagnostics remain the fallback. No second discovery call is introduced.

## Conditional Instruction Loading

`note-creation.md` remains the single ordinary reference and keeps the complete common path. Two exceptional branches move behind explicit one-level references:

- missing governed category details load only when discovery and governance show that the target category is absent;
- custom-template interpretation details load only when the selected type appears in `custom_templates`.

The ordinary reference retains enough inline gates to prevent accidental mutation: user confirmation for new categories, one-contract-only loading for custom templates, unknown-placeholder stop, and expected SHA-256 on both preflight and apply. The split must not add a reference read to ordinary existing-category captures.

## Rejected Alternatives

- Relaxing required template headings lowers quality and is rejected.
- Automatically appending empty headings hides incomplete drafting and is rejected.
- Returning every template shape in discovery adds unrelated context and is rejected.
- Reading the full standard template on every capture violates the default-path token goal and is rejected.
- Combining the Vault and Skill edits in one repository or PR is impossible to review and roll back cleanly and is rejected.

## Verification

Vault verification:

- measure `AGENTS.md`, `CLAUDE.md`, and Python-local governance with `o200k_base` in an isolated analysis environment;
- assert required policy phrases and every governed route remain present;
- run a read-only existing-category Web Clip governance walkthrough;
- confirm Git status contains only intended governance files.

Skill verification follows TDD:

- first add failing tests for `--type`, one selected ordered heading shape, omitted-type compatibility, unsupported-type errors, missing-template null, and no template prose leakage;
- add failing lazy-reference tests proving exceptional details are absent from the ordinary body and reachable through one-level conditional references;
- implement the minimal helper and instruction changes;
- regenerate packaged references and Skill payloads;
- run targeted tests, full pytest, build drift check, lock check, wheel build, installed runner doctor, hostile-directory discovery smoke, and Windows CI before merge.

## Non-goals

- no semantic model, webpage extractor, or `tiktoken` runtime dependency;
- no renamed-template discovery in this change;
- no change to template content, audit severity, note routing semantics, or Git publication policy;
- no removal of preflight, apply, audit, or custom-template hash checks.
