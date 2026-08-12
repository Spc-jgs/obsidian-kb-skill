# Crowded Folder Routing (conditional reference)

Load this reference only when compact `vault-info` reports the selected
destination in `crowded_folders`. Folder pressure is a navigation signal, not
permission to mutate the Vault.

## What these rules govern

**Taxonomy folders** — folders whose members share a subject, where crowding is
what drives a split. `20-Learning` and `30-Insights` are taxonomy folders, and
everything below is about them.

**Entity folders are excluded.** They group members by what they *belong to*
rather than what they are *about*: `40-Projects` holds one directory per
project, and that directory holds the project's heterogeneous output — a status
note, designs, retrospectives, meeting records. The thresholds below are
meaningless there. A project starts with exactly one note, so rule 5 would
forbid the correct structure; its retrospective and its meeting notes share the
directory without sharing any subject, so rule 2's cluster evidence never
appears. An instance directory exists because the project exists.

Applying these rules to an entity folder is not a hypothetical mistake — it is
what produced #95. See
`docs/superpowers/specs/2026-08-12-entity-folder-routing-design.md`.

## Read the Signals You Already Have

The crowded entry answers both routing questions without opening a single note:

- `child_folders` — the governed children that already exist here.
- `clusters` — subject terms shared by enough notes to justify a child, each
  with the number of notes that carry it, counted from tags and title tokens.
  Type-default tags are excluded, so what remains is subject, not paperwork.
- `cluster_min_notes` — the bar a cluster must clear, which is the same five
  notes rule 2 states below.

An empty `clusters` list is an answer: this folder is crowded but has no stable
subject to split off. Do not open notes to look for one.

A missing `clusters` key is different from an empty one: discovery analyzed
other folders first and stopped at its budget. The selected destination is
always analyzed, so this only appears on folders you are not writing to. If you
change the route, rerun discovery with `--folder <new-route>` rather than
reading the folder yourself.

## Choose the Destination

1. Reuse an existing governed child category when the new note clearly belongs
   there.
2. Propose a new child only when at least five existing or imminent notes form a
   stable subject cluster — a reported cluster at or above `cluster_min_notes`,
   or the same evidence from notes the user is about to add.
3. Name it by durable subject. Do not name a category after a date, source site,
   author, or the current article title.
4. Keep paths to at most two category levels beneath the managed root.
5. Never create a one-note directory. (Taxonomy folders only — an entity
   folder's instance directory begins with exactly one note.)
6. If no stable cluster exists, keep the current category and rely on its index,
   tags, links, and search.

Do not list or read every note by default. Judge from the reported clusters;
read notes only when the user disputes the routing and names what to check.

## Confirm Before Creation

Show one proposed full Vault-relative category path and tell the user they may
rename it. Do not silently create it or move historical notes.

After explicit approval, use the existing governed workflow:

```bash
python <skill-root>/scripts/run_helper.py create-category <vault> \
  --folder <approved-path> --preflight-json

python <skill-root>/scripts/run_helper.py create-category <vault> \
  --folder <approved-path> --apply --confirmed --compact-json
```

Then route the requested new note into that existing category. `create-note`
will reject a missing destination folder; never bypass the confirmation by
creating directories with another tool.

Historical rebalancing and wikilink rewrites are separate, explicitly reviewed
work. Do not combine them with ordinary note creation.
