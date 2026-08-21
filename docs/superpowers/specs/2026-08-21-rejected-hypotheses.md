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
