# Entity Folders — Design

**Status: proposed.** Design for #95. No code changes with this document.

## Why this document exists

The Skill has exactly one way to think about folders: a folder accumulates
notes of a kind, and when it gets crowded you split it by subject. That model
is correct for `20-Learning`, and it is wrong for `40-Projects` — in a way that
produced three separate defects before anyone noticed they were the same
defect.

A project is not a subject that notes happen to share. It is an **entity** that
owns heterogeneous output: a status note, design documents, retrospectives,
meeting records, candidate lists. Those documents have nothing in common
topically. What they share is that they belong to one project.

Applying subject-clustering rules to entity grouping yields conclusions that
are individually reasonable and collectively wrong.

## The three symptoms

**One — the crowding rules forbid the right structure.**
`core/references/folder-routing.md:37` says "Never create a one-note directory"
and `:31` requires "at least five existing or imminent notes". A project starts
with exactly one note. The reference Vault's `40-Projects/skill-mining/` holds
two files and is obviously organised correctly; by these rules it should not
exist. Meanwhile `folder-routing.md:4` names the trigger — "Folder pressure is
a navigation signal" — which is the tell: these rules solve *too many notes to
navigate*, not *which notes belong together*.

**Two — routing lands project notes in the wrong place.**
`note_catalog.py:37` maps `project-note` to `40-Projects`, the top level.
`process_inbox.py:103-104` returns that mapping directly. Filing a project note
from the Inbox therefore drops it at the root, beside the project directories
rather than inside one. `create-note` does the same without an explicit
`--folder`.

**Three — the revival radar counts one project as several.**
`review_projects.py:331` identifies a project instance by frontmatter alone:

```python
if _scalar(metadata.get("type")) != PROJECT_TYPE:
```

The radar's granularity is per-note; an entity folder's granularity is
per-directory. They agree only while every project directory holds exactly one
`project-note`. Nothing enforces that. The reference Vault has two notes both
typed `project-note` and both belonging to one project (鹅天渠) — grouped into
one directory, that project reports as two candidates, each with its own
staleness and open-task count.

## The shared root cause

All three follow from the same missing distinction:

- **Taxonomy folder** — members grouped by *what they are about*. Splitting is
  driven by crowding; children are subjects. `20-Learning`, `30-Insights`.
- **Entity folder** — members grouped by *what they belong to*. Splitting is
  driven by the entity's existence; children are instances. `40-Projects`.

The Skill models only the first. Every rule that reads "folder" today silently
means "taxonomy folder".

A fourth symptom is worth naming because it constrains the fix: an entity
folder's root legitimately holds notes that are not instances. The reference
Vault's `40-Projects/2026-07-09 项目小结实践-让工作自己说话.md` is
`type: project-note` with `status: template` — a reusable card whose body reads
"照着填" and "占位，请替换为真实项目". It belongs to no project, so no
instance directory fits; it is not unfiled material, so `00-Inbox` is wrong,
and the Vault's governance would nag it as unsorted after seven days. Its
correct home is the entity folder's root. Any rule asserting "the root should
contain no project notes" would report it as a violation — the same shape as
#83, where `status: template` notes were treated as stale project instances.

## Decision 1: folder grouping semantics become an explicit property

Introduce the taxonomy/entity distinction as a declared property of a folder,
not as prose an Agent has to infer. `40-Projects` is the only entity folder in
the shipped layout; a Vault may declare others through its own governance.

The crowding contract in `folder-routing.md` is scoped to taxonomy folders. Its
thresholds and its one-note prohibition do not apply to entity folders, and the
reference must say so rather than leaving the exemption to be re-derived.

**Rejected:** special-casing `40-Projects` by name wherever a rule needs it.
That is how the current situation arose — the rules never claimed to be about
subject clustering, they simply never contemplated anything else. Naming the
category makes the next entity folder cost nothing.

## Decision 2: an entity folder's members are not homogeneous

Three member kinds are legal at an entity folder's root:

