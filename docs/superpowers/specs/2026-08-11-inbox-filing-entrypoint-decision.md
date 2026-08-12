# Inbox Filing Entrypoint — Decision Record

**Status: accepted.** Records the boundary decisions required before
`process-inbox` gets an Agent-reachable entrypoint. Implementation follows in
the same change; this document exists because two of the decisions are not
recoverable from the diff.

## Why this document exists

`process-inbox` has been implemented, tested, registered in
`[project.scripts]`, listed in `skills/obsidian-knowledge-base/scripts/run_helper.py`
under `HELPERS`, and advertised in `docs/feature-guide.md` as an Inbox filing
capability. It ships to every user's disk on install.

No Agent can reach it. `core/` contains zero references to it: the routing table
in `core/OBSIDIAN_KB.md` has no branch that selects it, no
`core/references/*.md` describes its workflow, and the `description` in
`skills/obsidian-knowledge-base/header.md` contains no trigger vocabulary for
filing an Inbox. The capability is delivered and unreachable at the same time.

Connecting it is not a matter of adding one routing line. It collides with the
Skill's bounded-write contract, and resolving that collision requires a
deliberate decision that a future reader would otherwise have to re-derive —
and could easily re-derive wrongly, in the direction of loosening a safety
boundary that should not be loosened.

## Decision 1: filing is not authoring, and the `≤1 note written` bound does not apply to it

`core/OBSIDIAN_KB.md` states the bounded-write contract:

> **Stay bounded**: ≤10 files scanned, ≤1 note written, ≤5 wikilinks.

A naive reading says Inbox filing violates it: an Inbox with thirty quick
captures would touch thirty notes in one run. That reading is wrong, and the
correct one has to be written down.

**`≤1 note written` bounds authoring, not custody.** It exists to stop an Agent
from generating a pile of new notes from one conversation — the failure mode is
an Agent that decides, unprompted, that your remark deserves four notes. Every
note it bounds is a note that did not exist before the Agent produced it.

Inbox filing authors nothing. Each note already exists, was already written by
the user, and already survived the explicit-save-intent gate when it was
captured. Filing moves a note into its governed folder, fills in `date`, `type`
or `tags` that the quick capture omitted, and appends an index line. The count
of notes in the Vault is identical before and after. There is no new claim, no
generated prose, no invented link.

The two operations are different in kind, and the vocabulary should say so:

- **Authoring** — bringing a note into existence. Bounded at `≤1` per request.
  `create-note` is the only helper that authors.
- **Filing** — moving an existing note into its governed destination and
  completing metadata the capture omitted. Bounded by Inbox size, not by `≤1`.

**Consequence**: filing needs its own bound, since the authoring bound does not
constrain it. That bound is the Inbox itself — a run files what is in the Inbox
and nothing else. It never reaches outside `--inbox`, which
`resolve_target_within_vault` already enforces, and it never authors a note to
hold content it could not classify.

**Rejected alternative**: route Inbox filing through the single-note path, one
note per user request. This keeps one number in the contract, and it is
unusable — an Inbox of thirty notes would take thirty round trips, which is
precisely the friction that leaves an Inbox unfiled in the first place. It also
misrepresents the risk: thirty moves of user-authored notes are safer than one
Agent-authored note, because no new content enters the Vault.

## Decision 2: filing is a two-phase authorization, and the plan is not optional

`process-inbox --apply` moves files, rewrites frontmatter, and appends to static
`INDEX.md`. It is a write path, and the Skill's first rule governs it:

> This skill **never writes to the vault on its own**.

Explicit intent to file the Inbox authorizes *producing a plan*. It does not
authorize executing it. The two phases stay separate:

1. **Plan** — `process-inbox <vault> --plan --json`, read-only. Every note's
   destination, inferred type, and metadata additions are shown to the user.
2. **Apply** — `process-inbox <vault> --apply` runs only after the user
   confirms *that plan*.

This mirrors the established `create-note --preflight-json` → `--apply` shape,
so filing introduces no new authorization concept — it reuses the one the Skill
already has.

**The plan phase is mandatory even when the user's request sounds decisive.**
"整理一下 Inbox" is intent to file, not consent to a specific set of thirty
moves the user has not seen. Destinations are *inferred* — from note type when
present, from body keywords when not — and keyword inference is exactly the
step a user must be able to veto per note. An Agent that skips the plan is
guessing on the user's behalf and then acting on the guess.

**Consequence**: a user asking to file an Inbox will always see one plan before
anything moves. This costs one extra round trip and is not negotiable.

**Rejected alternative**: allow `--apply` directly when the user's phrasing is
imperative enough. This makes the safety boundary depend on how a request was
worded, which is the least reliable signal available and the easiest for a
future Agent to rationalize past.

## Decision 3: the entrypoint reaches only `process-inbox`, not `audit-vault`

`audit-vault` is unreachable for the same reason and is deliberately left that
way in this change.

It is read-only, so it needs no authorization design — but it does need a
placement decision. Semantically it belongs to the read-only Skill; mechanically
it imports `deep_capture_contract`, `capture_receipt`, and
`folder_index_policy`, so placing it there means adding write-side modules to
`build.py`'s `RETRIEVAL_HELPER_FILES` allowlist and inflating a bundle whose
value is being small.

That trade-off is independent of Inbox filing and is not resolved here.
Bundling the two would hide a real decision inside an unrelated change.

**Resolved separately in #96 (2026-08-12): the audit lives in the write
Skill.** The trade-off was settled on measured cost. `audit_vault`'s transitive
dependency closure is 13 modules; the read-only bundle carries 10 and would
need 9 more, taking its Python payload from 98 KB to 217 KB — a 121% increase
for a bundle whose value is partly that it is small. Nearly every addition is a
write-side contract (`capture_receipt`, `deep_capture_contract`,
`conversation_digest_contract`, `template_contract`, `folder_index_policy`), so
placing the audit there buys semantic purity — an audit is read-only — with
semantic impurity: a Skill that promises never to write, shipping a complete
set of write contracts. The write Skill already holds those dependencies, and
the repair a finding suggests would happen there anyway.

## Scope of this decision

**In scope**: one routing branch in `core/OBSIDIAN_KB.md`, one workflow
reference at `core/references/process-inbox.md`, and trigger vocabulary in
`skills/obsidian-knowledge-base/header.md`.

**Out of scope**: any change to `process_inbox.py` itself. The helper's
behavior — inference rules, refusal codes, index handling — is already
implemented and tested. This change makes it reachable; it does not redesign it.

The lazy-loading contract holds: the workflow lives in `core/references/`, and
the always-loaded body in `core/OBSIDIAN_KB.md` grows by one routing line.

## Terminology fixed by this decision

- **Authoring** — bringing a note into existence. Bounded at `≤1` per request.
- **Filing** — relocating an existing note into its governed destination and
  completing metadata the capture omitted. Authors nothing; bounded by Inbox
  contents.
- **Filing plan** — the read-only output of `--plan`, enumerating each note's
  destination and metadata changes. The object the user authorizes.

## Why no `CONTEXT.md` or `docs/adr/`

The `domain-modeling` skill's default layout is a root `CONTEXT.md` glossary and
`docs/adr/`. This repository already records decisions as dated documents under
`docs/superpowers/specs/` — `2026-08-01-backup-boundary-decision.md` is the
precedent this file follows. Introducing a second decision location would split
the record. The terminology above stays here rather than in a new root-level
glossary for the same reason.
