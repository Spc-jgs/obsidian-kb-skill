# YAML Frontmatter & Tags (reference)

Field requirements per note type and tag hygiene. The always-loaded skill body points here.

## YAML Frontmatter Standards

All notes must have:

```yaml
---
date: "YYYY-MM-DD"
type: note-type-slug
tags: [tag1, tag2]
---
```

Additional fields by type:

| Type | Extra Fields |
|------|-------------|
| `daily-note` | `related: []` |
| `meeting-note` | `participants: []`, `project: ""`, `related: []` |
| `learning-note` | `source: ""`, `category: ""`, `related: []` |
| `web-clip` | `source: ""`, `author: ""`, `published: ""`, `capture_depth: standard`, `related: []` |
| `project-note` | `status: active`, `updated: "YYYY-MM-DD"`, `related: []` |
| `insight-note` | `source: ""`, `related: []` |
| `person-note` | `role: ""`, `organization: ""`, `updated: "YYYY-MM-DD"`, `related: []` |
| `conversation-digest` | `source: ""`, `project: ""`, `related: []` |

For a `web-clip`, `source` stores the canonical source URL only. Keep the article title in the note heading and source-information section; use `author` and `published` for their respective values. New Web Clips also persist `capture_depth: standard` for ordinary finished capture or `capture_depth: verified` for the receipt-bound evidence path. Historical Web Clips without the field remain unclassified rather than being silently upgraded. For non-web notes, `source` may be a concise source description when no canonical URL exists.

Store semantic relationships in `related` as quoted Obsidian links, for example:

```yaml
related:
  - "[[Existing Note|Display Name]]"
```

Do not add a weak link only to satisfy a quota. Folder Index already supplies structural folder relationships; `related` is for high-confidence conceptual relationships.

The `related` property is the machine-readable source of truth for semantic relationships. A body section may repeat the same wikilink only when it adds a short explanation of why the notes are related. Do not duplicate `related` as an identical bare link list.

### Template Placeholders

Templates use `{{date}}` as a placeholder. When creating a note from a template, replace **all** `{{date}}` occurrences with the current date in `YYYY-MM-DD` format. Never leave `{{date}}` in the final note.


## Tag Hygiene

To keep the tag taxonomy from sprawling:

1. **Reuse the Vault's vocabulary first.** Discovery returns it: `tag_vocabulary.tags` lists the subject tags this Vault already uses, most-used first, with `distinct` reporting how many exist in total. Pick from that list whenever a term fits. Coin a new tag only when nothing in it does, and say which existing term you rejected and why. Do not sample a handful of nearby notes instead — the vocabulary is Vault-wide, and a local sample names almost none of it.
2. **kebab-case only.** All tags must be lowercase, hyphen-separated. No spaces, no camelCase, no underscores. Examples: `ai-agent`, `frontend`, `q3-okr`.
3. **No near-duplicates.** Before coining a tag, check it against `tag_vocabulary` ignoring case, separators, and a trailing `s` — that is the same normalization the audit applies. Do not introduce `ai-agents` if `ai-agent` exists, `springboot` if `spring-boot` exists, or `frontEnd`/`front_end` if `frontend` exists. The vocabulary is capped at the most-used terms, so a rarely used tag can still be missing from it; the audit reports the duplicate afterwards as `near-duplicate-tags`.
4. **Max 5 tags per note.** Pick the most specific ones; drop generic catch-alls like `note` or `misc`.
5. **Standard tags** (always available): `daily`, `meeting`, `learning`, `web-clip`, `insight`, `project`, `people`, `ai-generated`, `todo`.
