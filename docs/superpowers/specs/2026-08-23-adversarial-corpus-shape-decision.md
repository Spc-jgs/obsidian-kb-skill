# The adversarial corpus keeps its shape (#174)

**Status: accepted — the decision is to not reshape the corpus.**

#174 asks for a ruling: fill the adversarial corpus out toward the reference
Vault's size distribution, or build a second corpus for everyday shapes. This
records the ruling, both rejected branches, and the measurements behind them.

## What #174 got right, and what has changed since

The issue was filed on 2026-08-21 against a corpus whose mean was 8464 bytes.
`36e4993` has since resized the two long notes from 76 KB to 38 KB and added
`adv-dilution-06`. Re-measured today:

| | adversarial | reference Vault | #174's table |
|---|---:|---:|---:|
| n | 22 | 217 | 22 / 193 |
| median bytes | 262 | 1925 | 262 / 2390 |
| mean bytes | 5010 | 4468 | 8464 / 4247 |
| 2–8 KB | 4.5% | 34.6% | 4% / 38% |

**The mean converged; the shape did not.** The median is unchanged at 262 and
the middle of the distribution is still empty. On that much, #174 stands.

## The measurement #174 and 36e4993 both missed

Both measured **file bytes**. `_bm25_score` does not read file bytes — it
normalises by `average_length`, the mean of each document's
`average_scoring_length`: names plus one section, in tokens.

| relative to avgdl | adversarial | reference Vault |
|---|---:|---:|
| < 0.5x | **86.4%** | 41.2% |
| 0.5–1x | 4.5% | 18.1% |
| **1–2x** | **0%** | **31.2%** |
| **2–5x** | **0%** | 8.5% |
| >= 5x | 9.1% | 1.0% |
| **avgdl** | **569.1** | **261.0** |

The corpus is 2.18x the reference Vault on the unit that actually charges a
note for its length, and it holds **nothing at all** in the 1–5x band where
39.7% of real notes sit. Two notes own 80.9% of the corpus's total scoring
length; on the reference Vault the top two own 5.4%.

`test_the_corpus_mean_length_stays_near_the_reference_vault` is green and says
in its own docstring that a high mean means "every note under it is graded as
if length normalisation were off". That is happening — it guards the byte mean,
which is not the quantity it describes.

## Why the corpus is not being reshaped anyway

**The failure #174 wants to observe is already observable.** `adv-dilution-06`
holds a 4.9x detail pair, and its `must_see` note `phantom-full.md` ranks **2**
— the "written fuller, ranked lower" shape #171 filed. Reshaping the corpus to
the profile closest to the reference Vault that could be found
(`backoff-handbook` 60→8 filler paragraphs, `hotkey-rebuild` 40→6, plus ten
background notes; bands 38/19/34/9/0 against the real 41/18/31/9/1) leaves that
rank at **2, unchanged**.

**And it costs the dilution family what it exists to show.** The same reshape
moves three `must_see` ranks, all in the wrong direction:

| case | note | before | after |
|---|---|---:|---:|
| adv-dilution-01 | `backoff-handbook` (unsectioned) | **absent from Top-5** | 4 |
| adv-dilution-01 | `backoff-manual` (sectioned) | 2 | 3 |
| adv-dilution-03 | `backoff-handbook` | 4 | 3 |

The baseline's recorded observation — section-level ranking lets the sectioned
note compete while the unstructured one cannot appear at all — **disappears**
once the giant is cut down. The corpus would match the reference Vault's
histogram and stop demonstrating the thing it was built to demonstrate.

**The two properties are not jointly satisfiable at n=22.** Extreme dilution
requires one note to own most of the corpus's length; a realistic distribution
requires that no note does. Keeping the giants and adding small notes instead
does not escape it: reaching avgdl 261 needs `N = 6778 / (261 - L)` background
notes of scoring length `L` — 26 at L=0, 42 at L=100 — which pushes the <0.5x
band further from the real 41% and runs into the latency budget.

## Rejected branch 1: fill the corpus out

Rejected on the measurements above. It buys a histogram that matches, changes
no `must_see` rank for the better, and deletes the dilution family's finding.

## Rejected branch 2: build a second, everyday-shaped corpus

Rejected on cost against unproven benefit. #174 states the cost: two corpora to
maintain and a split `_aggregate`. The benefit would have to be a failure that
the everyday distribution reveals and the current one hides — and the one
candidate, #171's detail-gap shape, is already red in the current corpus at
`adv-dilution-06`. No second failure has been named.

## What is accepted instead

The divergence stays and is **recorded rather than fixed**:
`test_the_scoring_unit_diverges_from_the_reference_vault_by_a_recorded_factor`
pins the 2.18x ratio, so a change in either direction reopens this document
rather than passing silently. Registry row 62.

## What would reopen this

- A failure shape that the reference Vault produces, that a realistic
  distribution reveals, and that the current corpus cannot be made to show —
  named concretely, the way `adv-dilution-06` named the detail gap.
- The reference Vault's own distribution moving materially: these numbers are
  from 217 notes on 2026-08-23.
- Ranking changes that make the length penalty behave differently, at which
  point the 2.18x divergence stops being a known constant and has to be
  re-argued.
