# Source Archive — Design

Target: `obsidian-knowledge-base` and `obsidian-knowledge-retrieval`, on top of
v1.28.0.

A user asked for a captured article's original text to be kept, and the Agent
appended all of it to the end of the note. The Skill has no concept of "the
source, verbatim", so the Agent invented one on the spot — a heading called
`## 附：原网页完整剪藏`, which appears in exactly one of 42 web clips and is
mentioned in no reference file. The next time it happens, the placement, the
heading, and the format are all up for reinvention.

## Measured problem

`20-Learning/AI-Agent/2026-08-06 从零构建Coding Agent：Violin架构与工程实践.md`
is 56 KB across 889 lines. The digest is 7,629 characters (210 lines); the
appended original is 34,983 characters (680 lines) — **82% of the file**.

### The active harm: citations land in someone else's prose

Across twelve queries covering the note's subject matter, the note was returned
12 times and **3 of those citations (25%) pointed past line 211**, into the raw
clipping:

| Query | Cited line | What the reader gets |
|---|---|---|
| `UI 层 回调 注册` | L682 | the author's EventBus walkthrough |
| `zig 实现` | L354 | a Zhihu search link inside the source |
| `EventBus 事件总线` | L668 | the author's body text |

The user asks their own knowledge base and is cited to a stranger's blog post.

### The secondary harm: the digest is diluted, but not yet outranked

BM25 normalises by document length, so a 5×-oversized document has every term
weight crushed. A/B against a copy of the real Vault with the clipping removed:

| Query | With clipping | Digest only |
|---|---|---|
| 上下文压缩 compaction | #2 · 16.0 | **#1** · 20.2 |
| 资源注入 Skill 机制 | #1 · 13.6 | #1 · **19.2** |
| 会话树 上下文管理 | #1 · 10.7 | #1 · **14.8** |

Scores fall 20–30%, but **only one ranking actually changed**. State this
honestly: at 178 notes dilution is a trend, not yet a defect. The citation
problem is what is broken today; dilution is why it gets worse with scale.

## Decisions

### D1 — Archives live in `95-Sources/`, and are not notes

A top-level folder, sibling to the numbered note folders, subdivided by capture
month (`95-Sources/2026-08/`). One file per archived source.

Rejected: `90-Archive/`, which means "my own notes, no longer active" — an
archived source is someone else's writing and never became a note of the user's.
Rejected: `Attachments/`, which holds binaries by Obsidian convention.

An archive carries minimal frontmatter (`type: source-archive`, `source`,
`author`, `published`, `captured`, `sha256`, `note`) and is otherwise verbatim.
It is deliberately **not** subject to note contracts: no required headings, no
tag policy, no template. The audit skips `95-Sources/` the way it already skips
`Templates/`, or every archive would flood the findings list with contract
violations that describe the source's author, not the user.

### D2 — Retrieval excludes `95-Sources/` by default, and `--scope` still reaches it

Adding the folder to `IGNORED_DIRECTORY_NAMES` is the whole change. The existing
walk applies that set to *child* directories encountered from the scope root and
never to the root itself, so `--scope 95-Sources` already searches inside an
otherwise-ignored folder. Verified against the current build using `Templates`,
which behaves exactly this way today.

That accidental-looking property is now load-bearing, so it gets its own test.

This satisfies both halves of the requirement: the original is preserved and
citable when the user explicitly asks "what did the source actually say", and
invisible the rest of the time.

Rejected: de-ranking archives instead of excluding them. The weight would be a
made-up number, and the retrieval design settled one release ago that filters
are hard constraints which never touch `score`.

### D3 — The note points at the archive; the archive points back

The note gets a frontmatter field `source_archive` holding a wikilink, and one
line under `## 来源与结论` so it is visible and clickable in Obsidian rather than
only in metadata. The archive's frontmatter carries `note` pointing back.

Both directions matter: from the note, the reader needs a way in; from an
archive found by an explicit scoped search, the reader needs the way back to the
knowledge. A one-way link would make `95-Sources/` a dead end.

The link is a wikilink, so `audit_vault` resolves it like any other and a
deleted archive shows up as `broken-wikilink` instead of silently rotting.

### D4 — Archiving is a separate, explicit helper

A new `archive-source` helper, not a flag on `create-note`. Reasons: capture
already has a preflight/apply contract bound to a content hash for the *note*,
and threading a second document through it would mean two hashes, two templates,
and two failure modes in one call. Archiving is also legitimately standalone —
a user may archive a source for a note that already exists, as is the case for
the note that prompted this.

It writes exactly one file, never overwrites (numeric suffix on collision, like
`create-note`), and records the archived bytes' SHA-256 in frontmatter so a
later reader can tell whether the file has been edited since capture.

### D5 — Verbatim means verbatim

The archive stores the source text as captured, with no heading-level rewriting,
no template merge, and no truncation. The point of keeping an official blog post
is that it is evidence; a normalised copy is not evidence.

The one thing added is the frontmatter block. It is prepended, and the byte
range it covers is excluded from the recorded `sha256`, which hashes the source
text alone.

## Interface

```bash
archive-source <vault> --note <vault-relative-note> \
  --source-url <url> [--author <name>] [--published YYYY-MM-DD] \
  --stdin | --content-file <path> \
  --preflight-json | --apply --compact-json
```

Preflight reports the destination path, the byte count, the content SHA-256, and
whether the note already declares a `source_archive`. Apply writes the archive
and adds the link to the note.

Refusals follow the established `invalid-*` / contract shape: `invalid-note`
(target is not an existing note in the Vault), `note-already-archived` (the note
already links an archive; archiving again needs an explicit `--replace`),
`empty-source-content`, and the shared path and frontmatter codes.

## Skill instruction changes

`web-capture.md` gains a short section: when the user asks to keep the original,
archive it — never append it to the note. `deep-capture.md` cross-references it,
since a verified capture is the case most likely to want the evidence kept.
`search.md` notes that `95-Sources/` exists, is excluded by default, and is
reachable with `--scope` when the user asks what the source actually said.

## Out of scope

- Migrating the existing 680-line clipping out of the Violin note. The user
  chose to build the capability first and migrate afterwards, with the tool
  rather than by hand.
- Fetching source content. `archive-source` takes content on stdin or from a
  file; acquisition stays in `web-capture.md`.
- Any change to ranking, and the connectivity signal parked in issue #57.

## Verification

- A fixture proving `--scope 95-Sources` reaches an archive that a whole-Vault
  search does not return — the property D2 depends on.
- Byte-identity: the archived source text round-trips unchanged, and the
  recorded `sha256` matches the source alone, not the frontmatter.
- The note-to-archive link resolves under `audit_vault`, and a deleted archive
  produces `broken-wikilink`.
- `95-Sources/` produces no audit findings for missing note contracts.
- Refusal tests for each new code, with nothing written on refusal.
