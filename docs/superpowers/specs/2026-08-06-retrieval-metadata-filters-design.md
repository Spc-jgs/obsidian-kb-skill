# Retrieval Metadata Filters — Design

Target: `obsidian-knowledge-retrieval`, on top of v1.28.0.

The write Skill enforces `type`, `date`, and `tags` on every note it creates.
The retrieval Skill parses that same frontmatter on every search and then throws
all three away. Its entire query surface is `--query --scope --top-k`, so the
only question it can answer is "which notes are lexically similar" — and it
answers every other question confidently and wrongly.

## Measured problems

Both numbers come from the reference Vault (165 indexed files, 178 notes).

### P1 — Non-note files rank as knowledge

`audit_vault.EXEMPT_NAMES` already declares `README.md`, `AGENTS.md`, and
`CLAUDE.md` to be scaffolding rather than notes. `search_vault` does not know
this and indexes them like any note. A Vault README is long and mentions every
subject, which makes it a lexical magnet.

Across twelve realistic questions (60 top-5 slots), 11 slots (18%) went to
non-knowledge files; `README.md` alone appeared in 6 of the 12. Asking "我对知识
库沉淀有什么洞察" returned `README.md`, `AGENTS.md`, and `INDEX.md` in the top
three, and none of the 13 notes in `30-Insights`.

### P2 — Temporal questions return wrong answers, not empty ones

`15-Daily` plus `10-Work` is 47 notes — 28% of the Vault — organised entirely by
date, with `date` in frontmatter and in most filenames.

| Query | Rank 1 returned |
|---|---|
| `7月的日报` | a **June** note, 《Python高级特性-生成器》 |
| `最近的周报` | `docs/superpowers/specs/…-governance-design.md` |
| `上周我做了什么` | notes from 07-09 and 06-10, no temporal constraint at all |

CJK tokenisation splits `7月` into unrelated tokens, so "7月" happily matches a
note written in June. This is the failure mode that matters most: the caller
cannot tell a wrong answer from a right one.

## Decisions

### D1 — Relative time is resolved by the Agent, never by the helper

`--after` / `--before` accept ISO `YYYY-MM-DD` only. "上周", "最近", "last
quarter" are resolved in the Skill instructions, where the current date and the
user's language already are.

Rejected: parsing natural-language dates in Python. It would mean shipping a
bilingual date grammar plus timezone and week-start policy into a helper whose
whole value is being deterministic and testable. It also contradicts the
established split — helpers return facts, the Agent decides. The Agent knows
today's date; the helper should not have to guess what "recently" means.

### D2 — Filters are hard constraints applied before ranking

If the user asks for July dailies, a June note is *wrong*, not merely less
relevant. Filters therefore reduce the candidate set before scoring; they do not
adjust `score`. This keeps `score` meaning exactly what `search.md` already says
it means — an ordering device, not a confidence.

### D3 — A filter that removes everything must say so

The cost of D2 is that a wrong filter looks identical to an empty Vault. The
response reports, per active filter, how many candidates it excluded, and names
candidates dropped for *missing* the field rather than mismatching it. An Agent
must be able to distinguish:

- "nothing in your Vault matches" — a real answer;
- "your date range excluded all 47 dailies" — retry with a different range;
- "31 notes have no `date` at all" — a governance problem, not a search result.

This is the same rule the Git pre-write gate was fixed under: a gate that stops
you must tell you what to do next.

### D4 — Exclusion is limited to what the write Skill already excludes

`EXEMPT_NAMES` moves to the shared domain and both Skills import it, the same
fan-out the shared error codes use. Matching is by filename at any depth, so
`20-Learning/Python/AGENTS.md` is covered too.

Simulated on the twelve queries: noise drops from 11/60 (18%) to 2/60 (3%).

Explicitly **not** excluded:

- **`INDEX.md` and `type: folder-index` notes.** They are navigational
  knowledge; "这个知识库怎么组织的" legitimately wants them. They account for the
  2 remaining slots, and that is a correct answer, not noise.
- **Files with no frontmatter `type`.** Tempting — it separates scaffolding
  cleanly on paper — but on the reference Vault 9 files lack `type` and two of
  them are real user notes (`00-Inbox/0713日记.md`, `40-Projects/skill-mining/
  2026-08-05-skill-candidates.md`). Silently dropping a user's diary is a worse
  failure than ranking a README too high.
- **`docs/`.** Non-knowledge *in this Vault*, ordinary knowledge in another. A
  hardcoded folder name would be a guess about someone else's Vault; `--scope`
  and `--type` already let the caller say what they mean.

### D5 — Results carry the metadata they were filtered on

Each result gains `type` and `date`. Without them the Agent cannot explain why a
result qualified, and cannot tell an index note from an insight note when it
cites one. Zero extra I/O: `_document` already parses the frontmatter.

## Interface

```bash
search-vault <vault> --query "<q>" --json \
  [--scope <folder>] [--top-k N] \
  [--type <slug>]...  [--tag <tag>]... \
  [--after YYYY-MM-DD] [--before YYYY-MM-DD]
```

- `--type` and `--tag` are repeatable; repeats within one flag are OR, across
  flags are AND. `--tag ai-agent --tag llm` means either tag; `--type daily-note
  --tag work` means both conditions.
- `--after` / `--before` are inclusive and read frontmatter `date`. A note with
  no parsable `date` never satisfies a date filter, and is counted separately.
- Every filter is optional; with none supplied the output is byte-identical to
  today's apart from the new per-result fields.

Response gains:

```json
"filters": {
  "applied": {"type": ["daily-note"], "after": "2026-07-01"},
  "candidates": 165,
  "matched": 12,
  "excluded": {"type": 148, "after": 5, "missing-date": 2}
}
```

New refusal codes, following the existing `invalid-*` shape: `invalid-date`
(not ISO `YYYY-MM-DD`), `invalid-date-range` (`--after` later than `--before`),
`invalid-type`, `invalid-tag` (empty or over the length cap). All are argument
contract violations, so they refuse rather than silently returning nothing.

## Skill instruction changes

`RETRIEVAL.md` step 3 gains one sentence: resolve any relative time expression
against today's date before calling, and pass ISO dates.

`search.md` gains a section covering when to filter (the user named a period, a
note kind, or a topic tag), how to read `filters.excluded`, and the rule that an
empty result under an active filter must be reported as "nothing matched *this
filter*", never as "your Vault has nothing on this".

## Out of scope

- Ranking changes of any kind. `FIELD_WEIGHTS` and BM25 are untouched.
- Vector or embedding retrieval. The research this came from found keyword
  search beats vectors for the proper nouns and code identifiers a personal KB
  is full of, and the no-network, no-index guarantee is a feature.
- Answer synthesis or multi-hop retrieval.
- The connectivity signal parked in issue #57.

## Verification

- Filter unit tests per dimension, plus the interaction of two filters.
- A drift-lock that `EXEMPT_NAMES` has exactly one definition, matching the
  shared error-code contract test.
- The twelve reference queries as a regression fixture, asserting the noise
  count does not regress.
- A test that `filters.excluded` is populated on a filter that matches nothing —
  the empty-result case is the one that must never be silent.