1. **Instance directories** — one per project.
2. **The folder's own index** — Folder Index requires the same-named file.
3. **Non-instance long-lived assets** — templates and conventions belonging to
   the entity folder rather than to any instance, identified by a `status` in
   `NON_INSTANCE_STATUSES` (introduced in #84: `template`, `模板`).

Any check for "stray notes at the root" must exclude the third kind. This is
stated as a decision rather than an implementation note because the mechanical
version of the rule — *the root should hold no `project-note`* — is the obvious
one to write and is wrong.

## Decision 3: one instance note per instance directory

An instance directory holds exactly one `project-note`. Everything else it
holds is subordinate output and carries its own type: `insight-note` for a
retrospective, `conversation-digest` for a context snapshot, `meeting-note` for
a meeting record.

This is the rule that reconciles "a project produces many files" with "the
radar counts project notes". Both are true; the type field is what separates
them. A retrospective is finished when written — it has no next step and should
not be asked about its progress — so typing it `project-note` is not a
classification preference but a factual error about the note.

## Decision 4: the radar stays per-note; an audit rule guards the invariant

The radar continues to identify instances by `type`. Decision 3's invariant is
enforced by a new audit finding rather than by teaching `review-projects` about
directories.

**Why not make the radar directory-aware.** It would have to fold multiple
`project-note` files in one directory into a single candidate — and then decide
which one's status, staleness date, and next action represent the project. That
choice has no correct answer when the two notes disagree, and inventing one
would hide the very error that needs surfacing. The radar's behaviour is also
locked by a large body of tests in `tests/test_review_projects.py`, and path
semantics would newly couple a module that today reads only frontmatter.

The cost is that a violation surfaces on audit rather than immediately. That is
acceptable because the violation is created by a human typing a note, not by
the Skill, and because the audit is now reachable (#96) — before that it would
not have been.

**Rejected:** silently deduplicating by directory in the radar. It converts a
visible wrong answer into an invisible one.

## Decision 5: filing never guesses which project a note belongs to

`process-inbox` must not drop a `project-note` at the entity folder's root, and
must not guess an instance directory from body keywords. Project membership is
not inferable from text with acceptable reliability, and a wrong guess files a
note into another project's directory, where it will be read as that project's
history.

The note stays in the Inbox with a refusal code. This is consistent with the
existing `unknown-target` contract and with the Vault governance rule already
written for this case: 归属不明的项目笔记留在 `00-Inbox/`，不落
`40-Projects/` 根级.

`create-note` with an explicit `--folder` naming an instance directory is
unaffected — that is the user stating the destination, not the Agent inferring
it.

## Decision 6: an instance directory is created when its first note exists

Not before. `40-Projects/值不值小程序/` in the reference Vault holds a
same-named index and zero notes — a container created for a project that never
started. Not after, either: waiting for a second document reintroduces the
crowding threshold this design rejects, and means the first note has to be
moved later.

## Non-goals

- Migrating existing Vaults. Notes already at an entity folder's root stay
  valid; this design defines where new ones go and what an audit reports.
- Declaring `30-Insights` or any other shipped folder an entity folder.
- Inferring project membership from note content, in any component.
- Changing `review-projects` output shape.
- Automatic creation of instance directories during filing.

## Implementation order

1. Audit rule for Decision 3, with the Decision 2 exclusions. Delivers the
   safety net before anything starts relying on the invariant.
2. Routing behaviour for Decision 5 in `process-inbox` and `create-note`.
3. Reference updates scoping the crowding contract to taxonomy folders.

Each step is independently shippable; step 1 has standalone value on the
reference Vault today, which already violates Decision 3.

## Acceptance

- Folder grouping semantics are declared, and no rule special-cases
  `40-Projects` by name.
- The audit reports two `project-note` files in one instance directory, and
  reports neither a legal subordinate document set nor a root-level
  non-instance asset. Hard negatives for both are required, not optional.
- Filing a `project-note` of unknown membership refuses with a code and leaves
  the note in the Inbox; it never lands at the entity root and never guesses a
  directory.
- `review-projects` behaviour is unchanged, with its existing tests passing
  untouched.
- The crowding contract states which folder kind it governs.
