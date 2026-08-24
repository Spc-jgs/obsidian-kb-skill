# Naming what the Vault has never recorded (#195), and two rulings beside it

**Status: accepted.** One signal added to `confidence`; #192 and #194 close as
records. All three come from one measurement pass over the 42-case annotated set.

## The gap #195 states

`#170`'s `confidence` is reliable on cross-domain no-answer queries and fails on
near-miss ones. Its two motivating cases still come back as `evidence`:

- `Feign 和 HttpExchange 有什么区别` → coverage 0.538, top-1 a Python note
- `Spring Boot 事务失效` → coverage 0.479, top-1 the ArchUnit note

The design said the fix needs **another signal, not another knife**, because the
two coverage ranges overlap.

## What the measurement found, which is not what #192 guessed

#192 supposed that cross-boundary CJK bigrams (`么区` out of 什么/区别) let any
question-framed query win on a long tutorial note. Step 2 of its own checklist
refutes that. Stripping the question frame and re-querying:

```
带框架                              去掉框架                       top-1
Tailscale 和 ZeroTier 有什么区别      Tailscale ZeroTier 区别         同
SSE 和 WebSocket 该怎么选             SSE WebSocket 选型              同
MCP 的运行原理是什么                   MCP 运行原理                    同
六个必备的 MCP 服务分别是什么            六个必备 MCP 服务                同
ThreadLocal 内存泄漏怎么避免            ThreadLocal 内存泄漏 避免        同
Python 的生成器怎么用                  Python 生成器                   同
Feign 和 HttpExchange 有什么区别      Feign HttpExchange 区别         ★变
区块链的共识算法有哪些                  区块链 共识算法                  ★变
Flutter 的 Widget 重建机制是怎样的      Flutter Widget 重建机制         ★变
CompletableFuture 的异常传播          CompletableFuture 异常传播      ★变
OAuth2 授权码模式的完整流程             OAuth2 授权码模式 流程            ★变
```

**Every query with an answer keeps its winner; every query that changes is a
no-answer query.** The frame words decide nothing when there is something else
to match — and where they do decide, the ranking was noise already.

What the fragments really distort is the **coverage metric**, on both sides.
Decomposing it per token (df over the 201-note candidate set):

```
Feign 和 HttpExchange 有什么区别        coverage 0.538   ← wrong answer
  feign          df=0   IDF 6.001   ·      httpexchange   df=0   IDF 6.001   ·
  么区            df=1   IDF 4.903   ✓      有什            df=4   IDF 3.804   ✓
  区别           df=14   IDF 2.634   ✓      和             df=44   IDF 1.513   ✓
  什么           df=64   IDF 1.142   ✓

ThreadLocal 内存泄漏怎么避免             coverage 0.458   ← correct answer
  么避            df=0   IDF 6.001   ·      漏怎            df=0   IDF 6.001   ·
  泄漏            df=4   IDF 3.804   ✓      threadlocal    df=4   IDF 3.804   ✓
  ...
```

`么区` and `有什` supply **8.707 of the 13.995 held weight — 62%** of the
"evidence" for a wrong answer, because a cross-boundary bigram is *rare*, and
IDF reads rare as informative. In the other direction `么避` and `漏怎` are
df=0, so they inflate a correct answer's denominator. **A correct answer scores
lower than a wrong one.** That is why the ranges overlap, and it is a property
of the metric, not of near-miss queries.

## The signal

An **unseen term**: a Latin query token of at least 3 characters, not all
digits, whose document frequency in the searched scope is zero.

Such a token cannot be matched by anything, so its presence says the reader
named something the scope does not contain. When one exists, `confidence.level`
is `none` regardless of coverage, and the terms are reported so a caller can act
on them.

CJK bigrams are deliberately excluded. A df=0 bigram is a character adjacency
that happens not to occur (`么避`, `漏怎`); a df=0 Latin run of three or more
characters is a name. That distinction is mechanical and needs no word list —
which matters, because #147 and #75 both settled that a word list needs a
countable source.

## The measurement

Over the annotated set — 16 positives whose top-1 is correct, 4 whose top-1 is
wrong, 22 with no answer:

| variant | demotes correct answers | catches no-answer | catches the Feign leak |
|---|---:|---:|:--:|
| len≥2, digits kept | 0/16 | 15/22 | yes |
| len≥2, digits dropped | 0/16 | 14/22 | yes |
| **len≥3, digits dropped** | **0/16** | **13/22** | **yes** |
| len≥4, digits dropped | 0/16 | 10/22 | yes |

