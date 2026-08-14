# Run a Declared View (reference)

Loaded when the user names a saved view, or asks what views this Vault has.
A view is a search **the user already agreed on**, written into the Vault so it
runs the same way every time instead of being re-translated from words to flags
on each ask.

## Run it

```
python <skill-root>/scripts/run_helper.py run-retrieval-view <vault> \
  --view <id> --as-of YYYY-MM-DD --json
```

`--as-of` is required and you resolve it yourself, in the user's timezone. The
helper never reads the clock: a view whose window came from "now" gives
different answers on different runs, which is the opposite of what it is for.
"上周" is a phrase you turn into a date, never a value stored in the config.

One view per call. Running several is unbounded output by another name.

## What a view can and cannot say

A view declares **structured fields only** — no command, no pipe, no template,
no environment interpolation, and no field `search-vault` does not already have:

| Field | Meaning |
|---|---|
| `id` | The name the user calls it by |
| `query` | The search text |
| `types`, `tags` | The same filters `search-vault` takes |
| `scope` | A folder inside the Vault |
| `top_k` | How many results |
| `date_field` + `window_days` | A relative window, resolved against `--as-of` |

`date_field` is `date` or `updated`, and the two mean different things on
purpose — `date` is when the note was written, `updated` is when it changed. A
view picks one; it cannot blur them.

A view can only **narrow**. It reaches the same validated parameters a direct
call reaches, so it can never get past a guard a direct search would face.

## Read the plan, not just the results

`plan` is the resolved call — the actual scope, filters and dates, with the
relative window already turned into two ISO dates. It is there so the answer is
checkable: running that plan through `search-vault` directly gives the same
results, and saying "this came from the `recent-learning` view" without saying
what the view resolved to tells the user nothing they can verify.

The window appears as `after`/`before` or as `updated_after`/`updated_before`,
according to the view's `date_field`; the other pair is `null`. Which pair is
filled is itself information — it says whether this view is asking about when
notes were *written* or when they *changed*.

Report the window in dates. "The last 7 days" is what the config says;
`2026-08-08` to `2026-08-14` is what ran.

## Refusals

Structured refusal through `{"ok": false, "error": {"code", "message"}}`:

- `missing-view-config` — this Vault declares no views. That is the ordinary
  state for most Vaults, not a fault: say so and offer an ordinary search.
- `unknown-view` — no view by that name. The message lists the ones that exist;
  show them rather than guessing which the user meant.
- `invalid-view-config` — the file could not be trusted: malformed JSON, wrong
  `schema_version`, an unknown field, a duplicate `id`, or a value out of range.
  **Nothing runs.** A config that half-parsed would run a search the file does
  not describe, and the user would have no way to notice. Report the message and
  stop; this Skill never repairs the file.
- `invalid-view-scope` — the view scopes to a folder that is no longer there.
  This refuses rather than falling back to the whole Vault: a view that silently
  widened would keep working, return more than it ever did, and say nothing.

## Never edit the config

Creating or changing a view is a write, and it belongs to the user. If they want
a new view, show them the JSON to add and let them add it — this Skill does not
write to `.obsidian-kb/`, and a view the Agent invented is not a view the user
agreed on.

`.obsidian-kb/` is configuration, not knowledge: it is never searched, and its
contents never appear in results.

See `search.md` for how to read the results themselves, and `shared-errors.md`
for the path and Vault guards this helper shares with the rest of the Skill.
