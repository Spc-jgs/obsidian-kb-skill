# Relatedness Scoring — Design

Target: `obsidian-knowledge-base`, on top of v1.28.0.

This document defines when two notes are related enough to link. It exists to be
tuned: the weights and the threshold are stated as data, in one table, so
changing the policy is an edit here rather than an argument about a number
buried in `score_pair`.

## Why a scale at all

Four unrelated notes — a streaming storage engine, an SQL optimizer rewrite, a
RAG latency guide, and a Zig coding agent — all linked the same note, which was
merely the alphabetically first file in `20-Learning/Backend/`. The Agent
invented every one of those links; `suggest-links` had proposed none of them.
The instruction fix (never fill a required `关联笔记` section with an invented
link) landed in v1.28.0+. This document is the other half: saying out loud what
"related enough" means, so the judgement is checkable.

## The problem with the current score

`score_pair` returns an unbounded integer:

| Signal | Points today |
|---|---|
| Each shared non-generic tag | +3, no cap |
| Same `type` | +1 |
| Title token overlap | +min(6, 2 × tokens) |

`MIN_SCORE = 3` is the bar. Two consequences, both measured on the reference
Vault (169 notes):

- **The bar is the mode.** Of the candidate pairs the helper surfaces, the
  single most common score is exactly 3 — the minimum. A pair clears it on two
  shared title tokens and nothing else. `AI-Agent` (a folder index) paired with
  four different notes on `title overlap: agent, ai`.
- **"60分" has nowhere to land.** Scores observed range 3–30, with 30 meaning
  "these two notes are near-duplicates of each other". There is no scale a
  percentage could refer to.

A second defect feeds the first: CJK titles are tokenised into overlapping
bigrams, so the single word `企业级落地` becomes four tokens (`企业`, `业级`,
`级落`, `落地`) and reads as four independent pieces of evidence. Today
`min(6, …)` hides it; on any 0–100 scale it would not stay hidden.

## The scale

Relatedness is an integer 0–100. Three components, capped independently, summed,
then clamped:

| Component | Rule | Max |
|---|---|---|
| **Shared specific tags** | 30 for the first, 20 for the second, 10 for each after | 60 |
| **Title concept overlap** | 15 per shared concept, after re-joining CJK bigrams into words and dropping generic tokens | 30 |
| **Same note type** | 10, flat | 10 |

Diminishing returns on tags is deliberate: the second shared tag confirms the
first, the fifth adds almost nothing. Generic tags (`web-clip`, `learning`, …)
and tags carried by half the candidate set are excluded before counting, exactly
as they are today.

**Type alone is 10.** Two `web-clip` notes about unrelated subjects score 10 and
must never look like a relationship. This is the numeric statement of "proximity
is not a relationship".

### The bands

| Band | Meaning | What the Agent does |
|---|---|---|
| **80–100** | Same subject, often the same series | Link, and say which |
| **60–79** | Genuinely related; a reader following the link learns something | Link |
| **40–59** | One weak signal, usually a single shared tag plus the same type | Do **not** link on the score alone |
| **0–39** | Proximity at most | Never link |

**The threshold is 60.** Sixty is not arbitrary: it is exactly "two shared
specific tags" (30+20), or "one shared tag plus two title concepts" (30+30). One
piece of evidence is never enough; the bar is two independent ones.

## Measured against the reference Vault

2,046 candidate pairs, scored under the table above:

| Band | Pairs | Share |
|---|---|---|
| 80–100 | 20 | 1.0% |
| 60–79 | 26 | 1.3% |
| 40–59 | 110 | 5.4% |
| 0–39 | 1,890 | 92.4% |

**46 pairs (2.2%) clear 60.** Spot-checks at the boundary:

- `Harness企业级落地-让AI读懂项目` ←→ `Harness 企业级落地系列专题` → **100**
  (4 shared tags, same type, `harness` + `企业级落地`). Correct.
- `LEFT JOIN 何时被优化器改写` ←→ `外连接消除的关系代数与 KES 优化器实现` →
  **75** (`database`, `sql`, same type, `优化器`). Correct — this is the link the
  Agent should have made instead of the one it invented.
- `解剖Claude-Code逆向工程视角` ←→ `MCP运行原理与API Key需求分析` → **55**
  (`architecture` alone, plus `分析`). Correctly rejected: one abstract tag two
  backend notes happen to share.
- `Violin Coding Agent` ←→ `SSE vs WebSocket 选型` → **10**. Correctly rejected;
  this was one of the four invented links.

## The case that does not fit

`RAG系统流式输出与首字延迟（TTFT）` ←→ `SSE vs WebSocket 选型` scores **40** and
is rejected — but the link is real. The RAG note carries an `sse` tag, an entire
section `### 4. 基于 SSE 的检索进度流式反馈`, and the Nginx configuration for
disabling SSE buffering. A reader following that link learns exactly why SSE was
the right transport.

The scorer misses it because **it never reads the body.** It sees frontmatter
tags and the title, and the RAG note shares only one tag with the SSE note.
Nothing in the weights table can fix this without also admitting the 110 pairs
in the 40–59 band, which are genuinely weak.

So the rule is asymmetric, and this is the most important sentence in this
document:

> **60 is the bar for a link proposed by the score. It is not a ceiling on
> judgement.** An Agent may link below 60 only when it can cite specific
> evidence from the note's body — a section, a configuration, a decision that
> depends on the other note — and it must state that evidence in the link's own
> line. "Same domain", "same folder", "also mentions X" are not evidence.

Above 60 the score justifies the link. Below 60 the body must, in writing.

## What changes

- `score_pair` returns 0–100 under the table above; `MIN_SCORE` becomes
  `RELATEDNESS_THRESHOLD = 60`.
- CJK title bigrams are re-joined into words before counting, reusing the
  chaining `vault_info._merge_overlapping_runs` already does for cluster labels.
  One shared Chinese word must count once.
- Each suggestion reports its `score` and a per-component breakdown, so a reader
  can see *why* it scored what it did rather than trusting a number.
- `note-creation.md` Step 6 gains the bands and the below-60 evidence rule.

## Deliberately not doing

- **Reading note bodies to score.** It would make suggestion cost scale with
  Vault size, and the helper's whole value is being bounded and deterministic.
  The below-60 evidence rule covers the gap with the Agent's own reading, which
  has already happened by the time it is writing the note.
- **Embeddings or semantic similarity.** Same reason the retrieval Skill stays
  lexical: no network, no index, no model.
- **Auto-inserting links.** The helper proposes; a human or an Agent with stated
  evidence decides. Unchanged.
- **Retroactively rescoring existing links.** An audit finding for "this link
  would score below 60" is plausible future work, deliberately out of scope
  until the scale has been used for a while.