**Zero false positives in every variant**, and none of them fires on the four
positives whose top-1 is wrong (`NOT IN …`, `六个必备的 MCP 服务`,
`Harness 怎么让 AI 读懂项目`) — those name only terms the Vault does have.

Merged with the existing floor:

```
coverage < 0.30 alone                    19/22
unseen terms alone                       13/22
both                                     20/22
still missed   Spring Boot 事务失效, Spring Security 的过滤器链顺序
```

**The net gain is one query out of 22.** It is worth the code for what that one
query is, not for the count: `Feign` came back as `evidence` at 0.538 — a
*confidently wrong* answer, which is the failure #170 exists to prevent and the
only kind a caller cannot defend against. And the statement is actionable in a
way a coverage number is not: "the scope holds nothing for `feign`" tells an
Agent to capture the topic; "coverage 0.538" tells it nothing.

Digits are dropped because `H.264 和 H.265 编解码的码率差异` tokenises to `264`,
`265` — a Vault holding an H.265 note would be reported as knowing nothing about
it. `len≥3` costs one detection against `len≥2` and drops two-character runs,
which are mostly fragments of versions and abbreviations; if a real miss is ever
reported, `len≥2` is the first thing to try, and it too measured 0/16.

## Scope, not Vault

The frequencies are computed over the **filtered candidate set**, because #170
made IDF mean "informative among the notes the caller asked about". So an unseen
term is unseen *in the searched scope*, and a `--tag` filter can make a term
unseen that the Vault holds elsewhere. The reported explanation says scope, not
Vault, for that reason.

## #194: the `links` field is inert by construction, and stays

`FIELD_WEIGHTS["links"]` is 2.0 and #194 measured that 0.0 through 2.0 changes
nothing on the annotated set. The mechanism is now known, and it rules out both
options the issue offered.

**Every `links` token is also a `body` token — 1331 of 1331 instances, 100.0%.**
`_wikilink_text` feeds a link's visible text into the citing note, and that text
is already inside the citing note's body, because the link markup *is* body
text. So `links` is a duplicate count, never an independent one: on the 42
queries, **0 have a token matched by `links` and by no other field** (7 have a
`links` match, all also matched elsewhere).

The shape #194 wanted to construct — "the answer note does not contain the query
words, only notes citing it do" — **cannot exist**. A synthetic corpus where
`量子退火` appears only as a wikilink's visible text returns the *citing* note at
every weight (2.0, 0.0, 100.0) and never the cited one. The field points the
wrong way to do what it was imagined to do.

So raising the weight is also wrong: it would rank by how many links a note
carries, which is not relevance.

**Removal was measured and rejected.** Deleting the field leaves the annotated
set identical — 16/20 top-1, MRR 0.9000 — while failing 17 tests: both frozen
baselines, the whole query-expansion group, `build --check`, and the assertion
pinning the corpus's scoring-unit divergence at 2.0–2.4 (row 62), because
`weighted_length` feeds `average_scoring_length`. Regenerating two frozen
baselines to achieve no outcome change would pollute the diff of the next real
ranking change, which is what those baselines are for.

What is a defect is the misinformation: the table says link text is worth 2x
body when it is really worth **3x** — 1x in `body` plus 2x again in `links` —
and nothing said so. It came in with the original retrieval Skill (`9f7e634`,
2026-07-29) with no comment and no measurement. That is now stated where the
constant is declared, and guarded: an assertion that every `links` token is also
a `body` token. If that ever stops holding, the field has become a real signal
and its weight is worth tuning — and the test says so instead of the next person
re-running the sweep.

## #192: closed as refuted

Its hypothesis was that cross-boundary bigrams let question-framed queries win.
The contrast experiment above refutes it for every query that has an answer. The
real effect is on the coverage metric, and it is handled here. Four causes it had
already ruled out stay recorded; a fifth is added.

## Registry rows

| Boundary | Guard |
|---|---|
| `UNSEEN_TERM_MIN_CHARS` ↔ the sweep that chose it | `test_the_unseen_term_floor_is_the_value_the_sweep_chose`, with the variant table recorded here |
| `FIELD_WEIGHTS["links"]` as a claim about weight ↔ what link text actually scores | `test_every_link_token_is_also_a_body_token` — the field is a duplicate, so its documented 2x is really 3x; if the duplication ends the weight becomes tunable |
