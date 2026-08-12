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
tests, `build --check` and `doctor` all passed (#108). And twice the author's
own survey method produced a wrong premise that only a test caught.

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

Guards 12, 13 and 14 were added by this work. The rest already existed; several
had caught the author earlier the same day.

## What the guards are not

**Not automatic discovery.** This list is maintained by hand. That is the price
of covering relations a scanner cannot see — "a rule should state its scope" is
not a decidable property, and neither was #95's directory-versus-type mismatch
until someone named it.

**Not guards for the guards.** A meta-test asserting each registry row has a
live assertion would be one more hand-kept mirror, with the same failure mode
and no third level to catch it.

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
