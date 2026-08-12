# Vault Audit Workflow (reference)

Loaded only when the user asks to check, audit, or health-check the Vault. The
always-loaded skill body points here.

## The audit reports; it does not repair

`audit-vault` never writes and never repairs a note. It reads the Vault and
returns findings, and that is the whole of its job. A finding is a fact about
the Vault, not a task the Agent has been told to complete.

**Reporting a finding does not grant authority to fix it.** The user asked to
be told what is wrong, which is not the same as asking for it to be changed. A
repair is a separate request, and it goes through the ordinary write path with
its own explicit save intent. This matters most when a fix looks trivial — a
missing `date`, an obvious typo in a tag — because that is exactly when acting
without being asked feels harmless.

Never repair a note to make a finding disappear before reporting it.

## Step 1: Resolve & Validate Vault Path

Same as the Create workflow: env `OBSIDIAN_KB_VAULT` → `~/.obsidian-kb-config`
→ ask. Refuse unless a real Vault.

## Step 2: Run the Audit

```
python <skill-root>/scripts/run_helper.py audit-vault <vault> --json
```

Narrow it when the user asked something narrower:

- `--min-severity hygiene` or `--min-severity defect` when they want only the
  serious findings. Severity ranks `informational` < `hygiene` < `defect`.
- `--strict` makes the exit code non-zero when any finding exists. Use it only
  when the user wants a pass/fail gate; the default exit code says the audit
  ran, not that the Vault is clean.

Run the audit once. It scans the Vault itself, so do not pre-scan folders or
open notes to guess what it will say.

## Step 3: Report by Severity, Not by Count

Lead with `defect` findings, then `hygiene`, then `informational`. A count
alone ("47 findings") tells the user nothing about whether to care.

Group findings by kind rather than listing every occurrence: twelve notes
missing `tags` is one problem with twelve instances, not twelve problems. Give
the path and line for each finding the user is likely to act on, and say how
many similar ones were folded in.

Some findings are legitimate states, not errors. A `disconnected-note` may be
standalone knowledge that was never meant to link anywhere; a `duplicate-title`
may be two genuinely different notes. Report what the audit found and let the
user judge — do not translate a finding into a verdict about the note's value.

## Step 4: Offer, Then Stop

If the findings suggest work worth doing, say so and stop there. The user
decides whether any of it happens.

When they do ask for a fix, route it normally: an existing note follows
`update-note.md`, a missing category follows `missing-category.md`, an Inbox
full of unfiled notes follows `process-inbox.md`. The audit does not shortcut
any of those paths, and it does not batch them — the `≤1 note written` bound
still applies to whatever the user authorizes next.

## Refusals

Path and frontmatter guards refuse through the shared codes in
`rules-and-errors.md`. A refusal during an audit is reported like any other
finding: the Vault is left exactly as it was.
