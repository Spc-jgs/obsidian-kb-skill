# README Agent-First Installation Design

## Goal

Make the root README a stable product introduction instead of a second
changelog, and make asking an AI agent to install the Skill the primary setup
path for non-expert users.

## README Structure

Apply the same information hierarchy to `README.md` and `README_EN.md`:

1. product name, current version, value proposition, and language link;
2. problem and solution;
3. agent-first quick start;
4. usage scenarios and product explanation;
5. manual installation, configuration, maintenance, contribution, and reference
   material.

Remove the accumulated `v1.12` through `v1.19` feature sections. The README
keeps one compact current-version link to `CHANGELOG.md`; release history and
per-version details live only in the changelog.

## Agent-First Installation

The first installation path is a copyable prompt that asks the user's current
agent to install the latest release from the official repository. The prompt
must require the agent to:

- inspect the repository instructions and installer options before changing
  local state;
- detect the current supported agent platform;
- ask for the Obsidian Vault path when it cannot be determined safely;
- use the official installer for the selected platform;
- preserve existing user templates and Vault content;
- run installed-state `doctor --json` and report the installed version and
  paths.

The prompt must not embed a release number, clone destination, or platform
guess that will become stale. Git clone, ZIP download, direct file copying, and
manual installer commands remain available under a clearly secondary
manual/advanced installation section.

## Compatibility and Scope

- Keep all currently supported platforms and installer flags documented.
- Do not change installer behavior, Skill runtime instructions, templates, or
  release version.
- Keep Chinese and English README content structurally equivalent.
- Do not duplicate the changelog in collapsible sections or retain only a
  rotating list of recent releases; both approaches recreate the maintenance
  problem.

## Verification

- Assert both README files contain the agent-first installation heading and a
  copyable prompt before manual instructions.
- Assert historical `What's New` / `新增的能力` headings are absent.
- Assert both files link to `CHANGELOG.md` and retain platform, configuration,
  upgrade, uninstall, and contribution documentation.
- Run Markdown/link-oriented repository tests, the full test suite, generated
  artifact drift check, lock check, and `git diff --check`.

