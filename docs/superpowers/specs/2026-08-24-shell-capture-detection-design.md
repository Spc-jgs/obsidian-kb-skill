# Reporting a web-clip that captured nothing (#167)

**Status: accepted.** The criterion is a floor on captured body text, scoped to
`web-clip` and skipping notes that already declare themselves unfinished.

## The problem

Two notes on the reference Vault are placeholders left by a blocked fetch. In
retrieval they are ordinary web-clips: they are hit, they enter neighbourhoods,
and they stand as evidence that the topic has already been captured. The audit
says nothing about their emptiness — on them it reports only
`web-clip-missing-author` and `web-clip-missing-published`, both `hygiene`.

`empty-template-note` misses them because it fires on `content_chars == 0`, and
placeholder prose is still characters. The three-line one has no heading at all,
so it fails that check's `has_heading` precondition as well.

## What is already settled

Do not re-open these; each cost a measurement.

- **The wording cannot be a word list.** `占位内容`, `未能自动抓取`,
  `暂无内容，请后续补充` appear nowhere in this repo, and #147 and #75 both
  settled that a word list needs a countable source. Two notes is not one.
  `2026-08-21-rejected-hypotheses.md` §3.
- **Prevention is closed.** No helper performs network I/O, so no helper can
  learn that a capture's fetch failed; the one field naming the fetch outcome is
  deliberately non-persisted. §7 of the same file, guarded by registry row 66.
- **The two existing notes are pre-rule residue.** They predate
  `Terminal Failure Means Zero Writes` by eight and nine days, and today's
  `create-note --apply` refuses both. They are the evidence, not the target: the
  target is the shell a compliant-looking capture can still write today.
- **The structural predicate is not the answer.** §3's correction measured it
  at 1 true positive and 0 false positives once scoped to web-clips — but it is
  blind by construction to the shell with no level-2 heading, which is half the
  known population.

## The criterion

A note is reported when all three hold:

1. its `type` is `web-clip`;
2. it does not carry the Vault's draft tag; and
3. its body content is under `WEB_CLIP_MIN_CONTENT_CHARS`.

"Body content" is the count `empty-template-note` already computes —
non-whitespace characters on lines that do not begin with `#`. Both checks read
one extracted helper rather than two loops, so the two findings cannot come to
disagree about what a note's content is.

## The measurement

Over the 55 `web-clip` notes on the reference Vault, outside `Templates/`,
`95-Sources/`, `.obsidian-kb-backups/` and `docs/`, ranked by that count:

```
content_chars  draft?  note
          100     no   20-Learning/2026-07-22 掘金文章-7664407325864558628.md   ← shell
          220     no   20-Learning/2026-07-23 掘金文章-7664904418249900084.md   ← shell
          329    yes   00-Inbox/2026-08-13 Claude Artifact Capture 草稿.md
          383    yes   00-Inbox/2026-08-06 Spring Boot 接入金仓数据库….md
          799     no   20-Learning/2026-07-23 掘金文章-…-补充正文.md            ← smallest real capture
          819     no   20-Learning/Backend/2026-07-26 微信文章-…雪花id和uuid….md
```

**Both shells rank first and second**, including the one the structural
predicate cannot see. The two self-declared drafts follow, and then a 3.6x jump
to the smallest real capture. Excluding the two shells and the two drafts, the
51 remaining web-clips have a minimum of 799.

## Why the type scoping is load-bearing

Without it the criterion is unusable. Counting every note type under 800
characters returns 92, of which 87 are legitimate:

```
daily-report    45   (75–223 chars, template sections a day did not need)
folder-index    23   (26–207)
weekly-report    9   (261–403)
daily-note       3
archive-note     2   (15 each)
learning-note / project-note / insight-note / person-note / moc   1 each
```

A short daily report is a short day. A folder index is a list of links. Only a
web-clip makes a claim about *external* material it captured, and only there
does "almost no body" contradict what the note says it is.

## Why the draft exclusion

The two Inbox notes are honest: they carry the `incomplete` tag and say what is
missing. `process_inbox` already refuses to file them (`draft-incomplete`), and
`rules-and-errors.md` states the reason — "the marker is the user's statement
about their own note". Reporting them as defects would punish the declaration
this system asks for.

The tag comes from `process_inbox.DEFAULT_DRAFT_TAGS` by import, not by a second
copy. Folder position is deliberately *not* part of the criterion: `00-Inbox/`
holds unfinished work, but an undeclared shell sitting there is still a shell.

## The threshold

`WEB_CLIP_MIN_CONTENT_CHARS = 400`.

The gap it sits in is 220 (largest shell) to 799 (smallest real capture). The
geometric midpoint is 419; 400 is chosen just below it, so the number leans
toward the false-negative side on purpose:

- a real capture must fall to **2.00x** below the smallest one ever observed
  before it is flagged;
- a shell must grow to **1.82x** the largest one observed before it escapes.

That asymmetry is the intended one. Telling a user their real note captured
nothing is worse than missing a shell, because the shell is still visible as
`web-clip-missing-author` and the false positive teaches the user to ignore the
audit.

## Severity

`defect`. A note that claims to hold a captured article and holds none is wrong,
not untidy — and the existing `hygiene` findings on these two notes are exactly
the level that let them sit unnoticed since July.

## Rejected branches

**Fence-aware counting.** `content_chars` skips every line beginning with `#`,
so a `# comment` inside a fenced block is read as a heading — the same defect
#189 fixed in `search_vault`. Counting fenced lines as content instead changes
10 of the 55 web-clips, all of them by between 22 and 152 characters, and all
already above 2429. The minimum real capture stays 799 and the shells stay 100
and 220: **on this corpus the fix changes no outcome.** It is left undone and
recorded here rather than done speculatively. The latent risk it leaves is a
short web-clip that is mostly a commented code block; none exists today, and it
would have to be under 400 characters to matter.

**A second criterion for skeleton shells.** A shell padded past 400 characters
with more placeholder sections would escape the floor while scoring high on §3's
empty-section fraction. Adding both criteria was considered and dropped: the
structural one has one true positive behind it, and shipping a predicate that
covers a case nobody has observed is how row 17 came to assert less than its
name said. It stays in #167's record as what to add when a third shell appears.

## Acceptance, against #167's own criteria

| #167 asked for | Answer |
|---|---|
| Statistics on the code path generating this placeholder text; register it if it is a repo constant | **There is no such path.** The wording is absent from the repo, and the rule forbidding the write postdates both notes. §3's correction and §7 |
| An assertion that a shell is reported, red before the fix | `test_reports_a_web_clip_that_captured_nothing`, both shapes |
| A hard negative: a short but real note is not reported | `test_a_short_real_capture_is_not_reported`, at the measured 799 |
| A ruling on whether a failed capture still creates a note | Ruled in §7: prevention is closed, and the declared-incomplete path is the supported product |

## Registry rows

| Boundary | Guard |
|---|---|
| `WEB_CLIP_MIN_CONTENT_CHARS` ↔ the reference-Vault distribution it was chosen from | `test_the_content_floor_is_the_value_the_distribution_supports`, with the measurement recorded beside the constant |
| What `empty-template-note` counts as content ↔ what the new finding counts | **relation removed** — one `_body_content_chars`, read by both |
| The draft tag the audit skips ↔ the one `process_inbox` files on | **relation removed** — `DEFAULT_DRAFT_TAGS` imported, not restated |
