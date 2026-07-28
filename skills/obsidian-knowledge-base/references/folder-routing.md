# Crowded Folder Routing (conditional reference)

Load this reference only when compact `vault-info` reports the selected
destination in `crowded_folders`. Folder pressure is a navigation signal, not
permission to mutate the Vault.

## Choose the Destination

1. Reuse an existing governed child category when the new note clearly belongs
   there.
2. Propose a new child only when at least five existing or imminent notes form a
   stable subject cluster.
3. Name it by durable subject. Do not name a category after a date, source site,
   author, or the current article title.
4. Keep paths to at most two category levels beneath the managed root.
5. Never create a one-note directory.
6. If no stable cluster exists, keep the current category and rely on its index,
   tags, links, and search.

Do not list or read every note by default. Use the bounded filenames already
returned by the index helper, then inspect only the small set whose titles or
tags could support the proposed cluster.

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
