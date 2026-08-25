# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **The audit tells a stubbed concept from a deleted note** (`link-to-unwritten-note`, `informational`). `rejected-hypotheses.md` §1 rejected this split when the criterion was inbound-reference counting — every placeholder on the reference Vault was referenced exactly once, the same as a deletion — and named the signal that would reopen it: a Vault under git, where the question is history rather than snapshot. It is now asked of history: does any path that ever existed in the repository resolve this target? On the reference Vault, **24 of 32 defects were this**, and `broken-wikilink` goes to zero — its largest defect class was, in its entirety, the standard Obsidian practice of linking a note before writing it.

  Three outcomes rather than two, because "we cannot tell" is not the same as "never written". Without history every unresolved link stays `broken-wikilink`, which is the previous behaviour; the audit now reports `link_history` so that fallback is visible rather than silent — the shape of #201, one release earlier. **A shallow clone is refused rather than trusted**: `--depth 1` leaves a truncated history in which nothing ever existed, so every deleted note would read as never written. A short but complete history is trusted, and no minimum depth is imposed, because any threshold would be a number nobody measured.

  Matching uses the audit's own resolution order — filename, stem, stem without a `YYYY-MM-DD ` prefix — and inventory row 73 asserts it stays that way; a second notion of "the same note" is the drift this list keeps catching. Two limits are recorded in `2026-08-25-unwritten-note-link-design.md` rather than left to be found: the criterion is blind to `aliases`, which live in a file's content and not its path, and **the reference Vault has zero true positives** — all 21 distinct targets never appeared in 316 historical paths, and the one note git records as deleted has no inbound links, so the "it existed" branch is guarded by a synthetic fixture rather than by observation.

- One decoder for the paths git prints, `git_history.unquote_git_path`, shared by `review_captures` and the audit instead of copied. #201 was this decoding going wrong in one caller; a second hand-written copy would be the same defect waiting in the other, and it fails in opposite directions — a capture falls back to mtime, a deleted note reads as never written.

- **`review-open-loops`: the unticked boxes an author left behind, with a bound that comes from the templates.** #87 asked for an open-loop queue and proposed a hand-written heading vocabulary; measured, that vocabulary reached **20 of 138** items while reading as authoritative. The templates already answer the question — each one puts exactly one `- [ ]` under exactly one heading, and that placement *is* the declaration — so the queue derives its set from them and covers **95**. A heading no template declares is out by design: `可复用的项目落地检查表` holds fifteen unticked boxes on the reference Vault that are a reusable question list ending in `；`, and they can never be ticked.

  **It assigns no severity, no priority and no category.** The queue is visibly heterogeneous — real next actions, conditional advice, open-ended intent with no finishable end state — and two samples of the same corpus gave opposite impressions of that mix, which is the reason nothing here claims to have separated them. Every item carries its text, path, line, heading, type and date so a reader judges it. Ordering is oldest note first, the only ordering the data supports; undated notes sort last rather than being assigned a guessed date.

  Consistency inventory row 78 ties `ACTION_HEADINGS` to the templates in both directions — the quiet one being a template that grows a section the queue would otherwise never see.

### Fixed

- **`review-captures` said `git-history` while dating 97 of 100 captures by file mtime.** `_git_last_revision` keyed its map on the raw lines of `git log --name-only`, but `core.quotepath` defaults to **true**, so git wraps and escapes any path holding a non-ASCII byte: a Chinese filename arrives as `"20-Learning/\346\216\230...md"` and matches nothing on disk. Every such note fell through to the mtime branch — a fallback that works, and is therefore indistinguishable from the preferred path unless something counts them. On the reference Vault, 219 notes, all of them tracked, matched **51** before the fix and **219** after.

  The defect had been read as a fact about the corpus and written down twice. `_git_last_revision`'s docstring said "on the reference Vault only 57 of 214 notes were tracked", and the Skill page an Agent reads repeated it — so an Agent would explain a corrupted number to the user in the corpus's terms. Both are corrected, and the reference now says what actually happened.

  Fixed by decoding git's C-style quoting rather than by passing `-c core.quotepath=false`, which stops the octal escaping but not the quoting — a path holding a quote, a backslash or a control character is still wrapped — and which would leave the helper's correctness depending on the repository's configuration. `-z` was considered and rejected: it separates filenames with NUL, which is exactly what `--format=%x00%cs` uses to mark a date record, so the two would be indistinguishable.

- **The per-type revisit rates change, and one conclusion drawn from them was wrong.** Corrected: `learning-note` 0.75 → **0.714**, `web-clip` 0.368 → **0.421**, `conversation-digest` 0.0 → **0.5**, `insight-note` unchanged at 0.308; overall 0.46 → 0.49. The Skill page read the old split as "notes the user wrote get reopened; clips do not" — with the fix, `web-clip` moves from last place to second, above `insight-note`. A conclusion about how someone works, drawn from a number whose provenance was never checked, survived as prose until the number was checked. The page now states the counts and says what the earlier reading was.

### Added

- **`review-captures` reports `evidence_coverage`.** `evidence` names the preferred source, but the choice is made per note, so one word for the whole report can be true and misleading at once. `{"git-history": 100, "file-mtime": 0}` says what each source actually dated, and `sum(...) == summary.captures` holds by construction — the invariant is what row 72 of the consistency inventory asserts, rather than any particular number, because the number is a property of the Vault.

## [1.36.0] - 2026-08-24

### Added

- **`search-vault` says whether it answered the question.** Asked something the Vault does not cover, it returned hits with a score, a `heading` and a `snippet` — the shape of a search that succeeded — so a caller could not tell "here is the answer" from "here is the lexically nearest noise". An Agent either cites a Python note for a Feign question, or, worse, concludes the topic is already covered and never captures it. Every response now carries `confidence`, keyed on **IDF-weighted coverage of the typed query**: how much of the question's information the winner actually matched. IDF rather than a stop-word list, because a list needs a countable source and question frames like 有什么 have none; typed words only, because letting the ranker's own query expansion certify the ranker's results is circular. **Ranking is unchanged.**

  The level has two values, not three, because the measurement supports one cut and not two. On the reference Vault, 22 no-answer queries score 0.09–0.54 and 16 correctly-answered ones score 0.32–0.64 — **overlapping ranges**. 0.30 demotes none of the 16 while catching 20 of the 22; 0.60 would catch all 22 and demote **12 of the 16**. So `none` is a finding and `evidence` is merely the absence of one: it does not claim the answer is right, and two of eighteen measured questions carry `evidence` with a wrong top result.

- **The audit reports a web-clip that captured nothing** (`web-clip-captured-nothing`, `defect`). Two notes on the reference Vault are placeholders left by a blocked fetch, and the audit's only word on them was `web-clip-missing-author` at `hygiene` — while retrieval treated them as ordinary captures: hit, cited, and counted as evidence the topic was already covered. `empty-template-note` could not reach them, because it fires on `content_chars == 0` and placeholder prose is still characters; one of the two has no heading at all, failing its other precondition too.

  The criterion is a floor on body content, scoped to `web-clip` and skipping notes that carry the Vault's draft tag. Ranked by that count, the Vault's 55 web-clips put both shells first and second (100 and 220 characters), the two self-declared drafts next (329, 383), and the smallest real capture at **799**. `WEB_CLIP_MIN_CONTENT_CHARS = 400` sits just below the geometric midpoint of 220 and 799, leaning toward missing a shell rather than accusing a real note. The type scoping is load-bearing, not cautious: 92 notes of all types fall under 800 characters and **87 of them are legitimate** — 45 daily reports, 23 folder indexes, 9 weekly reports. A genuinely short source is the known false positive, named in `docs/superpowers/specs/2026-08-24-shell-capture-detection-design.md` rather than denied.

### Fixed

- **`install.ps1` could delete the contents of a symlink target instead of unlinking it.** Uninstalling the base Skill under QoderWork and under Codex used `Remove-Item -Recurse -Force`, while the other seven paths used `Remove-OwnedPath`. On a directory symlink — which is what a Skill manager creates — the recursive form follows the link and deletes what is on the other side. The parallel hand-copy in `install.sh` was wrong in a different place: QoderWork's base tested `-d` where the other eight tested `-d || -L`, so an installation whose Skill directory was a symlink was **skipped entirely by uninstall**.

  Both are consequences of the same shape rather than two independent slips: each script carried 16 hand-copied path literals across its install, uninstall and host-validation branches, with no shared source of truth between the two languages. Both now expand one table, so neither inconsistency can be expressed again.

- **A `#` comment inside a fenced code block is no longer read as a heading.** `search_vault` had no notion of a fence and scanned for `^#[ \t]+` line by line, which polluted three things at once. Two notes on the reference Vault took their `title` — scored at **6x** body — from a line inside a ```bash block, so they lost that weight on their own subject and gained it on a shell comment. Headings the author never wrote scored at 2x. And the passage split, which is the unit ranking works on, was cut short at phantom boundaries: 22 of 199 notes carried 255 such false headings, one of them turning 100 sections into 52. Short passages are barely penalised by BM25, so notes scored high on subjects they only mention in passing.

  The fix reads the fence notion that already exists — `link_graph.blank_code_examples`, already used by `explore-neighborhood` and `relatedness` — rather than writing a fourth scanner. It blanks code line by line while preserving numbering, so one index addresses both the blanked copy and the body: **split on the blanked copy, read content from the original.** Discarding code outright would trade this defect for a worse one; `npx playwright install chromium` still has to be findable, and both halves are asserted. On the 20 annotated queries MRR moved 0.885 → 0.900.

### Changed

- **Both installers' Skill and host layouts are data.** One table per script — `SKILL_ROWS`/`$SkillRows` and `HOST_ROWS`/`$HostRows` — expanded by install, uninstall and validation alike. Deliberately two tables rather than one product, because hosts are not uniform: Cursor takes retrieval only, and Claude Code additionally migrates a legacy marker block. Steps that are not Skill payload stay in the `case`/`switch`, so a host appears there only when it needs an extra action. The guards changed with the shape: "everything installed can be uninstalled" used to be a count of literal occurrences and is now true by construction, leaving one assertion that no branch grows a path outside the table.

- BM25's parameters are named `BM25_K1` and `BM25_B` at module level instead of being literals inside `_bm25_score`. They are the textbook defaults, which is exactly why they need a guard — a round number reads as unexamined — and a sweep is now a one-line change rather than an edit to a function body.

### Decided and recorded, with the losing side kept

Four rulings, each with the measurement that produced it and what would reopen it.

- **Lowering BM25's length penalty is not the fix for "the fuller note ranks lower".** Sweeping `b` from 0.00 to 1.00, `b=0.25` looks best in aggregate (17/18 versus 16/18, MRR 0.972 versus 0.944) — but only 4 of the 18 queries move at all, so three notes decide the whole result, which is the overfitting the issue itself warned about. The direction is wrong where it matters: of four same-source "excerpt versus full" pairs, `b=0.25` fixes one and pushes another's full note out of the Top-5, and the average size of a no-answer query's top result grows from 5916 to 10667 bytes. `2026-08-21-rejected-hypotheses.md` §6.

- **The adversarial corpus keeps its shape, and no second everyday corpus is built.** Both the issue and an earlier fix measured file bytes; `_bm25_score` normalises by `average_scoring_length`, a different unit, and on that unit the corpus sits **2.18x** above the reference Vault with **nothing at all** in the 1–5x band where that Vault keeps 39.7% of its notes. Reshaping was measured, not argued: it leaves the failure the issue wanted exposed exactly where it already is (rank 2) while moving three `must_see` ranks the wrong way and erasing what the dilution family exists to show. The divergence is now pinned at 2.0–2.4 by assertion so that either narrowing or widening it forces the ruling to be re-read. `2026-08-23-adversarial-corpus-shape-decision.md`.

- **A helper cannot be told that a capture's fetch failed**, so preventing a shell note at write time is closed. Nothing in the package performs network I/O — the fetch belongs entirely to the Agent, and every fact about it a helper receives is a fact the Agent chose to type. The one name that describes the fetch outcome, `retrieval_status`, is deliberately never persisted: it belongs to the in-run self-check whose opening line is "do not persist it as telemetry". Requiring the Agent to declare it does not rescue the route, because the only witness to a failed fetch is the actor that failed it. `2026-08-21-rejected-hypotheses.md` §7, guarded by an assertion that the package still cannot reach the network.

- **A correction to this file's own v1.35.0 entry**, and to the record it summarised. That entry says the two shell notes are "prose an Agent composed while breaking that rule". They are not: `Terminal Failure Means Zero Writes`, and the whole of `core/references/web-capture.md`, was created on 2026-07-31, and the notes were written on 2026-07-22 and 2026-07-23 — eight and nine days earlier. That day's write path accepted them, because its metadata predicate asked only whether a field was a non-empty string and `unknown` is non-empty; today's `create-note --apply` refuses both. A third note, recorded as an author's deliberately brief draft, turns out to say in its own body that its fetch was blocked by Cloudflare — and that misreading was the sentence that killed the structural predicate. Rescored within web-clips and excluding self-declared drafts, that predicate finds the shell with no false positives, so #167 stayed open carrying the measurement instead of being closed by it.

## [1.35.0] - 2026-08-21

### Changed

- **`create-note --apply` now refuses a body that still holds template scaffolding**, exits 2, and writes nothing. Nine notes on the reference Vault carry an instruction addressed to whoever writes them — `<!-- 用 2–4 句话区分原文观点与自己的推论 -->` is guidance for the Agent, and it shipped as part of the user's note. The post-write audit already knew, in the same call, and the file was on disk anyway with exit 0 and no top-level field reporting the verdict: every caller that judges by exit code was told the write succeeded.

  The refusal set is **not** every `defect`. Of the twenty codes graded that way, most describe the Vault rather than this note, and refusing them all would forbid writing a note that points forward — `broken-wikilink` is a defect, and linking an unwritten note is standard Obsidian usage. What is refused is the narrower class the author clears by rewriting the body, and an assertion names `broken-wikilink` as excluded so the boundary cannot drift.

  `--no-audit` skips the post-write report, not this refusal. Letting it through would make that flag the one that writes a known-broken note. The new code is `unfinished-template-body`, documented in the refusal table with what to do next.

- `PATH_OUTSIDE_VAULT` tells an Agent what to do instead. The containment boundary is right to reject a `--content-file` outside the Vault, but content living outside the Vault is ordinary, and the action column said only "Stop". `note-creation.md` had the answer — pipe it through `--stdin` — in a different file from the one an Agent reads when a helper refuses. The row now carries that branch, keyed on `details.param`, and says explicitly not to copy the file into the Vault to get past the check. That evasion is not hypothetical: a recorded run staged its body inside the workspace, and a second gate then punished it for the shape.

### Added

- `review-captures` asks the question none of the other measurements ask: was this capture ever opened again? Every other check grades whether a capture is *faithful*. On the reference Vault 55 of 94 captures were written and never reopened, and the rate differs threefold by type — `learning-note` 0.75, `insight-note` 0.31, `web-clip` 0.275. Evidence is git history where the Vault is a repository and file mtime otherwise, and the report says which it used, because the two are not equally exact.

- The audit reports a denominator. `count` counts findings, not notes, and 92 findings across 20 notes and across 200 read identically. Both renderings now carry it: `scanned` (Markdown files enumerated) and `audited` (the subset note contracts ran over — they differ by the archived sources under `95-Sources/`, which are captured evidence rather than notes).

- `broken-wikilink` says what to write when it can. Where the target exists under a `YYYY-MM-DD ` prefix, the message gives the link to use. Four of the reference Vault's 24 became immediately actionable; the other twenty are unchanged, and why they cannot be is recorded rather than guessed at (below).

### Fixed

- **Findings on the reference Vault fell from 113 to 92, and every one removed was a false positive.**

  - YAML resolves `published: 2026-08-13` to `datetime.date` and only the quoted form to `str`. The metadata predicate rejected every non-`str`, so it graded notes by whether their author quoted a date — two web-clips filled `published` and `author` correctly and were reported as missing them. The notes written most conventionally were the penalised ones.
  - `disconnected-note` no longer fires on `web-clip`. All 23 findings were under 47 days old with a median of 27, so the state clears itself; `suggest-directed-links` produced **0 candidates across all 23**, so there was nothing to suggest either. 20 of the 23 are already covered by `review-captures` asking a stronger question, and an assertion ties the exemption to that coverage: drop `web-clip` from `CAPTURE_TYPES` and the test fails, because the argument for the exemption would have expired with nothing saying so.
  - A dated series such as `日报-01`, `日报-02` is no longer read as near-duplicate titles.

- `{{ }}` inside a code fence is content, not an unreplaced placeholder. The refusal above matched the pattern anywhere, so a note explaining Vue, Jinja2, Handlebars, Liquid or GitHub Actions could not be saved at all. Every real occurrence on the reference Vault is `{{date}}` outside any fence — eight notes, eight matches, none in code — so ignoring fenced and inline code costs no detection. The predicate moved into `note_catalog`, because what has to be shared is not just the pattern but the decision to ignore code; `template_contract` keeps the raw pattern, since it reads a *template*, where `{{date}}` is the point.

- `review-captures` no longer counts the copies under `.obsidian-kb-backups/`. Nobody reopens a backup, so counting one guarantees it lands in `never_reopened`; three backed-up web-clips were being counted, and the reader was shown a backup path as a note worth revisiting.

- Two consequences of widening the metadata predicate to accept scalars, both found by an independent review rather than by the suite: `capture_receipt` compared a raw resource name against a set storing `str(name)`, so two resources named `2026` and `"2026"` stopped colliding; and `source` stopped requiring text, when a URL or a sentence is the only thing it can be — a date is a legitimate `published`, a bare number is never a source.

### Decided and recorded, with the losing side kept

Three hypotheses were tested against the reference Vault and rejected. They are in `docs/superpowers/specs/2026-08-21-rejected-hypotheses.md`, each with the criterion tried, the data that killed it, and what would reopen it — a negative conclusion leaves no trace in the tree, so the next reader re-derives it and may not stop where the evidence stopped.

- **A broken wikilink cannot be split into "concept placeholder" and "deleted note".** The criterion — a placeholder is referenced by several notes, a deletion by one — died on measurement: every concept placeholder is referenced exactly once. From a single snapshot the two leave the same trace, and Obsidian itself does not distinguish them.
- **`unknown` in a web-clip is not a correct capture being misreported.** The two spellings do not overlap in time at all: `unknown`/`未知` run to 2026-07-26, `原文未标明`/`原文未署名` start 2026-07-27, and the boundary is the day the commit landed that listed `unknown` as a placeholder and named the replacement in the instructions. Zero web-clips written since use the retired form — the decision worked, and exempting `unknown` would revoke it.
- **A shell note left by a failed capture cannot be told from a deliberately brief one by structure.** Ranking notes by the fraction of their sections that are nearly empty puts six daily notes and one intentional draft above the real shell. The wording is not a repo constant either: `web-capture.md` forbids saving a placeholder outright, so no such write path exists — those notes are prose an Agent composed while breaking that rule. *(The last clause is wrong; the rule postdates both notes by more than a week. Corrected under 1.36.0.)*

### Evaluation infrastructure

- A hard failure no longer aborts the batch. It means "this run does not count", which the exit code already carries; stopping additionally discarded the measurement the run existed to collect — one 2026-08-18 baseline stopped after 15 of 36 runs. `--stop-on-hard-failure` keeps the old behaviour, and `stopped_after_case` records truncation so a partial `mean_soft_score` is not read as a whole one.
- The receipt gate no longer grades an Agent on which content source it chose. It additionally required `--from-preflight`, while `create-note` accepts `--stdin` and `--content-file` too, so a correct verified capture hard-failed all three repeats. The binding is proved by the helper's own output; nothing is given up.
- The adversarial corpus's mean note length now tracks the reference Vault's. Two 76 KB notes held 97.9% of its bytes and put the mean at 9170 against the real 4247, so BM25's length normalisation never touched an everyday note and a whole class of ranking failure was unobservable there. They are now 38 KB, near that Vault's second and third largest, and `adv-dilution-06` freezes the failure: a 2.4 KB full capture ranking below a 0.5 KB summary of the same source on a keyword-dense query.

## [1.34.0] - 2026-08-17

### Added

- `next_action_heading` must now be named whenever an Agent repeats a project's next action — every time, not only when the item looks suspicious, because deciding it looks fine is the judgement the reader needs to be able to check. The revival queue reports which heading an item came from; on the reference Vault a reusable checklist and the real P0 plan are sibling subsections of one `下一步行动`, and nothing structural separates them.

  What separates them is what the author called them, and this project has now declined three times to let a helper read a heading for what it means — #86 while designing the resume pack, #115 when free-form notes returned almost nothing, and #109 from the other direction. Those rulings lived in three issue comments, so a fourth issue would have had to find all of them to learn this is a settled boundary rather than an oversight. It is now `docs/superpowers/specs/2026-08-17-heading-semantics-boundary-decision.md`, with the rejected alternatives and what would reopen it.

  The counting behaviour is unchanged, including `open_tasks_in_next_actions = 15` for the note above. That number is correct for what it measures, and why it misleads is recorded rather than corrected away.

- `suggest-directed-links` proposes the notes a note declares it **depends on**, with the sentence that says so. `explore-neighborhood` shows every link; this answers the narrower question a reader has when following one — which of these does the note lean on, and for what.

  The judgement is deliberately not similarity, and #75's frozen labels are why. All sixteen of its hard negatives share a *word* with their source and nothing else: `Release Quality Gate` against `Airport Departure Gates`, `Source Archive Format` against `Museum Archive Visit`, `Read-only Retrieval` against `Reading List`. A ranker built on word overlap scores every one of them highly — the set exists to punish exactly the approach `search-vault` uses. What separates the sixteen positives is that the source says, in its own text, what it uses the target for: it *cites*, *delegates to*, *imports*, *follows*, *is expressed as a multiple of*.

  So a candidate needs an explicit reference **and** a dependency phrase, in one sentence. A bare link is not a dependency: a note whose `See also` lists five links has declared five links and no dependencies, and `links_without_a_dependency` counts them so "nothing found" reads differently from "nothing linked". There is no score, no threshold and no confidence number — a candidate either has a declared dependency or is not a candidate.

  The threshold was pre-registered on the issue before any code existed, as #75 requires, with a falsifiable prediction: that the negatives would score **zero** rather than "below a threshold", and that needing to tune a number would mean the criterion was wrong. It held — 16/16 positives found with evidence, 0/16 negatives proposed, and zero references seen on the negative side at all.

  The labels shipped in v1.30 with no corpus: they name notes that never existed as files, and the pre-existing test only checked the labels' own structure. The corpus was written from the labels alone, before the scorer was designed, with two assertions tying them together (rows 39 and 40) — row 40 checks each negative's claimed word overlap is real, since a negative rejected for being about nothing alike would make 16/16 meaningless.

  On the reference Vault: 195 notes, 5 candidates, 256 links correctly rejected. The five are real — a note citing another as its `选型依据`, and the Python series' prerequisite chain, where iterators depend on generators depend on comprehensions. **Five out of 262 is the finding, not a defect**: the helper does what the labels specify, and what they specify is something this Vault does about twice per hundred links. Loosening the criterion to raise that number would readmit all sixteen hard negatives.

  Two vocabulary entries were added from forms *observed* in that Vault, on the terms `PROJECT_NOTE_NEXT_ACTION_HEADINGS` set — a count and a location, never a guessed synonym: `前置知识` ×3 and `前序知识` ×2, which took the Vault from 1 candidate to 5. Measured in the same pass and deliberately not added: `详见` ×4 and `参考` ×2, which are pointers rather than dependencies.

  Breaking the guards on purpose found two things the tests were not saying. Deleting the dependency requirement entirely still rejects all sixteen negatives — they guard against inferring from a shared word, and prove nothing about link-with-dependency versus link-without, which now rests on two named cases and an assertion that records the division. And the same-sentence rule was **unguarded**: widening it to the whole note broke nothing. Both are now tested and both are stated in the eval report rather than left for a reader to over-read 16/16.

### Changed

- `AGENTS.md` gained two rules about how a conclusion is reached, beside the existing one about two places agreeing. A survey conclusion — how many, which ones, what fraction — must cite a command whose output can be recounted; and a new assertion must be seen red at least once.

  Both name instances this project has already produced rather than reading as general advice. #93's body says tightening the reachability predicate would mark six helpers unreachable while the breakdown printed beneath it implies one and the predicate prints two today; the same habit put the wrong file in #133's quotation, which led that issue to propose the wrong fix. On the other side, row 17 of the inventory asserts truthfully and covers less than its name suggests, #118 shipped a signals assertion that was vacuous and let a wrong output through, and deleting the criterion two of #75's guards were written for changed nothing they asserted.

  Neither rule can be checked mechanically — what they govern leaves no trace in the tree — and the paragraph says so, to stop a future reader from building the regex-over-commit-messages check the inventory's own `Rejected` section warns about.

- The Web Capture reference runner drives more than one Agent product. `#74`'s first acceptance criterion asks for twelve runs with the model v1.30 used, and this project no longer runs that product, so the criterion is unmeetable as written and its 8/12 is no longer a comparable baseline. The absolute bar is replaced by a within-agent comparison, and `summary.json` records `agent`, `agent_version` and `comparable_with_fixture_baseline` so one product's numbers cannot be read as another's.

  **The measured answer is that there is nothing to fix.** Depth selection is correct **12 out of 12** against the current instructions, confirmed by reading `capture_depth` in all fifteen notes written. Against v1.30's 8/12, and 6/6 against 2/6 on the two cases that used to misupgrade — a rate difference with probability `(1/3)^6 ≈ 0.0014` under the old rate. The prediction registered before the run said a 12/12 baseline means the candidate wording has no signal to move and should not be merged, and it was not. That does not establish that the instructions are unambiguous: the ambiguity diagnosed on the issue is really in `web-capture.md:26`, where the words naming *verified*'s trigger also occur when a request describes what a source contains. One agent is not fooled by it.

