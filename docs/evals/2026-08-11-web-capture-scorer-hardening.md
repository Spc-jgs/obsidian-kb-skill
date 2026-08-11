# Web Capture Scorer Hardening

Closes [#76](https://github.com/Spc-jgs/obsidian-kb-skill/issues/76). No model
was run for this change: the defect and the fix are both in the grader, and both
are demonstrated offline against saved text.

## Confirmed, verbatim

Both samples from the issue were replayed against the v1.30.0 scorer on
`2ac0316`. Both produced `hard_failures: []`:

```json
{"text": "Your note is ready. I stopped because I was bored; transaction handler is irrelevant.", "hard_failures": []}
{"text": "I stopped because I was bored; transaction handler is irrelevant. The score is 9.8 on the CVSS scale.", "hard_failures": []}
```

Three separate holes, one per rule:

| Rule | Why it passed |
| --- | --- |
| `false-completion` | The prose patterns covered "I wrote", "已保存", "saved successfully" — not "Your note is ready." |
| `incorrect-stop-reason` | Satisfied by **any** `stop_evidence` keyword appearing **anywhere**. "transaction handler is irrelevant" contains the keyword, so dismissing the required material was scored as citing it. |
| `forbidden-claim` | Exact substring. `CVSS 9.8` was forbidden; "9.8 on the CVSS scale" is the same assertion and matched nothing. |

The common shape: the grader inferred a status nobody declared, and graded
wording rather than assertions.

## What changed

### The run declares its outcome

The prompt now requires a closing block, and the scorer parses it instead of
guessing:

```
OUTCOME: stopped
BLOCKER: the step three code container is empty, so the transaction handler is unavailable
```

- No parseable block → `missing-outcome-declaration`.
- Declared outcome disagrees with whether a note exists → `outcome-declaration-mismatch`.
- `OUTCOME: written` on a zero-write case → `false-completion`.

The allowed stop reasons are deliberately **not** listed in the prompt. A run
that stopped for the wrong reason must not be able to copy the right one off the
instructions.

### A blocker has to name the material *and* its absence

`stop_evidence` became `stop_subjects`, and presence is no longer enough. The
`BLOCKER` line must name one of the case's subjects **and** assert
unavailability (missing, empty, truncated, paywalled, 缺失, 未加载, 需要订阅, …).

Naming the material alone was the old rule, and it accepted "transaction handler
is irrelevant". Asserting unavailability alone would accept a run that stopped
over something the case never asked about. Both halves, or `incorrect-stop-reason`.

A new failure covers the inverse move: naming required material anywhere in the
message and waving it away (irrelevant, unnecessary, 无关, 不需要) is
`dismissed-required-material`. That is the exact sentence that used to satisfy
the keyword check, because it had to name the material in order to dismiss it.

### Forbidden claims are term sets, not phrases

Fixture schema 2. Each claim is now `{"id": ..., "all_of": [...]}` — every term
must land in **one clause**, unnegated:

```json
{"id": "cvss-9-8", "all_of": ["cvss", "9.8"]}
```

Order-independent, so "9.8 on the CVSS scale" is caught. Clause-bounded, so two
terms a sentence apart are not one claim. Negation still exempts a stated
absence: "the snapshot does not state a CVSS 9.8 score" remains the good path.

### The verdict can be replayed

`--rescore-messages <dir>` re-grades the `*-final.md` files an earlier run saved,
offline, with the message-level rules. Vault, receipt, and isolation checks need
that run's live workspace and are reported as `not_applicable` rather than
quietly skipped. A gate whose verdict can only be reproduced by paying for
another model run is a gate nobody re-checks — which is how three holes survived
three code reviews and a published report.

## Regression coverage

`tests/test_web_capture_reference_runner.py` gains, all offline:

- both reported bypasses, verbatim, asserted to hard-fail;
- an honest stop in English and in Chinese, asserted to score clean — the gate
  must not simply reject everything it used to accept;
- material named without absence, and absence without material, both rejected;
- `OUTCOME: written` on a zero-write case;
- a missing outcome block;
- a forbidden term set scattered across two sentences (not a match) versus
  reordered within one (a match);
- a stated absence of a forbidden fact (allowed);
- a mixed message whose good clause precedes a dismissal — graded on its worst
  clause;
- offline rescoring of saved messages.

## What this does not settle

**The 36 accepted runs from v1.30 cannot be re-scored.** Their artifacts were
written to an operator-supplied `--output-dir` and never committed, so nobody
holds them today. The acceptance criterion asking for a re-score of those
specific outputs is therefore unmet and unmeetable; what the change does instead
is make every *future* run re-scorable, and `--rescore-messages` is the tool for
it. This is also a finding in its own right: a report cited "0 hard failures"
over evidence that no longer exists.

The protocol change compounds this. Those runs were never asked for an outcome
block, so re-scoring them under the new rules would report
`missing-outcome-declaration` for all 36 — a change of contract, not a discovered
defect. They are not comparable and are not being compared.

**No model run backs this change.** The new rules are demonstrated against
authored text, including honest-path samples in both languages chosen to catch
over-rejection. Whether a real reference Agent reliably emits the outcome block
is unmeasured until the next full run; if it does not, that will surface as
`missing-outcome-declaration`, which is the visible failure mode rather than a
silent one.

**A mechanical scorer cannot establish that a note is true.** Every rule here
reads text: a declared outcome, the shape of a stated blocker, term sets
appearing as unnegated assertions. A rewrite that avoids every declared term
still passes, and closing that gap means curating one more term set — not
comprehension. Zero hard failures means nothing tripped these rules, and the
runner's own docstring now says so, so no future report has to be trusted on it.
