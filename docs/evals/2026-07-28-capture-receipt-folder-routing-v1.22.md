# Capture Receipt and Folder Routing v1.22 Evaluation

## Scope

This evaluation checks that v1.22 converts the observed cross-model article
quality failures into inspectable pre-write failures and reports real folder
pressure without mutating the Vault.

It does not claim that a structured receipt proves semantic truth. It proves
that the exact candidate supplied complete, profile-specific review evidence,
that measurement-shaped values received provenance context, and that preflight
and apply used the same candidate and receipt identity.

## Deterministic Gates

The receipt suite covers:

- complete primary-source access and candidate-source agreement;
- content SHA-256 and preflight receipt SHA-256 binding;
- required material kinds for tutorial, resource, conceptual, and evidence
  profiles;
- exact note anchors for material items, numerical claims, inferences, and the
  practical artifact;
- numerical provenance and measurement context;
- explicit inference labels and evidence bases;
- empty unresolved items;
- valid YAML in copyable shell examples that create `SKILL.md`;
- inline JSON and bounded non-symlink UTF-8 receipt files;
- quick Inbox captures that retain the receipt-free path.

The final local suite passed 596 tests. Generated adapters and payloads passed
`build.py --check`; `uv.lock` passed `uv lock --check`.

The source distribution and wheel built as v1.22.0. An isolated installer run
from a neutral directory installed both Codex and WorkBuddy payloads with
explicit template replacement; both installed `doctor --json` calls returned
`ok: true`, version `1.22.0`, and no missing, extra, or changed payload files.

## Real Article Regression

The real Vault was inspected read-only.

### AI Workflow Opinion Article

Candidate:

`20-Learning/AI-Agent/2026-07-28 掘金文章-别再学工具了先搭你的AI工作流.md`

A content-bound conceptual receipt supplied the existing causal, application,
and boundary anchors. Validation failed with:

```json
{
  "code": "incomplete-profile-evidence",
  "missing_kinds": ["counterexample"]
}
```

This article can no longer pass only by restating the workflow thesis and
author metrics. It must preserve or explicitly discuss a counterexample before
conceptual semantic acceptance.

The measurement scanner separately covers the observed unsupported `60%` and
`70/30` shapes, along with percentages, ratios, durations, before/after values,
abbreviated counts, and star counts. Each occurrence must sit inside a receipt
excerpt with declared provenance and measurement context.

### Spring Boot Resource Guide

Candidate:

`20-Learning/Java/2026-07-27 知乎文章-SpringBoot相关的Skills全景指南.md`

Validation stopped before self-attestation with:

```json
{
  "code": "invalid-copyable-skill-frontmatter",
  "block": 1,
  "line": 5,
  "column": 1
}
```

The detector found the unkeyed `Use when...` line in the copyable shell example
that creates `SKILL.md`. Resource receipts also require separate compatibility,
limitation, selection-criteria, canonical-link, and starting-example evidence,
so one global compatibility claim cannot satisfy the profile contract.

## Real Folder Pressure

Compact discovery returned:

```json
[
  {
    "path": "10-Work/日报",
    "direct_notes": 25,
    "threshold": 20
  },
  {
    "path": "20-Learning/AI-Agent",
    "direct_notes": 25,
    "threshold": 20
  }
]
```

Folder indexes, hidden files, nested notes, and directory symlinks are excluded.
No category or note was created, moved, or rewritten. The Skill loads
`folder-routing.md` only when the selected destination appears in this bounded
list; it still requires explicit confirmation and the existing
`create-category` preflight before creating a child.

## Progressive Disclosure

Raw UTF-8 instruction size:

| Path | v1.21 | v1.22 | Change |
| --- | ---: | ---: | ---: |
| Always-loaded core | 2,451 bytes | 2,596 bytes | +145 |
| Ordinary create reference | 9,476 bytes | 10,714 bytes | +1,238 |
| Conditional deep-capture reference | 6,674 bytes | 12,260 bytes | +5,586 |
| Conditional crowded-folder reference | absent | 1,811 bytes | conditional |

The substantial evidence schema remains article-only. Folder taxonomy guidance
is loaded only for a crowded selected destination. Quick Inbox and ordinary
notes do not build or validate a receipt.

## Acceptance

- source tree and generated payloads: passed;
- 596 local tests: passed;
- Skill Creator validation: passed;
- sdist, wheel, Bash syntax, and isolated Codex/WorkBuddy install: passed;
- real Vault crowded-folder discovery: passed, read-only;
- real AI workflow semantic regression: failed as intended;
- real Spring Boot copyable-example regression: failed as intended;
- real Vault Git state after evaluation: clean.
