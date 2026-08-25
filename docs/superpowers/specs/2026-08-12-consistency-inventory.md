# Cross-Boundary Consistency — Inventory

**Status: accepted.** The registry #106 asks for. Lists every relation in this
project where two places must agree, and what checks that they do.

## Why this exists

On 2026-08-12 the same defect shape appeared seven times in one day:

> Something is stated in two places, nothing checks they agree, and the failure
> is silent — no error, no red test, just a wrong answer where nobody is
> looking.

`process-inbox` and `audit-vault` shipped to every user's disk with nothing in
`core/` referencing them (#90). Filing refusals set `applied: false` with no
reason a JSON consumer could read (#92). Two `project-note` files in one
directory made the radar count one project twice (#95). The crowding contract
never said which folders it governed, so it was applied to a structure it would
have forbidden (#95). The wrong runner answered a real capability with `invalid
choice` (#103). A bundle shipped with an unresolvable import graph while unit
tests, `build --check` and `doctor` all passed (#108). An installer reported
`Installation complete` with all five platforms ticked while `skillctl doctor`
went from OK to FAILED with eight link-drift errors (#113). And twice the
author's own survey method produced a wrong premise that only a test caught.

Every instance is the same underlying gap, so the response is not seven fixes.
It is a list of the boundaries, and the discipline of adding to it.

## The registry

| # | Boundary | Guard |
|---|---|---|
| 1 | Bundled helper list ↔ instructions that invoke it | `test_every_bundled_helper_is_reachable_from_the_instructions` |
| 2 | Unrouted-helper exemptions ↔ current reachability | `test_unrouted_helper_list_does_not_outlive_its_reason` |
| 3 | Codes helpers emit ↔ `rules-and-errors.md` | `test_every_emitted_code_is_documented` |
| 4 | `rules-and-errors.md` ↔ codes that actually exist | `test_reference_documents_no_codes_the_helpers_never_emit` |
| 5 | Retrieval helper codes ↔ the reference that Agent reads | `test_retrieval_codes_are_documented_where_that_agent_can_read_them` |
| 6 | `core/` sources ↔ generated artifacts | `build.py --check`, `test_build_check_still_passes` |
| 7 | Human-readable refusal ↔ machine-readable refusal | `test_every_unapplied_note_carries_a_machine_readable_reason` |
| 8 | Directory layout ↔ instance type semantics | `duplicate-project-note` audit finding |
| 9 | Write runner peer list ↔ retrieval runner contents | `test_peer_helper_lists_cannot_drift_from_the_runners_they_mirror` |
| 10 | Retrieval bundle allowlist ↔ that bundle's import graph | `test_every_retrieval_helper_imports_from_the_installed_bundle` |
| 11 | Retrieval runner registry ↔ test helper tuple | `test_retrieval_runner_exposes_only_read_only_helpers` |
| 12 | Write runner registry ↔ test helper tuple | `test_the_write_test_helper_list_matches_its_runner` |
| 13 | `[project.scripts]` ↔ runner registries | `test_every_helper_has_a_console_script_or_a_stated_exemption` |
| 14 | Capability table ↔ helpers that exist | `test_the_feature_guide_only_advertises_helpers_that_exist` |
| 15 | Digest section names ↔ the resume contract that uses them | `test_digest_heading_variants_are_derived_not_copied` |
| 16 | Installer paths ↔ Skill × platform matrix | `test_both_installers_write_to_the_same_hosts_and_skills` and `test_every_host_is_reached_by_both_installing_and_uninstalling` — #91 replaced 32 hand-copied path literals with one table per script (`SKILL_ROWS`/`HOST_ROWS`, `$SkillRows`/`$HostRows`), so the guards now read the declaration rather than scanning four branches for uses. Install and uninstall expand the same table, which makes the two sets equal by construction; what is still asserted is that the two scripts' tables agree and that neither branch grew a path outside its table. The host is discovered, never enumerated |
| 17 | Managed-link decision in `install.sh` ↔ `install.ps1` ↔ `tests/windows_installer_smoke.ps1` | `test_bash_install_does_not_clobber_a_managed_skill_symlink` (POSIX behaviour) and `test_powershell_installer_has_managed_symlink_parity` (reads `install.ps1` text only) — **the smoke script is unguarded**, and only Windows CI executes it |
| 18 | Headings the resume report calls recognized ↔ headings its matcher can match | `test_every_known_variant_is_both_matchable_and_reported_as_matched` |
| 19 | `core/templates/*/project-note.md` headings ↔ the resume vocabulary that reads them | `test_this_projects_own_templates_are_fully_readable_by_the_extractor` |
| 20 | The unreplaced-placeholder rule across `audit-vault`, `template-contract` and `process-inbox` | **relation removed** — one `TEMPLATE_PLACEHOLDER_RE` in `note_catalog`, shared by object; `test_the_placeholder_rule_is_the_audits_rule_not_a_second_copy` asserts identity so a local copy cannot come back |
| 21 | Default draft tag in `process_inbox` ↔ the reference an Agent reads | `test_the_filing_reference_names_the_draft_tag_the_code_defaults_to` |
| 22 | Next-actions headings in `review_projects` ↔ `resume_project` | **relation removed** — one `PROJECT_NOTE_NEXT_ACTION_HEADINGS` in `note_catalog`; `test_both_retrieval_helpers_mean_the_same_thing_by_next_actions` asserts both derive from it |
| 23 | `--runtime-only` in `install.sh` ↔ `-RuntimeOnly` in `install.ps1` ↔ `tests/windows_installer_smoke.ps1` | `test_bash_runtime_only_*` (POSIX behaviour), `test_powershell_installer_has_runtime_only_parity` (text), and the smoke script now exercises the Windows **behaviour** — the coverage row 17 lacked |
| 24 | Installer flag names ↔ the READMEs and installation guide | `test_the_docs_explain_installing_alongside_a_skill_manager`, `test_both_installers_document_runtime_only_in_their_help` |
| 25 | Tests that invoke `install.sh` ↔ the `test_bash_` prefix the Windows skip keys on | `test_every_bash_invoking_installer_test_is_named_for_the_windows_skip` |
| 26 | Zero-result reason in JSON ↔ the same reason in text mode | **relation removed** — one `ZERO_RESULT_REASONS` table, read by both `search_vault()` and `main()` |
| 27 | Zero-result reason codes ↔ the reference the retrieval Agent reads | `test_every_zero_result_reason_is_documented_for_the_agent_that_reads_it` |
| 28 | `search-vault --updated-*` (reads `updated` only) ↔ `review-projects` activity (`updated` falling back to `date`) | `test_the_two_activity_semantics_are_documented_as_different` — **deliberately different**, guarded as a documented distinction rather than unified |
| 29 | `resume_project.ORIGIN_TRUST` ↔ the reference that ranks each origin's reliability | `test_every_resume_origin_is_ranked_in_the_reference` |
| 30 | What each Skill means by "this note is an index" | **relation removed** — one `INDEX_TYPES` in `note_catalog`, from which `VALID_NOTE_TYPES` also derives; `test_both_skills_mean_the_same_thing_by_an_index_note` asserts identity across `audit_vault` and `resume_project` |
| 31 | The shape of a long note in the adversarial fixture ↔ the shape long notes actually have | `test_a_long_note_is_long_the_way_real_long_notes_are`, with the reference-Vault measurement recorded beside the constant it justifies |
| 32 | Cases the adversarial fixture runs ↔ cases the frozen baseline records | the `unrecorded` assertion in `test_the_recorded_baseline_still_describes_this_ranker` |
| 33 | The unit a result is ranked on ↔ the unit it is cited from | **relation removed** — `_bm25_score` returns the winning `Passage` and `_snippet`, `_field_matches` and `_expansion_signals` all read it; `test_the_citation_comes_from_the_section_that_won` and `test_a_body_signal_names_only_words_in_the_section_that_won` |
| 34 | `field_tokens["body"]` ↔ the union of the note's passages | **relation removed** — the body counter is summed from the passages rather than tokenized again, which the tokenizer's own definition makes exact: `TOKEN_RUN_RE` matches runs of Latin or CJK and a newline is neither, so no run can span a line break |
| 35 | What a wikilink resolves to for the audit ↔ what it resolves to for retrieval | **relation removed** — one `link_graph` module, imported by `audit_vault` and `explore_neighborhood`; the alternative was a second implementation of Obsidian's alias-and-stem resolution in a bundle that cannot import the first |
| 36 | A view's field names ↔ `search_vault`'s actual signature | `test_every_view_field_maps_to_a_parameter_search_vault_really_has`, which reads the live signature with `inspect` rather than a second list |
| 37 | The plan a view reports ↔ the search it actually ran | `test_the_resolved_plan_is_shown_and_reproduces_the_same_results` re-runs the reported plan through `search_vault` and compares the result paths |
| 38 | A module's import block ↔ the names it actually uses | `test_no_module_declares_a_dependency_it_does_not_use`; a deliberate re-export declares `__all__` so intent is stated rather than special-cased |
| 39 | The v1.30 directional labels ↔ the corpus written to realise them | `test_the_corpus_realises_every_label_and_invents_no_pair` and `test_each_source_names_its_positive_target_and_never_its_negative` |
| 40 | Each hard negative's claimed word overlap ↔ the overlap the corpus actually has | `test_each_hard_negative_really_does_collide_lexically` — a negative rejected for being about nothing alike proves nothing about a scorer that had to tell a real collision apart |
| 41 | The eval fixture's `hard_failures` list ↔ the codes `score_run` can actually raise | `test_the_recorded_hard_failure_codes_match_the_ones_the_scorer_can_raise` — the fixture recorded 8 of 14 and named two the scorer never raises, so the gate read wider than it is; what remains unraisable is kept in `hard_failures_not_implemented` with what happened to it rather than deleted — `invented-source-access` left that list when it was implemented, `invented-factual-claim` stays because it ships under the name `forbidden-claim` |
| 42 | Each alternative form of a required fact ↔ a recorded observation of it | `test_every_alternative_fact_form_records_where_it_was_observed` — a translation nobody saw a run write is a guess, and #115 shows what a vocabulary two characters short costs |
| 43 | Each forbidden claim's term set ↔ the required facts of the same case | `test_no_forbidden_claim_is_satisfied_by_the_facts_the_case_demands` — three claims declared only terms the note was required to record, so the gate punished a correct note unless the negation detector happened to know its phrasing; `supports-python-3-10` declared `['python', '3.10']` and omitted `supports`, tripping two of three runs at soft_score 1.0 and halting a 36-run batch after three |
| 44 | `review-captures`'s capture-type set ↔ the note types whose value depends on later use | `test_notes_that_are_not_captures_are_out_of_scope` — a daily report is written once by design and a folder index is generated, so counting either measures the Vault's shape rather than its intake; adding a type to `CAPTURE_TYPES` without deciding that changes every number the helper reports |
| 45 | The number reported ↔ the evidence it came from | `test_the_report_says_which_evidence_it_used` and `test_git_history_is_preferred_and_declared_when_the_vault_is_a_repo` — git history is exact but covered 57 of 214 notes on the reference Vault, and file mtime is perturbed by sync clients and by any checkout; an unstated source invites being read as the stronger one |
| 46 | A truncated run's `mean_soft_score` ↔ the summary declaring it was truncated | `test_the_summary_names_the_case_that_ended_a_truncated_run` and `test_a_complete_run_says_it_was_not_truncated` (both drive `main()` against a scripted `run_case` and read the written `summary.json`), plus `test_stopping_early_names_the_case_so_a_partial_mean_is_not_read_as_whole` (covers `run_all_cases`'s return value only) — the 2026-08-18 baseline stopped after 15 of 36 runs and still reported `mean_soft_score` under the key a complete run uses, so a number covering 5 of 12 cases read exactly like one covering all 12. The first two replaced a source-text check that could not see the failure at all: discarding the returned value and rebinding `stopped_after = None` below it left both string assertions true while every summary claimed to be complete |
| 47 | The types `is_meaningful_metadata` accepts ↔ the types YAML frontmatter produces | `tests/test_metadata_quality.py` and `test_a_web_clip_dated_with_yamls_own_syntax_is_not_reported_as_undated` — YAML resolves `published: 2026-08-13` to `date` and `published: 2025` to `int`, so a `str`-only predicate graded notes by whether their author quoted the value and reported two correctly filled reference-Vault clips as missing it; every earlier web-clip test quoted its dates, so no assertion covered the unquoted form |
| 48 | `create-note`'s refusal set ↔ the audit's `defect` severity | `test_every_refused_code_is_a_defect_the_author_can_fix_by_rewriting` — a subset, not an equality, and the test names `broken-wikilink` as excluded: it is graded `defect` and #159 settled that linking an unwritten note is standard Obsidian usage, so refusing every defect would forbid creating a note that points forward. `process-inbox` already refuses the same unfinished-note class as `draft-incomplete`; the write path had no counterpart, and nine reference-Vault notes ship instructions addressed to the Agent |
| 49 | `disconnected-note`'s exempt types ↔ `review-captures`'s `CAPTURE_TYPES` | `test_a_type_exempted_from_connectivity_is_still_watched_somewhere` — the audit stopped reporting web-clips on the argument that `review-captures` already covers 21 of the 23 reference-Vault findings by a stronger question (the other two are a `project-note` and a note with no `type`, both outside `CAPTURE_TYPES`); drop `web-clip` from `CAPTURE_TYPES` and neither reports it, so the note goes unwatched and the argument for the exemption expires with nothing saying so |
| 50 | The receipt gate's accepted command shapes ↔ `create-note`'s content sources | `test_verified_write_requires_an_accepted_receipt_bound_to_note` (the `--from-preflight` shape) and `test_a_receipt_is_accepted_whichever_content_source_the_agent_used` (the `--content-file` shape) — the helper accepts `--stdin`, `--content-file` and `--from-preflight`, and the gate required the third; the only fixture that built an apply command built the shape the gate already recognised, so a correct Agent hard-failed all three `verified-evidence-report` repeats while the suite stayed green |
| 51 | The audit's reported denominator ↔ the notes it actually audited | `test_the_audit_reports_how_many_notes_its_findings_came_from` and `test_the_json_report_carries_the_denominator` — `count` counts findings, not notes, and the report named only it: 92 findings across 20 notes and across 200 read identically. `audited` is incremented past the `95-Sources/` skip, so moving the counter above that `continue` turns 3 into 4 and both assertions go red |
| 52 | The options `PATH_OUTSIDE_VAULT`'s action column names ↔ the options `create-note` declares | `test_the_path_refusal_points_at_an_option_that_exists` — the row now tells an Agent to pipe a rejected `--content-file` through `--stdin`; rename either flag and the advice points at nothing, silently, and the Agent improvises. #154 is what improvising looked like: it staged the body inside the Vault to get past the check, and a second gate then punished it for that shape |
| 53 | Every Vault-walking helper's exclusion list ↔ the backup directory | `test_every_helper_that_walks_the_vault_skips_the_backup_directory` — three modules keep their own list on purpose, because they answer different questions, but `.obsidian-kb-backups/` is not a question any of them should differ on: `review_captures.IGNORED_DIRECTORIES` omitted it and counted three backed-up web-clips as captures, reporting two of them as never reopened. Counting a copy is wrong whichever way it moves the number, and here it moved it up: web-clip's revisit rate read 0.278 instead of 0.275, because the third backup was not tracked by git and its mtime fallback scored it as revisited |
| 54 | The adversarial corpus's mean note length ↔ the reference Vault's | `test_the_corpus_mean_length_stays_near_the_reference_vault` — BM25 penalises length *relative to the corpus mean*, so the mean decides which notes are penalised at all. Three notes at or above 25 KB held 97.9% of the set's bytes — the two 76 KB ones alone were 83.8% — and put the mean at 9170 against the real 4247, leaving every everyday note unpenalised: `adv-dilution-06` ranked first here while its real-Vault counterpart ranked second. The set now means 5010; restoring 120 filler paragraphs turns the guard red at 8468 (that figure and 9170 differ because the guard runs against the 22-note set, which includes the pair `adv-dilution-06` added) |
| 55 | `note_catalog`'s fenced-code masker ↔ `capture_receipt`'s | `test_the_two_fence_maskers_agree` — two implementations of "which bytes are inside a fence", written for different reasons (hiding an HTML comment vs ignoring `{{ }}` in a code sample). A Markdown fence has enough corner cases — tildes, indentation, backticks in the info string, no closing fence, CRLF — that two hand-written answers do not stay equal: this assertion went red on the day it was written, on a copy whose closing-fence regex had lost its interpolation and so never closed a fence at all |
| 56 | The value `capture_receipt` compares for duplicate resource names ↔ the value it stores | `test_two_resources_named_the_same_number_are_still_duplicates` — the check read `name in resource_names` while the set stored `str(name)`. The two could not disagree while `is_meaningful_metadata` rejected every non-`str`; #162 widened it to accept scalars so an unquoted YAML date would stop reading as a placeholder, and that made `2026 in {"2026"}` reachable — two resources named the same number stopped colliding, and validation failed later under a different code |
| 57 | The codes a helper emits ↔ the codes the contract scanner can see | `test_the_web_clip_metadata_codes_are_visible_to_the_scanner` — `_codes_in` collects string constants, so `f"web-clip-missing-{field}"` was skipped in silence and `test_every_emitted_code_is_documented` never asked for those three rows: they were undocumented for as long as they existed, suite green throughout. The guard asserts on what the collector *found*, not on the syntax, because a loop variable hides a code just as well as an f-string |
| 58 | `audit-vault`'s `scanned` ↔ `search-vault`'s `scanned` | **none** — same name, different question, and deliberately so: `search_vault` excludes 15 directories including `Templates/`, `Attachments/` and `95-Sources/` because none of them is searchable knowledge, while `audit_vault` excludes 5 plus any hidden directory because it *must* audit templates (it grades `missing-template-heading`). 194 vs 183 follows from that. No assertion can relate them without asserting that one of the two scopes is wrong; what is checkable is that each states its own, which rows 51 and 53 cover. #173's claim that the two are "same name, same meaning" was wrong — one is an integer, the other an object |
| 59 | A version literal in a test ↔ the version `pyproject.toml` declares | `test_only_the_release_contract_hardcodes_the_version` — three test files spelled the version out and thereby joined the release checklist without being on it; v1.35.0 found all three by running the suite, after the CHANGELOG was already written. They asserted that an installed artifact carries the repository's version, which reads stronger from `build.project_version()` than from a literal someone has to remember. `test_build.py` keeps two on purpose: the anchor, and the per-release contract meant to be edited by hand |
| 60 | `CONFIDENCE_LEVELS` ↔ the reference the retrieval Agent reads | `test_every_confidence_level_is_documented_for_the_agent_that_reads_it` — same shape as row 27, and for the sharper reason: acting on `none` means declining to cite results the Agent can see |
| 61 | `CONFIDENCE_FLOOR` ↔ the measurement that chose it | `test_the_confidence_floor_is_stated_where_it_was_measured` — the constant must appear in both the design and the Agent's reference. 0.30 is not adjustable taste: 0.60 was equally plausible and demoted 12 of 16 correct answers, recorded in `2026-08-21-rejected-hypotheses.md` §4 |
| 62 | The adversarial corpus's scoring-unit length ↔ the reference Vault's | `test_the_scoring_unit_diverges_from_the_reference_vault_by_a_recorded_factor` — **deliberately different**, guarded as a recorded 2.18x rather than unified. The neighbouring byte-mean assertion is green and describes an effect it does not measure; #174 was argued on those bytes. Ruling and both rejected branches in `2026-08-23-adversarial-corpus-shape-decision.md` |
| 63 | What counts as fenced code, across `search_vault`'s title, headings and passage split ↔ `explore_neighborhood` ↔ `relatedness` | **relation removed** — one `link_graph.blank_code_examples`, which preserves line numbering so the same index addresses the blanked copy and the body. `search_vault` had no fence notion at all: on the reference Vault 22 of 199 notes carried 255 shell comments read as headings, and 2 notes took their `title` — scored at 6x — from a ```bash line. `test_a_fenced_comment_does_not_open_a_section` and `test_a_shell_comment_inside_a_code_block_is_not_the_notes_title`; the adversarial corpus holds no fence and could not catch it |
| 64 | `BM25_K1` / `BM25_B` ↔ the sweep that ruled on them | `test_the_length_penalty_is_the_value_the_sweep_ruled_on` — the values are the textbook defaults, which is why they need a guard: a round number reads as unexamined. `b=0.25` scores better in aggregate and trades one real group for another, measured in `2026-08-21-rejected-hypotheses.md` §6 |
| 65 | `build.py`'s Skill directory names ↔ both installers' Skill tables | `test_the_installers_place_the_skill_directories_build_produces` — three declarations in three languages that **cannot** share one: the installers are fetched and run standalone and can import nothing, which is the delivery model. #91's sixth acceptance criterion asked for this evaluation; the answer is assert, not share |
| 66 | "A helper never fetches" as `rejected-hypotheses.md` §7 relies on it ↔ what the package can actually reach | `test_no_helper_can_reach_the_network`. #193's prevention route was closed *because* the Agent fetches and the helper only receives text; a helper that could fetch would silently make a recorded conclusion false. Guarded in the two halves an added capability must cross — the runtime dependency set read live from `pyproject.toml`, and network-capable stdlib imports found by AST. `urllib.parse` is deliberately not on the list; `capture_receipt` splits a URL with it |
| 67 | `WEB_CLIP_MIN_CONTENT_CHARS` ↔ the reference-Vault distribution it was chosen from | `test_the_content_floor_is_the_value_the_distribution_supports` — the floor must sit strictly inside the measured gap (largest shell 220, smallest real capture 799), and the design must state all three numbers. A threshold is a claim about a corpus; moved without re-measuring it starts accusing real notes, and nothing else would say so. #167 |
| 68 | What `empty-template-note` counts as content ↔ what `web-clip-captured-nothing` counts | **relation removed** — one `_body_content_chars`, called by both. `test_both_emptiness_findings_read_the_same_content_count` asserts each finding calls it *and* that exactly one `content_chars` accumulator exists in the module: sharing a helper does not stop a copy being added beside the call, which is the shape this list keeps catching |
| 69 | The draft tag the audit skips ↔ the one `process_inbox` refuses to file on | **relation removed** — `DEFAULT_DRAFT_TAGS` moved into `note_catalog`, which both import; `test_the_audit_skips_the_draft_tag_filing_files_on` asserts identity by object, so an equal copy fails. The two modules **cannot** import each other — `process_inbox` already takes `_note_title` from `audit_vault` — and drift would give one note contradictory advice: a draft to filing, a defect to the audit |
| 70 | `UNSEEN_TERM_MIN_CHARS` ↔ the sweep that chose it | `test_the_unseen_term_floor_is_the_value_the_sweep_chose`. Every variant demotes 0 of the 16 correct answers, so the length is not chosen by safety but by reach: 14 of 22 no-answer queries at 2, 13 at 3, 10 at 4. The design must keep stating the table, or the constant cites a measurement a reader cannot check. #195 |
| 71 | `FIELD_WEIGHTS["links"]` as a claim about weight ↔ what link text actually scores | `test_every_link_token_is_also_a_body_token`. `_wikilink_text` feeds a link's visible text into the citing note, where it is *already* body text — 1331 of 1331 instances on the reference Vault — so the table's 2x is really **3x** and #194's sweep of 0.0–2.0 could not move anything. Removal was measured and rejected: no outcome change, two frozen baselines burned. If the duplication ends, the field becomes a real signal and the weight becomes tunable, and this says so |

Guards 12, 13 and 14 were added by this work. The rest already existed; several
had caught the author earlier the same day. Row 17 arrived late, in #114 — see
below. Rows 18 and 19 came with #115.

Row 28 is the registry's first row for two places that must **stay different**.
`search-vault` filters on `updated` alone; `review-projects` ranks on `updated`
falling back to `date`, because a project note without one still has an age
worth ordering. Unifying them would be the easy move and the wrong one — a
search for "changed in August" must not return a note whose only date is June.
What needs guarding is not agreement but that the difference is written down
where the Agent reads it, since the failure mode is a reader assuming there is
only one answer. Not every boundary wants to be closed; some want to be legible.

Row 25 was written from a red CI run, and the boundary is a *naming
convention*: `tests/test_installers.py` skips bash lifecycle tests on Windows
through an autouse fixture keyed on the prefix `test_bash_`. Nothing checked
that a test running `install.sh` carried it, so a correctly-written hard
negative under a different name ran on Windows and failed. This is the registry's
own claim in miniature — a rule enforced only by whoever notices — and it is
mechanically checkable, which is why it is a row and not a comment.

Row 23 is row 17 with its gap closed, and it is the reason to read row 17's
guard column rather than its name. Row 17 records a parity assertion that reads
`install.ps1` and stops there; the Windows *behaviour* it is named after is
exercised by exactly one file, which runs only in CI. The new mode therefore
shipped with a scenario added to that file in the same change — the step #114
skipped. Nothing local can run it: `pwsh` is absent on the development machine,
so "the tests pass here" says nothing about the Windows half. That is a fact
about this repository worth stating plainly rather than rediscovering.

Row 22 is the registry's first same-day catch of its own author. #125 widened
one of two vocabularies for *next actions* and left the other alone, without a
row — the rule this document sets, broken in the change made right after citing
it. Nothing failed: the radar kept working because it falls back to the first
checkbox anywhere in the note. It surfaced a few hours later while scoping that
very count to the section, where the drift would have zeroed out the one project
whose checkboxes all sit under the widened heading. An unregistered boundary
does not announce itself; it waits for the change that depends on it.

Rows 39 and 40 guard an evaluation against the person who builds for it. The
v1.30 labels were committed on 2026-08-09 with `purpose` reading "v1.30 adds no
scorer" — a commitment about what a scorer would have to achieve, written before
one existed, which makes them the only half of #75's evaluation not authored to
make the implementation look good. The corpus realising them was written five
days later by the same hand that then wrote the scorer, so what needs guarding
is that the corpus did not drift toward what was convenient.

Row 40 is the sharper of the two. Every hard negative claims a shared word —
`Release Quality Gate` against `Airport Departure Gates`. If the corpus failed
to reproduce that overlap, all sixteen would be rejected for being about nothing
alike, the scorer would score 16/16, and the number would mean nothing. The
guard checks the collision is real before crediting the rejection.

Row 38 came out of reviewing the four changes above, and it is the smallest
boundary in this list — which is why it went unnamed for so long. An import
block is a claim about what a module needs. Extracting `LinkIndex` into
`link_graph` left five names imported into `audit_vault` and used nowhere;
nothing failed, and the next reader deciding what may safely move is handed a
dependency map that is wrong in five places. Six more had been sitting in other
modules for longer. The guard is trivial to satisfy and trivial to check, and
the only judgement it needs — "is this a re-export or a leftover?" — is made
declarable by `__all__` rather than by exempting a filename.

Rows 36 and 37 guard a configuration format, which is the first time this list
covers something a *user* writes. A view's schema is a second spelling of
`search_vault`'s signature: renaming a parameter would leave the mapping
pointing at nothing and fail in someone's Vault rather than in CI, so row 36
reads the live signature with `inspect` instead of comparing two hand-kept
lists — the check cannot be satisfied by editing it.

Row 37 guards something subtler. The helper returns a `plan` so its answer is
reproducible, and a plan that does not describe the call actually made is worse
than no plan: it is a wrong answer wearing the costume of a checkable one. The
assertion re-runs the reported plan through `search_vault` and compares, so the
two cannot drift while continuing to look consistent.

Row 35 is worth reading beside what *did not* need a row. Adding a helper
(#121) crossed six boundaries in this list, and five of them — the peer helper
lists, the retrieval bundle's import graph, the runner registries, the console
scripts, and the codes an Agent can receive — **failed immediately, by name, on
the first test run**, each error naming its own fix. That is the whole return on
this document: the work of registering a boundary is paid once, and collected
every time someone extends the thing. Only the sixth was new, and it is a
deletion rather than a guard.

Row 33 is a boundary that existed for as long as the ranker did and nobody had
named: a note was ranked whole, then a snippet was chosen from it afterwards, so
the ranking's reason and the citation's location were two independent decisions
about the same note. Nothing was wrong while both looked at the whole note.
Section-level ranking (#118) made them separable, and the first implementation
promptly separated them — a result citing a section holding only `jitter`
reported `body: jitter, 毫秒`, with `毫秒` three sections away. The issue had
listed exactly this risk before the code existed; writing the risk down did not
prevent it, and the assertion written to cover it was *vacuous on its first
draft* and passed. What caught it was printing the output and reading it.

Row 34 is a relation deliberately created, because the alternative was worse.
Deriving the body's token counts from the passages rather than tokenizing the
body a second time is a real coupling — but it is exact by the tokenizer's own
definition rather than by agreement, and tokenizing twice cost 60% of query
latency on the reference Vault for an identical result. A relation whose
correctness follows from a definition needs the definition recorded, which is
what the row is for.

Rows 31 and 32 are the registry reaching a place it had not covered: a *test
asset*. Both boundaries were invisible because the file that would notice them
is the same file that defines them.

Row 31 is the sharpest instance so far of a world built from a belief. The
adversarial set's long notes were generated by appending unstructured filler,
because that is how the author pictured "a long note". Measured afterwards on
the reference Vault: of the 19 notes at or above 10 KB, the fewest headings any
carries is 12 and the median is 30 — **none** has a single heading. Real notes
are long *because they have many sections*. The set therefore reproduced length
dilution through a mechanism this Vault does not exhibit, and a section-ranking
candidate scored byte-identically to master on it: a note with one heading has
one passage, so any heading-based split is a no-op. #117's own bar was that an
evaluation set which cannot fail is a guard green from birth; this set could
fail, but not at the question it was about to be asked. The guard records the
measurement next to the constant, so the next person changing it argues with a
number rather than with a picture.

Row 32 was found while fixing row 31. The baseline comparison walks the
*recorded* cases, so a query added to the fixture without a baseline row was
compared against nothing — frozen in name, free in fact. The new case would
have been the first to slip through.

Row 30 was filed as `guard: none` on the strength of a quotation, and the
quotation was attributed to the wrong file. #133 said the promise "index files
are excluded" sat in `core/retrieval-references/resume-project.md`; that file
contains no occurrence of the word *index*. The sentence was a docstring in
`resume_project.py`. The defect was real and the fix is the one below, but the
row as first written described a boundary between a reference and the code,
which is not the boundary that existed — and the issue's proposed direction
followed from the wrong description. Attribution is part of a claim: a quotation
without the read that produced it is an assertion about a file nobody opened.

The row's real content is that `{"folder-index", "moc"}` existed twice —
`audit_vault.INDEX_TYPES` and `note_catalog.VALID_NOTE_TYPES`' inline literals —
with nothing tying them together, and #133 was about to make retrieval a third.
Sharing one object removes the boundary. Two criteria were available and the
positional one was rejected: `expected_folder_index` returns
`<folder>/<folder>.md` even when the Folder Index plugin is disabled, so it
would silently drop a real note that happened to carry its directory's name.
`test_a_note_named_after_its_directory_is_still_a_source` is the hard negative
that keeps that criterion from arriving later, and it fails when it is applied.

Row 20 is the shape this whole document prefers: the relation was **deleted**
rather than guarded. Three modules were about to hold the same placeholder rule;
two already did, and they had silently diverged — only `template_contract`'s
pattern captured the placeholder's name, which its `findall` depends on. Sharing
one object makes the agreement structural. Prefer this to a new assertion
whenever the two places can actually import each other; a row that says
*relation removed* is the best outcome available.

Row 19 is row 15's other half, and it had already drifted when it was written:
`core/templates/en/project-note.md` says `## Overview` while the vocabulary knew
only `project overview`, so every note written from this project's own English
template reported its goal as missing. The digest side was derived from a
contract and stayed correct; the project-note side was hand-copied and did not.
Writing the assertion is what found it.

## What the guards are not

**Not automatic discovery.** This list is maintained by hand. That is the price
of covering relations a scanner cannot see — "a rule should state its scope" is
not a decidable property, and neither was #95's directory-versus-type mismatch
until someone named it.

**Not guards for the guards.** A meta-test asserting each registry row has a
live assertion would be one more hand-kept mirror, with the same failure mode
and no third level to catch it.

**Not coverage of everything the guard is named after.** Row 17 was created by
#114, which shipped a parity assertion in the same commit that created the
boundary — and was then broken by the very platform gap that assertion was
written for, because it reads `install.ps1` while the drift was in
`tests/windows_installer_smoke.ps1`. The guard was real and its name was
accurate; its scope was narrower than a reader would assume. A row records what
a guard covers, not what it is called. The row itself was also missing until the
next day: writing the gap into a commit message put a known risk somewhere
nobody reads, which is the shape of #92.

**Not a substitute for judgement.** Two of the seven instances — the author's
`head -1` sampling read as a full survey, and a drift assertion written as
"equals the peer's entire set" — are method errors no assertion could have
prevented. They were caught by tests written before the code, which is a
different discipline and remains necessary.

## Registering a new relation

When a change makes two places have to agree, it needs a row here and an
assertion, in the same change that creates the dependency. Waiting means the
first drift is found by a user.

Signals that a boundary is being created:

- A constant restating something another module already declares
- A list duplicated because importing across the two bundles is not allowed
- Documentation naming a capability, code, or path the code also names
- Anything copied "because the build syncs it anyway"

If the relation cannot be asserted mechanically, the row still belongs here
with its guard recorded as **none** and a reason. Row 16 spent months that way
and was the last such row; writing it down is what eventually got it guarded,
which is the point — an unguarded boundary that is written down is a known
risk, one that is not is a surprise waiting.

Being written down is not the same as being guarded, and neither is having a
test. Row 16's first guard enumerated the five known host directories, so a
brand-new host added to one installer was invisible to the check on the very
script that introduced it: the assertion passed on exactly the case it existed
to catch. It was found by breaking the code on purpose, never by running the
suite. Discovering the host instead of listing it is what made it real.

## Rejected: deriving the inventory from code

Scanning for duplicated literals would find some rows and miss the ones that
matter. #95's boundary was a directory layout disagreeing with a frontmatter
field; #108's was a module list disagreeing with an import graph across a
packaging step. Neither is textual duplication. A tool that found rows 9 and 12
while missing 8 and 10 would be worse than this list, because it would look
complete.
| 72 | The evidence source `review-captures` **names** ↔ the source it actually dated each capture from | `test_the_report_counts_how_many_captures_each_evidence_source_actually_covered` and `test_the_capture_reference_documents_the_evidence_fields_the_helper_emits`. `evidence` is one word for a decision made per note, so it can be true and misleading at once — and was: `_git_last_revision` keyed the map on git's C-quoted output, so every non-ASCII path missed and the note fell through to mtime while the report still said `git-history`. On the reference Vault the captures split **3 / 97** before the fix and **100 / 0** after. The failure is silent by construction — a fallback that works is indistinguishable from the preferred path unless something counts them — so the guard asserts the invariant `sum(evidence_coverage) == summary.captures` rather than any particular number. The reference page is in the relation because it tells an Agent which field to quote |
| 73 | The keys `LinkHistory` matches a target against ↔ the keys `LinkIndex` resolves one with | `test_link_history_matches_the_keys_the_link_index_resolves_by`. The audit resolves a bare target by filename, then by stem, and `dated_matches` by the stem with a `YYYY-MM-DD ` prefix removed; history must ask the same question of the past or the two disagree about what "the same note" is — and the disagreement is invisible, because both answers are well-formed findings. `strip_date_prefix` is shared rather than restated (`link_graph`), so only the name/stem pair can drift, and the guard builds an index and a history from one set of paths and asserts every key the index resolves is a key history holds |
| 74 | `FINDING_SEVERITY` ↔ the severity tables in `docs/rules-and-algorithms.zh.md` | `test_the_algorithms_doc_lists_the_severities_the_code_assigns`. The document enumerates every code under its severity **and states the count, twice** — once in a summary table and once above each list — which is what made it look maintained. Nothing checked it, and it had drifted for two releases: `duplicate-project-note` and `web-clip-captured-nothing` were missing from `defect` while the stated 19 read as authoritative. The guard compares both counts and the membership, because a count that agrees with a wrong list is the failure mode a count alone invites |
| 75 | `search_vault`'s note-size ceiling ↔ `review_projects`' | **relation removed** — one `MAX_NOTE_BYTES` in `note_catalog`, imported by both; `test_the_vault_walkers_share_one_note_size_ceiling` asserts identity by object, so an equal copy fails, and scans the package for a module that grew its own literal beside the import. The two were `2 * 1024 * 1024` each with nothing relating them, and equality is exactly what hid that they were two decisions: a note one walker refuses and the other loads is one file with two answers, neither of which says why |
| 76 | `OBSIDIAN_KB.md`'s always-loaded ceiling ↔ `RETRIEVAL.md`'s | `test_retrieval_core_body_is_bounded_too`. Both bodies load on every invocation of their Skill and both cost tokens on every call, but only the first was bounded (`< 45` lines); the second stood at 129 with nothing watching it. The asymmetry was the defect, not the size — the numbers differ on purpose, because retrieval's six operation sections must show their steps *before* the agent picks a reference. Held at exactly the current count with no slack, so growth has to edit the guard, which is the moment to ask whether the material belongs in `references/` instead |
| 77 | The `web-clip` template's sections ↔ the deep-capture contract the audit grades it against | `test_the_web_clip_template_satisfies_the_contract_it_ships_with`. `scaffold-templates` writes the template into a Vault and the audit then grades that same file; drift means the Skill ships a template its own audit calls `outdated-deep-capture-template` — a `defect` — on installation day, and every note created from it inherits the mismatch. The contract is a **subsequence** check, which is what let #87's action section be added without a contract bump: raising `DEEP_CAPTURE_CONTRACT_EFFECTIVE_DATE` would have exempted every note written between the old and new dates from the ordering rule as well, a silent loss of coverage in exchange for a section nobody was required to write. So the guard asserts ordered equality *after removing a declared extras list*, and fails on an undeclared extra — a template cannot grow a section unnoticed, and cannot drop or reorder a required one either. Both locales are covered; the English template was found out of step the moment the assertion was widened to it |
| 78 | `ACTION_HEADINGS` ↔ the one heading each template puts a `- [ ]` under | `test_the_action_headings_match_the_templates_that_declare_them`. The retrieval bundle ships no templates, so `review-open-loops` cannot read them at run time and the set is restated in `action_heading_contract`. The direction that matters is the quiet one: a template gaining an action section would otherwise be invisible to the queue with the suite green — which is exactly what #87's hand-written vocabulary was, covering 20 of 138 items while reading as authoritative. Both the headings and the template each is attributed to are asserted, because an entry naming the wrong template is a comment that lies. Verified red in both directions: adding a section to a template, and mis-attributing an existing one |
| 79 | Every helper that exists ↔ the capability table a reader looks it up in | `test_the_feature_guide_only_advertises_helpers_that_exist`, extended. The assertion was `cited <= helpers` — a subset, so it only ever caught the loud failure of advertising something absent. The quiet one went unguarded and had accumulated three: `resume-project` and `review-captures` for releases, and `review-open-loops` on the day it shipped, with the suite green throughout. #90 already shipped two helpers nothing referenced; this is the same shape one document over. The reverse check searches the whole file rather than the table's last column, because `capture-receipt` and `scaffold-templates` are named by their console script (`obsidian-capture-receipt`) — a narrower extraction would have reported two false positives and been loosened back |