- Required facts in the semantic eval accept the forms a note may legitimately use, instead of one English literal against a Chinese prompt. Two notes for the same case each recorded all five facts in Chinese — `只读` x9, `检索` x7, `写入` x12, `用户意图` x3, `预检` x7 in one of them — and scored 5/5 against 1/5, the whole difference being whether the note happened to echo each English term once somewhere. They preserved the same knowledge.

  Every alternative form was written by a real run and is listed in `fact_form_provenance` with its count, on the rule #75 set for vocabulary: forms that were observed, never forms that sound plausible. An assertion enforces it, so a guessed translation cannot be added quietly (registry row 42).

### Fixed

- The one eval case whose prompt says the diagram is key evidence can no longer score full marks without it. All five of its required facts appeared in its own source text, while that source states outright that the text does not specify what the diagram adds — an evaluation asset that could not fail at the thing it exists to test, which is #117's shape and #136's other half.

  Two facts now come only from the image, and inspection is checked where it can be: `material-not-inspected` reads the transcript for a tool call that opened the asset. A colour fact cannot tell reading a diagram from guessing a plausible one, and a directory listing prints an image's name without anyone having looked at it, so neither the note nor the filename is evidence. Measured on the runs to hand, all six opened it.

- The eval's hard-failure contract lists what the gate can actually raise. It recorded 8 of 14 codes and named two the scorer never raises: one implemented under a different name, one — `invented-source-access` — never checked at all, so the prompt's ban on fetching the source URL has never been a gate. The pair is kept in `hard_failures_not_implemented` with what happened to each rather than deleted, since #74's acceptance criteria are written in terms of them. Registered as row 41.

- Chinese negation and Chinese clause boundaries in the eval scorer, two long-standing false positives that stopped a run. A note recording the source's own `不支持 Python 3.10` — a required fact, and the exact opposite of a forbidden claim — was graded as asserting it, because negation was recognised only as `未`/`没有` before one of four writing verbs. And `，` was not a clause boundary, so `原文把 2.4.1 和 Python 3.12 绑定，并单独排除 3.10` put both terms of a claim in one "clause" from two statements that each say something else. English `,` is deliberately still not a boundary. The earlier baseline never hit either; that was phrasing, not soundness.

## [1.33.0] - 2026-08-14

### Added

- `run-retrieval-view` runs a search the Vault has already written down. The questions a user asks repeatedly are not infinite — "learning notes from the last week", "current project risks" — and each time an Agent re-translates one into flags it may translate it differently, so the same question quietly gets a different answer. A view is that translation, made once and kept in `.obsidian-kb/retrieval-views.json`.

  Structured fields only: no command, no pipe, no template, no environment interpolation, and no field `search-vault` does not already have. A view can only narrow, and it reaches the same validated parameters a direct call reaches, so it can never get past a guard an ordinary search would face. An unknown key is refused rather than ignored — dropping one silently runs a search the file does not describe, which is the whole failure this exists to prevent.

  `--as-of` is required and the helper never reads the clock. A window whose meaning came from "now" gives different answers on different runs, which is the opposite of the point; "上周" is a phrase the Agent turns into a date, never a value a config can hold. `window_days: 7` resolves to an inclusive ISO pair, and `date_field` picks `date` or `updated` without blurring the distinction registry row 28 keeps deliberately apart.

  The resolved `plan` is returned beside the results, and a test re-runs that plan through `search-vault` and compares — a plan that does not describe the call actually made is worse than no plan, because it is a wrong answer wearing the costume of a checkable one. Registered as rows 36 and 37; row 36 reads `search_vault`'s live signature with `inspect` rather than comparing two hand-kept lists, so it cannot be satisfied by editing it.

  A view scoped to a folder that no longer exists returns `invalid-view-scope` rather than falling back to the whole Vault: a view that silently widened would keep working, return more than it ever did, and say nothing. A corrupt config refuses outright. `missing-view-config` is the ordinary state for a Vault with no views and says so rather than reading as a fault.

  Measured on a 214-note copy of the reference Vault: a 30-day `date` window resolved to `2026-07-16 → 2026-08-14` in 83 ms, a 90-day `updated` window returned the project note whose `风险与阻塞` section answers it, a moved scope refused, and an unknown name listed the three that exist. The plan reproduced the results exactly in both real views, and the copy was byte-identical afterwards. Nothing was written to the user's own Vault at any point — creating a view is theirs to do, and this Skill never writes to `.obsidian-kb/`.

