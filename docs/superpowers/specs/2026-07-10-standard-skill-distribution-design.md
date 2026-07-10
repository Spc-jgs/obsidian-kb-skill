# Standard Skill Distribution and Runtime Design

## Goal

Turn `obsidian-knowledge-base` into a standard, installable Skill whose installed
copy remains fully usable after the source checkout is removed. A successful
installation must let an agent load lazy references, execute every bundled
helper, scaffold templates, create and update notes, and audit the result.

## Product Contract

A standard installed Skill is a product-owned directory with this shape:

```text
obsidian-knowledge-base/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── *.md
├── scripts/
│   ├── run_helper.py
│   └── obsidian_kb_skill/
│       └── ... bundled Python implementation ...
└── assets/
    └── templates/
        ├── *.md
        └── en/*.md
```

`skills/obsidian-knowledge-base/` is the canonical standard Skill payload.
`build.py` generates or synchronizes every derived file in that payload from
the existing sources of truth:

- `core/OBSIDIAN_KB.md` and `skills/obsidian-knowledge-base/header.md` produce
  `SKILL.md`;
- `core/references/` produces `references/`;
- `core/templates/` produces `assets/templates/`;
- `obsidian_kb_skill/` produces the bundled helper package under `scripts/`,
  excluding build artifacts and the package-data resource copy that the Skill
  resolves through `assets/` instead.

`build.py --check` must compare complete expected trees, including missing,
changed, and unexpected files. A green build gate must prove that platform
references, wheel resources, Skill assets, and bundled helper code are all in
sync.

## Helper Runtime

`scripts/run_helper.py` is the single Skill-local launcher. It accepts one of
these stable helper names and forwards the remaining arguments unchanged:

```text
audit-vault
process-inbox
suggest-links
create-note
update-note
vault-info
detect-index
scaffold-templates
```

The launcher adds the Skill's `scripts/` directory to `PYTHONPATH`, sets
`OBSIDIAN_KB_SKILL_ROOT` to the directory containing `SKILL.md`, and invokes
the corresponding `obsidian_kb_skill.scripts.*` module. The resource locator
accepts a standard Skill root containing `assets/templates/` and
`references/`.

The installer selects a Python 3.11-or-newer interpreter and records its command
as JSON under `~/.obsidian-kb-skill/runtime.json`. If that interpreter cannot
import PyYAML, the installer installs `PyYAML>=6` into the product-owned
`~/.obsidian-kb-skill/vendor/` directory. The launcher prepends this directory
to `PYTHONPATH`. It falls back to its current interpreter when run directly
from a source checkout without an installer runtime record.

This keeps dependencies out of global site-packages, avoids modifying shell
profiles, and leaves the installed Skill independent of the checkout.

## Platform Installation

Every installation creates the canonical support copy at
`~/.obsidian-kb-skill/skill/`, regardless of selected platform. Compatibility
adapters use this location for references, assets, and the helper launcher.

- Codex: install the complete standard payload at
  `~/.agents/skills/obsidian-knowledge-base/`.
- QoderWork: install the same complete payload at
  `~/.qoderwork/skills/obsidian-knowledge-base/`.
- Claude Code: keep the marker-managed `~/.claude/CLAUDE.md` adapter and state
  the canonical support-root path in its generated header.
- Cursor: keep the rule at `~/.cursor/rules/obsidian-kb.mdc` and state the
  canonical support-root path in its generated header.

Bash and PowerShell copy the same canonical payload tree rather than maintaining
separate filename lists. Platform parity is proven from actual installed file
sets, not from string searches in installer source.

## Install, Upgrade, and Uninstall Semantics

Installation and upgrade are idempotent:

- Skill-owned platform directories and the canonical support payload are
  refreshed to the exact current payload, so newly added resources appear and
  stale product files disappear.
- Vault templates and notes remain user-owned. They are created only when
  missing unless `--force` / `-Force` is supplied.
- A newly created or existing Vault path is canonicalized before it is written
  to `~/.obsidian-kb-config`.
- Unknown platform names and an unusable Python runtime fail the installation
  instead of reporting success.
- Post-install verification checks the reference tree and runs `vault-info`
  through the installed launcher from a neutral working directory.

Uninstall removes platform-owned Skill files, marker blocks, Cursor rules, and
`~/.obsidian-kb-skill/`. It preserves the Vault, notes, sibling skills, and
`~/.obsidian-kb-config` by default. `--purge-config` / `-PurgeConfig` explicitly
removes that configuration file.

Malformed shared-file markers are handled in a separate safety commit. A lone,
reversed, or duplicated marker causes a clear failure without modifying the
shared file.

## Functional Integrity Iteration

After distribution is complete, the helpers are exercised as an installed
product and the following existing contract gaps are repaired in separate
commits:

1. `update_note.py` creates the mandatory byte-for-byte backup under
   `.obsidian-kb-backups/<timestamp>/<relative-path>` before every in-place
   update and reports the backup path in text and JSON output.
2. `scaffold_templates.py` supports `--json` so all eight helpers have a
   machine-readable mode.
3. `detect_index.py` uses the valid `#!/usr/bin/env python3` shebang.
4. Documentation stops referring to the removed top-level `scripts/` package,
   distinguishes source-development console commands from installed Skill
   launcher commands, and accurately states the Python/PyYAML runtime boundary.

No installer run may silently create a sample content note. Note creation and
update are exercised only in tests and explicit forward-test fixtures.

## Verification

The release gate requires all of the following:

- `quick_validate.py skills/obsidian-knowledge-base` succeeds.
- `python build.py --check` succeeds and detects intentional drift in every
  generated resource tree.
- The complete pytest suite succeeds on Python 3.11 and 3.14.
- Bash black-box tests install from a disposable release tree into a temporary
  `HOME`, delete the release tree, and then read a reference, call every helper
  family, scaffold templates, create a note, update it with a backup, and audit
  the Vault from an unrelated working directory.
- Windows CI executes the PowerShell installer and the same installed-product
  smoke path; textual PowerShell assertions are not sufficient release proof.
- Upgrade restores missing payload files, removes stale owned files, and keeps
  edited Vault templates.
- Uninstall preserves sibling skills, Vault contents, and config by default;
  explicit purge removes config.
- Symlink Vault roots work, while traversal and out-of-root symlink targets
  remain rejected.

## Release

This is a new installation and runtime contract rather than a documentation-only
patch, so the release version is `1.11.0`. Update `pyproject.toml`, core version
metadata, both READMEs, and `CHANGELOG.md`. Create and push the tag only after
local gates and the pushed Linux/Windows CI matrix are green.
