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
| 16 | Installer paths ↔ Skill × platform matrix | **none — #91**, 20 hand-copied paths across two languages |
| 17 | Managed-link decision in `install.sh` ↔ `install.ps1` ↔ `tests/windows_installer_smoke.ps1` | `test_bash_install_does_not_clobber_a_managed_skill_symlink` (POSIX behaviour) and `test_powershell_installer_has_managed_symlink_parity` (reads `install.ps1` text only) — **the smoke script is unguarded**, and only Windows CI executes it |
| 18 | Headings the resume report calls recognized ↔ headings its matcher can match | `test_every_known_variant_is_both_matchable_and_reported_as_matched` |
| 19 | `core/templates/*/project-note.md` headings ↔ the resume vocabulary that reads them | `test_this_projects_own_templates_are_fully_readable_by_the_extractor` |
| 20 | The unreplaced-placeholder rule across `audit-vault`, `template-contract` and `process-inbox` | **relation removed** — one `TEMPLATE_PLACEHOLDER_RE` in `note_catalog`, shared by object; `test_the_placeholder_rule_is_the_audits_rule_not_a_second_copy` asserts identity so a local copy cannot come back |
| 21 | Default draft tag in `process_inbox` ↔ the reference an Agent reads | `test_the_filing_reference_names_the_draft_tag_the_code_defaults_to` |
| 22 | Next-actions headings in `review_projects` ↔ `resume_project` | **relation removed** — one `PROJECT_NOTE_NEXT_ACTION_HEADINGS` in `note_catalog`; `test_both_retrieval_helpers_mean_the_same_thing_by_next_actions` asserts both derive from it |

Guards 12, 13 and 14 were added by this work. The rest already existed; several
had caught the author earlier the same day. Row 17 arrived late, in #114 — see
below. Rows 18 and 19 came with #115.

Row 22 is the registry's first same-day catch of its own author. #125 widened
one of two vocabularies for *next actions* and left the other alone, without a
row — the rule this document sets, broken in the change made right after citing
it. Nothing failed: the radar kept working because it falls back to the first
checkbox anywhere in the note. It surfaced a few hours later while scoping that
very count to the section, where the drift would have zeroed out the one project
whose checkboxes all sit under the widened heading. An unregistered boundary
does not announce itself; it waits for the change that depends on it.

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
with its guard recorded as **none** and a reason. #91 has sat unguarded for
months precisely because nothing named it — an unguarded boundary that is
written down is a known risk; one that is not is a surprise waiting.

## Rejected: deriving the inventory from code

Scanning for duplicated literals would find some rows and miss the ones that
matter. #95's boundary was a directory layout disagreeing with a frontmatter
field; #108's was a module list disagreeing with an import graph across a
packaging step. Neither is textual duplication. A tool that found rows 9 and 12
while missing 8 and 10 would be worse than this list, because it would look
complete.
