# Hypotheses this project tested and rejected

A conclusion that something **cannot** be done, or **should not** be done, leaves
no trace in the tree. No test guards it, no code names it, and the next person to
look at the same finding will re-derive it from scratch — and may not stop where
the evidence stopped.

Each entry records the hypothesis, the criterion that was tried, how the data
killed it, and what would reopen it. An entry belongs here only if it was
rejected **by measurement**, with the command that produced the numbers.

---

## 1. A broken wikilink cannot be split into "concept placeholder" and "deleted note"

**Hypothesis.** `broken-wikilink` over-reports: in Obsidian, linking a note that
does not exist yet is standard usage, so the audit should separate real breakage
from a deliberate concept placeholder and grade the latter `informational`.

**Criterion tried.** A concept placeholder would be referenced by *several* notes
(that is why it deserves its own note); a deleted note usually has *one* inbound
link. Counting inbound references per unresolved target should separate them.

**How it died.** Measured on the reference Vault, per target:

```
Obsidian知识库Skill使用指南与原理   2   ← has a date prefix, fixable
构建跨平台AI Agent知识管理Skill     2   ← has a date prefix, fixable
AI Agent            2
Prompt Engineering  2
SpringBoot          2
CQRS                1
系统架构与设计            1
MySQL / InnoDB / AGI …  1 each
```

Every concept placeholder is referenced exactly once — identical to a deletion.
The count cannot separate them.

**The deeper reason.** From a single snapshot, "the note was deleted" and "the
note is not written yet" leave the same trace: no file, and a link pointing at
it. **Obsidian itself does not distinguish them.** An audit claiming to would be
claiming knowledge it does not have, and downgrading on a hypothesis the data
has already refuted hides real breakage.

