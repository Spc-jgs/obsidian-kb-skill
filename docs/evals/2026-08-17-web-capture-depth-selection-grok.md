# Web Capture Depth Selection — Second Reference Agent (2026-08-17)

**Conclusion: the candidate instruction change is not merged, because there is
nothing left for it to fix.** On the reference Agent this project now runs, the
depth selection #74 was opened about is correct **12 out of 12** times against
the current instructions. Changing prose that produces 12/12, on the strength of
a diagnosis validated only against a model no longer in use, would risk what
works for a repair that cannot be verified.

This document records the measurement, what it establishes, what it does not,
and six defects found on the way — two in the scorer, two in the new backend,
two in the fixture.

## What #74 asked for, and what could not be met

Acceptance criterion 1 reads: *"使用同一模型、prompt、Skill revision 与 source
snapshot 重跑 12 次 standard 基线"*. That criterion is unmeetable as written and
the reason is not technical. The v1.30 baseline was measured with Codex CLI and
`gpt-5.6-sol`; this project does not run that product. Its 8/12 is therefore no
longer a comparable baseline, and the fixture's `reference_agent` block records
the product a stored baseline came from rather than pinning every future run.

The criterion's *intent* survives, with the absolute bar replaced by a
**within-agent comparison**: freeze a baseline on master with one Agent, then run
the candidate wording with the same Agent, same machine, same day, same scorer.
That is a stricter control than comparing against v1.30 ever was.

`summary.json` now carries `agent`, `agent_version`, and
`comparable_with_fixture_baseline`, so a reader cannot mistake one product's
numbers for another's.

## Why grok and not the first choice

The isolation this eval depends on is a redirected `HOME`, and it is not
optional:

- `~/.agents/skills/obsidian-knowledge-base` on the machine used here is a
  symlink to an **installed copy of the very Skill under test**. A run with the
  real `HOME` may load that copy instead of the workspace one, and would then be
  measuring a different revision than the one on disk in this checkout.
- `run_helper.py:49` resolves the runtime record from `Path.home()`, so the
  helpers would read the operator's install rather than the disposable one.

The first product tried keeps its credential in the system keyring bound to the
real `HOME` and demands an interactive login under a redirected one — three
probes stopped at the same place, and copying the token file or symlinking the
config directory did not change it. A batch run cannot answer a login prompt.

grok keeps its credential in a file, so the disposable `HOME` can carry exactly
that one file and nothing else. Measured in the workspace it produces:

| Question | Answer |
|---|---|
| `echo $HOME` | the disposable directory |
| Skills in scope | `obsidian-knowledge-base`, and only it |
| The operator's other 20 global Skills | out of scope |
| `run_helper.py vault-info` | runs |

**Only the credential is copied, never the configuration.** The operator's
`~/.grok/config.toml` enables a plugin and pins a reasoning effort; importing it
would make the eval measure the operator's setup alongside the Skill. Model and
effort are passed as flags so a summary states them rather than inheriting them
invisibly.

## What isolation is actually established by

| Mechanism | How it is known |
|---|---|
| Each run in a `TemporaryDirectory` | destroyed with the run |
| `HOME` redirected into the workspace | probe reported the disposable path |
| Only the workspace Skill in scope | probe listed exactly one |
| Helpers read the disposable runtime | `run_helper.py` resolves from `Path.home()` |
| No network acquisition | `--disable-web-search`; the source is an inline snapshot at an `.invalid` URL |

**`isolation-breach` establishes none of it.** That check looks for the
operator's own Vault path in the transcript, taken from `OBSIDIAN_KB_VAULT` —
which is unset on this machine, so the check had no subject and could not fire
in any run reported here. A guard with nothing to check reads from a summary
exactly like a guard that passed, so runs now report
`isolation_check: no-operator-vault-to-compare` instead of staying silent. Zero
hard failures is not evidence of isolation; the table above is.

## Result

Four `standard` cases, three repeats each, `grok-4.6` at medium reasoning effort,
against the instructions on master.

| Case | Depth correct | Hard failures | Soft score |
|---|---|---|---|
| `standard-versioned-tutorial` | **3/3** | 0 | 1.0, 1.0, 1.0 |
| `standard-material-diagram` | **3/3** | 0 | 0.84, 1.0, 1.0 |
| `standard-qualified-benchmark` | **3/3** | 0 | 0.857, 1.0, 1.0 |
| `standard-resource-comparison` | **3/3** | 0 | 0.978, 1.0, 0.978 |

Depth was confirmed by reading `capture_depth` in the written notes, not only
from the score: fifteen notes were written across the baseline and the discarded
runs below, and every one of them says `capture_depth: standard`.

`standard-material-diagram` was run twice. The first three runs are **discarded**
and are not in the table: the grok backend was dropping the material asset, so
the case whose prompt says the diagram is key evidence was never handed one, and
its prompt's "the attached image" pointed at nothing. The runs above are after
that repair, with the image path named in the prompt. Depth was 3/3 both times.

**Correction to an earlier draft of this document**, which said those runs were
"never shown" the image. They were not *given* it, but `scaffold_workspace`
copies the asset into the workspace, and the transcripts show all three finding
it and issuing `read_file` against the `.webp` anyway — as do all three of the
repaired runs, six for six. The defect was that the eval left this to chance:
an agent that did not think to explore would have written the note blind, and
nothing would have said so. That is now a hard failure, `material-not-inspected`,
checked against the transcript rather than the note.

Against v1.30's 8/12 with the other product, concentrated in the two cases that
misupgraded 2 times in 3 each:

| | `gpt-5.6-sol` (v1.30) | `grok-4.6` (today) |
|---|---|---|
| All twelve | 8/12 | **12/12** |
| The two misupgrading cases | 2/6 | **6/6** |

