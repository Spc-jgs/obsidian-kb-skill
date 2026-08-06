# Obsidian Personal Knowledge Base — Universal Instructions

> **Version**: 1.28.0 · **Single source of truth**: `core/OBSIDIAN_KB.md`. Full workflows live in `core/references/*.md`, loaded only when about to save. This file is tiny on purpose: loading the skill costs almost no tokens, and the first rule is "do not auto-save".
> Do not edit generated files directly — edit this file, then `python build.py`.

## Overview

Agent-agnostic instructions to create, organize, and update notes in an Obsidian vault. Any tool that reads/writes local files can use it.

## DO NOT auto-save

This skill **never writes to the vault on its own**. Write only after **explicit save intent** ("save to Obsidian", "沉淀", "总结存档"). An explicit request to evaluate what from a conversation is worth capturing may run `conversation-harvest.md` as analysis only. For unrelated Q&A, debugging, or casual chat: do nothing.

## When the user asks to save or review capture candidates

1. **Route analysis before Vault discovery**: for an analysis-only conversation review, read `conversation-harvest.md`, return the candidate proposal, and stop without locating or scanning a Vault. Otherwise continue.
2. **Find vault for a write**: env `OBSIDIAN_KB_VAULT` → `~/.obsidian-kb-config` → ask. Refuse unless a real vault (`.obsidian/` + `Templates/`).
3. **Read the smallest operation-specific reference set before writing**. Read Vault governance first, then let one compact discovery call answer this: `required_references` names every file the selected type, template, and destination require, so read that set instead of discovering it one failure at a time. Pass the governed route as `--folder` — a crowded child folder does not make its parent look crowded. The full map:
   - New note: read only `note-creation.md`.
   - Finished source-backed article: after `note-creation.md` routes it, also read
     `web-capture.md`; verified captures additionally load `deep-capture.md`.
   - Crowded selected destination: when compact discovery reports it, also read
     `folder-routing.md`; uncrowded destinations do not load it.
   - Existing note: read only `update-note.md`.
   - Conversation context archive: read `conversation-digest.md`.
   - Conversation knowledge review: read `conversation-harvest.md`; load
     `note-creation.md` only after one durable candidate is selected for writing.
   - Task Memory: read `task-memory.md` only after explicit opt-in (**off by default**).
   - YAML, rules, and Git references are troubleshooting or post-processing material: load `yaml-standards.md`, `rules-and-errors.md`, or `git.md` only when the current task requires it.
4. **Prefer bundled helpers** (never a one-off script): run `python <skill-root>/scripts/run_helper.py <helper> ...`, where `<skill-root>` contains this `SKILL.md`. For new notes use `create-note --preflight-json`, inspect the structured validation, then apply with `--from-preflight <content.sha256> --apply --compact-json` instead of resending the body; `update-note` is only for Task Memory, while ordinary existing-note edits follow `update-note.md` with native file tools.
5. **Stay bounded**: ≤10 files scanned, ≤1 note written, ≤5 wikilinks. Never overwrite; add `-2` on name clash. Validate after.
6. **Route**: daily→`15-Daily` · meeting→`10-Work` · learning/article→`20-Learning` · insight/digest→`30-Insights` · project→`40-Projects` · person→`50-People` · quick/unread source→`00-Inbox`. An ordinary finished article uses standard capture; verified capture is explicit or evidence-sensitive.
