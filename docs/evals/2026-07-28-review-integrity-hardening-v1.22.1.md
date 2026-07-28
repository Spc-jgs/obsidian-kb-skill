# Review Integrity Hardening v1.22.1 Evaluation

## Scope

This evaluation covers every P1 and P2 review finding reported after PR #21
and PR #22. The release goal is not to make a receipt prove that an article is
true. It is to prevent known deterministic ways to bypass the published
deep-capture contract and to make the remaining evidence reader-visible,
resource-specific, and reproducible.

The findings were reproduced against v1.22.0 before implementation. One PR #21
finding, material source-backed rewrites bypassing deep capture, was already
fixed in v1.22.1's base and received regression coverage rather than a second
behavior change.

## P1 Release Blockers

### Canonical destination routing

`create-note` now resolves the destination inside the canonical Vault before it
decides whether a capture receipt is required. Regression tests prove that:

- `00-Inbox/../20-Learning` cannot inherit the Inbox exemption;
- an Inbox child symlink resolving to `20-Learning` cannot inherit it;
- preflight and apply both report and write the canonical Vault-relative path;
- traversal outside the Vault remains rejected.

The original disposable apply case now stops at the receipt gate instead of
writing into `20-Learning`.

### Reader-visible semantic evidence

Semantic anchors now search a reader-facing Markdown projection. YAML
frontmatter and HTML comments outside fenced examples are excluded. A candidate
whose anchors exist only in hidden metadata or comments fails even if the
visible article is empty. Visible fenced commands remain eligible because they
are part of the rendered article.

Multiline comments containing fence-looking text are covered so hidden content
cannot accidentally reopen the visible projection.

## P2 Contract Coverage

The regression suite verifies:

- exact English template markers used by the shipped templates;
- tilde fences and variable-length backtick fences;
- heredoc-first shell commands that create `SKILL.md`;
- English months and years, `B`, thousand/million/billion, 万, and 亿
  measurement shapes;
- inference labels occurring inside their exact note excerpt;
- a concrete resource inventory with canonical URL plus compatibility,
  limitation, and canonical-link evidence for every declared resource;
- finished source-backed articles routing through `web-clip`;
- fresh Task Memory preflight remaining read-only and apply creating only
  `Tasks/<slug>`;
- ordinary missing destinations continuing to fail;
- material source-backed rewrites continuing to load deep capture and require a
  receipt.

## Build and Test Evidence

- full local suite: 621 tests passed;
- focused capture, creation, and audit suites passed again after the final
  defensive input hardening;
- generated adapters, packaged references, and embedded scripts match source;
- `uv.lock`, whitespace, Python compilation, and Bash syntax checks passed;
- Skill Creator validation returned `Skill is valid!`;
- source distribution and wheel built as version `1.22.1`;
- the wheel installed into an isolated Python 3.14 environment and reported
  distribution version `1.22.1`.

The release remains gated on GitHub Actions for Python 3.11, Python 3.14, and
Windows before merge.

## Real Vault Read-Only Check

The real Vault remained unmodified. The current Spring Boot resource guide:

`20-Learning/Java/2026-07-27 知乎文章-SpringBoot相关的Skills全景指南.md`

still fails before self-attestation with:

```json
{
  "code": "invalid-copyable-skill-frontmatter",
  "block": 1,
  "line": 5,
  "column": 1
}
```

This confirms that the stronger receipt changes do not mask the article's
existing malformed copyable `SKILL.md` example.

## Progressive Disclosure

Raw UTF-8 instruction size:

| Path | v1.22.0 | v1.22.1 | Change |
| --- | ---: | ---: | ---: |
| Always-loaded core | 2,596 bytes | 2,596 bytes | 0 |
| Ordinary create reference | 10,714 bytes | 11,016 bytes | +302 |
| Conditional deep-capture reference | 12,260 bytes | 13,185 bytes | +925 |

The always-loaded Skill body does not grow. Detailed per-resource evidence
stays in the conditional deep-capture reference and transient receipt. Ordinary
notes do not pay the article-only contract cost.

## Local Acceptance

- all reproduced P1 bypasses: blocked;
- all reproduced P2 gaps: covered;
- existing rewrite fix: regression-protected;
- source and generated payloads: current;
- package build and isolated installation: passed;
- real Vault read-only regression: failed as intended;
- repository and real Vault state before publishing: no unrelated changes.
