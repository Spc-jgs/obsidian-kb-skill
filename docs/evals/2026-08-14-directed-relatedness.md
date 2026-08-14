# Directional relatedness — evaluation (#75)

v1.30 froze 32 labelled directions and shipped no scorer. This is what happened
when one was finally built against them.

## The labels are the independent half

`tests/fixtures/directed_link_eval_cases.json` was committed on 2026-08-09 with
`purpose` reading *"v1.30 adds no scorer"* — a commitment about what a scorer
would have to achieve, made before one existed. Everything else in this
evaluation was written afterwards by the same hand that wrote the scorer, so the
labels are the only part not authored to make the implementation look good.

They also came with no corpus. The labels name notes — `Retry Policy`,
`Backoff Measurements` — that did not exist as files, and the pre-existing test
only checked the labels' own structure. Building the corpus was therefore step
one, done from the labels alone and before the scorer was designed, with two
assertions tying the two together (registry rows 39 and 40).

## What the labels actually say

**All sixteen hard negatives are a single shared word.**

| negative | the word |
|---|---|
| `Release Quality Gate ↛ Airport Departure Gates` | gate |
| `Deterministic Ranking ↛ University Rankings` | rank |
| `Source Archive Format ↛ Museum Archive Visit` | archive |
| `Read-only Retrieval ↛ Reading List` | read |
| `Semantic Candidate Order ↛ Election Candidates` | candidate |
| `Capture Receipt Contract ↛ Receipt Printer Review` | receipt |

A ranker built on word overlap scores every one of them highly. This set exists
to punish exactly the approach `search-vault` uses, and it says so by
construction rather than in prose.

**All sixteen positives are a declared dependency.** Their `evidence` lines use:
*cites, names, delegates to, traced to, adopted in response to, expressed as a
multiple of, references, links to … for its, selected from, consumes, imports,
branches on, proven with, follows, fails when*. Every one has the same shape:
the source note says, in its own text, what it uses the target for.

## The threshold, pre-registered

Recorded on the issue before any code existed:

> The criterion is not similarity but declared dependency. Positives need an
> explicit reference plus a dependency phrase in the same sentence; negatives
> are predicted to score **zero**, not "below a threshold". If the sixteen
> negatives can only be rejected by tuning a number, the criterion is wrong and
> the answer is to redesign, not to tune.

**The prediction held.** There is no numeric threshold in the implementation.

| | |
|---|---:|
| positives found, with evidence | **16 / 16** |
| hard negatives proposed | **0 / 16** |
| links seen on the negative side without a dependency | **0** |

That last row is the one that matters. Zero means the negatives never produced a
reference at all — `Retry Policy` does not mention `Museum Archive Visit` — so
they score nothing rather than scoring low. No threshold separates them because
nothing needs separating.

### What 16/16 does *not* prove

Found by breaking the implementation on purpose, which is the only reason it is
in this report. Deleting the dependency requirement entirely — admitting every
declared link — still rejects **all sixteen negatives**, because a note the
source never links to cannot become a candidate whatever the rule is.

So the sixteen guard one thing and not the other: they prove a relation is not
inferred from a shared word, which is real and is what they were written for.
They say nothing about the distinction that actually earns this helper its place
— a link with a stated dependency versus a link without one. That distinction
rests on two hand-written cases (`See also` with a bare link, and a dependency
phrase sitting in a different section from the link), and
`test_the_hard_negatives_do_not_exercise_the_dependency_requirement` asserts the
division so this paragraph cannot quietly stop being true.

The same pass found the same-sentence rule was **unguarded**: replacing the
sentence window with the whole note broke nothing. It has a test now.

## The reference Vault: precise, and honest about the yield

195 notes, 9.5 ms each, byte-identical afterwards.

| | |
|---:|---|
| 262 | lines containing a wikilink |
| **5** | candidates, across 3 notes |
| 256 | links correctly rejected as bare mentions |

The five are all real:

```
…RAG系统流式输出与首字延迟（TTFT）全链路优化指南.md  →  …SSE vs WebSocket 服务端推送选型对比.md
   「那篇是 SSE / WebSocket / 轮询的选型依据」

…Python高级特性下-迭代器.md   →  …Python高级特性中-生成器.md
…Python高级特性中-生成器.md   →  …Python高级特性上-切片迭代与列表生成式.md
   「前置知识：你需要了解 …」
```

The Python series' prerequisite chain is precisely the directed dependency #75
describes: iterators depend on generators depend on comprehensions.

**Five out of 262 is the finding, not a defect.** The scorer does what the
labels specify, and what the labels specify is something this Vault does
roughly twice per hundred links. People link; they rarely write down what they
are leaning on. Loosening the criterion to raise that number would readmit the
sixteen hard negatives, which is the trade the whole evaluation set exists to
refuse.

## The vocabulary, and what was left out of it

The dependency phrases come from the frozen labels. Two more were added from
forms **observed in the reference Vault**, on the same terms
`PROJECT_NOTE_NEXT_ACTION_HEADINGS` uses — a count and a location, never a
guessed synonym:

- `前置知识` ×3, `前序知识` ×2 — "you need to understand X first" is a
  dependency by any reading. Adding them took the Vault from 1 candidate to 5.

Measured in the same pass and deliberately **not** added:

- `详见` ×4 and `参考` ×2. Both are pointers rather than dependencies — "for
  details see X" is `See also` in Chinese, and one of the two `参考` hits is
  literally "官方参考链接". Admitting either would readmit every bare mention,
  which the `See also` hard negative exists to prevent.

A Vault that states dependency some other way returns nothing. That is an honest
miss rather than a silent one, and the reference says so.

## Explicit non-goals, held

- No score, no threshold, no confidence number.
- No link is created or modified; candidates are proposals for a human.
- No inference from folder, type, date or proximity.
- An ambiguous name is skipped rather than guessed, as in `explore-neighborhood`
  and `resume-project`.
- `suggest-links` is untouched and its tests are unchanged.