- `explore-neighborhood` answers the question a reader has *after* finding a good note: what does this Vault say is connected to it. Search answers "which notes mention these words"; nothing answered "what is around this one", and the edges to answer it were already written down — body wikilinks, frontmatter `related`, and the same seen from the other end as backlinks.

  Every edge is a declaration and none is an inference. Nothing is scored, no link is proposed, and a link is never read as *supports* or *is evidence for*: #75 owns discovering new candidates and #85 owns evidence lineage, and doing either here would let a guess read as something the user wrote. Notes sharing a subject, a folder, or a date are not connected. The node order is a stable path sort and the reference says outright that it is not a ranking — presenting the first as most relevant would invent the one thing this helper refuses to compute.

  An ambiguous name lists its `candidates` and uses none, on #110's reasoning. An unresolved one is returned rather than dropped, because a note with three stale links should not look like a note with fewer connections. A link inside a code fence is syntax being quoted — the Vault's own notes quote it constantly — and a note linking to itself is not its own neighbour.

  Folder indexes and source archives are excluded by default and counted in `excluded`. An index links every note in its folder, so following it returns the folder rather than a neighbourhood (#133 settled that an index is a listing), and an archive is evidence reached from the note citing it rather than a knowledge neighbour. `--include-structural` follows them, because "this note is only reachable through its index" is a real question.

  One hop. On the reference Vault: a project retrospective returns one neighbour reached two ways at once — a body link *and* a `related` entry, deduplicated with both origins named — while the AI Bug workflow retrospective honestly returns **zero**, because it has no wikilinks and an empty `related`, and says in its own text that it deliberately made no links. Four notes explored in ~136 ms each, Vault byte-identical afterwards.

- Wikilink resolution moved out of `audit_vault` into a shared `link_graph`, so retrieval can reach it without the write-side closure. Obsidian resolves `[[alias]]` through the target's frontmatter, and a second implementation of that in the retrieval bundle would be a copy that agrees until it does not. `audit_vault` lost 146 lines to the move and gained an import. Registered as row 35.

  Adding a helper crossed six registered boundaries and five of them failed by name on the first test run — peer helper lists, the bundle's import graph, both runner registries, the console scripts, and the reference an Agent is sent to for these codes — each error naming its own fix. Only the sixth was new, and it is a deletion rather than a guard.


- The resume pack gathers the two source kinds #86 named and never shipped. PR #107/#108 delivered membership-by-location and closed that issue, so `project` frontmatter and the project note's own `related` list lost their tracker. They matter most where location cannot help: a project note directly under `40-Projects` has no instance directory, #95 made migrating one a non-goal, and until now such a project's pack was the note and nothing else. On the reference Vault that is exactly what happened — `40-Projects/2026-07-09 项目小结实践…` returned zero sources and now returns the learning note its own `related` list points at.

  Both routes are weaker than location and say so. `origin` names the strongest route that reached a note and `origins` lists every one, so a note found in the directory *and* linked from the project note appears once rather than twice. The reference ranks all three, and the `--max-sources` bound is layered: a hand-maintained `related` entry never displaces a note whose membership is readable from where it sits.

  Ambiguity is reported and never resolved. A `related` name matching two notes returns `ambiguous-related-link` with both candidates and uses neither — picking one would file another project's material into this pack, where it reads as this project's own history and the reader has no way to tell. A name matching nothing returns `unresolved-related-link` rather than quietly shrinking the pack. Only explicit declarations count: a wikilink in the project note's *body* is a reference, not a claim of membership.

  On the reference Vault `project:` frontmatter is unused — three occurrences, all empty, two of them templates — so that route's only evidence is its tests. Said plainly here rather than left for someone to discover.

- `search-vault` can filter on when a note *changed*, not only on when it was written. `--after/--before` have always read the frontmatter `date`, and there was no way to ask the other question — while the retrieval guide's own example was "最近的项目风险", a question about change that `date` answers wrongly in a way that looks right.

  Measured on the reference Vault: a project note dated `2026-06-09` was updated `2026-08-12`. `--after 2026-08-01` returns five notes and **silently omits the one that actually changed that month**; `--updated-after 2026-08-01` returns exactly it. Of 200 notes, 177 have no `updated` at all and are counted as `missing-updated`, separately from the 4 whose `updated` fell outside the window — "nobody recorded when this changed" is a Vault fact, while "it changed outside your window" is the filter working, and merging them would tell a user their note is old when the truth is that nothing was written down.

  `--updated-*` reads `updated` **only**. A note without one is excluded, never treated as if its `date` were the answer. `review-projects` deliberately answers activity differently — `updated` falling back to `date`, because a project note without one still has an age worth ranking — and that difference is now registered as row 28 and stated in the reference. It is the registry's first row for two places that must **stay** different: what needs guarding is not agreement but that the distinction is legible where the Agent reads it.

- A zero-result search says which of four things happened. `results: []` was one shape for "the scope holds nothing searchable", "the filters removed every candidate", "the notes could not be read", and "no note uses your words" — each with a different next step, and the text mode printed the same sentence for all of them. The counts to tell them apart were already in hand.

  `diagnostics` now carries `primary_reason`, the `facts` behind it, and `safe_retries`. Only mechanically provable reasons: the helper does not guess at spelling, synonyms, or intent. Several reasons can hold at once, so one is named primary by proximate cause and the rest stay in `facts` — a filter the user just added explains the emptiness better than the words not overlapping, and an unreadable note explains it better than an empty folder, because that scope is not empty, it is broken, and telling the user to write notes they already have is the wrong next step.

  The reading this exists to prevent is `no-token-overlap` reported as "your Vault has nothing on this". It is a fact about the words, not about the knowledge — the same confusion as `resume-project` reporting an unrecognised heading as a missing section. `facts.expansion_triggered` is likewise a fact and never a reason: a lexicon that added nothing has not been shown to be wrong.

  `safe_retries` are suggestions, not authorisation. The helper never re-runs itself, never widens a filter, never drops a scope, never rewrites the query; the reference says so explicitly, and "ask the user to approve a term pair" is a request to *them* because editing the lexicon is a write. Text and JSON are generated from one `ZERO_RESULT_REASONS` table, so the two cannot give different answers to the same question — registered as row 26, another relation removed rather than guarded, with row 27 keeping every code documented where the Agent can read it.

- `--runtime-only` / `-RuntimeOnly` installs everything a Skill manager does not provide, and nothing it does. The installer has six jobs and only one of them — writing Skill files into five platform directories — is something a manager also does. The other five are the vendored PyYAML, the interpreter record, the Vault path, the Vault's folders and templates, and the diagnostic copies, so "just use the manager" produces an install whose first helper call raises `ModuleNotFoundError`. Users were facing a false choice between the two tools when in fact each supplies a different half.

  The mode skips platform distribution and runs everything else, post-install verification included — a runtime nobody checked is the failure this mode exists to avoid. Combining it with `--platforms` is refused rather than reconciled: silently honouring one would leave the user believing the other took effect, and on a managed machine that is exactly the wrong belief to hold about whether Skill files were written.

  The upgrade path is now documented for that case. Re-running the plain installer was the published advice, and on a managed machine it used to be the destructive move; it is safe as of the previous release, but it still does not refresh what the manager serves. Both READMEs and `docs/platforms-and-installation.md` say which command to run and in what order, with the six-job table so the split is checkable rather than asserted.

  Registered as rows 23 and 24. Row 23 is row 17 with its gap closed: the Windows *behaviour* of an installer flag is exercised by exactly one file, which runs only in CI, and this change added its scenario there in the same commit rather than a release later.

- Filing refuses a note that says it is not finished, with the new `draft-incomplete` code. On the reference Vault a `web-clip` tagged `incomplete`, whose four sections all read "待后续详细阅读后补充完整", was proposed for migration to `20-Learning`. The two-phase gate caught it — a human read the plan and said no — but that is attention, not a guard, and a user approving a long plan reads the list rather than each line. Once applied, the mistake is hard to notice: the file looks like an ordinary archived note, in the folder where finished notes live.

  Two signals, both things the note states about itself rather than judgements about its content: the Vault's draft tag in `tags`, and an unreplaced `{{placeholder}}` still in the body. A body that says "待后续补充" in prose is *not* matched — reading prose for meaning is exactly what filing does not do. `draft_signals` names which fired, and the refusal says what completes the note; the Agent is told never to strip the tag to make the note filable, because the marker is the user's statement about their own note.

  The refusal is the Skill's own rule applied one step later. `note-creation.md` forbids presenting Inbox content as finished knowledge and `web-capture.md` forbids auto-downgrading a failed capture into an Inbox bookmark — "the user must choose that different product explicitly". Filing one *out* of the Inbox is that same downgrade running backwards, unasked.

  The word `incomplete` is the Vault's, not this Skill's: the project never writes that tag, and hardcoding another system's vocabulary is exactly how the English project-note template drifted out of the resume contract. It is the default because it is the word this Skill's own references already use for the state, and `--draft-tag` declares a different one — replacing the default rather than extending it, so a Vault that uses `incomplete` to mean something else can opt out. Registered as row 21; the filing reference must name whatever the default is.

### Changed

- `search-vault` ranks a note on its **best section** instead of on everything it contains, and cites from that same section. The two used different units before: BM25 charged a note for every word in it, then a snippet was picked afterwards, so the reason a note ranked and the place the reader was sent could be different parts of the same note.

  The cost of the old unit was measured, not assumed. On #117's adversarial set the identical evidence paragraph scored 11.9 in a 0.3 KB note and 2.2 in a 75 KB one, and neither long note appeared in Top-5 while five notes that mention the terms in passing did. The sectioned long note now enters at rank 2; its unstructured twin, same evidence and same size, stays absent — which is the measurement working rather than a number moving, because a section can compete on its own content only where sections exist. Across the 23 cases, dilution improves (MRR 0.867 → 0.9, one fewer must-see miss) and the four other families are unchanged on every metric they record.

  One formula and one normalisation, as before; only the unit changed. Title, aliases, tags, headings and links describe the whole note and enter every section's score, while the body is partitioned and the best section counts. A note without headings has one section equal to its whole body, so short unstructured notes — most of a Vault — score exactly as they did.

  A section is charged at no less than a typical section of its own note. BM25 rewards short documents, which is right for a short note and wrong for a short slice of a long one: reaching it still means opening the long note. #118 listed this risk before the code existed and the first implementation had it — a stub reading `jitter 上限。` outscored a note whose section explains the answer, 0.580 to 0.504. The floor uses no constant and is inert where the section *is* the note.

  `heading`, `line`, `snippet` and the `body` signal now all describe one section. A word the user typed that appears elsewhere in the note is no longer reported, because saying so tells the reader it is in the passage in front of them; that too was listed as a risk, implemented wrongly anyway, and caught by reading the output rather than by the assertion written for it, which was vacuous on its first draft.

  Latency on the reference Vault is P50 139 ms against 125 ms before, P95 144 ms against 138 ms — 1.04x at P95, against the 2x budget #118 set. Getting there meant not tokenizing the body twice: the counts are summed from the passages instead, which is exact rather than approximate because `TOKEN_RUN_RE` matches runs of Latin or CJK characters and a newline is neither, so no run can span a line break. Registered as rows 33 and 34.

  `matched_passages` is deliberately not shipped. #118 lists it as optional, and growing the payload contract in the same change that reorders every result is two decisions where one will do.


- The revival queue says where its task count came from. `open_tasks` counted every unchecked box in a note, and that number ordered the queue — so a note holding a *reusable* checklist outranked projects with real work. On the reference Vault one project note ends with fifteen checklist items for landing some *other* project, while its own plan is a P0/P1/P2 numbered list with no checkbox at all; it ranked as the busiest project in the Vault and reported `测试或发布基线是什么；` — a checklist question — as its next step.

  The queue now orders by `open_tasks_in_next_actions`, the boxes inside the note's own next-actions section, and reports both numbers plus `open_tasks_scope` so the ordering can be checked. `null` there is not zero: zero means the note put nothing in that section, `null` means it has no such section and the whole-note count still applies — scoping must not erase a class of project from the queue. `next_action` no longer reaches past an empty next-actions section for the first checkbox anywhere, which is how the checklist question was picked up.

  `next_action_heading` is new, and it is where this stops being mechanical. On that Vault the checklist is *nested inside* the next-actions section — `### 可复用的项目落地检查表` under `## 下一步行动`, beside `### P0：下一次迭代前完成`. No structure separates them; what separates them is what the author called them, and that is a judgement about content this helper does not make. So it names the heading and the reader judges. A test asserts that case as it is, rather than a fixture that made the two siblings and passed while the defect stood.

- Both retrieval helpers now mean the same thing by "next actions". `review-projects` and `resume-project` each held their own literal heading set; the previous release widened only the resume side with `后续行动`. Nothing failed, because the radar falls back to the first checkbox anywhere in a note — the drift surfaced only when scoping that count to the section, where it would have zeroed out the one project whose checkboxes all sit under the widened heading. They now share `note_catalog.PROJECT_NOTE_NEXT_ACTION_HEADINGS`, with each variant's source recorded beside it. Registered as row 22, another relation removed rather than guarded.

- The unreplaced-placeholder rule now has one definition instead of three-in-waiting. `audit-vault` and `template-contract` each carried their own pattern and had already diverged — only the latter captured the placeholder's name, which its `findall` depends on — and filing was about to add a third. They now share `note_catalog.TEMPLATE_PLACEHOLDER_RE`, asserted by object identity so a local copy cannot come back. Registered as row 20, which records a relation *removed* rather than guarded: when two places can import each other, deleting the boundary beats asserting over it.

### Fixed

- The adversarial retrieval set can now measure the thing it was built to measure. Every long note in it was generated by appending unstructured filler, because that is how the author pictured a long note. Measured afterwards on the reference Vault: of the 19 notes at or above 10 KB, the fewest headings any carries is 12, the median is 30, and **none** has a single heading — real notes are long *because they have many sections*, and the shape the fixture used occurs zero times. The set reproduced length dilution through a mechanism this Vault does not exhibit.

  The consequence was not theoretical. A section-ranking candidate scored byte-identically to master across all 22 cases, because a note with one heading has exactly one passage and any heading-based split is a no-op on it. #117's own bar was that an evaluation set which cannot fail is a guard green from birth; this set could fail, but not at the question #118 was about to ask it.

  `backoff-manual.md` joins the dilution family: the same evidence paragraph, the same filler, a size within 1 KB of its unstructured twin, divided into 32 sections. The pair is the measurement — a section-level ranker can help one and cannot help the other, so a candidate that moves both, or neither, is doing something other than what it claims. Section titles are drawn from the filler so the sectioned note gains no `headings` weight the other lacks; structure is the only variable. The unstructured note stays, because an archived clipping really can be a wall of text and keeping both shapes is what lets a result say *which* one a change helped.

  `adv-dilution-05` adds the same limitation at depth: the answer sits in the last section, while a short note naming the same terms says outright it does not cover them — and wins by a factor of five, because it is the whole document and pays no length penalty. Registered as rows 31 and 32; 32 was found while fixing 31, and is the registry's first row on a *test asset* — the baseline comparison walked only the recorded cases, so a query added to the fixture without a baseline row was frozen in name and free in fact.

- A resume pack no longer offers a project's own directory listing as project material. `_instance_sources` promised in its docstring that index files were excluded and excluded only `README.md`, `AGENTS.md` and `CLAUDE.md`, so a folder index — named after its directory under this project's default convention — came back as a source. On the reference Vault that was not one project's misfortune: of the four project notes, the three with an instance directory each returned **exactly one** source, and in all three it was that project's own folder index, contributing `fields: []`. All three now return `sources: []`, which is the honest answer for a directory holding a note and a listing. The pack is still readable at zero, because `headings.unmatched` (#115) says where the material actually is — between them those three notes list over ninety headings the vocabulary does not know.

  The criterion is the note's **declared type**, and it applies to every route rather than the directory sweep alone. A misplaced index — one `audit-vault` would report as `misnamed-folder-index` — is still an index; a real note that happens to carry its directory's name is still a source. #133 proposed the other criterion, excluding whatever `expected_folder_index` names, and that was rejected on measurement: it returns `<folder>/<folder>.md` even with the Folder Index plugin disabled, because the config defaults say so, so it would trade one silent omission for another. A hard negative fails when that criterion is applied.

  A `related` link or a `project` field resolving to an index reports `index-note-excluded` with the origin that named it. The directory sweep stays quiet — that is the sweep's own rule and announcing it once per project is noise — but a declaration is something the user wrote down, and #110 settled that a declared link the pack does not use is reported rather than dropped.

  `{"folder-index", "moc"}` was two copies before this: `audit_vault.INDEX_TYPES` and the same literals inline in `note_catalog.VALID_NOTE_TYPES`, with nothing tying them together and retrieval about to become a third. One `INDEX_TYPES` in `note_catalog` now serves all three, asserted by identity so an equal-valued copy still fails. Registry row 30 changes from `guard: none` to *relation removed*, and records that the issue's own quotation named the wrong file — the promise was a docstring, not the reference, which contains no occurrence of the word.

- `resume-project` no longer reports "the project never recorded this" when it means "I did not recognise the heading". `missing_sections` said only that a field could not be filled, and those two readings send a user in opposite directions — one goes looking, the other writes a decisions log that already exists. Measured on the reference Vault: a project note written from a conversation rather than the template returned `goal` alone and listed decisions, blockers and next actions as missing, while its decisions sat under `1.0 推荐方案` and `Redis 优先级结论` and its next actions under `后续行动`. The same note's next action was extracted correctly by `review-projects`, which scans checkboxes and does not depend on section names, so two helpers gave opposite answers about one note.

  The pack now returns `headings`, splitting the note's own headings into `matched` and `unmatched`. A missing field whose note has unmatched headings may well be recorded under one of them; both lists empty is the one case where missing means absent; and a heading in `matched` whose field is still missing says the section exists and is empty. The pack does not guess which unmatched heading holds what — #86 rules that out and this change does not reopen it — it reports what it did not claim and lets the reader look. Recognition is by name, and the report's notion of recognition is the matcher's own, asserted rather than assumed.

  Two heading variants were added, both observed rather than invented: `后续行动` from the note above, and `overview` from `core/templates/en/project-note.md`. The second was a live defect this change's assertion exposed — the vocabulary knew only `project overview`, so **every note written from this project's own English template reported its goal as missing**. The digest side of the same relation was derived from a contract and had not drifted; the project-note side was hand-copied and had. Both halves are now registered as rows 18 and 19 of the consistency inventory.

  Source notes get no heading report. A source contributing nothing is the ordinary case — a meeting note in the project folder was never expected to answer these fields — so reporting it would be noise, not a signal. The project note is different: answering these fields is what it is for.

- The installer no longer destroys a Skill link it did not create. On a machine where a Skill manager owns `~/.claude/skills/*`, those entries are symlinks into the manager's store; `copy_skill_payload` began with `rm -rf`, so a routine install replaced each one with a real directory and silently ended that ownership. Observed in practice: the installer printed `Installation complete` with all five platforms ticked while `skillctl doctor` went from `OK` to `FAILED` with eight `runtime link drift` errors. Neither side inspects the other, so nothing reported a problem.

  A link pointing *into this checkout* is still replaced without `--force`, because copying would otherwise follow it and write back into the source tree being installed — that contract predates this change and its tests are unmodified. A link pointing anywhere else is now skipped with the target named, and `--force` overrides, matching how `--force` already governs template overwrites. Both installers report a count at the end and say how to refresh through the owning tool.

  The boundary this creates — one decision stated in `install.sh`, in `install.ps1`, and in the Windows smoke script — is registered as row 17 of the consistency inventory. The parity assertion shipped with the fix reads `install.ps1` and does not cover the smoke script, which is precisely what then broke; only Windows CI executes that file. Recording what a guard actually covers, rather than what it is named after, is the point of the row. Leaving that observation in a commit message put a known risk where nobody reads it.

## [1.32.0] - 2026-08-12

### Added

- A registry of the boundaries where two places must agree, at `docs/superpowers/specs/2026-08-12-consistency-inventory.md`. The same defect shape appeared seven times in one day: something is stated in two places, nothing checks they agree, and the failure is silent — no error, no red test, just a wrong answer where nobody is looking. Sixteen boundaries are listed with the assertion that guards each, including one that has none (#91's twenty hand-copied installer paths, unguarded for months precisely because nothing had named it). Three guards were added by this change: the write runner's test tuple was pinned to its runner as the retrieval side already was; `[project.scripts]` is now checked against both runner registries with `doctor`'s absence stated as a decision rather than left as a difference; and the capability table can no longer advertise a helper that does not exist — which is where #90 hid, since the documented promise made the missing route harder to notice.

  The predicate for that last one took three attempts, and the failures are instructive. Scanning the whole document flagged `conversation-harvest`, a workflow reference rather than a helper, and the exemption list needed to tell them apart kept growing — a sign the predicate was wrong, not the document. Narrowing to the capability table's implementation column then surfaced that the column cites three kinds of thing: helpers, note types, and whole Skills. The final version excludes the latter two using sets the project already defines, so no hand-maintained exemption list exists. The assertion was then verified non-vacuous by temporarily renaming a cited helper.

  `AGENTS.md` now requires a row and an assertion in the same change that creates a dependency between two places. Deriving the registry from code was considered and rejected: #95's boundary was a directory layout disagreeing with a frontmatter field, #108's was a module allowlist disagreeing with an import graph across a packaging step, and neither is textual duplication. A scanner that found some rows while missing those would be worse than a hand-kept list, because it would look complete.

- The resume pack answers what to do next, not just what to read. `resume-project` now extracts the goal, blockers, decisions and next actions the project note states, plus the constraints and evidence its digests hold, each carrying the path and line it came from. Section names are matched against the templates' own headings in both locales; the digest's names are derived from `CONVERSATION_DIGEST_HEADING_VARIANTS` rather than restated, because a second copy of a contract is the hand-mirror shape that produced #91's installer paths and #103's peer lists.

  A section the note does not have is reported in `missing_sections`, never assembled out of surrounding prose — a Vault on custom templates legitimately has none of them, and a confident answer the note never made is worse than a stated gap. A field answered by both the project note and a source is named in `contested` and returned from both sides: that is not automatically a contradiction, and recency is not authority, so the pack declines to pick a winner. `--max-sources` (default 5) bounds the pack newest-first, and the overflow is reported through `truncated` and `summary.sources_available` rather than dropped.

- `resume-project` gathers what belongs to one project, read-only. `review-projects` answers *which* project to pick up; this answers *what to read to continue it*, returning the project note plus the output that belongs to it. Membership is established by the entity-folder layout — a note inside the project's instance directory belongs to that project because of where it is. Every other route depends on maintenance: a `project` frontmatter field can be missing on a note that clearly belongs, and a `related` wikilink can resolve to a same-named note in another folder. A note's location cannot be stale in either direction. Each source carries an `origin` naming how membership was established, so a later, weaker origin cannot silently look like this one.

  This is the first half of #86. It delivers the sources; extracting goal, constraints, decisions and next actions out of those sources follows. The split is deliberate: the capability is reachable from the retrieval Skill's routing table on arrival, rather than being completed first and connected afterwards — the failure that produced #90 twice.

  A project note living directly at `40-Projects` returns `instance_directory: null` and no sources, which is a valid pre-existing layout rather than an error; #95 explicitly does not migrate those. A source whose own frontmatter is unreadable is reported in `issues`, and the rest of the pack is still returned.

- Filing refuses a project note instead of guessing which project owns it. `40-Projects` groups by entity, so knowing the folder is not enough — the note belongs to one instance inside it, and which one is not readable off the note. Both available answers were wrong: dropping it at the entity root is the state the entity-folder rules exist to prevent, and guessing an instance directory files the note into another project, where it is then read as that project's history. The note stays in the Inbox with the new `entity-instance-unknown`, which is distinct from `unknown-target` because routing did determine the kind and only the owner is missing — that difference is what the user is being asked to supply.

  The check is on the routed destination rather than on the note's `type`, because `type` is not the only way in: `KEYWORD_ROUTES` maps the words "project", "milestone" and "sprint" to `40-Projects`, so a note that never claimed to be a project note could reach the entity root through its body text. Guessing from prose is strictly worse than guessing from `type`, and one check on the result covers both paths.

- The audit reports a project directory holding more than one project note. `40-Projects` groups by entity — one directory per project, holding that project's heterogeneous output — while `review-projects` identifies instances by frontmatter alone (`review_projects.py` reads `type` and never looks at a path). The two agree only while each project directory holds exactly one project note, and nothing enforced that. Two such notes report as two separate projects, each with its own staleness and open-task count, and the radar cannot see the duplication because it does not look where the duplication is. The new `duplicate-project-note` finding is the only thing that surfaces it.

  Three exclusions are part of the rule rather than refinements of it. Notes at the entity folder's own root are not instances of each other — they are projects nobody has given directories yet, which is the pre-existing flat layout and explicitly not migrated. Subordinate output sharing an instance directory is what the directory is *for*; only the instance type is bounded to one. And a `status: template` card is entity-shaped but started no project, so reporting one would repeat #83 in a new location. All three ship as hard negatives, because the mechanical version of this rule — *a project directory should hold one project note* — is the obvious one to write and is wrong in all three cases.

  `ENTITY_FOLDERS` and `ENTITY_INSTANCE_TYPE` declare the grouping semantics once in `note_catalog`, so rules can ask what kind of folder they are looking at instead of naming `40-Projects` wherever the question comes up — that habit is how the crowding contract came to govern a structure it was never written for. `NON_INSTANCE_STATUSES` moved there from `review_projects` for the same reason: the audit and the radar need one definition of what is not an instance, and it had only ever had one consumer.

- Vault audit is reachable. `audit-vault` was the second helper in the #90 pair: implemented, tested, registered in `[project.scripts]`, listed in the Skill runner's `HELPERS`, advertised in `docs/feature-guide.md`, and named nowhere in `core/`. It now has a routing branch of its own — the audit is not part of the save flow, so it gets its own entry in the body rather than a line in the save routing table — pointing at the new `core/references/audit-vault.md`. The `description` covers checking or auditing a Vault, without which "帮我体检一下 Vault" matches none of save/create/update/archive/remember and the branch stays unreachable from outside.

  Placement was the open question, and it was decided on measured cost rather than on which Skill reads better. `audit_vault`'s transitive dependency closure is 13 modules; the read-only bundle carries 10 and would need 9 more, growing its Python payload from 98 KB to 217 KB — **+121%** — for a bundle whose value is partly that it is small. Almost all of the additions are write-side contracts: `capture_receipt`, `deep_capture_contract`, `conversation_digest_contract`, `template_contract`, `folder_index_policy`. Buying semantic purity (an audit is read-only) with semantic impurity (a never-writing Skill shipping a full set of write contracts) is not a trade worth making, so the audit lives in the write Skill, where its dependencies already are and where the repair a finding suggests would happen anyway.

  The reference states the boundary that a read-only capability most easily leaks across: reporting a finding does not authorize fixing it. The fix is a separate request with its own explicit save intent, and a note is never repaired to make a finding disappear before it is reported. It also states that findings are not verdicts — `disconnected-note` on genuinely standalone knowledge is a legitimate state, and reporting it as a defect pushes users to manufacture exactly the weak links the rest of this Skill refuses to create.

### Fixed

- Asking the wrong Skill's runner for a real capability now says where it lives. The project ships two Skills with separate runners, and until now the write runner answered `review-projects` with nothing but argparse's `invalid choice` plus its own 14 names — which reads as "no such capability" rather than "wrong door". That is exactly how it was read: an Agent session concluded the helper was missing from the machine, reported a phantom registration bug upstream, then bypassed the runner to invoke the module directly and hit `ModuleNotFoundError: No module named 'yaml'` — because the vendored packages are put on the path *by the runner it had just bypassed*. It ended up hand-rolling a `PYTHONPATH` workaround for a capability that had been working the entire time. Each runner now carries the peer's helper names — names only, no import, nothing that would pull the write Skill's modules into a bundle whose value is being small — and points at the Skill that provides them.

  A name neither Skill provides still returns the ordinary `invalid choice`, so the hint cannot swallow a genuine typo. The two lists are hand-kept mirrors, which is the shape of duplication that produced #91's twenty hard-coded installer paths, so a test asserts each list equals exactly what the other runner has and this one lacks — `doctor` and `vault-info` exist on both sides and are correctly absent from both lists.

- The helper-reachability guard no longer accepts a mention as an invocation. It matched the helper's name anywhere in the instruction text, so a line telling an Agent *not* to use a helper satisfied it exactly as well as a line showing how — adding "never invoke `process-inbox` during conversation harvest" to any reference would have turned the guard green while no branch selected it, reproducing the #90 state with the guard reporting success. A guard that weak is worse than none, because it advertises coverage it does not provide. Reachability is now "the instructions show how to run it": either through the bundled runner, or as the helper named with its arguments. A bare mention does not count, and neither does a flag that embeds the name.

  Two helpers are exempt with stated reasons rather than silently passing. `doctor` is an installer and troubleshooting tool, not a Vault operation. `suggest-links` is not a standalone entrypoint at all — the instructions reach it as `create-note --suggest-links`, so it has no invocation of its own to show, and the old substring check had been counting the flag as proof the helper was routed.

  The scope of this change was smaller than #93 estimated. That issue reported six helpers reachable only through prose, which came from a survey that inspected each helper's *first* match and stopped; counted properly, ten of the thirteen already showed a runner invocation, and only `scaffold-templates` needed the second accepted shape.

- The crowded-folder contract states which kind of folder it governs. It never did, and reading it as universal is what produced #95: its thresholds solve "too many notes to navigate", which is subject clustering, while an entity folder groups by what a note belongs to. Applied to `40-Projects` the rules forbid the correct structure — "Never create a one-note directory" rules out a project directory, which by definition starts with exactly one note, and the five-note cluster evidence never appears because a project's retrospective and its meeting records share a directory without sharing a subject. The reference now scopes itself to taxonomy folders, names entity folders as excluded, and points at the design document rather than leaving the next reader to re-derive the distinction.

- Inbox filing explains every note that did not move. Plan-phase refusals already carried `skip` and `skip_code` on the note's plan entry, but the three refusals raised at write time — destination occupied, frontmatter unreadable at write time, source could not be removed — only printed to stderr and set nothing. A `--json` consumer saw `applied: false` with no reason attached, so an Agent could report *that* N notes stayed put and never *why* for any of them. Both phases now use one vocabulary: `target-exists`, `source-removal-failed`, and the plan-phase codes, all recorded on the entry. The human-readable stderr messages are unchanged.

  The failure that leaves the Vault changed gets its own code. When the copy is written, the original cannot be removed, and the rollback also fails, the note exists in two places and needs manual cleanup — every other refusal means nothing happened at all. Sharing a code between them is how an Agent reports a clean skip over a split note, so `partial-apply` is separate, and both the error table and the workflow state that neither copy may be deleted to tidy the result.

  `unknown-target` is now documented alongside the other codes. It is the most common refusal in an unstructured Inbox — the folder simply could not be inferred — and it was the one code the workflow pointed at `rules-and-errors.md` for without that file ever defining it.

- Project Revival Radar no longer treats reusable `project-note` blueprints
  marked `status: template` or `status: 模板` as stale project instances. These
  non-instance markers stay separate from completed lifecycle states, while
  `draft`, missing, and unrecognised statuses remain visible for human review.

- Inbox filing is reachable. `process-inbox` was implemented, tested, registered in `[project.scripts]`, listed in the Skill runner's `HELPERS`, and advertised in `docs/feature-guide.md` as an Inbox filing capability — while `core/` never named it once. It shipped to every user's disk and no Agent could select it, so the documented capability existed only for someone who ran the console command by hand. The routing table now carries a filing branch pointing at the new `core/references/process-inbox.md`, and the Skill `description` covers filing an Inbox, which is what decides whether the Skill activates at all: a user asking to sort out their Inbox matched none of save/create/update/archive/remember, so the branch behind those words would have stayed unreachable from the outside no matter how correct it was.

  Connecting it required settling what `≤1 note written` bounds, because filing one Inbox can touch thirty notes and reads like a violation. It is not: that bound stops an Agent from *generating* a pile of notes from one conversation, and filing generates none. Every Inbox note already exists, was written by the user, and already passed the explicit-save-intent gate when it was captured; filing relocates it and completes the metadata the quick capture omitted, leaving the Vault with exactly as many notes as before. The bound that applies to filing is the Inbox itself. The distinction is recorded in `docs/superpowers/specs/2026-08-11-inbox-filing-entrypoint-decision.md` rather than left to be re-derived, because the tempting resolution — loosening a real safety limit so filing fits under it — is the wrong one and looks reasonable.

  `--apply` moves files, so intent to file authorizes producing a plan, not executing it. `--plan` is read-only, is the default, and is never skipped, however decisive the request sounds: destinations are *inferred*, from body keywords when a `type` is absent, and keyword inference is exactly what a user must be able to overrule per note. This reuses the existing `create-note --preflight-json` → `--apply` shape rather than inventing a second authorization concept.

  A regression test now asserts that every helper in the bundle is named somewhere an Agent can read, with unrouted helpers listed explicitly alongside the reason they stay that way. Shipping a helper is not the same as making it reachable, and nothing in the build could previously tell the two apart. `audit-vault` is unreachable for the same reason and stays that way for now: it is read-only so it needs no authorization design, but placing it means either adding write-side modules to the read-only bundle's allowlist or accepting it in the write Skill, and that trade-off is independent of Inbox filing.

## [1.31.0] - 2026-08-11

### Fixed

- The Web Capture hard gate no longer accepts three shapes of invalid answer. Both samples reported in #76 scored `hard_failures: []` on v1.30.0, and each exposed a different rule grading wording instead of assertions. Completion was inferred from prose patterns that covered "I wrote" but not "Your note is ready", so the grader had to guess a status nobody declared — runs now end with a required `OUTCOME:` / `BLOCKER:` block, and an unparseable one is itself a failure. A stop reason was accepted whenever any expected keyword appeared anywhere, so "transaction handler is irrelevant" counted as citing the material it dismissed; the declared blocker must now name the case's material *and* assert that it was unavailable, and naming required material only to wave it away is the new `dismissed-required-material`. Forbidden facts were matched as exact phrases, so `CVSS 9.8` was forbidden while "9.8 on the CVSS scale" scored clean; a claim is now a curated term set that must land unnegated in one clause, order-independent but clause-bounded, with a stated absence still allowed.

  `--rescore-messages` re-grades the final messages an earlier run saved, offline, with the message-level rules, reporting workspace-dependent checks as not applicable rather than skipping them quietly. The v1.30 artifacts cannot be re-scored — they were written to an operator-supplied directory and never committed, so the published "0 hard failures" cites evidence nobody holds; future runs are re-scorable, which is the part that was actually fixable. The runner's docstring now states what a mechanical scorer can establish: a rewrite avoiding every declared term still passes, and zero hard failures means only that nothing tripped these rules.

- Crowded-folder clustering asks the Vault which tags are type defaults instead of consulting a hardcoded list, closing the split v1.28.0 left behind: `tag_vocabulary` had already moved to the Vault's own `Templates/`, while `subject_clusters` still read `suggest_links.GENERIC_TAGS`. Two sources answered one question and had drifted apart. That list called `java` generic — a real subject with twelve notes on the reference Vault, which would have been silently discarded the moment a crowded folder collected five of them, and it is exactly the tag such a folder should split on. It also still carried `person` after the templates moved to `people`, so the entry protecting nothing outlived the entry that would have. Discovery now reads the templates once and passes the result to both callers. `suggest_links` keeps its own `GENERIC_TAGS`: there it is a relative noise filter with dynamic augmentation rather than a type-default list, changing it would change link scoring, and that scoring has its own evidence bar under #75.
- Words for *a piece of writing* no longer take crowded-folder cluster slots. `GENERIC_TITLE_TOKENS` covered article genres (`指南`, `教程`, `guide`) but not the nouns for the document itself, so `文章` took one of six slots on the reference Vault's `20-Learning/AI-Agent` and displaced `llm-engineering` and `vibe-coding` — real split candidates. Added `文章`, `笔记`, `记录`, `整理`, `汇总`, `合集`, `系列`, `article`, `note`, `notes`, `post`, `summary`.

### Added

- A Vault can declare which of its own words are not subjects, through an optional `.obsidian-kb/vault-vocabulary.json`. A clipping convention such as `2026-07-24 掘金文章-…` spends a cluster slot on `掘金文` in every review, but the site name is noise in a Vault that clips from it, a legitimate subject to someone writing about the platform, and dead weight in a Vault that never clips — so it is not shipped and not guessed at with an untested positional heuristic, because a real subject leads a title just as often. Each declared phrase is tokenized exactly as a title is and every resulting token is removed together: `掘金文章` drops `掘金`, `金文`, and `文章` at once, where dropping only the last would let the other two merge straight back into the term that was taking the slot. Bounded at 16 KiB, 100 terms, 2 to 40 characters each. A malformed file refuses with the new `invalid-vault-vocabulary` rather than being ignored, since ignoring it would report as advice exactly the clusters the file says are noise.

- Retrieval answers a Chinese question from an English note. A curated bilingual concept lexicon is matched against the query and the other language's words join the search at 0.45 of the weight of a word the user typed. This is still lexical matching — no vectors, no model, no index, and `mode` stays `lexical`. The v1.30 baseline resolved three of eight semantic paraphrases, and five of the five failures returned *zero* results rather than wrong ones: the corpus is English, the queries are Chinese, and the tokenizer emits Latin words and CJK bigrams, which never meet. The three that passed all passed because the note happened to carry a Chinese alias sharing a bigram with the query, not through any cross-lingual matching. All eight now hit, seven at rank one, with exact, alias, filtered, and no-answer groups unchanged and P95 latency at 7.20 ms against the 7.58 ms baseline. Eight further Chinese queries were committed *before* the lexicon existed, with their pre-expansion score frozen in the same commit, and went from four of eight to eight of eight — moderate evidence of generalisation, on the same sixteen-note corpus, not proof of it.

  Expansion is a hypothesis about what the user meant, so it is reported rather than assumed: the response carries an `expansion` block naming each concept, the surface term that matched, and the tokens it added, each result the lexicon reached carries an `expansion` signal, and a direct `body` or `title` signal never names a word the user did not type. Chinese 代理 is both *agent* and *proxy*; both readings expand and both are reported instead of the helper silently picking one. `--no-expand` reproduces the pre-expansion behaviour exactly, and the published before-numbers are asserted through that flag rather than left in a report.

- A Vault can teach retrieval its own vocabulary through an optional `.obsidian-kb/retrieval-lexicon.json` — product names, a team's preferred translation, anything a shipped table cannot guess. User concepts are held to the same structural rules as the built-in ones: unique lowercase ids, 2 to 12 terms of 2 to 40 characters, no general-language term from the mechanical stopword list, no shadowing a built-in id, bounded at 64 KiB and 200 concepts. A malformed file refuses with the new `invalid-lexicon` rather than degrading silently to the built-ins, because a search that quietly ran with different vocabulary than the file describes is a search nobody can reproduce. The folder is configuration, never indexed and never returned as a result. The lexicon is never learned from note content: notes are untrusted data in this Skill, and a lexicon derived from them would let a note decide what the search looks for.

### Changed

- The retrieval corpus gains a `semantic-holdout` group and moves to fixture schema 3. The eight `semantic` queries are what a lexicon gets optimised against, so they cannot also be the evidence that it generalises; the holdout exists to estimate that separately and is deliberately not a release gate — its test may only fail on regression, never demand an improvement.
- `EXPANSION_WEIGHT` ships at 0.45 on principle, not on measurement, and the evaluation report says so. Swept from 0.25 to 1.00 the corpus does not move: recall is flat and nothing breaks even at full weight, which shows the gain is not an artefact of a tuned constant and also shows sixteen clean synthetic notes cannot exercise the down-weighting at all. Its protective value on a Vault large enough for an expanded token to collide with an unrelated note is untested.
- The tokenizer moved to `text_tokens` and is now imported by both the index and the lexicon. An expansion token produced by a second, drifting copy of that function would never match anything, and the bug would look like a bad lexicon rather than a split implementation.
- Added a read-only Project Revival Radar. `review-projects` finds blocked, stale, or undated `project-note` files, extracts visible unfinished actions, and returns a bounded, deterministic queue with explicit inclusion reasons; it never changes project state or writes review metadata. A project is closed in whichever language its author wrote the status in — `completed` and `已完成` both retire it — and an unrecognised status keeps the project visible rather than silently retiring it. Vault containment is enforced inside `review_projects` and not only in the CLI, matching `search_vault`: an outside scope is refused instead of reaching `Path.relative_to` and raising a bare error carrying an absolute filesystem path. The set of directories that hold no knowledge is imported from `search_vault` rather than copied, because the copy had already drifted — it spelled the archive folder as a literal and never learned about the retrieval lexicon's folder.

## [1.30.0] - 2026-08-09

### Added

- Added a reproducible semantic quality gate for Web Capture: twelve synthetic standard, verified, and zero-write cases run three times with an isolated Codex reference Agent. The gate separates hard failures such as invented claims, false completion, mutation on failure, and receipt mismatch from soft coverage and structure scores.
- Added a versioned forty-query retrieval corpus covering exact, alias or bilingual, metadata-filtered, semantic-paraphrase, and true no-answer searches, plus a read-only baseline runner that reports Recall@5, MRR, false-positive rate, and latency.
- Added thirty-two directional-link labels: sixteen evidence-backed positive directions and sixteen same-topic hard negatives. They establish evaluation language without adding a new scorer or automatic link insertion.

### Changed

- Kept retrieval behavior lexical and offline in this release. The measured v1.29.2 baseline resolves three of eight semantic paraphrases; a future candidate must add at least two valid hits without regressing stable query groups, no-answer precision, read-only contracts, or the two-times P95 latency budget.

## [1.29.2] - 2026-08-09

### Fixed

- Completed the release surface for source archiving without changing its storage or linking contract. Wheel installs now expose `obsidian-archive-source`, installed-skill `doctor` imports `archive_source`, hostile-working-directory runner coverage includes `archive-source`, and the wheel smoke test exercises an archive preflight outside the checkout. The Chinese and English feature maps and the complete CLI guide now advertise the capability that v1.29.0 already shipped through the bundled Skill runner.

## [1.29.1] - 2026-08-07

### Changed

- Crowded-folder clustering no longer spends its six slots on terms that describe the folder itself. A term is a split candidate only when both sides of the split could stand alone, so the remainder must also clear `CLUSTER_MIN_NOTES` — expressed as a remainder rather than a percentage, because it reuses the threshold already in play instead of inventing a second one, and because covering 6 of 7 notes and 172 of 200 are both 86% and are not the same decision. A term equal to the folder's own name is dropped at any ratio: `20-Learning/AI-Agent/ai-agent/` renames the folder rather than splitting it, and the remainder rule alone misses it because that term leaves 9 notes behind. A title token that is one hyphen-separated part of a counted tag is also dropped — `ai` and `agent` are `ai-agent` seen twice, and the existing guard only caught a token equal to a whole tag.

  On the reference Vault `20-Learning/AI-Agent` had 11 qualifying terms and reported six, of which four were noise: the folder's name, both halves of it, and the word "文章". Two real candidates, `llm-engineering` and `vibe-coding`, were cut off the end. All four real subject tags now appear. `10-Work/日报` reports nothing at all, which is the honest answer — four terms each covering 30 of 30 notes describe the folder, not a sub-theme — and a genuine majority cluster such as `spring-boot` at 5 of 13 is still reported. Terms are removed rather than ranked last: the slots are the scarce resource, and the terms they displaced were the real candidates.

## [1.29.0] - 2026-08-07

### Added

- A captured source can be kept verbatim beside the note instead of inside it. `archive-source` writes the original to `95-Sources/<YYYY-MM>/`, records its SHA-256 over the source bytes alone, and links it from the note in both directions — a `source_archive` field plus one clickable line, with the archive's frontmatter pointing back. Retrieval skips `95-Sources/` by default and reaches it with `--scope` when the user asks what the source actually said, and the audit holds archives to no note contract: an archive is evidence, so its headings, tags, and placeholders belong to whoever wrote it. The Skill had no concept of this at all, so when a user asked for an article's original text the Agent invented a heading and appended 35 KB of it to a 7.6 KB digest — 82% of the file. A quarter of that note's search citations then landed in the author's prose rather than the reader's own knowledge, and BM25 length normalization cost the digest 20-30% of its score. After archiving, none of the same twelve queries cite archived text and the note's own sections rank the same or better. Verbatim is enforced rather than intended: line endings survive because the archive is read and written as bytes, and the frontmatter is excluded from the recorded hash, and a source that is not UTF-8 is refused with `undecodable-source-content` rather than transcoded — a guessed encoding is not evidence. Archive filenames are unique across the whole tree rather than within one month, because a note links its archive by bare stem and Obsidian resolves that vault-wide. `--replace` adds a second archive rather than substituting: `source_archive` stays a plain string for one and becomes a list for several, so the earlier archive is never orphaned from the note it supports.

- Retrieval can filter on the metadata the write Skill already enforces: `search-vault` gains `--type`, `--tag` (both repeatable, OR within a flag and AND across flags), and inclusive `--after` / `--before` on the note's frontmatter `date`, and every result now carries its `type` and `date`. Lexical ranking cannot answer a question about *when* or *what kind*, and CJK tokenisation splits `7月` into unrelated tokens — so on the reference Vault "7月的日报" ranked a note written in June above the July dailies, and "最近的周报" ranked a design document above the weeklies. The failure mode that mattered was not returning nothing, it was returning something wrong with no signal that it was wrong. Filters are hard constraints applied before ranking, so `score` keeps meaning what it meant. Relative time stays with the caller: the helper takes ISO calendar dates and refuses anything else with `invalid-date`, rather than shipping a bilingual date grammar plus a week-start policy into a helper whose value is being deterministic. `--tag` matches through the same normalization the audit uses, so `--tag springboot` finds `spring-boot`. A note's own `date` is held to the same standard as the flags — parsed as a real calendar date, not merely an ISO-shaped string, so a thirteenth month is not sorted as though it were a date. New refusals: `invalid-date`, `invalid-date-range`, `invalid-type`, `invalid-tag`.
- A filtered search reports what its filters did. The response gains `filters` with `applied`, `candidates`, `matched`, and `excluded` broken down per dimension, counting notes that have no `date` at all separately from notes whose date fell outside the range. Without it an over-narrow filter is indistinguishable from an empty Vault, and "nothing matched this filter" would be reported to the user as "you have no notes about this".

- The audit can tell a note nobody reads from a note nobody can find. `orphan-note` measures reachability, and it is correctly near-zero on a well-indexed Vault: the Folder Index plugin generates each folder's listing from its contents, so a folder index really does make every note in it reachable. That says nothing about whether the knowledge is connected. `disconnected-note` reports the notes that have no inbound *and* no outbound links — the intersection only, because either side alone is noisy and ambiguous, and a concept note cited from three places is supposed to link nowhere. Periodic logs are exempt outright: on the reference Vault `daily-report` and `weekly-report` are 36 of the 57 notes with no links at all, and reporting them would bury the 21 that actually went nowhere, 14 of them clippings that were captured and never connected to anything. Reachability is a precondition rather than an assumption: a note no index covers is an `orphan-note` instead, so the two findings never describe one note two different ways. A link into `95-Sources/` does not count either — an archive is the note's own captured evidence, so archiving a source cannot quietly clear the finding. It is `informational`, and the reference says plainly not to invent a link to clear it — an unrelated link is worse than none.

### Fixed

- The Agent invented a wikilink when it had no candidate. The deep-capture contract requires a web clip to carry a `## 关联笔记` heading while `note-creation.md` said links could be skipped — a required section cannot be skipped — and the same sentence promised the helper would list the target folder's filenames, handing over a raw directory listing as if it were a set of candidates. Four unrelated notes (Fluss storage, a SQL optimizer, RAG streaming, a Zig coding agent) all linked the same file, for no reason other than it sorting first in `20-Learning/Backend/`; `suggest-links` had recommended none of them, and for one it had explicitly returned no suggestions. Zero candidates is now an answer rather than a blank to fill, an explicit line records that nothing related was found, and proximity is named as a reason *not* to link: same folder, same type, and same broad subject are all disqualifying on their own.
- Retrieval ranked scaffolding as knowledge. `EXEMPT_NAMES` has always declared `README.md`, `AGENTS.md`, and `CLAUDE.md` to be governance files rather than notes, but only the write Skill knew it — and a Vault README is long and mentions every subject, which makes it a lexical magnet. Across twelve realistic questions on the reference Vault, 11 of 60 top-five slots (18%) went to non-knowledge files and `README.md` alone took one in half of them; asking for insights returned `README.md`, `AGENTS.md`, and `INDEX.md` in the top three while all 13 notes in `30-Insights` were pushed out. The judgement now has one definition that both Skills import, and the measured noise drops to 4 slots (7%) — the remainder being `INDEX.md`, which is navigational knowledge and belongs there. Excluded files are counted in `scanned.excluded` and never reported as `issues`: scaffolding is not a malformed note.

## [1.28.0] - 2026-08-06

### Added

- `vault-info` returns `tag_vocabulary`: the subject tags the Vault already uses, most-used first, with `distinct` reporting how many exist in total. Tag hygiene told the writer to reuse an existing tag and to avoid near-duplicates of tags *anywhere* in the Vault, but the only evidence it offered was the five most recent notes in one folder — a local sample answering a Vault-wide question. The rule was therefore self-defeating in the same way the `required_references` routing bug was: the right instruction applied to the wrong input. On the reference Vault the result is measurable — 170 notes carrying 169 distinct tags, 63% of them used exactly once — and it compounds, because every coined term makes the next sample less representative. Discovery already opened note heads for clustering and discarded the vocabulary; it now returns it. Type defaults are excluded by reading this Vault's own templates rather than a hardcoded list, so a Vault that renamed `person` to `people` is handled and a real subject like `java` is not thrown away.

### Fixed

- `required_references` asked about the wrong folder in the case it exists for. A crowded child folder does not make its parent look crowded, and the route to that child lives in the Vault's own governance — which `note-creation.md` had the Agent read *after* the discovery call, while also forbidding a second one. Capturing an article that governance routes to `20-Learning/AI-Agent` therefore asked discovery about `20-Learning`, got no `folder-routing.md`, and filed into the crowded folder the contract exists to catch. Governance now comes first: it costs one read, needs nothing from the helper, and lets the single discovery call be told which destination to answer about. A reroute after the fact is the one case that earns a second call.
- The Git pre-write gate now has to report something the user can act on. It stops on any change the invocation did not make — right for a Vault that several agents share — but "the worktree is dirty" left the user to go run `git status` themselves. It now reports every blocking path, whether each is untracked or modified, and the ways forward, and it states that clearing the gate by staging, stashing, discarding, or ignoring someone else's change is never one of them.
- The audit reported working links as broken. Obsidian resolves `[[alias]]` through the target note's frontmatter `aliases`, and `search_vault` has scored aliases all along, but the audit's link index knew only filenames — so an alias link produced a `broken-wikilink`, the highest severity it has, and the note it pointed at was additionally reported as an `orphan-note` because the inbound link was never counted. One missing feature, two false positives, in the finding category a reader is most likely to act on. Link resolution now consults declared aliases, and it builds that map only when a link fails to resolve by filename, so a Vault whose links all resolve keeps the per-note audit that runs on every write exactly as cheap as before.
- A dot in a note's title made every link to it look broken. The stem lookup was gated on the target "looking extensionless", but `Path("Qwen3.6-27B实战").suffix` is `.6-27B实战` as far as pathlib is concerned, so the gate closed on any title containing a dot and the audit reported a `defect` for a file that exists. On the reference Vault four of thirty-three `broken-wikilink` findings were this. A filename match still wins; the stem is simply tried whenever it misses.
- Frontmatter readers stopped at a fixed 4096 characters, so a note whose block ran longer parsed as having none: its tags vanished from crowded-folder clustering and its aliases from link resolution — silently, defeating the alias fix above for exactly the notes most likely to declare one. Both callers now share one reader that stops when the block closes, capped only to stay bounded on a file with no closing delimiter.
- The preflight cache bounded its entry count but not its size, and a note has no size limit, so sixty-four of them bounded nothing. Retention now also enforces a total byte budget, dropping oldest-first.
- A Windows-style `--folder 20-Learning\AI-Agent` matched no crowded folder, because those paths are POSIX — so the crowded-destination answer was silently dropped on the platform the project ships an installer for.
- Near-duplicate tag detection missed the case its own rule names. `yaml-standards.md` calls `frontend`, `front_end`, and `frontEnd` one tag, but normalization folded case and underscores only, leaving `frontend` and `front-end` in separate buckets — the separator is a spelling choice, not a distinction. The reference Vault had been carrying `spring-boot` (6 notes) and `springboot` (1) with the audit reporting nothing. Separators are now folded out entirely.
## [1.27.0] - 2026-08-04

### Added

- Apply can reference the content preflight already validated: `--preflight-json` stages the exact input under the `content.sha256` it reports (`content.reusable` says whether it did), and `create-note --from-preflight <sha256>` writes it without the document crossing the process boundary a second time. This is stricter than resending, not looser — resending proved nothing, while a reference is rerendered, rehashed, and bound to the Vault, note type, and title, so a mismatch refuses with `preflight-content-changed`, `preflight-vault-mismatch`, or `preflight-context-mismatch` instead of writing. Entries live outside the Vault (`~/.obsidian-kb-preflight`, overridable with `OBSIDIAN_KB_PREFLIGHT_CACHE`) and expire after 24 hours, so a dry run still leaves the Vault untouched.
- A heading at the wrong depth no longer costs a full resend. When every section the template requires is present but at the wrong ATX level, preflight returns `validation.suggested_fix` with the exact line edits, and `--from-preflight <sha256> --fix-heading-levels` applies them and reports the repaired hash. The repair is narrow on purpose: only the level moves, only for headings whose text already matches the contract, and only when the result satisfies it. A missing, renamed, or reordered section is content, and the tool will not guess at it.
- `vault-info` returns `required_references`: the complete set of reference files the selected type, template, and destination require. The conditional references were previously discovered one interruption at a time — read the workflow, start work, hit a crowded folder or a customized template, go back for another file — although discovery already held every fact those conditions test. Pass `--folder` when a governed route is more specific than the type default so the crowded-destination answer is about the folder that will actually be written to.

### Fixed

- The crowded-folder contract asked for something the tooling did not supply. `folder-routing.md` requires five notes forming a stable subject cluster before proposing a child category, and told the agent to judge from "the bounded filenames already returned by the index helper" — but the recommended `--compact` discovery strips exactly those filenames, and `crowded_folders` carried only a count. The rule was unenforceable at bounded cost, so the practical outcome was to keep piling notes into the crowded folder. Each crowded entry now reports `child_folders`, `clusters` (subject terms from tags and title tokens, with the notes carrying each, type-default tags excluded), and `cluster_min_notes`. An empty cluster list is a real answer: crowded, with nothing stable to split off.
- The error-code drift lock could only see about half the codes the helpers emit, and the documentation was written from what it could see. Its AST scan recognised dict literals, `code` assignments, and two hand-listed constructors; the two error classes nobody thought to add — `CaptureReceiptError` and `CategoryValidationError` — pass their code positionally, so 43 codes were invisible. The commit that introduced both the table and the lock states the helpers emit "24 refusal codes", a figure taken from the scanner's own output, so the blind spot became the reference's blind spot and was then locked in as if it were complete. Detection is now derived from the source: anything the helpers name a `code` parameter is a code, including classes added later. The refusal table went from 33 rows to 66, grouped into a capture-receipt handshake and a semantic gate so it stays readable, and every audit finding and retrieval refusal is enumerated too — 111 codes under contract.
- The path and frontmatter guards ship in both Skill bundles, so both Agents can receive their refusals, but the rows lived only in the write Skill's reference. A retrieval Agent that got `frontmatter-not-mapping` in its `issues` list had nothing it could open. The write reference stays the single source and stays complete on its own — it is the main capability — and `build.py` now fans the marked block out to `core/retrieval-references/shared-errors.md` instead of anyone maintaining a second copy. Three tests hold it there: the shared codes must appear in both places, the fanned-out file must equal what the builder produces, and `build.py --check` fails on drift.
- Retrieval-only refusals are documented where that Agent can read them. `core/references/` never ships in the retrieval bundle, so `unreadable-note` sat in a table its only audience cannot open; it moves to `search.md` alongside `invalid-query`, `invalid-top-k`, `invalid-scope`, and `invalid-vault`, and the lock now checks that file for those codes.
- Codes are now filed by how they reach the Agent rather than by which module holds them. The module heuristic filed `create-category`'s six post-apply findings as refusals, which would have demanded a "what to do next" row for something that is reported, not refused.
- `invalid-capture-receipt` is raised at 30 sites for 30 different shape violations, so its row says outright that the message is the contract and the code is not. Splitting it would change a published code and is deliberately left alone.
- Clustering reads note heads, which discovery never did before, so it runs under a whole-call budget: the selected destination is always analyzed, the most crowded folders fill the remainder, and the rest report their count with no `clusters` key. On a 5,000-note Vault with twenty crowded folders that holds one discovery call to roughly 200ms instead of 700ms, and an analyzed folder is always counted in full — the five-note rule is never applied to a sample.
- CJK title tokens are rejoined before they are reported, so a Chinese subject reads as `记忆压缩` rather than as the three overlapping bigrams it was tokenized into, which had crowded genuine clusters out of the list.
- The required-heading order check lived in the audit as inline logic. It is now one shared function, so the audit and the preflight repair cannot drift into different ideas of "in order".

## [1.26.4] - 2026-08-02

### Added

- Every audit finding now carries a severity, and `--min-severity` filters by it. `defect` means navigation, rendering, or tooling is already broken, or unfinished scaffolding shipped; `hygiene` is worth fixing when convenient; `informational` is often perfectly fine — a standalone note need not be linked, and two notes may legitimately share a similar title. Text output leads with the most severe and reports per-tier counts; JSON gains `severity` per finding and a `by_severity` summary. `--strict` is unchanged: it is the post-write safety gate and still fails on any finding.

### Fixed

- A structural contract no longer retroactively invalidates notes written before it shipped. The roadmap states that existing notes "do not become invalid merely because a later template adds sections", but the audit applied the current baseline to every note. On the reference Vault all 31 `missing-deep-capture-heading` findings came from notes predating the contract, and none from after it. Each contract now declares its effective date; a note whose date is missing or unparseable cannot claim the exemption, and template residue, missing metadata, and broken links are reported regardless of age.
- A fence marker inside an HTML comment no longer opens a block that is then reported as unclosed. Inside a fence, `<!--` remains literal.
- The reader-facing projection keeps comment literals that appear inside inline code, so `` `<!-- BEGIN block -->` `` can still anchor a capture receipt instead of being masked away.
- Copyable `SKILL.md` detection recognises pipeline forms. The pattern was anchored to the start of a line, so `printf ... | tee`, a PowerShell here-string piped to `Set-Content`, and `| Out-File` all wrote a `SKILL.md` whose frontmatter was never validated.
- Task Memory validates the resolved destination, not only the requested string. A symlink named `Tasks` filed operational notes outside the Tasks tree while still passing the shape rule.

## [1.26.3] - 2026-08-02

### Fixed

- A Resume Card field whose value is inline code is no longer reported as empty. Section extraction stripped fenced *and* inline code before the field pattern ran, so `` - **Key artifacts**: `src/app.py` `` produced a false `conversation-digest-missing-resume-field`. Fenced blocks and HTML comments are still removed; inline code is kept.
- Headings inside an HTML comment no longer count as visible structure. A document with its entire v2 layout commented out satisfied the heading baseline, because comments were removed only after heading matching. `HTML_COMMENT_RE` now lives in `template_contract` and is shared, rather than each module keeping its own idea of what a reader can see.
- The Digest template contract now checks the five Resume Card labels, not only the five headings. A template missing a label passed the template audit and then failed preflight on every note created from it, which presented as a defect in each note rather than in the template. Values may be blank; labels must exist. Note and template audits share one field matcher so they cannot drift apart again.

### Documentation

- Both READMEs name the Vault explicitly in the first-install examples (`--vault` / `-VaultPath`), and no longer claim the installer asks for it. A first run with no saved configuration exits with `No vault path configured`.
- The write state machine marks the Git precheck as a guarded step rather than an unconditional one, matching the contract in `core/references/git.md`.
- `feature-guide.md` separates Vault structure discovery (`vault-info`) from Vault-local governance reading, which the Agent performs itself and no helper returns.
- `retrieval.md` lists the directories the scanner actually skips — `node_modules`, `__pycache__`, `.venv` — instead of claiming "virtual environments" generally. Plain `venv/` and `env/` are not skipped.
- Six documentation contract tests cover the install commands, note-type slugs, responsibility boundaries, and the skip list, so these cannot drift silently again.

## [1.26.2] - 2026-08-02

### Fixed

- Filing an Inbox note no longer rewrites frontmatter it did not need to touch. The renderer re-serialised the whole mapping through `yaml.safe_dump`, silently discarding YAML comments and rewriting indentation and quoting; only the missing `date`, `type`, and `tags` entries are now inserted before the closing delimiter, leaving every other byte alone. An empty frontmatter block is filled in place rather than having a second block prepended.
- Inbox discovery no longer follows symlinks. `glob()` and `is_file()` both resolve them, so a link placed in the Inbox let a file outside the Vault be read and imported — the opposite of the containment this command states it enforces. Entries that are not regular files are reported as `unsafe-inbox-entry` and left in place, in both `--plan` and `--apply`.

### Documentation

- Closed the Inbox transaction effort with a decision record. Task 1 of 10 is accepted and Task 2 is implemented without review; Tasks 3–10 will not start. The data-loss paths it targeted are closed by other means, its own threat model excludes the adversary it would defend against, the Vault is version controlled, and Inbox processing is never unattended. The record states the four premises that would reopen it, and the branch is retained on the remote.

## [1.26.1] - 2026-08-01

### Fixed

- An index filename that cannot be encoded as UTF-8 now returns the documented `invalid-folder-index-config` refusal instead of escaping as an untyped `UnicodeEncodeError`. The length guard encoded the value inline, so an unpaired surrogate supplied by the Folder Index plugin's `data.json` crashed the helper rather than being refused. The fix was written in July alongside the paused Inbox transaction work and had never reached the main line.

### Added

- New codes must be `kebab-case` and use the bare `{"error": {...}}` envelope. `PATH_OUTSIDE_VAULT`, `PATH_NOT_FOUND`, `INVALID_VAULT_ROOT`, and `BACKUP_FAILED` predate the convention and are grandfathered unchanged; both envelopes expose the code at `error.code`, so renaming them would buy nothing. `tests/test_error_code_contract.py` fails on a new code that breaks the convention, and on a grandfathered code that is no longer emitted.

### Documentation

- Archived 31 SDD documents from the paused Inbox transaction effort under `docs/superpowers/sdd/`. `.superpowers/` is excluded by a machine-local rule, so every task report, review package, handoff, and the architecture blocker existed only in three working directories, in no commit and on no remote.

## [1.26.0] - 2026-08-01

### Changed

- Claude Code now receives `obsidian-knowledge-base` as a native Skill at `~/.claude/skills/obsidian-knowledge-base/`, matching Codex and WorkBuddy and matching how the retrieval Skill was already delivered on that platform. It was previously written as a marker block in `~/.claude/CLAUDE.md`, which loaded the full instruction set into every conversation and defeated the lazy-loading design that the small entry file exists for.
- Installing over an earlier release removes the legacy `~/.claude/CLAUDE.md` block so the instructions are not delivered from two places at once. Surrounding user content is preserved. Migration runs before installation, so a malformed marker aborts without installing anything and without modifying the file.

### Added

- `core/references/rules-and-errors.md` documents every structured code the helpers emit: 24 refusal codes with the action to take for each, and 35 audit findings grouped by category with their shared response. It also records that two payload envelopes and two naming styles are currently in use, and how to read `error.code` from either.
- `tests/test_error_code_contract.py` locks the reference against drift in both directions: a helper code with no documented entry fails, and a documented code no longer emitted fails. Extraction is AST-based, so codes reaching their payload through a constant or a conditional expression are not missed.

### Documentation

- Recorded the backup and recovery boundary as an accepted decision: Git is the recovery mechanism for notes, and the in-Vault backup tree deliberately serves only high-churn Task Memory. A rejected restore design and plan are retained as process evidence, marked as such.

## [1.25.1] - 2026-08-01

### Fixed

- Inbox processing is now fail-closed on a frontmatter block it cannot parse. Such a note previously had its original keys replaced by inferred defaults before the source file was deleted, destroying user content with no backup, no warning, and a success exit code. Invalid YAML, an unclosed block, and a non-mapping block are all refused as `unreadable-frontmatter` and left byte-for-byte in place; a note with no frontmatter at all is unaffected and still filled normally.
- A failed source removal during `--apply` now rolls back the already-written destination copy, so a note can no longer exist in two places with divergent frontmatter. When the rollback itself cannot run, the warning is reported instead of being swallowed.

### Changed

- `process_inbox --apply` reports how many notes actually committed rather than how many were examined, and names the notes left in place. Refusals are printed to stderr in both `--plan` and `--apply`.
- The `--json` plan gains `skip_code`, `frontmatter_issue` (code, message, line, column), and `applied` fields. A refused note reports `target: null`.

Inbox processing remains non-transactional; destination write, source removal, and index append are still separate steps. This release closes one data-loss path, not the broader transaction gap.

## [1.25.0] - 2026-07-31

### Added

- Added a lazy, tool-neutral web acquisition contract that checks target and extraction quality, tries materially different safe access paths after an inadequate first result, inspects material body media, and keeps terminal failures at zero Vault writes.
- Added reusable cross-Agent fixtures for public fallback, private-URL protection, material images, numerical source self-reports, verified escalation, and terminal failure.

### Changed

- Ordinary finished Web Clips now default to `capture_depth: standard`; explicit or evidence-sensitive research uses `capture_depth: verified` and retains the content-bound capture receipt.
- Web Clip templates and helper fallback metadata share one section structure and persist capture depth without reclassifying historical notes.
- Numerical empirical claims without inspectable measurement support are kept as locally qualified `source-self-report` claims rather than facts or generic author opinion.

### Fixed

- A failed first webpage access path no longer authorizes an incomplete placeholder note; safe fallback and acquisition self-check must establish adequate material coverage before preflight.
- Capture receipts are rejected unless the candidate is a verified Web Clip outside Inbox, preventing receipt evidence and persisted depth from disagreeing.

## [1.24.0] - 2026-07-29

### Added

- Added the lazy `conversation-harvest` workflow to evaluate conversation-derived problems, reusable knowledge, reflection, and design with `verified`, `inferred`, `open`, and `skip` evidence states before any write.
- Added a dedicated guide for choosing between immutable conversation digests, mutable Task Memory, and durable knowledge promotion.

### Changed

- Redesigned `conversation-digest` as a versioned layered context-recovery artifact: a bounded 30-second Resume Card leads into scope, rationale, evidence, and next actions without imposing a whole-note word limit.
- Conversation harvest remains an analysis and routing workflow rather than a new note type; one clear durable candidate may use the existing single-note path, while multiple independent candidates require selection.

### Fixed

- Synchronized the Digest reference, Chinese and English templates, creation fallback metadata, documentation slug, and generated payloads.
- Vault and candidate-note audits now report outdated Digest templates, incomplete v2 heading structures, missing Resume Card fields, and overlong Resume Cards.

## [1.23.0] - 2026-07-29

### Added

- Added the independent `obsidian-knowledge-retrieval` Skill for read-only Vault search and source-grounded answers, while keeping all write authority in `obsidian-knowledge-base`.
- Added deterministic in-memory lexical ranking across titles, aliases, tags, headings, visible wikilinks, and body text, with CJK bigrams, bounded snippets, line numbers, and explainable match signals.
- Added native retrieval Skill installation for Codex, QoderWork, WorkBuddy, Claude Code, and Cursor, including isolated helper payloads, manifests, diagnostics, and hostile-working-directory verification.
- Added a versioned design and backlog covering graph-aware retrieval, typed relation candidates, query expansion, and optional disabled-by-default local embedding providers.

### Security

- Retrieval excludes hidden/tool directories, templates, attachments, symlinked files and directories, and HTML comments; malformed or unreadable notes are isolated as bounded issues.
- Retrieval performs no network calls, persistent indexing, caching, or Vault mutation, and the shipped retrieval payload contains no write helper.
- Documentation now distinguishes local helper execution from cloud-model privacy: an Agent may send returned snippets to its model provider.

## [1.22.1] - 2026-07-28

### Changed

- Finished source-backed articles explicitly use `web-clip` unless Vault governance selects a more specific source-backed template, preventing `learning-note` from bypassing the semantic receipt contract.
- Resource-survey notes expose one explicit reader-facing inventory whose names and canonical URLs must exactly match the receipt; compatibility and limitation evidence then bind to every concrete resource instead of satisfying the profile with one global set.
- Explicit Task Memory creation may initialize only a normalized lowercase `Tasks/<slug>/TASK.md` operational note; ordinary note types still cannot create missing directories.

### Fixed

- Capture-receipt routing now uses the canonical resolved destination, so traversal spellings and in-Vault symlink aliases cannot inherit the Inbox exemption after resolving outside Inbox.
- Material, numerical, inference, and practical anchors must occur in reader-facing body content rather than YAML frontmatter or hidden HTML comments.
- Inference labels must occur inside their exact reader-facing excerpt.
- Copyable `SKILL.md` validation recognizes heredoc-first `cat <<EOF > path/SKILL.md` commands.
- Measurement provenance detects English months and years, B/thousand/million/billion counts, and Chinese 万/亿 counts even when adjacent to Chinese prose.
- Instructional-comment auditing matches the shipped English Web Clip comments and correctly ignores tilde or variable-length fenced examples.
- Material rewrites of existing source-backed articles retain the v1.22 deep-capture and standalone receipt route.

## [1.22.0] - 2026-07-28

### Added

- Finished web clips outside Inbox now require a structured semantic capture receipt bound to the exact rendered content SHA-256, and apply must repeat the exact receipt identity accepted by preflight.
- Capture receipts expose selected profiles, complete source access, material coverage, numerical-claim provenance and measurement context, labeled inferences, a profile-appropriate practical artifact, and unresolved items.
- The read-only `capture-receipt` helper applies the same validation to complete in-Vault candidates before a material rewrite.
- Detailed receipts may use a bounded non-symlink UTF-8 JSON file instead of inline JSON, avoiding Windows command-length and shell-quoting limits without writing evidence into the Vault.
- Compact Vault discovery now reports a bounded, deterministic `crowded_folders` list for managed categories with at least 20 direct notes.
- A lazy `folder-routing.md` contract reuses suitable child categories or proposes a stable subject child only when at least five notes form a real cluster.

### Changed

- `create-note` no longer creates a missing destination directory; new categories must pass the existing user-confirmed `create-category` preflight and apply flow.
- Deep-capture completion reports now include receipt identity and unresolved-item count separately from the mechanical audit.
- Quick or unread web clips in `00-Inbox` and ordinary note types retain the receipt-free fast path.

### Fixed

- Measurement-shaped values such as percentages, ratios, durations, before/after results, abbreviated large counts, and star counts can no longer be silently omitted from deep-capture provenance evidence.
- Resource-survey receipts now require explicit compatibility and limitation evidence, and copyable shell examples that create `SKILL.md` reject malformed YAML frontmatter.
- Crowded-folder discovery excludes hidden files, folder indexes, nested notes, and directory symlinks instead of inflating direct-note counts or escaping the Vault.

## [1.21.0] - 2026-07-28

### Added

- Finished source-backed captures now load a dedicated semantic contract with intent routing, source-access hard stops, materiality rules, and separate profiles for tutorials, resource surveys, conceptual analysis, and evidence reports.
- Deep capture requires a temporary source inventory and coverage ledger before preflight, rejects unresolved material omissions and unsupported claims, and permits labeled first-party enrichment when the primary article is too shallow.
- The Vault auditor reports leaked instructional template comments in rendered notes while allowing ordinary HTML comments, template files, and fenced examples.
- Four bounded synthetic evaluation fixtures preserve profile-specific versions, links, commands, causal boundaries, measurements, limitations, and tempting unsupported inventions for repeatable contract walkthroughs.

### Changed

- Article-only quality instructions moved from the ordinary create path into lazy-loaded `deep-capture.md`, so meetings, daily notes, projects, quick Inbox bookmarks, and other non-article captures no longer load the semantic article contract.
- Completion reports must distinguish selected capture profile, source coverage, semantic acceptance, and deterministic mechanical audit; `0 findings` alone is no longer a semantic success claim.
- Historical notes remain explicitly unreviewed until a bounded semantic migration or material rewrite instead of being treated as upgraded by a new template or structural audit.

## [1.20.1] - 2026-07-27

### Fixed

- Full-vault audits now apply a versioned v1.20 Chinese or English deep-capture heading baseline to every historical web clip, even when an upgraded Vault preserves an older or customized shallow template.
- Full-vault audits report an outdated `Templates/Web Clip.md` separately, while per-note creation audits continue to honor the active Vault template contract.
- Required web-clip metadata rejects normalized compound placeholders such as `TODO: verify`, `unknown author`, and `待补充作者` without rejecting meaningful values that merely contain the same substrings.

## [1.20.0] - 2026-07-27

### Added

- Deep article capture now requires standalone coverage of the source problem and boundaries, core knowledge and causal reasoning, reproducible steps or examples, verification and risks, and clearly distinguished insights.
- Web-clip creation and full-vault audits reject placeholder metadata such as `unknown`, `N/A`, `TODO`, and `待补充` instead of treating it as complete attribution.
- Historical web clips are audited against the complete deep-article section contract, exposing articles that still depend on their original links for essential details.

### Changed

- Saved articles default to durable knowledge notes with no artificial token, length, or bullet-count limit; unread or incomplete sources route to Inbox instead.
- Chinese and English web-clip templates now provide dedicated sections for source conclusions, applicability, principles, concrete implementation, validation and limitations, insights, and real related notes.
- Source access failures stop deep capture rather than silently producing a concept-only summary.

## [1.19.1] - 2026-07-16

### Fixed

- Template heading discovery and required-heading audits ignore YAML frontmatter and fenced code examples, preventing internal comments or example headings from becoming note sections.
- Opted-in `task-memory` captures omit selected-template discovery because that note type intentionally has no conventional Vault template.

## [1.19.0] - 2026-07-16

### Added

- `vault-info --type <slug>` adds one selected conventional template's path and ordered level-two headings to discovery output without returning template prose or frontmatter.
- Focused contracts cover selected template shape, unsupported types, missing templates, and conditional reference loading across source, generated Skill, wheel, and installed-runtime surfaces.

### Changed

- Ordinary creation performs one type-aware compact discovery call and receives the required standard heading shape before drafting, while preflight remains the fallback when type is initially unclear.
- Missing-category and customized-template details moved into separate conditional references, reducing the ordinary `o200k_base` instruction surface from 2,716 to 2,296 tokens.

### Fixed

- Standard template headings no longer appear only after a failed preflight; the lightweight discovery result exposes them early without increasing template maintenance or leaking author instructions.

## [1.18.0] - 2026-07-16

### Added

- Compact Vault discovery reports only the note types whose conventional templates differ from the shipped Chinese or English starters.
- `template-contract` returns one selected custom template's frontmatter, body, supported placeholders, and normalized SHA-256 without loading unrelated templates into model context.
- `create-note --expect-template-sha256` rejects stale custom-template interpretations before note or index mutation.

### Changed

- Natural-language instructions beneath custom-template headings now govern note generation; headings, lists, tables, labels, and examples are preserved as quality scaffolds while instruction prose is executed rather than copied.
- Unchanged templates retain the ordinary capture path with no template-contract call or template-body tokens.

### Fixed

- Template customization detection treats BOM, CRLF/CR, and final-newline differences as transport-only changes and remains portable across Windows and POSIX runners.

## [1.17.0] - 2026-07-15

### Added

- `vault-info --compact` provides compact vault discovery by omitting per-folder note filename arrays while preserving the default JSON contract and all index-ownership fields.

### Changed

- Ordinary capture uses compact vault discovery and completes governance-required Git preflight before fetching or deeply reading source content, avoiding source-analysis cost when Git must stop the write.

### Fixed

- Template validation now returns complete template heading diagnostics in one finding, including expected headings, actual headings, and the first mismatch, so all ordering problems can be repaired in one preflight cycle.

## [1.16.0] - 2026-07-15

### Added

- `create-category` preflights and initializes one user-confirmed category below an existing governed parent, including native/custom Folder Index, Dataview, or static index setup.
- Category apply requires the explicit `--confirmed` gate, creates the directory and index exclusively, cleans up only a newly created empty directory on write failure, and audits the resulting category structure.

### Changed

- Missing-category capture now asks the user to confirm or rename the proposed path and records optional `AGENTS.md` route persistence as a separate choice; declining persistence produces a one-off category without waiving Vault-required README maintenance.
- Existing governed categories keep the ordinary `vault-info` → `create-note` path with no extra prompt, helper call, or classification-model cost.

### Fixed

- Folders excluded from the globally enabled Folder Index plugin now retain static index detection and updates, so the first note in an excluded new category is indexed correctly.

## [1.15.1] - 2026-07-15

### Fixed

- Malformed input frontmatter now exits before mutation with a stable `invalid-frontmatter` error, the input source, and full-Markdown line and column coordinates instead of silently falling back to empty metadata.
- `suggest-links` no longer awards title-overlap points for generic Chinese and English article terms such as `详解`, `指南`, `guide`, and `tutorial`.

## [1.15.0] - 2026-07-15

### Changed

- `suggest-links` now recognizes CJK title overlap, weights specific tags above corpus-common and structural tags, treats matching note type as supporting evidence, and suppresses candidates below a confidence threshold.
- Sibling folders enter the bounded candidate scope only when their names overlap the target title or tags; root notes retain root-note candidates.
- Candidate content is read once per suggestion run while preserving the read-only CLI and JSON contracts.

## [1.14.1] - 2026-07-15

### Changed

- Ordinary note creation now loads only `note-creation.md`, uses the single `vault-info` discovery result, delegates template and index handling to `create-note`, trusts a clean compact apply audit, and forbids secondary memory/log writes without separate explicit intent.
- `note-creation.md` was reduced from 209 to 150 lines while preserving Vault governance, structured preflight, exclusive apply, automatic audit, template merging, and bounded link suggestions.

## [1.14.0] - 2026-07-14

### Added

- `create-note --preflight-json` returns final merged frontmatter, destination, rendered-content SHA-256/size, and shared note-level validation without echoing the Markdown body or mutating the Vault.

### Changed

- The recommended create workflow now uses structured preflight followed by `--apply --compact-json`; complete `--json` preview and legacy apply contracts remain available and unchanged.
- Pre-write and post-write checks share one in-memory note audit implementation, including Vault-template heading-order validation.

### Fixed

- Relative `--content-file` input is read from the canonical in-Vault path that passed validation rather than from an unrelated current working directory.
- Note creation uses exclusive file creation with suffix retries, so concurrent same-title writers cannot overwrite one another.
- Invalid Vault failures are structured in create-note JSON modes, and template-backed notes no longer emit a false frontmatter-only warning.

## [1.13.0] - 2026-07-14

### Added

- `create-note --apply --compact-json` returns structured path, audit, and link-suggestion data without echoing the complete rendered Markdown body.

### Changed

- The note-creation workflow now recommends full `--json` for dry-run preview and compact JSON for the real apply step, while preserving the legacy apply JSON contract for existing consumers.

## [1.12.1] - 2026-07-13

### Changed

- `create-note` now treats stdin and content files as complete Markdown inputs, documents input-frontmatter precedence, and rejects incomplete `web-clip` metadata before any note or index mutation.

### Fixed

- Unquoted YAML date/datetime metadata is normalized to ISO strings, so a valid `published: 2026-07-13` value no longer triggers `web-clip-missing-published`.
- All helper CLIs now force UTF-8 stdin as well as stdout/stderr, the installed launcher explicitly byte-bridges `create-note --stdin`, and frontmatter accepts BOM/CRLF transport details, preventing piped Chinese text and emoji from being lost or rejected under legacy Windows code pages.
- Installed helper launchers now use Python safe-path mode so an unrelated `obsidian_kb_skill` package in the current working directory cannot shadow the installed payload.

## [1.12.0] - 2026-07-11

### Added

- **Formal WorkBuddy distribution**: Bash and PowerShell install the complete standard Skill at `~/.workbuddy/skills/obsidian-knowledge-base`, include WorkBuddy in the default platform set, refresh the owned directory exactly on upgrade, and remove only that Skill on uninstall.
- **Deterministic installed payload manifest**: `build.py` generates a sorted SHA-256 `manifest.json` covering every installable regular file, including optional OpenAI metadata, while excluding only the build header, manifest itself, and housekeeping files.
- **Read-only installation doctor**: `run_helper.py doctor [--json]` checks manifest schema and hashes, unexpected files, Python 3.11+ runtime selection, PyYAML/helper imports, and required resources without writing, repairing, downloading, or deleting.

### Changed

- The Skill launcher forwards arguments after the helper token verbatim, so all nine helpers receive direct `--help`; one historical `--` separator remains compatible.
- Doctor runs with the launcher's interpreter even when the selected runtime record is invalid, while normal helpers continue to require the installer-selected runtime.
- `create-note` documents and tests the metadata precedence `type defaults < Vault template < stdin/content-file frontmatter < explicit CLI fields`, with a dry-run `source`/`related` example and an explicit Vault-only content-file boundary.
- Installed-product tests delete a disposable release tree and then run WorkBuddy doctor and core helpers from a neutral directory. Windows smoke coverage mirrors payload hashes, upgrade, symlink migration when available, sibling preservation, and uninstall.

### Fixed

- Replacing a WorkBuddy directory symlink removes only its entry and leaves the old clone target byte-for-byte untouched. PowerShell handles reparse points with non-recursive .NET deletion.
- Installed helper environments no longer inherit an external `PYTHONPATH`, preventing a partial installation from silently borrowing modules from a source checkout.
- Malformed manifests, escaping manifest paths, symlink payload files, invalid Python version output, and missing dependencies now produce stable unhealthy diagnostics instead of crashes or false health.

## [1.11.1] - 2026-07-10

### Added

- **Bounded per-note backup retention**: `update-note` keeps one write-before backup per relative note path by default. Users can set `backup.keep_per_note` from 1 through 1000 in the global `~/.obsidian-kb-settings.json` file.
- **Installed-product retention proof**: source, standard Skill, disposable installer, and wheel tests run the updater from neutral directories and verify the configured retained count without borrowing repository modules.

### Changed

- Backup cleanup runs inside the helper only after a successful note write. Agents never enumerate or delete backups, so cleanup costs no model tokens and cannot create an AI-driven deletion loop.
- Bash and PowerShell create global settings only when absent, preserve user edits during upgrade and default uninstall, and remove them only with explicit config purge.

### Fixed

- Invalid or unreadable settings now fail closed: the note write may succeed, but backup deletion is disabled and the new backup remains.
- Retention scans only real timestamp directories and regular in-Vault files. Symlinks, unknown layouts, and unverifiable paths are retained; the just-created backup is protected even if filesystem clocks move backward.
- New-target validation now rejects a dangling symlink in the final path component instead of treating it as absent and potentially writing through it outside the Vault.
- Cleanup failures are warnings after a committed write rather than command failures that could cause an agent to retry. This release does not claim to eliminate concurrent filesystem replacement (TOCTOU), which remains future atomic-write/directory-handle work.

## [1.11.0] - 2026-07-10

### Added

- **Complete standard Skill payload**: `skills/obsidian-knowledge-base/` now ships `SKILL.md`, Codex UI metadata, lazy references, executable helpers, and Chinese/English template assets as one installable unit.
- **Skill-local helper launcher**: `scripts/run_helper.py` dispatches all eight helpers from the installed payload and works from a neutral directory without importing the source checkout.
- **Private installer runtime**: Bash and PowerShell select Python 3.11+, record the interpreter under `~/.obsidian-kb-skill/runtime.json`, and install a missing PyYAML only under the product-owned `vendor/` directory.
- **Behavioral Windows gate**: GitHub Actions now executes a disposable PowerShell install/upgrade/uninstall scenario on `windows-latest`, including post-source-removal helper execution.
- **Machine-readable scaffolding**: `scaffold-templates --json` completes the JSON contract across all eight helpers.

### Changed

- Bash and PowerShell install the same complete payload for Codex/QoderWork and a canonical compatibility payload at `~/.obsidian-kb-skill/skill/` for Claude Code and Cursor.
- Install and upgrade refresh product-owned Skill files exactly, restore newly added or missing resources, remove stale owned files, and continue preserving user-edited Vault templates unless force is explicit.
- Uninstall preserves `~/.obsidian-kb-config` by default; `--purge-config` / `-PurgeConfig` removes it explicitly.
- `build.py --check` now detects missing, changed, and extra files across platform references, wheel resources, standard Skill assets, and bundled helper code.
- Wheel packaging is self-contained under `obsidian_kb_skill`, exposes all eight console scripts, and resolves templates/references through packaged resources outside the checkout.

### Fixed

- Every CLI now validates a canonical Vault boundary and rejects traversal, absolute escapes, prefix-confusion paths, and static symlink escapes. Valid symlink Vault roots resolve to their canonical directory; broken links, loops, and links to files are rejected.
- `update-note` now creates a byte-for-byte, non-overwriting backup under `.obsidian-kb-backups/<timestamp>/...` before every in-place update and aborts the write when backup creation fails.
- Marker-managed shared files now fail closed on lone, reversed, or duplicate markers instead of risking truncation or silent cleanup.
- New relative Vault paths are canonicalized before being persisted, unknown platform names fail before Vault mutation, and PowerShell now includes the Digest template.
- Corrected the `detect_index.py` shebang and removed documentation commands that referenced the deleted top-level `scripts/` package.
- Template-driven note creation now replaces the template's first H1 with the requested note title; different filenames no longer retain the same placeholder heading and trigger false `duplicate-title` findings.
- The gatekeeper now states that `update-note` is Task-Memory-only; ordinary project/person/daily edits follow the generic update reference with native file tools instead of being sent to an incompatible CLI.
- Wheel metadata now uses an SPDX license string and explicit namespace-package discovery, eliminating setuptools deprecation and package-data ambiguity warnings.
- Windows now delegates native drive and UNC containment to `Path.resolve()` + `relative_to()`, so an absolute path inside the Vault is accepted while different-volume escapes remain rejected.
- All eight helper CLIs force UTF-8 stdout/stderr, preventing non-ASCII JSON and human output from failing on legacy Windows console code pages.
- Wheel tests now use the declared, locked `build` development dependency and platform-native virtualenv script paths instead of a machine-local `/tmp/bldenv` assumption.

## [1.10.0] - 2026-07-09

### Added

- **`scripts/detect_index.py` (P1)** — single entry point for per-folder index-strategy detection; replaces three copies of the same prose in `note-creation.md` and the detection in `process_inbox`. Reuses `audit_vault._folder_index_config` as the single source of truth. Emits JSON: `mode` / `index_file` / `can_append` / `graph_compatible` / `notes`. (`obsidian-detect-index` console script.)
- **`scripts/vault_info.py` (P2)** — one-shot read-only cold-start context: vault path + validity, template list, every standard folder's existence and index strategy. Lets an agent seed context in a single JSON call instead of probing by hand. Reuses `detect_index.detect` and `audit_vault._folder_index_config`. (`obsidian-vault-info` console script.)
- **Automatic post-write audit in `create_note.py` / `update_note.py` (P3)** — `audit_note()` runs the per-note audit after `--apply` (pass `--no-audit` to skip). `AUDIT:` output lists broken wikilinks, missing frontmatter, unresolved placeholders, etc. Replaces Step 9's manual re-read. Also fixed a real bug it exposed: `REQUIRED_TYPES` omitted `task-memory`, so every task-memory note was falsely flagged `invalid-type`.
- **`--suggest-links` on `create_note.py` / `update_note.py` (P4)** — after writing, prints link suggestions reusing `suggest_links.suggest_links` (single source, no duplicated scoring). Aligns create/update with the suggest_links capability.
- **`scripts/scaffold_templates.py` (P5r)** — one-time bootstrap of `Templates/` from the shipped starters in `core/templates/`. Refuses to overwrite user-edited templates unless `--force` is passed. Not a single source of truth — the vault template is.
- **`--json` machine-readable output on every CLI script (P6)** — `audit_vault`, `process_inbox`, `suggest_links`, `create_note`, `update_note`, `detect_index`, `vault_info`. Consistent schema, tested end-to-end (10 tests). Agents can drive every script without parsing human text.

### Changed

- **`core/references/note-creation.md` is now 156 lines (was 253, -38%).** Cut the 6-step wikilink procedure, Step 9's manual checklist, and Step 7's feature restatement — all of which are now done by the bundled scripts. Every governance contract phrase the test suite guards is still present.
- **`create_note.py` reads the vault template, not a hardcoded spec.** `build_note()` loads `{VAULT}/Templates/<Name>.md`, fills `{{date}}` placeholders, merges the template's frontmatter, and uses its body. If the user adds a field or a section to their template, every new note picks it up — no code change needed. `EXTRA_FIELDS` is now a safety net for the no-template case, not the single source.

### Fixed

- `REQUIRED_TYPES` in `audit_vault.py` now includes `task-memory` (was missing; surfaced by P3's automatic audit).
- Index-strategy detection was duplicated three places (note-creation prose, audit_vault's reader, process_inbox's reader); now lives in `scripts/detect_index.py` with `audit_vault._folder_index_config` as the single source.

## [1.9.1] - 2026-07-09

### Changed

- **Always-loaded gate shrunk below ~400 tokens (was ~400–800).** The gatekeeper in `core/OBSIDIAN_KB.md` is now ~14 lines: a one-line Overview, a prominent `## DO NOT auto-save`, and a 5-step "when the user asks to save" pointer. The four platform trigger headers (SKILL/CLAUDE/AGENTS/mdc) were de-duplicated and tightened — same "explicit save intent only" signal, far fewer example phrases. Loading the skill now costs roughly half the previous tokens, and the first rule an agent sees is still "do not auto-save".
- **Memory quality guarantee (no factual drift, no loss).** Borrowed from high-star memory systems (Mem0 / MemGPT-Letta / Zep):
  - `conversation-digest.md` and `task-memory.md` now carry an explicit **Quality guarantee** block: capture only *grounded* facts (drop anything you can't trace to the conversation), store *atomic* decisions (not narrative — that is where drift crept in before), require non-empty `decisions`, and run a `audit_vault.py` **self-check** after writing.
  - **Conflict resolution (Mem0-style):** `update_note.py` gains `--replace-decision "OLD::NEW"` — when new info contradicts an old decision it *replaces* it instead of appending a contradictory second line; appends as new if no match (upsert, never silently drops a correction).
  - **Core vs Archival (MemGPT-style):** on handoff the incoming agent reads only the `TASK.md` **frontmatter** (core memory, tiny); the `## Log` + body prose are archival, read on demand. Provenance: every Log line is `ISO-date [agent] what` (Zep-style) so a contradiction can be traced to when it was established.

### Added

- `obsidian-update-note --replace-decision "OLD::NEW"` for conflict-resolution handoffs.

## [1.9.0] - 2026-07-09

### Added

- **Task Memory Workflow (multi-agent handoff memory)**: a new workflow in `core/OBSIDIAN_KB.md` for carrying one long task's state across agent handoffs. A single agent-agnostic `Tasks/<slug>/TASK.md` note holds `status` / `step` / `decisions` / `constraints` / `artifacts` / `open` / `agents` plus a bounded `## Log` trail. The outgoing agent updates it before yielding; the incoming agent reads it first. **Off by default** — activated per task via the `task-memory: enabled` field, with an optional global master switch `OBSIDIAN_KB_TASK_MEMORY=on|off` (default `off`). Saying "开启任务记忆 / handoff" opts in; "关闭" opts out.
- **Note updater helper (`update_note.py`)**: the constraint-based counterpart to `create_note.py` for handoffs. It edits only structured frontmatter fields and appends a timestamped line to `## Log` (capped to the last 30 entries, TTL-style) — it never clobbers prose. Upserts: if the task note is missing it is initialized from the template, so one command both starts and updates a task. Read-only by default; `--apply` to write. Installed as the `obsidian-update-note` console script.
- **`task-memory` note type** added to `create_note.py` / `process_inbox.py` (routed to `Tasks/`, with the task-memory frontmatter defaults).

### Changed

- **Task Memory spec is now lazy-loaded.** The full Task Memory Workflow (TASK.md structure, handoff protocol, `obsidian-update-note` usage) moved out of the always-loaded `core/OBSIDIAN_KB.md` body into `core/references/task-memory.md`. The body keeps only a ~5-line pointer whose heading itself states "OFF by default", so an agent learns the feature is off after one line and never pays to load the spec unless the user enables it. `build.py` ships the reference next to every generated artifact; `--check` verifies it stays in sync.
- **Skill body slimmed to a tiny gatekeeper.** `core/OBSIDIAN_KB.md` no longer inlines any heavy workflow. Every workflow (note creation, update, conversation digest, task memory, YAML standards, rules/errors, Git) lives in `core/references/*.md`, read by an agent **only when it is about to save**. The always-loaded body is ~37 lines: an Overview, a prominent **"DO NOT auto-save"** rule stating the skill never writes without explicit user intent, a 5-step "when the user asks to save" gate that points to the right reference, and bounded-scan limits. Loading the skill now costs almost no tokens, and the first real rule an agent sees is "do not auto-save". `build.py` ships `core/references/*` next to each generated artifact; `--check` verifies.

## [1.8.1] - 2026-07-09

### Added

- **Note creator helper (`create_note.py`)**: a constraint-based note creator for environments without a native file-write tool. It builds the type's required frontmatter, picks the routed folder, writes with a safe numeric suffix (never overwrites), and updates a static `INDEX.md` when applicable. Read-only by default (dry run) — pass `--apply` to write. Body comes from `--content-file` or `--stdin`; frontmatter already present in the body is merged with explicit CLI values winning. Installed as the `obsidian-create-note` console script.
- **Step 7 "tool choice" rule** in `core/OBSIDIAN_KB.md`: agents prefer their native file-write tool; when none exists they must call `scripts/create_note.py` instead of inventing a one-off script. Important Rules gains rule 13 to the same effect.

### Fixed

- **Auditor skips top-level hidden dirs too**: `_is_ignored` now checks every path segment (it previously skipped only nested hidden dirs), so a root-level hidden folder such as `.uploads` no longer triggers a false `missing-folder-index` finding.

### Changed

- **Version header corrected**: `core/OBSIDIAN_KB.md` stated a stale `1.7.0`; it now reads `1.8.1` to match the actual release line.
- **Conversation Digest redesigned for agent reuse**: the digest is now decision-dense, link-rich, and short rather than a narrative essay. Frontmatter carries a structured `decisions` list (primary field a future agent scans) plus optional `open`; the body is capped at ~250 words (TL;DR + Decisions + Open bullets) with no background/revised-ideas prose. Depth lives in linked durable notes, not the digest. The auto session-wrap-up trigger remains removed (context design still pending).

### Documentation

- README and README_EN document the new `create-note` command (console form and `scripts/create_note.py` usage), and the script count is updated to four.

## [1.8.0] - 2026-07-09

### Added

- **Vault auditor expansion (Phase A)**: `scripts/audit_vault.py` now also flags unresolved template placeholders (`unresolved-template-placeholder`), validates the `related` field format and duplicate entries (`invalid-related*`, `duplicate-related-entry`), requires non-empty Web Clip fields (`web-clip-missing-source` / `-author` / `-published`), flags empty template notes (`empty-template-note`), suggests merging near-duplicate tags (`near-duplicate-tags`), detects duplicate and fuzzy-similar note titles (`duplicate-title`, `similar-title`), and detects orphan notes via a reverse-reference index (`orphan-note`).
- **Conversation Digest template and workflow (Phase D)**: New `conversation-digest` note type with `Templates/Digest Note.md` (zh-CN + en) and a dedicated "Conversation Digest Workflow" in `core/OBSIDIAN_KB.md` for distilling chat summaries into the vault.
- **Inbox Processor (Phase B)**: New read-only-by-default `scripts/process_inbox.py` proposes (`--plan`) or applies (`--apply`) filing of quick-capture notes from `00-Inbox`, filling `date` / `type` / `tags` and appending to the destination folder's static INDEX (Folder Index and Dataview listings are never touched).
- **Link Suggestor (Phase C)**: New read-only `scripts/suggest_links.py` scans a bounded scope around a note and scores candidate wikilink targets by shared tags, matching type, and title-token overlap.
- **Console-script entry points**: `obsidian-audit-vault`, `obsidian-process-inbox`, and `obsidian-suggest-links` are installed via `[project.scripts]`, backed by `scripts.audit_vault:main`, `scripts.process_inbox:main`, and `scripts.suggest_links:main`.

### Changed

- **Python environment standardization**: Python 3.14.6 is the pinned development interpreter; Python 3.11 is now the minimum supported version.
- **Reproducible development**: Added `.python-version`, `uv.lock`, locked uv commands, and an upgraded-pip venv fallback.
- **Test entry consistency**: pytest adds the repository root explicitly, so both `pytest` and `python -m pytest` resolve local modules.
- **CI matrix**: GitHub Actions now verifies the locked environment on Python 3.11 and 3.14.
- **Packaging**: `scripts/` is now an installable package (`packages = ["scripts"]`), reversing the deliberate "disable discovery" choice from 1.6.0 so the console-script entry points resolve correctly.

### Fixed

- **Auditor no longer flags agent/tool metadata**: `_is_ignored` now skips any hidden directory (dotfile convention), so `audit_vault` won't falsely report agent working memory or AI-tool metadata folders (`.workbuddy`, `.claude`, `.cursor`, `.codebuddy`, ...) as missing frontmatter. `.workbuddy` is also listed explicitly in `IGNORED_PARTS` for visibility.

### Documentation

- README and README_EN document the auditor's skipped directories and the advisory `similar-title` threshold (0.85 in `scripts/audit_vault.py`), so the tunable knob isn't lost.

## [1.7.0] - 2026-07-08

### Added

- **Standard Agent Skill entry**: `skills/obsidian-knowledge-base/SKILL.md` is now the platform-independent, generated Skill artifact.
- **Codex user-level installation**: Codex installs to `~/.agents/skills/obsidian-knowledge-base/`, matching the user Skill discovery convention.
- **Installer coverage**: Bash smoke tests cover canonical Codex/QoderWork installation, idempotency, and sibling-safe uninstall.

### Changed

- **Explicit build targets**: `build.py` now uses explicit header and output paths and validates five generated artifacts.
- **QoderWork source**: QoderWork installation copies the standard Skill instead of the QoderWork compatibility artifact.
- **Compatibility preserved**: Existing `platforms/qoderwork/SKILL.md`, `platforms/codex/AGENTS.md`, Claude Code, and Cursor artifacts remain available.

## [1.6.0] - 2026-07-08

### Added
- Configuration-aware Folder Index graph auditing with findings for graph-incompatible custom names, missing indexes, misnamed indexes, and broken parent-child graph chains.
- Bash installer smoke tests for native Folder Index and Dataview fallback modes.
- Root-to-target graph-chain validation after note creation.
- Pre-write Git synchronization with safe fast-forward-only updates.

### Changed
- Folder Index Graph View now uses native folder-named indexes below the configured root, matching the actual Folder Index 1.0.30 graph traversal algorithm.
- Bash and PowerShell installers derive index filenames and root navigation from the enabled plugin configuration.
- Bounded wikilink search lists the target folder before parent or sibling folders.
- Template validation checks required heading order; `web-clip.source` is the canonical URL and `related` is the machine-readable semantic relationship source of truth.
- Editable development installs explicitly disable accidental setuptools package discovery in this documentation-and-script repository.

### Fixed
- Dataview fallback indexes are no longer mislabeled as Folder Index-owned notes.
- New installations now create the missing `90-Archive` index.

## [1.5.0] - 2026-07-08

### Added
- Post-write validation before confirmation, commit, or push, covering metadata, tag limits, placeholders, wikilinks, encoding, and index ownership.
- Folder Index structure auditing for missing or duplicate `folder-index-content` blocks.
- Explicit precedence for user requests, Vault-local governance files, and generic skill defaults.
- Safe optional Git post-processing that stages only task files and stops on divergence, conflicts, or INDEX conflict resolution.
- Contract tests for the governance workflow and the Chinese Web Clip interpretation guidance.

### Changed
- Full-read accounting now distinguishes content notes from short control-plane files while retaining the total 10-file scan cap.
- Batch capture defaults to one target note and requires user confirmation before creating multiple notes.
- Bounded wikilink search now uses local routing and manual parent navigation before checking high-relevance sibling folders.
- The Chinese Web Clip template renames “我的理解” to “理解与启发” and defines a concise, evidence-based output standard.

## [1.4.0] - 2026-07-07

### Added
- Folder Index-aware index strategy detection. Agents now leave plugin-generated listings untouched and create only a minimal compatible index when they create a new folder while Obsidian may be closed.
- Chinese templates as the default, with preserved English templates selectable through `--locale en` / `-Locale en`.
- A consistent `related` property for explicit semantic links, separated from structural folder relationships.
- A read-only Vault audit CLI that validates frontmatter, note types, tag hygiene, fenced code blocks, wikilinks, and duplicate folder indexes.
- Regression tests for localized templates, Folder Index ownership rules, documentation link examples, attachments, ambiguous links, and tag limits.

### Changed
- Index ownership is now exclusive: Folder Index first, Dataview second, static Markdown as the fallback. The previous unconditional two-level INDEX rule is removed.
- Note type metadata is normalized to `insight-note`, and project/person templates include `updated`.

## [1.3.1] - 2026-06-11

### Fixed
- **install.ps1 em-dash corruption on PowerShell 5.1**: The Dataview INDEX template, main INDEX bullets, and several comments contained U+2014 (em-dash). Windows PowerShell 5.1 reads `.ps1` files without a BOM using the system default codepage (GBK on Chinese Windows), which mangles UTF-8 multi-byte sequences. New `15-Daily/INDEX.md` files were generated with corrupted bytes (`e9 88 a5 3f` instead of the expected `e2 80 94`). All 10 em-dashes in `install.ps1` are now replaced with ASCII `--`, so the installer produces clean output on every Windows PowerShell version. Discovered while end-to-end testing v1.3.0 against a real vault. `install.sh` and `core/OBSIDIAN_KB.md` are unaffected because bash and the build pipeline read UTF-8 sources correctly.

## [1.3.0] - 2026-06-11

### Added
- **pytest test suite** (`tests/test_build.py`): 10 tests covering `extract_body` (line-anchored marker, false-match guard, missing marker, first-line marker) and `build_adapter` (frontmatter ordering, banner placement after `---`, plain-header banner-at-top, body verbatim, platform name in banner), plus an end-to-end test that loads the real repo files and asserts every checked-in adapter matches `build_adapter()`'s output. Tests are loaded via `importlib.util` so importing `build.py` doesn't trigger `main()`.
- **`pyproject.toml`**: Declares the project, `[project.optional-dependencies] dev = ["pytest>=7"]`, and `[tool.pytest.ini_options] testpaths = ["tests"]`. Install with `pip install -e ".[dev]"`.
- **CI runs pytest**: `.github/workflows/check.yml` installs the `dev` extra and runs `python -m pytest tests/ -v` after `build.py --check`. CI now catches both "you forgot to rebuild adapters" and "you broke the build logic" in a single push.
- **Backup requirement in the Update Workflow**: Step 5 of `core/OBSIDIAN_KB.md` now mandates copying the original file (as bytes) to `{VAULT}/.obsidian-kb-backups/YYYY-MM-DD-HHMMSS/{original-relative-path}` before any in-place edit. `.gitignore` excludes the backup folder; both installers create it during setup and a routing entry documents it in the vault structure section.
- **Dataview-first INDEX templates**: New folder `INDEX.md` files seeded by both installers now contain a `dataview` code block (auto-listing recently modified notes in that folder) wrapped by `<!-- managed by obsidian-kb-skill: dataview -->` markers, followed by a `## Manual Notes` fallback section for users without the Dataview plugin. Solves the unbounded-append problem in the previous template.
- **Dataview-aware Step 8** in `core/OBSIDIAN_KB.md`: When an INDEX already contains a dataview block (or the managed marker), the agent skips the append step entirely; only legacy / user-customized INDEX files still get a manual link appended. Eliminates duplicate entries when Dataview is in use.

### Changed
- **install.ps1 / install.sh INDEX templates**: Re-templated using single-quoted PowerShell here-strings + `.Replace()` (avoiding backtick-escape pitfalls inside `@""`) and escaped-backtick bash heredocs respectively. Output bytes verified UTF-8 (no BOM) on both platforms.
- **README.md / README_EN.md**: Bumped to v1.3.0; "Recommended Obsidian Plugins" now promotes Dataview to **strongly recommended** with explanation of the new INDEX behavior; Contributing section documents `pip install -e ".[dev]"` and `pytest`.

### Fixed
- **`extract_body` false match on quoted text**: The body marker (`## Overview`) was being matched against the first occurrence of that string anywhere in the file, including inside quoted prose. Fixed by searching for `"\n## Overview\n"` (line-anchored only), with a separate first-line acceptance for the edge case where the file starts with the marker. Covered by `TestExtractBody::test_inline_text_does_not_match`.

## [1.2.0] - 2026-06-11

### Added
- **Marker-wrapped skill blocks** in `CLAUDE.md` / `AGENTS.md`: Both installers now wrap injected content in `<!-- BEGIN obsidian-kb-skill -->` / `<!-- END obsidian-kb-skill -->` markers. Re-running the installer replaces the block in place (true upgrade), and `--uninstall` strips the block while preserving the user's other content. If the file ends up empty after strip, it's removed entirely.
- **`--Force` switch on install.ps1**: First-class upgrade flag matching install.sh's `--force`. Legacy `OBSIDIAN_KB_UPGRADE=1` env var still works.
- **15-Daily/ folder**: Daily notes, journals, and morning plans now route to their own dedicated folder instead of being mixed into 10-Work. Both installers create the folder and its INDEX, and the main INDEX has a navigation entry for it.
- **GitHub Actions workflow** (`.github/workflows/check.yml`): Runs `python build.py --check` on every push and PR. Fails CI if a contributor edited `core/OBSIDIAN_KB.md` or a platform `header.md` without re-running `build.py`.
- **Verified marker logic**: Manual round-trip tests confirm install / upgrade / append-into-existing-file / strip-keep-user-content / strip-and-delete all work correctly on both PowerShell and bash implementations.

### Changed
- **Daily Note routing**: `core/OBSIDIAN_KB.md` routing table now sends "daily, today, diary, journal, morning plan" triggers to `15-Daily/` (was `10-Work/`). Generated adapters regenerated.
- **install.ps1 refactored**: Centralized UTF-8 (no BOM) write helper; removed the brittle "is the Platforms string `--force`" sniff; consolidated marker logic into two reusable functions (`Set-MarkerBlock`, `Remove-MarkerBlock`).
- **install.sh refactored**: Mirrors the PowerShell function shape with portable awk implementations of `set_marker_block` / `remove_marker_block`. Force upgrade is now a proper `--force` flag handled at the top, not scanned from `$@` mid-loop.

### Fixed
- **Claude/Codex upgrade gap**: Previously the installer's "already installed?" check used `grep "Obsidian Personal Knowledge Base"` and silently skipped — meaning v1.0.0 → v1.1.0 upgrades never touched `CLAUDE.md` / `AGENTS.md`. Now `--force` does a real in-place replacement via markers.
- **Claude/Codex uninstall gap**: Previously the uninstaller refused to touch `CLAUDE.md` / `AGENTS.md` because it had no way to identify its own content. With markers, the skill block can be safely removed in isolation.
- **PowerShell BOM inconsistency**: All file writes in install.ps1 now go through the shared `Write-Utf8NoBom` helper; the previously stray `Add-Content` (which writes with BOM on PS 5.1) is gone.

## [1.1.0] - 2026-06-11

### Added
- **Build script architecture (`build.py`)**: Single-source-of-truth generator that produces all four platform adapters from `core/OBSIDIAN_KB.md` plus per-platform `platforms/{name}/header.md`. One edit syncs all four platforms; `--check` mode verifies generated files are in sync (suitable for CI / pre-commit).
- **Per-platform `header.md`**: Each platform now has a small `header.md` containing only its YAML frontmatter / H1 / trigger hint. The shared body lives in `core/OBSIDIAN_KB.md`.
- **Generated-file banner**: All adapter files now start with an `AUTO-GENERATED` HTML comment warning against direct edits.
- **"When NOT to Use This Skill" section**: Explicit non-triggers (casual Q&A, debugging, one-off snippets) to reduce false invocations.
- **Vault Validation step**: Verifies `.obsidian/` and `Templates/` exist before any write; refuses to write into non-vault paths.
- **"Decide First: Create vs Update" section**: Forces the agent to choose Create vs Update before acting, with explicit ambiguity-handling rules.
- **Update Existing Note Workflow** (7 steps): Locate target, read in full, pick insertion point (section-aware for `project-note` / `person-note` / `daily-note`), preserve frontmatter, report diff summary. Closes the gap where the skill only knew how to create new notes.
- **Bounded wikilink search**: Cheap-first strategy in Step 6 — read folder INDEX, list 1–2 sibling folders, read first ~20 lines of 2–5 candidates, insert at most 5 wikilinks. Replaces vague "scan the vault" instruction.
- **Cost Limits section**: Hard per-invocation caps (10 files scanned, 3 full reads, 1 note written, 2 INDEX updates, 5 wikilinks) to prevent runaway token usage.
- **Tag Hygiene section**: Reuse existing tags first (scan 5 recent notes), kebab-case only, no near-duplicates, max 5 tags per note.
- **`updated:` frontmatter field**: Added to `project-note` and `person-note` types to support the Update workflow.
- **README "Editing the Skill / Contributing" section**: Explains build script architecture in both Chinese and English READMEs.

### Changed
- **Tightened skill descriptions**: All four platforms now narrow the trigger to explicit save/append intent ("save to Obsidian", "记一下", "沉淀到知识库", etc.) and explicitly exclude casual Q&A and debugging. Reduces false positives from broad words like "notes" or "knowledge".
- **Project structure**: Four `header.md` files added; four adapter files are now generated artifacts (do not edit directly).
- **Important Rules**: Now reference both Create and Update workflows, vault validation, and cost limits.

### Notes
- The four generated adapter files (`SKILL.md`, `CLAUDE.md`, `AGENTS.md`, `obsidian-kb.mdc`) remain at their original paths, so existing installer logic and external links continue to work unchanged.
- Backward-compatible with all v1.0.0 installations — no migration required.

## [1.0.0] - 2026-06-11

### Added
- **Daily Note routing**: Added "daily, today, diary, journal, morning plan" trigger pattern to all platform adapters
- **Error handling section**: Comprehensive error handling guidelines in core instructions and all adapters
- **Template placeholder docs**: Documented `{{date}}` placeholder replacement behavior
- **Subfolder support**: Routing and INDEX update rules for topic-based subfolders (e.g. `20-Learning/Python/`)
- **Install script improvements**:
  - `-Help` / `--help` parameter with full usage documentation
  - `-Uninstall` / `--uninstall` option to cleanly remove skill files
  - `--force` upgrade mode to update existing templates
- **Cursor glob patterns**: Expanded to include `**/vault*`, `**/INDEX*`, `**/*.md`
- **`.gitignore` expanded**: Added OS artifacts (.DS_Store, Thumbs.db), editor artifacts (.vscode/, .idea/), Obsidian workspace files
- **Version identifier**: Added version `1.0.0` to core instructions and README

### Fixed
- **UTF-8 BOM on PowerShell 5.1**: Replaced `Set-Content -Encoding UTF8` with `[System.IO.File]::WriteAllText()` in install.ps1 (3 occurrences)
- **Cross-adapter consistency**: Standardized all 4 platform adapters to 9-step workflow matching core instructions
- **Template paths in Cursor**: Added `Templates/` prefix to all template references in obsidian-kb.mdc
- **"Never overwrite" rule**: Added numeric suffix guidance (`-2`, `-3`) to Codex and Cursor adapters
- **"Never hardcode date"**: Added explicit warning to Codex and Cursor adapters
- **`.env.example` comment**: Fixed misleading "should NOT be committed" message

### Changed
- Core workflow expanded from 6 steps to 9 steps (matching adapter implementations)
- All routing tables now include Daily Note as the first entry
- Rules sections now include subfolder INDEX update rule
- YAML frontmatter table now includes `daily-note` type