**What was done instead** (#155). Only the half that stands: when the target
exists under a `YYYY-MM-DD ` prefix, the error says what to write.

```
unresolved wikilink: X — the note exists as 2026-06-10 X;
write the filename into the link, for example [[2026-06-10 X|X]]
```

4 of 24 became immediately actionable; the other 20 are unchanged.

**What would reopen it.** A signal that genuinely separates the two — for
example a Vault under git, where whether the target ever existed is history
rather than snapshot; cost and availability would need separate evaluation. Or
an explicit user declaration (a `concepts:` directory, a frontmatter convention)
that hands the judgement back to the only person who knows the answer, in line
with #109.

*Refs #159, #155, #109.*

---

## 2. `unknown` in a web-clip is not "a correct capture being misreported"

**Hypothesis** (#158). `web-clip-missing-published` / `-author` conflate two
different things: the source genuinely not stating the value, and the capture
having missed it. Values that explicitly declare absence should be exempt.

**Where the issue went wrong.** It named `原文未标明` / `原文未署名` as the
misreported form. They are not reported at all:

```python
is_meaningful_metadata('原文未标明')  # True
is_meaningful_metadata('原文未署名')  # True
```

11 notes on the reference Vault carry `原文未署名` and **none is reported**. The
issue inferred the cause from one note's frontmatter without checking which
notes were actually reported.

**What is actually reported**, and the question that replaced it: should
`unknown` — the highest-frequency form, 10 web-clips — be exempted too?

**How it died.** The two spellings do not overlap in time, at all:

| form | date range | count |
|---|---|---|
| `unknown` / `未知` | 2026-07-17 … **2026-07-26** | 10 |
| `原文未标明` / `原文未署名` | **2026-07-27** … 2026-08-13 | 9 |

The boundary is the day `0cfdac0` landed, and that commit is what put `unknown`
into `PLACEHOLDER_VALUES`. Its instruction text:

> Do not use vague placeholders such as `unknown`, `未知`, `N/A`, `TODO`, or …
> use an explicit provenance marker such as `author: "原文未署名"` or
> `published: "原文未标明"`.

So the asymmetry is not an accident of the word list. It is a decision that was
made deliberately, written into the instructions, and **it worked**: zero
web-clips written on or after 2026-07-27 use the rejected form.

**Conclusion.** The audit is right. The 10 reported notes were written under a
convention this project retired, and exempting `unknown` would revoke that
decision — letting future captures use the very form the instruction names as
the thing to avoid. The remedy, if the 10 findings are unwanted, is to migrate
those notes to the current convention: a data change, not a code change.

**What would reopen it.** A form observed in real captures that declares absence
explicitly and is *not* covered by the existing markers. Sampling the field's
values first, per #147's rule — only spellings with a countable source.

*Refs #158, #147.*

---

## 3. A shell note cannot be told from a deliberately brief one by structure

**Hypothesis** (#167). Two web-clips on the reference Vault are placeholders left
by a failed capture — one is three lines saying the fetch was blocked, the other
carries a full section skeleton whose every section reads `暂无内容，请后续补充`.
`empty-template-note` misses both because it fires only when `content_chars == 0`,
and placeholder prose is still characters. A structural predicate — what fraction
of a note's sections are nearly empty — should separate them.

**Criterion tried.** Split the body at headings, count sections whose non-whitespace
content is under 20 characters, and report notes where that fraction is high.

**How it died.** Measured over the 113 notes that carry at least three headings at level 2 or deeper, excluding `Templates/`, `95-Sources/` and `.obsidian-kb-backups/` (that scope is what makes the count reproducible — a reviewer who included or dropped a different folder got 108, 111, 116 and 119):

```
71%  5/7   15-Daily/2026-07-07.md
71%  5/7   15-Daily/2026-07-06.md
71%  5/7   00-Inbox/2026-08-13 Claude Artifact Capture 草稿.md
67%  6/9   15-Daily/2026-07-05.md
57%  4/7   15-Daily/2026-07-10.md
57%  4/7   15-Daily/2026-07-09.md
43%  3/7   20-Learning/…7664904418249900084.md   ← the actual shell
```

The top six are daily notes, whose template sections are legitimately unfilled.
The real shell ranks **seventh**, below all of them. Median across the corpus is
12%.

Excluding periodic types (`daily-report`, `daily-note`, `weekly-report`,
`folder-index`, `moc`) does not rescue it:

| threshold | matched | actual shells | false positives |
|---|---:|---:|---:|
| ≥40% | 2 | 1 | 1 |
| ≥50% | 1 | **0** | 1 |

At ≥50% the only match is `Claude Artifact Capture 草稿.md` — a note the author
deliberately left brief. **The predicate ranks an intentional draft above a
genuine shell.** *(That classification is wrong — see the correction below.)*

And it misses half the population by construction: the other shell has a single
heading, so it never reaches the three-section precondition at all.

**Why the obvious alternative is also closed.** What the two shells actually share
is *semantic*: the text states that it is incomplete. Encoding that needs a word
list, and #147 and #75 both settled that a word list may only contain forms with
a countable source. The countable source here is **two notes** — far too few to
define one, and a list drawn from two samples is exactly the想当然 word list those
decisions rejected.

**A correction to the issue's own proposal.** #167 suggested the wording could be
treated as a repo constant, since a failed capture is something the Skill itself
writes. That is wrong: `占位内容`, `未能自动抓取`, `暂无内容，请后续补充` appear
**nowhere** in the Skill's code or references. No such write path exists —
`web-capture.md`'s `Terminal Failure Means Zero Writes` forbids it outright. The
two notes are prose an Agent composed while violating that rule, so there is no
constant to key on. *(The first sentence holds. The rest dates the rule against
the notes without checking — see the correction below.)*

**What this leaves.** The rule already exists and the code has no path that breaks
it; what is missing is any way to notice an Agent ignored it. That is the same
shape as #74 — the judgement lives in instruction prose, not in code — and no
predicate over the current corpus can stand in for it.

**What would reopen it.** More samples. If failed captures recur, the forms they
take become countable and a word list drawn from them would have the source #147
requires. Until then the two existing notes are a data question — delete or
complete them — not a detection question.

### Correction (2026-08-24, from #193)

The percentages above reproduce and the 113-note scope is right. Two
classifications and one date are wrong, and the verdict rests on them.

**1. The two 掘金 notes predate the rule they are said to violate.**

```bash
git log -S "Terminal Failure Means Zero Writes" --format="%ad %h %s" --date=short --reverse -- core/ | head -1
```

`2026-07-31 d734401` — that rule, and the whole of `core/references/web-capture.md`,
was created that day. The notes were written on `2026-07-22 17:36` and
`2026-07-23 22:35` (file mtimes, agreeing with their frontmatter `date`), eight
and nine days earlier. They cannot be prose composed while violating it.

**2. They were the write path's legal output at the time.** Run the
`missing_required_metadata` from `ea08c4f` — master on 2026-07-22 — over both
notes' frontmatter and it returns `[]`. That day's predicate asked only whether
the field was a non-empty string, and `unknown` is non-empty; `PLACEHOLDER_VALUES`,
which is what makes `unknown` a placeholder, arrived on 2026-07-27 in `0cfdac0`,
and `capture_depth` appears **0** times in that day's `create_note.py`. So "no
such write path exists" is true today and false then — these two notes are what
that path produced. Today it refuses both: `create-note --apply` exits 2 with
`missing-required-metadata` and writes nothing.

**3. `Claude Artifact Capture 草稿.md` is not a deliberately brief note.** Its own
body reads `自动抓取失败，网页受 Cloudflare 保护，需人工补充原始内容` and
`抓取已被 Cloudflare 拦截`. It is a placeholder for a blocked fetch, the same kind
as the two 掘金 notes — not the intentional draft it was read as.

**What that does to the verdict.** The measurement ran over all 113 notes with
three or more headings, where daily notes fill the top of the ranking. Scoped to
`type: web-clip` and excluding notes that already declare themselves drafts — the
`incomplete` tag that `process_inbox.DEFAULT_DRAFT_TAGS` defaults to — 52 of the
54 web-clips remain, and the ranking is:

```
43%  3/7    20-Learning/2026-07-23 掘金文章-7664904418249900084.md   ← the shell
31%  5/16   20-Learning/Java/2026-08-22 SpringBoot …图片盲水印.md
31%  5/16   20-Learning/Backend/2026-08-06 Apache Fluss 架构详解.md
29%  5/17   20-Learning/Java/2026-08-22 Spring Boot 3 …ArchUnit….md
```

`≥40%` matches one note, it is the shell, and nothing else — a 12-point gap to
the first legitimate note. **Within web-clips, structure does separate them**, so
this section's heading overstates. What survives is the other half of the
original finding: the second shell has no level-2 heading and never enters the
population, so the predicate covers one of the two known shells.

**Still not enough to implement.** One true positive stands behind that
threshold. #167 stays open carrying this measurement rather than closed by it,
and what would reopen it is unchanged: more samples.

*Refs #167, #147, #75, #74, #193.*


---

## 4. Answer confidence cannot be thresholded from a positive set drawn out of the notes

**Hypothesis** (#170). `search-vault` returns lexical noise shaped exactly like
an answer, so the payload should carry a confidence level. IDF-weighted coverage
of the typed query looked cleanly separable: 22 unanswerable queries peaked at
0.538 while 40 answerable ones bottomed out at 0.664, a gap of +0.126. Three
bands were implemented, `high` at 0.60.

**Criterion tried.** Draw the positive set automatically: for each note over
1500 bytes, lift the first prose sentence of 12–40 characters from its body and
use it as a query, expecting that note to win.

**How it died.** The construction guarantees the query's words are in the note —
it samples the one case where coverage is 1.00 by definition, and its median was
exactly that. Run the shipped code against questions written the way a person
types them, each naming a topic the Vault demonstrably covers:

```
cov=0.47  RIGHT  ThreadLocal 内存泄漏怎么避免   -> 2026-06-13 ThreadLocal内存泄漏与线程池传递方案.md
cov=0.55  RIGHT  RAG 首字延迟怎么优化           -> 2026-08-05 RAG系统流式输出与首字延迟（TTFT）全链路优化指南.md
cov=0.32  RIGHT  SSE 和 WebSocket 该怎么选     -> 2026-06-11 SSE vs WebSocket 服务端推送选型对比.md
```

Correct answers run **0.32–0.64**, against negatives at **0.09–0.54**. The ranges
overlap; the +0.126 gap was a property of the sampling. At the implemented 0.60,
**12 of 16 correct answers** would have been flagged as doubtful:

| cut | negatives passing | correct answers demoted |
|---:|---:|---:|
| 0.30 | 2/22 | 0/16 |
| 0.60 | 0/22 | 12/16 |

**What survived.** One threshold at 0.30 and two levels. `none` is a finding;
`evidence` is only the absence of it, and says nothing about correctness — two
of the 18 questions score `evidence` on a wrong top-1.

**How it was caught.** By running the shipped helper against hand-written
questions and reading the output. The suite was green before and after; the
three-band version passed its own adversarial assertion, because that corpus's
no-answer cases sit at 0.19–0.35 and clear a 0.60 bar comfortably. **A synthetic
corpus cannot refute a threshold derived from a synthetic positive set.**

**What would reopen it.** A positive set of real questions with recorded correct
answers, large enough to fit a threshold against — the same annotated-cases
fixture `test_a_real_vault_run_reports_without_exposing_it` already expects via
`OBSIDIAN_KB_EVAL_CASES`. Near-miss detection (#170's own two examples, which
0.30 does not catch) needs a different signal, not a different cut.

---

## 5. A repeated `source` is not by itself a defect

**Hypothesis** (#168). Three notes on the reference Vault share one `source`
URL, and the audit reports nothing. `source` is a web-clip's canonical identity,
so notes sharing one are duplicates and should be a finding.

**Criterion tried.** Group notes by `source`, report every group of two or more.

**How it died.** Counted before implementing, as the issue itself asked:

```bash
grep -rh '^source:' --include='*.md' ~/Documents/my-knowledge-base \
  | sed 's/^source: *//' | sort | uniq -c | sort -rn | awk '$1>1'
```

Nine groups, of four shapes — and only one is a defect:

| shape | groups | example | verdict |
|---|---:|---|---|
| a course or book as `source` | 2 | 廖雪峰 Python 教程, across 5 notes | legitimate |
| `95-Sources/` archive beside its note | 2 | `…·原文.md`, same URL | legitimate, `source_archive.py` does this by design |
| one article captured twice | 3 | `…·web-clip.md` beside the note | suspect |
| failed capture retried | **1** | juejin `7664904418249900084`: 769 B shell + 2186 B partial + 7741 B complete | the defect |

A plain "group by `source`" rule fires on all nine: **five false positives out of
nine, before it finds anything**. The predicate has to exclude archive folders
and non-URL sources before a finding means anything.

**What would reopen it.** Nothing about the shape — the count stands. What is
open is the narrower rule: same URL, both notes outside `95-Sources/`, and one
of them a shell. That is one group on this Vault, and #167 §3 above is why "a
shell" is not currently detectable.

---

## 6. Lowering BM25's length penalty is not the fix for #171

**Hypothesis** (#171). Notes written in full rank below fragments on the same
subject, because BM25 charges them for length. `b` controls how hard that
penalty bites, so lowering it should let the fuller note win.

**Criterion tried.** Sweep `b` over 0.0–1.0 against 18 hand-written questions
with known correct answers, 22 queries with no answer in the Vault as hard
negatives, and the adversarial set's own control cases.

**How it died.** The aggregate looks like `b=0.25` wins — 17/18 against 16/18,
MRR 0.972 against 0.944. Per query, only **four** of the eighteen move at all,
and the winner is decided by **three notes**:

| query | b=0 | 0.25 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|
| SSE 和 WebSocket 该怎么选 | 3 | 1 | 1 | 1 | 1 |
| Tailscale 和 ZeroTier 有什么区别 | 2 | 1 | 1 | 1 | 1 |
| NOT IN 遇到 NULL 为什么返回空集 | 1 | 2 | 2 | 2 | 2 |
| NOT IN 子查询 NULL 返回空集 | 1 | 1 | 2 | 2 | 2 |

Fitting a global parameter to three notes is what #171 itself warned against.

**And the direction is wrong where it matters.** On the four same-source
"fragment vs complete" groups the reference Vault actually holds, lowering `b`
to 0.25 fixes one — the NOT IN pair — and makes another **worse**: the complete
MCP note falls from rank 5 out of the Top-5 entirely. A weaker length penalty
was supposed to help long notes.

The hard negative moves too: the mean size of the top-1 returned for a query
with no answer climbs from 5916 bytes at `b=0.75` to 10667 at `b=0.25`. Long
off-topic notes float up, which is the cost #171 asked to be measured.

**Two neighbouring branches were already closed** by the adversarial set's own
controls, before any of this: `adv-dilution-04` states a fix "cannot be a
blanket length bonus", `adv-field-04` that it "cannot simply demote short
notes".

**What the sweep did find.** The MCP group was never a length problem. Its
answer note had no H1 and took its `title` from a shell comment inside a
```bash block, losing the 6x title weight on its own subject — fixed in #189,
which moved it from rank 5 to 2 without touching `b`.

**What would reopen it.** A larger annotated set — enough that no single note
decides the value — showing a `b` that improves the whole set rather than
trading groups against each other. The parameters are now named `BM25_K1` and
`BM25_B` in `search_vault`, so a sweep is a one-line change rather than an edit
to a function body.

---

## 7. A helper cannot be told that a capture's fetch failed

**Hypothesis** (#193). If shell notes are the residue of a write that broke
`Terminal Failure Means Zero Writes`, then detecting them afterwards is cleaning
up something that should never have happened, and the route is to make that rule
executable in the helper layer instead. The issue set its own go/no-go: if
`create-note` or `capture-receipt` cannot learn that this capture's body came
from a failed fetch, prevention is closed.

**How it died.** Two independent measurements, either one sufficient.

No helper performs network I/O:

```bash
grep -rnE "urllib\.request|import requests|requests\.(get|post)|httpx|urlopen|socket\.|http\.client" obsidian_kb_skill/ --include="*.py" | wc -l
```

`0`. The fetch happens entirely inside the Agent's own tooling, so every fact
about it that reaches a helper is a fact the Agent chose to type — and none of
`create_note`'s arguments is such a fact (`grep -c add_argument
obsidian_kb_skill/scripts/create_note.py` → 20, none naming a fetch outcome).

The one name that does describe the fetch cannot be pressed into service either.
`retrieval_status: adequate | partial | blocked | uncertain` is declared in
`web-capture.md` and reaches 0 lines of `obsidian_kb_skill/` — but that is by
design, not a gap. It belongs to the *Bounded In-Run Self-Check*, whose opening
line is "do not persist it as telemetry". Making it a frontmatter field a helper
could validate would contradict the reference that defines it.

**Why requiring the Agent to declare it does not rescue the route.** The only
witness to a failed fetch is the actor that failed it. A gate keyed on the
Agent's own declaration converts silence into a statement, which is not nothing,
but it cannot distinguish a truthful `adequate` from an untruthful one — and the
case it would need to catch is exactly the one where the Agent is already not
following the prose.

**What this leaves.** The honest case is already handled, and by structure rather
than by detection. A capture that declares itself incomplete carries the
`incomplete` tag, and `process_inbox` refuses to file it (`draft-incomplete`,
`DEFAULT_DRAFT_TAGS`). Of the 189 notes carrying frontmatter outside
`Templates/`, `95-Sources/`, `.obsidian-kb-backups/` and `docs/`, exactly 2 carry
that tag and both sit in `00-Inbox/`. The two 掘金 shells carry no such tag and
are filed under `20-Learning/`: what separates them is not the fetch but the
absence of the declaration, and that is #167's question, not this one.

**A hole that is real and is not this one.** A web-clip whose metadata is
plausible and whose body is entirely placeholder prose is written without
complaint today — `create-note --apply` returns `audit: {ok: true, count: 0}`,
and a full `audit-vault` over it reports only `missing-deep-capture-heading`
(hygiene) and `orphan-note` (informational), `defect: 0`. That is a body
question. On the two real shells the shipped audit does fire, as
`web-clip-missing-author` and `web-clip-missing-published`, both hygiene.

**What would reopen it.** A capture path that runs inside a helper. While the
Agent fetches and the helper only receives text, no assertion can see past the
Agent's account of what happened. Registry row 66 guards that asymmetry, in both
halves an added capability would have to cross.

*Refs #193, #167, #74.*

---

## 8. Question frames are not what puts an unrelated note first

**Hypothesis** (#192). `tokenize` splits CJK into overlapping bigrams, so
`有什么区别` yields `有什`, `什么`, `么区`, `区别`. Those cross-boundary fragments
appear in any long tutorial note that asks itself questions, so the guess was
that a question-framed query can win on such a note without matching a single
technical term — as `Feign 和 HttpExchange 有什么区别` does, returning a Python
functional-programming note at twice second place.

**Criterion tried.** The issue's own step 2: strip the question frame, re-query
with the content words alone, and see whether the winner changes. If the frame
were driving the result, removing it should move it.

**How it died.** Over 12 pairs, the winner changes on 5 — and **all five are
queries with no answer in the Vault**:

```
Tailscale 和 ZeroTier 有什么区别   → Tailscale ZeroTier 区别      same
SSE 和 WebSocket 该怎么选          → SSE WebSocket 选型           same
MCP 的运行原理是什么                → MCP 运行原理                 same
六个必备的 MCP 服务分别是什么         → 六个必备 MCP 服务             same
ThreadLocal 内存泄漏怎么避免         → ThreadLocal 内存泄漏 避免     same
Python 的生成器怎么用               → Python 生成器                same
Feign 和 HttpExchange 有什么区别   → Feign HttpExchange 区别     CHANGED
区块链的共识算法有哪些               → 区块链 共识算法               CHANGED
Flutter 的 Widget 重建机制是怎样的   → Flutter Widget 重建机制      CHANGED
CompletableFuture 的异常传播       → CompletableFuture 异常传播   CHANGED
OAuth2 授权码模式的完整流程          → OAuth2 授权码模式 流程        CHANGED
```

Every query that has an answer keeps its winner. The frames decide nothing when
there is anything else to match, and where they do decide, the ranking was
already noise — which `confidence` is what exists to report.

**What the measurement found instead.** The fragments distort the *coverage
metric*, not the ranking, and in both directions. Decomposed per token over the
201-note candidate set, `么区` (df=1, IDF 4.903) and `有什` (df=4, IDF 3.804)
supply **8.707 of the 13.995 held weight — 62%** of the "evidence" for that
wrong Feign answer, because a cross-boundary bigram is rare and IDF reads rare
as informative. In the other direction `么避` and `漏怎` are df=0 and inflate a
*correct* answer's denominator: `ThreadLocal 内存泄漏怎么避免` scores 0.458,
**below** the wrong Feign answer's 0.538. That is why #170's two ranges overlap.

Acted on in `2026-08-24-unseen-terms-signal-design.md`, which reports the names
a query used that the scope does not hold — Latin-only, precisely because a df=0
CJK bigram is an accident of adjacency and a df=0 Latin run is a name.

**The four causes this issue had already ruled out** stay ruled out, and are
worth keeping: fenced-comment titles (#189 changed nothing for this query), the
BM25 length penalty (`b` swept 0.0–1.0, top-1 unmoved, §6), the `links` field
weight (2.0 → 0.0 no effect, and §8's own design explains why), and now the
frames themselves.

**What would reopen it.** A query *with* an answer whose winner changes when the
frame is removed. None of the six measured does.

*Refs #192, #170, #171, #195.*

---

## 9. Three capability directions the reference corpus cannot feed

**Hypothesis** (#85, #88, #89). Three read-only helpers, each proposed after the
v1.31.0 capability review: `trace-decisions` builds a project's decision
timeline (#89), `plan-compost` proposes a lifecycle review queue (#88), and
`trace-evidence` walks a conclusion back to the bytes it rests on (#85). Each
issue cites real template sections and real design documents as its existing
basis, so each looked ready to build.

**Criterion tried.** Count, on the reference Vault, the material each MVP's
*first hop* requires — not whether the feature is desirable, but whether the
corpus holds enough of its input to produce a non-empty answer.

```bash
cd ~/Documents/my-knowledge-base
# type distribution, excluding hidden dirs, docs/ and Templates/
find . -name '*.md' -not -path '*/.*' -not -path './docs/*' -not -path './Templates/*' \
  -exec grep -h '^type:' {} + | sed 's/^type: *//' | tr -d '"'"'"'' | sort | uniq -c | sort -rn
# decision sections, and where they live
grep -rn '^## \(决策记录\|决策与依据\|Decisions Log\)' --include='*.md' .
grep -rln '^### 决策 [0-9]' --include='*.md' .
# explicit supersession, in the directories that hold decisions
grep -rn '取代\|废弃\|不再适用\|已作废\|supersed' --include='*.md' 40-Projects 30-Insights
```

**How they died.**

*#89, the decision timeline.* Three notes carry a decision section — one
`决策与依据`, one `Decisions Log`, one `决策记录` — and the seven numbered
entries (`### 决策 1` … `### 决策 7`) are **all inside a single note**, one
retrospective's output rather than a sequence that evolved. `meeting-note`, one
of the three sources the issue names, has **zero real instances**: the only file
with that type is `Templates/Meeting Note.md`. `conversation-digest` has two.
Most decisive: the issue's `supersedes` edge may be drawn only where the text
says so explicitly, and across `40-Projects/` and `30-Insights/` that phrasing
appears **zero times**. Eight occurrences exist Vault-wide, all under
`20-Learning/` and `95-Sources/`, and the two largest are an article explaining
a deprecated API — prose about deprecation, not a decision superseding another.
`trace-decisions` would return one note's list and no edges.

*#88, the compost plan.* Its first signal is "a project explicitly finished or
cancelled and long untouched". There are four `project-note`s; their `status`
values are `active`, `active`, `active`, and `template`. **No project on this
Vault has ever been marked finished or cancelled**, so the signal matches
nothing and the queue's leading criterion is inert.

*#85, the evidence lineage.* Its first and only *verbatim* edge is
`source_archive` → archived original, which exists on **3 notes**. `related` is
on 122 — but the issue itself rules that `related` may never be promoted past
`declared-related`. So the helper's output on this corpus is three real lineage
chains plus a re-rendering of frontmatter the reader can already see.

**The shape underneath all three.** The reference Vault is a personal clipping
library: 57 `web-clip`, 45 `daily-report`, 28 `learning-note`, 25
`folder-index`, 13 `insight-note` — **168 of the 196 notes that declare a type**
(202 Markdown files are in scope; six carry no `type:`). It is not a team Vault
with meetings, project lifecycles and decision chains. All three directions were
derived by reasoning forward from what the templates *offer*, not by measuring
what the corpus *holds*, which is the same mistake #136 and #171 record about
the adversarial corpus: built to the author's picture of a note rather than to
the notes.

**What would reopen them.** Each has a countable threshold, and each is a
property of the corpus rather than of the code:

- #89 — decision sections in **more than one** project, plus at least one
  explicit supersession inside `40-Projects/` or `30-Insights/`.
- #88 — a `project-note` whose `status` is finished or cancelled.
- #85 — enough `source_archive` notes that a lineage walk is not three chains;
  or a second verbatim edge type that does not route through `related`.

Note that #85's threshold could also be crossed by *using* `archive-source` more,
which no measurement here forbids. These are rulings about sequencing, not about
whether the features are worth building.

*Refs #85, #88, #89, #136, #171.*