If grok's true rate matched codex's on those two cases, six correct in a row has
probability `(1/3)^6 ≈ 0.0014`. The difference is not sampling noise.

## What this establishes, and what it does not

**Established**: with the current instructions and this reference Agent, standard
captures are not upgraded to verified. There is no defect to observe, so there is
no signal a wording change could move, and the prediction registered before the
run — *"if the baseline is already 12/12 the change has nothing to measure and
should not be merged"* — decides the matter.

**Not established**: that the instructions are unambiguous. The ambiguity
diagnosed on the issue is really present in the prose. `web-capture.md` says to
select `verified` when the user asks to *verify*, *research deeply*, *reproduce*,
or *compare evidence*, and those words also occur when a request describes what
the **source contains** — "保留…验证和失败边界", "配图是关键证据". Nothing in the
text separates a request to perform verification from a description of material
that is about verification. grok is not fooled by it; that is a fact about grok.

A note on provenance: the issue comment that diagnosed this named
`deep-capture.md` as where depth is chosen. The selection rule is in
`web-capture.md:26`; `deep-capture.md:12` only echoes it. The quotation was
accurate and the attribution incomplete — the same shape as #133, where a
mis-attributed quotation led an issue to propose the wrong fix.

## Defects found on the way

**Scorer, two — both pre-existing, both false positives, neither backend-specific.**

1. Chinese negation was recognised only as `未`/`没有` before one of four writing
   verbs. A note recording the source's own `不支持 Python 3.10` — a *required
   fact*, and the exact opposite of a forbidden claim — was graded as asserting
   it, and the hard gate stopped the run. Negation is now the closed class of
   particles before any predicate, matching how one English `not` already
   negates its clause.
2. `，` was not a clause boundary, so `原文把 2.4.1 和 Python 3.12 绑定，并单独
   排除 3.10` put both terms of a forbidden claim in one "clause" from two
   statements that each say something else. Chinese chains independent clauses
   with `，` where English starts a new sentence; English `,` is deliberately
   still not a boundary, and a genuine assertion still sits inside one comma
   clause, so the gate keeps its bite.

The Codex baseline never hit either. That is not the scorer being sound — it is
one product's phrasing happening to miss two traps.

**Backend, two — both mine, both introduced in this change.**

3. The grok backend accepted the `material` argument and never used it, so the
   one case whose prompt says the diagram is key evidence ran with nothing
   attached. Backends now declare `attaches_material`, and one that cannot
   attach is given the path in the prompt.
4. `isolation_check` did not exist, so a vacuous check was indistinguishable
   from a passing one. Described above.

**Fixture, two — filed rather than fixed here, since neither is #74's question.**

5. **#146**: `standard-material-diagram`'s five required facts all appear in its
   own `source_markdown`, while the source states that the text does *not*
   specify what the diagram adds. The case can score full marks without opening
   the image it exists to test — #117's shape again.
6. **#147**: required facts are English literals against Chinese prompts. In
   `standard-qualified-benchmark`, one repeat scored 2/7 with a Chinese note and
   two scored 7/7 with English ones, missing **exactly** the five English words
   while still matching `40%` and `1000`. `soft_score` is therefore partly a
   measure of output language, which also contaminates #74's third acceptance
   criterion.

   The issue as first filed claimed `standard-material-diagram` showed the same
   thing, on the strength of a similarly shaped spread. It does not: after the
   material repair, that case's low repeat and its perfect one were **both**
   written in Chinese, 1535 bytes against 2149, so its variance is thoroughness
   and not language. Corrected on the issue. Two similar-looking spreads are not
   two instances of one cause until each has been checked, and this one was
   written down before it was.

## Every new guard was seen red

Nine guards were added across the backend abstraction and the scorer repairs.
Each was broken on purpose and the failing test recorded:

| Broken | Test that caught it |
|---|---|
| grok `HOME` → real home | `test_every_backend_points_the_agent_at_the_disposable_workspace` |
| web search re-enabled | `test_no_backend_lets_the_agent_reach_the_network_for_source_material` |
| unfinished commands counted | `test_a_grok_command_still_running_does_not_prove_a_receipt` |
| helper output not stripped | the grok half of the receipt test |
| narration kept in the final message | `test_the_final_message_is_the_last_turn_and_not_the_whole_run` |
| config file copied too | `test_no_backend_copies_anything_but_a_credential_out_of_the_real_home` |
| Chinese negation reverted | `test_a_chinese_note_recording_what_a_source_excludes_is_not_asserting_it` |
| `，` no longer splits | `test_two_chinese_statements_joined_by_a_comma_are_not_one_claim` |
| everything counted as negated | seven tests, including the Chinese hard negative |
| grok claims it attaches material | `test_every_backend_either_attaches_the_material_or_is_told_to_name_it` |
| material path dropped from prompt | `test_a_backend_without_attachments_is_told_where_the_material_is` |
| isolation check always "checked" | `test_a_run_says_when_the_isolation_check_had_nothing_to_compare` |

One of them was hollow on its first draft. The English half of the comma test put
both claim terms on the same side of the comma, so it passed whether or not `,`
was a boundary — it asserted something true and defended nothing. Replaced with
terms that straddle the comma, which then failed correctly when the boundary was
added.

## What would reopen this

- **A reference Agent that reproduces the misupgrade.** The candidate wording is
  recorded on #74 and can be tested against it the same way. The diagnosis is
  unchanged; only the evidence for acting on it is missing.
- **A real capture, unprompted by an eval, that upgrades to verified because the
  source is about evidence.** One instance is worth more than the whole synthetic
  set, because it is not built from anyone's picture of the failure.
- **#147 being fixed**, which would make `soft_score` mean what it claims and
  make acceptance criterion 3 checkable at all.
