# Obsidian Personal Knowledge Base — Universal Instructions

> **Version**: 1.12.0 · **Single source of truth**: `core/OBSIDIAN_KB.md`. Full workflows live in `core/references/*.md`, loaded only when about to save. This file is tiny on purpose: loading the skill costs almost no tokens, and the first rule is "do not auto-save".
> Do not edit generated files directly — edit this file, then `python build.py`.

## Overview

Agent-agnostic instructions to create, organize, and update notes in an Obsidian vault. Any tool that reads/writes local files can use it.

## DO NOT auto-save

This skill **never writes to the vault on its own**. Act only after **explicit save intent** ("save to Obsidian", "沉淀", "总结存档"). For Q&A, debugging, or casual chat: do nothing.

## When the user asks to save

1. **Find vault**: env `OBSIDIAN_KB_VAULT` → `~/.obsidian-kb-config` → ask. Refuse unless a real vault (`.obsidian/` + `Templates/`).
2. **Read the matching reference *before* writing**:
   - `note-creation.md` new note · `update-note.md` edit existing · `conversation-digest.md` compress a chat · `task-memory.md` handoff (**off by default**) · `yaml-standards.md` · `rules-and-errors.md` · `git.md`
3. **Prefer bundled helpers** (never a one-off script): run `python <skill-root>/scripts/run_helper.py <helper> ...`, where `<skill-root>` contains this `SKILL.md`. Use `create-note --apply` · `audit-vault` (read-only) · `suggest-links`; `update-note` is only for Task Memory, while ordinary existing-note edits follow `update-note.md` with native file tools.
4. **Stay bounded**: ≤10 files scanned, ≤1 note written, ≤5 wikilinks. Never overwrite; add `-2` on name clash. Validate after.
5. **Route**: daily→`15-Daily` · meeting→`10-Work` · learning→`20-Learning` · insight/digest→`30-Insights` · project→`40-Projects` · person→`50-People` · quick→`00-Inbox`.
