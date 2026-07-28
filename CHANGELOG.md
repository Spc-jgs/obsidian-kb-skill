# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.22.1] - 2026-07-28

### Changed

- Finished source-backed articles explicitly use `web-clip` unless Vault governance selects a more specific source-backed template, preventing `learning-note` from bypassing the semantic receipt contract.
- Resource-survey receipts declare every concrete resource and bind canonical-link, compatibility, and limitation evidence to that resource instead of satisfying the profile with one global set.
- Explicit Task Memory creation may initialize only a normalized lowercase `Tasks/<slug>` operational path; ordinary note types still cannot create missing directories.

### Fixed

- Capture-receipt routing now uses the canonical resolved destination, so traversal spellings and in-Vault symlink aliases cannot inherit the Inbox exemption after resolving outside Inbox.
- Material, numerical, inference, and practical anchors must occur in reader-facing body content rather than YAML frontmatter or hidden HTML comments.
- Inference labels must occur inside their exact reader-facing excerpt.
- Copyable `SKILL.md` validation recognizes heredoc-first `cat <<EOF > path/SKILL.md` commands.
- Measurement provenance detects English months and years, B/thousand/million/billion counts, and Chinese 万/亿 counts.
- Instructional-comment auditing matches the shipped English Web Clip comments and correctly ignores tilde or variable-length fenced examples.
- Material rewrites of existing source-backed articles retain the v1.22 deep-capture and standalone receipt route.

## [1.22.0] - 2026-07-28

### Added

- Finished web clips outside Inbox now require a structured semantic capture receipt bound to the exact rendered content SHA-256, and apply must repeat the exact receipt identity accepted by preflight.
- Capture receipts expose selected profiles, complete source access, material coverage, numerical-claim provenance and measurement context, labeled inferences, a profile-appropriate practical artifact, and unresolved items.
- The read-only `capture-receipt` helper applies the same validation to complete in-Vault candidates before a material rewrite.
- Detailed receipts may use a bounded non-symlink UTF-8 JSON file instead of inline JSON, avoiding Windows command-length and shell-quoting limits without writing evidence into the Vault.
- Compact Vault discovery now reports a bounded, deterministic `crowded_folders` list for managed categories with at least 20 direct notes.
- A lazy `folder-routing.md` contract reuses suitable child categories or proposes a stable subject child only when at least five notes form a real cluster.

### Changed

- `create-note` no longer creates a missing destination directory; new categories must pass the existing user-confirmed `create-category` preflight and apply flow.
- Deep-capture completion reports now include receipt identity and unresolved-item count separately from the mechanical audit.
- Quick or unread web clips in `00-Inbox` and ordinary note types retain the receipt-free fast path.

### Fixed

- Measurement-shaped values such as percentages, ratios, durations, before/after results, abbreviated large counts, and star counts can no longer be silently omitted from deep-capture provenance evidence.
- Resource-survey receipts now require explicit compatibility and limitation evidence, and copyable shell examples that create `SKILL.md` reject malformed YAML frontmatter.
- Crowded-folder discovery excludes hidden files, folder indexes, nested notes, and directory symlinks instead of inflating direct-note counts or escaping the Vault.

## [1.21.0] - 2026-07-28

### Added

- Finished source-backed captures now load a dedicated semantic contract with intent routing, source-access hard stops, materiality rules, and separate profiles for tutorials, resource surveys, conceptual analysis, and evidence reports.
- Deep capture requires a temporary source inventory and coverage ledger before preflight, rejects unresolved material omissions and unsupported claims, and permits labeled first-party enrichment when the primary article is too shallow.
- The Vault auditor reports leaked instructional template comments in rendered notes while allowing ordinary HTML comments, template files, and fenced examples.
- Four bounded synthetic evaluation fixtures preserve profile-specific versions, links, commands, causal boundaries, measurements, limitations, and tempting unsupported inventions for repeatable contract walkthroughs.

### Changed

- Article-only quality instructions moved from the ordinary create path into lazy-loaded `deep-capture.md`, so meetings, daily notes, projects, quick Inbox bookmarks, and other non-article captures no longer load the semantic article contract.
- Completion reports must distinguish selected capture profile, source coverage, semantic acceptance, and deterministic mechanical audit; `0 findings` alone is no longer a semantic success claim.
- Historical notes remain explicitly unreviewed until a bounded semantic migration or material rewrite instead of being treated as upgraded by a new template or structural audit.

## [1.20.1] - 2026-07-27

### Fixed

- Full-vault audits now apply a versioned v1.20 Chinese or English deep-capture heading baseline to every historical web clip, even when an upgraded Vault preserves an older or customized shallow template.
- Full-vault audits report an outdated `Templates/Web Clip.md` separately, while per-note creation audits continue to honor the active Vault template contract.
- Required web-clip metadata rejects normalized compound placeholders such as `TODO: verify`, `unknown author`, and `待补充作者` without rejecting meaningful values that merely contain the same substrings.

## [1.20.0] - 2026-07-27

### Added

- Deep article capture now requires standalone coverage of the source problem and boundaries, core knowledge and causal reasoning, reproducible steps or examples, verification and risks, and clearly distinguished insights.
- Web-clip creation and full-vault audits reject placeholder metadata such as `unknown`, `N/A`, `TODO`, and `待补充` instead of treating it as complete attribution.
- Historical web clips are audited against the complete deep-article section contract, exposing articles that still depend on their original links for essential details.

### Changed

- Saved articles default to durable knowledge notes with no artificial token, length, or bullet-count limit; unread or incomplete sources route to Inbox instead.
- Chinese and English web-clip templates now provide dedicated sections for source conclusions, applicability, principles, concrete implementation, validation and limitations, insights, and real related notes.
- Source access failures stop deep capture rather than silently producing a concept-only summary.

## [1.19.1] - 2026-07-16

### Fixed

- Template heading discovery and required-heading audits ignore YAML frontmatter and fenced code examples, preventing internal comments or example headings from becoming note sections.
- Opted-in `task-memory` captures omit selected-template discovery because that note type intentionally has no conventional Vault template.

## [1.19.0] - 2026-07-16

### Added

- `vault-info --type <slug>` adds one selected conventional template's path and ordered level-two headings to discovery output without returning template prose or frontmatter.
- Focused contracts cover selected template shape, unsupported types, missing templates, and conditional reference loading across source, generated Skill, wheel, and installed-runtime surfaces.

### Changed

- Ordinary creation performs one type-aware compact discovery call and receives the required standard heading shape before drafting, while preflight remains the fallback when type is initially unclear.
- Missing-category and customized-template details moved into separate conditional references, reducing the ordinary `o200k_base` instruction surface from 2,716 to 2,296 tokens.

### Fixed

- Standard template headings no longer appear only after a failed preflight; the lightweight discovery result exposes them early without increasing template maintenance or leaking author instructions.

## [1.18.0] - 2026-07-16

### Added

- Compact Vault discovery reports only the note types whose conventional templates differ from the shipped Chinese or English starters.
- `template-contract` returns one selected custom template's frontmatter, body, supported placeholders, and normalized SHA-256 without loading unrelated templates into model context.
- `create-note --expect-template-sha256` rejects stale custom-template interpretations before note or index mutation.

### Changed

- Natural-language instructions beneath custom-template headings now govern note generation; headings, lists, tables, labels, and examples are preserved as quality scaffolds while instruction prose is executed rather than copied.
- Unchanged templates retain the ordinary capture path with no template-contract call or template-body tokens.

### Fixed

- Template customization detection treats BOM, CRLF/CR, and final-newline differences as transport-only changes and remains portable across Windows and POSIX runners.

## [1.17.0] - 2026-07-15

### Added

- `vault-info --compact` provides compact vault discovery by omitting per-folder note filename arrays while preserving the default JSON contract and all index-ownership fields.

### Changed

- Ordinary capture uses compact vault discovery and completes governance-required Git preflight before fetching or deeply reading source content, avoiding source-analysis cost when Git must stop the write.

### Fixed

- Template validation now returns complete template heading diagnostics in one finding, including expected headings, actual headings, and the first mismatch, so all ordering problems can be repaired in one preflight cycle.

## [1.16.0] - 2026-07-15

### Added

- `create-category` preflights and initializes one user-confirmed category below an existing governed parent, including native/custom Folder Index, Dataview, or static index setup.
- Category apply requires the explicit `--confirmed` gate, creates the directory and index exclusively, cleans up only a newly created empty directory on write failure, and audits the resulting category structure.

### Changed

- Missing-category capture now asks the user to confirm or rename the proposed path and records optional `AGENTS.md` route persistence as a separate choice; declining persistence produces a one-off category without waiving Vault-required README maintenance.
- Existing governed categories keep the ordinary `vault-info` → `create-note` path with no extra prompt, helper call, or classification-model cost.

### Fixed

- Folders excluded from the globally enabled Folder Index plugin now retain static index detection and updates, so the first note in an excluded new category is indexed correctly.

## [1.15.1] - 2026-07-15

### Fixed

- Malformed input frontmatter now exits before mutation with a stable `invalid-frontmatter` error, the input source, and full-Markdown line and column coordinates instead of silently falling back to empty metadata.
- `suggest-links` no longer awards title-overlap points for generic Chinese and English article terms such as `详解`, `指南`, `guide`, and `tutorial`.

## [1.15.0] - 2026-07-15

### Changed

- `suggest-links` now recognizes CJK title overlap, weights specific tags above corpus-common and structural tags, treats matching note type as supporting evidence, and suppresses candidates below a confidence threshold.
- Sibling folders enter the bounded candidate scope only when their names overlap the target title or tags; root notes retain root-note candidates.
- Candidate content is read once per suggestion run while preserving the read-only CLI and JSON contracts.

## [1.14.1] - 2026-07-15

### Changed

- Ordinary note creation now loads only `note-creation.md`, uses the single `vault-info` discovery result, delegates template and index handling to `create-note`, trusts a clean compact apply audit, and forbids secondary memory/log writes without separate explicit intent.
- `note-creation.md` was reduced from 209 to 150 lines while preserving Vault governance, structured preflight, exclusive apply, automatic audit, template merging, and bounded link suggestions.

## [1.14.0] - 2026-07-14

### Added

- `create-note --preflight-json` returns final merged frontmatter, destination, rendered-content SHA-256/size, and shared note-level validation without echoing the Markdown body or mutating the Vault.

### Changed

- The recommended create workflow now uses structured preflight followed by `--apply --compact-json`; complete `--json` preview and legacy apply contracts remain available and unchanged.
- Pre-write and post-write checks share one in-memory note audit implementation, including Vault-template heading-order validation.

### Fixed

- Relative `--content-file` input is read from the canonical in-Vault path that passed validation rather than from an unrelated current working directory.
- Note creation uses exclusive file creation with suffix retries, so concurrent same-title writers cannot overwrite one another.
- Invalid Vault failures are structured in create-note JSON modes, and template-backed notes no longer emit a false frontmatter-only warning.

## [1.13.0] - 2026-07-14

### Added

- `create-note --apply --compact-json` returns structured path, audit, and link-suggestion data without echoing the complete rendered Markdown body.

### Changed

- The note-creation workflow now recommends full `--json` for dry-run preview and compact JSON for the real apply step, while preserving the legacy apply JSON contract for existing consumers.

## [1.12.1] - 2026-07-13

### Changed

- `create-note` now treats stdin and content files as complete Markdown inputs, documents input-frontmatter precedence, and rejects incomplete `web-clip` metadata before any note or index mutation.

### Fixed

- Unquoted YAML date/datetime metadata is normalized to ISO strings, so a valid `published: 2026-07-13` value no longer triggers `web-clip-missing-published`.
- All helper CLIs now force UTF-8 stdin as well as stdout/stderr, the installed launcher explicitly byte-bridges `create-note --stdin`, and frontmatter accepts BOM/CRLF transport details, preventing piped Chinese text and emoji from being lost or rejected under legacy Windows code pages.
- Installed helper launchers now use Python safe-path mode so an unrelated `obsidian_kb_skill` package in the current working directory cannot shadow the installed payload.

## [1.12.0] - 2026-07-11

### Added

- **Formal WorkBuddy distribution**: Bash and PowerShell install the complete standard Skill at `~/.workbuddy/skills/obsidian-knowledge-base`, include WorkBuddy in the default platform set, refresh the owned directory exactly on upgrade, and remove only that Skill on uninstall.
- **Deterministic installed payload manifest**: `build.py` generates a sorted SHA-256 `manifest.json` covering every installable regular file, including optional OpenAI metadata, while excluding only the build header, manifest itself, and housekeeping files.
- **Read-only installation doctor**: `run_helper.py doctor [--json]` checks manifest schema and hashes, unexpected files, Python 3.11+ runtime selection, PyYAML/helper imports, and required resources without writing, repairing, downloading, or deleting.

### Changed

- The Skill launcher forwards arguments after the helper token verbatim, so all nine helpers receive direct `--help`; one historical `--` separator remains compatible.
- Doctor runs with the launcher's interpreter even when the selected runtime record is invalid, while normal helpers continue to require the installer-selected runtime.
- `create-note` documents and tests the metadata precedence `type defaults < Vault template < stdin/content-file frontmatter < explicit CLI fields`, with a dry-run `source`/`related` example and an explicit Vault-only content-file boundary.
- Installed-product tests delete a disposable release tree and then run WorkBuddy doctor and core helpers from a neutral directory. Windows smoke coverage mirrors payload hashes, upgrade, symlink migration when available, sibling preservation, and uninstall.

### Fixed

- Replacing a WorkBuddy directory symlink removes only its entry and leaves the old clone target byte-for-byte untouched. PowerShell handles reparse points with non-recursive .NET deletion.
- Installed helper environments no longer inherit an external `PYTHONPATH`, preventing a partial installation from silently borrowing modules from a source checkout.
- Malformed manifests, escaping manifest paths, symlink payload files, invalid Python version output, and missing dependencies now produce stable unhealthy diagnostics instead of crashes or false health.

## [1.11.1] - 2026-07-10

### Added

- **Bounded per-note backup retention**: `update-note` keeps one write-before backup per relative note path by default. Users can set `backup.keep_per_note` from 1 through 1000 in the global `~/.obsidian-kb-settings.json` file.
- **Installed-product retention proof**: source, standard Skill, disposable installer, and wheel tests run the updater from neutral directories and verify the configured retained count without borrowing repository modules.

### Changed

- Backup cleanup runs inside the helper only after a successful note write. Agents never enumerate or delete backups, so cleanup costs no model tokens and cannot create an AI-driven deletion loop.
- Bash and PowerShell create global settings only when absent, preserve user edits during upgrade and default uninstall, and remove them only with explicit config purge.

### Fixed

- Invalid or unreadable settings now fail closed: the note write may succeed, but backup deletion is disabled and the new backup remains.
- Retention scans only real timestamp directories and regular in-Vault files. Symlinks, unknown layouts, and unverifiable paths are retained; the just-created backup is protected even if filesystem clocks move backward.
- New-target validation now rejects a dangling symlink in the final path component instead of treating it as absent and potentially writing through it outside the Vault.
- Cleanup failures are warnings after a committed write rather than command failures that could cause an agent to retry. This release does not claim to eliminate concurrent filesystem replacement (TOCTOU), which remains future atomic-write/directory-handle work.

## [1.11.0] - 2026-07-10

### Added

- **Complete standard Skill payload**: `skills/obsidian-knowledge-base/` now ships `SKILL.md`, Codex UI metadata, lazy references, executable helpers, and Chinese/English template assets as one installable unit.
- **Skill-local helper launcher**: `scripts/run_helper.py` dispatches all eight helpers from the installed payload and works from a neutral directory without importing the source checkout.
- **Private installer runtime**: Bash and PowerShell select Python 3.11+, record the interpreter under `~/.obsidian-kb-skill/runtime.json`, and install a missing PyYAML only under the product-owned `vendor/` directory.
- **Behavioral Windows gate**: GitHub Actions now executes a disposable PowerShell install/upgrade/uninstall scenario on `windows-latest`, including post-source-removal helper execution.
- **Machine-readable scaffolding**: `scaffold-templates --json` completes the JSON contract across all eight helpers.

### Changed

- Bash and PowerShell install the same complete payload for Codex/QoderWork and a canonical compatibility payload at `~/.obsidian-kb-skill/skill/` for Claude Code and Cursor.
- Install and upgrade refresh product-owned Skill files exactly, restore newly added or missing resources, remove stale owned files, and continue preserving user-edited Vault templates unless force is explicit.
- Uninstall preserves `~/.obsidian-kb-config` by default; `--purge-config` / `-PurgeConfig` removes it explicitly.
- `build.py --check` now detects missing, changed, and extra files across platform references, wheel resources, standard Skill assets, and bundled helper code.
- Wheel packaging is self-contained under `obsidian_kb_skill`, exposes all eight console scripts, and resolves templates/references through packaged resources outside the checkout.

### Fixed

- Every CLI now validates a canonical Vault boundary and rejects traversal, absolute escapes, prefix-confusion paths, and static symlink escapes. Valid symlink Vault roots resolve to their canonical directory; broken links, loops, and links to files are rejected.
- `update-note` now creates a byte-for-byte, non-overwriting backup under `.obsidian-kb-backups/<timestamp>/...` before every in-place update and aborts the write when backup creation fails.
- Marker-managed shared files now fail closed on lone, reversed, or duplicate markers instead of risking truncation or silent cleanup.
- New relative Vault paths are canonicalized before being persisted, unknown platform names fail before Vault mutation, and PowerShell now includes the Digest template.
- Corrected the `detect_index.py` shebang and removed documentation commands that referenced the deleted top-level `scripts/` package.
- Template-driven note creation now replaces the template's first H1 with the requested note title; different filenames no longer retain the same placeholder heading and trigger false `duplicate-title` findings.
- The gatekeeper now states that `update-note` is Task-Memory-only; ordinary project/person/daily edits follow the generic update reference with native file tools instead of being sent to an incompatible CLI.
- Wheel metadata now uses an SPDX license string and explicit namespace-package discovery, eliminating setuptools deprecation and package-data ambiguity warnings.
- Windows now delegates native drive and UNC containment to `Path.resolve()` + `relative_to()`, so an absolute path inside the Vault is accepted while different-volume escapes remain rejected.
- All eight helper CLIs force UTF-8 stdout/stderr, preventing non-ASCII JSON and human output from failing on legacy Windows console code pages.
- Wheel tests now use the declared, locked `build` development dependency and platform-native virtualenv script paths instead of a machine-local `/tmp/bldenv` assumption.

## [1.10.0] - 2026-07-09

### Added

- **`scripts/detect_index.py` (P1)** — single entry point for per-folder index-strategy detection; replaces three copies of the same prose in `note-creation.md` and the detection in `process_inbox`. Reuses `audit_vault._folder_index_config` as the single source of truth. Emits JSON: `mode` / `index_file` / `can_append` / `graph_compatible` / `notes`. (`obsidian-detect-index` console script.)
- **`scripts/vault_info.py` (P2)** — one-shot read-only cold-start context: vault path + validity, template list, every standard folder's existence and index strategy. Lets an agent seed context in a single JSON call instead of probing by hand. Reuses `detect_index.detect` and `audit_vault._folder_index_config`. (`obsidian-vault-info` console script.)
- **Automatic post-write audit in `create_note.py` / `update_note.py` (P3)** — `audit_note()` runs the per-note audit after `--apply` (pass `--no-audit` to skip). `AUDIT:` output lists broken wikilinks, missing frontmatter, unresolved placeholders, etc. Replaces Step 9's manual re-read. Also fixed a real bug it exposed: `REQUIRED_TYPES` omitted `task-memory`, so every task-memory note was falsely flagged `invalid-type`.
- **`--suggest-links` on `create_note.py` / `update_note.py` (P4)** — after writing, prints link suggestions reusing `suggest_links.suggest_links` (single source, no duplicated scoring). Aligns create/update with the suggest_links capability.
- **`scripts/scaffold_templates.py` (P5r)** — one-time bootstrap of `Templates/` from the shipped starters in `core/templates/`. Refuses to overwrite user-edited templates unless `--force` is passed. Not a single source of truth — the vault template is.
- **`--json` machine-readable output on every CLI script (P6)** — `audit_vault`, `process_inbox`, `suggest_links`, `create_note`, `update_note`, `detect_index`, `vault_info`. Consistent schema, tested end-to-end (10 tests). Agents can drive every script without parsing human text.

### Changed

- **`core/references/note-creation.md` is now 156 lines (was 253, -38%).** Cut the 6-step wikilink procedure, Step 9's manual checklist, and Step 7's feature restatement — all of which are now done by the bundled scripts. Every governance contract phrase the test suite guards is still present.
- **`create_note.py` reads the vault template, not a hardcoded spec.** `build_note()` loads `{VAULT}/Templates/<Name>.md`, fills `{{date}}` placeholders, merges the template's frontmatter, and uses its body. If the user adds a field or a section to their template, every new note picks it up — no code change needed. `EXTRA_FIELDS` is now a safety net for the no-template case, not the single source.

### Fixed

- `REQUIRED_TYPES` in `audit_vault.py` now includes `task-memory` (was missing; surfaced by P3's automatic audit).
- Index-strategy detection was duplicated three places (note-creation prose, audit_vault's reader, process_inbox's reader); now lives in `scripts/detect_index.py` with `audit_vault._folder_index_config` as the single source.

## [1.9.1] - 2026-07-09

### Changed

- **Always-loaded gate shrunk below ~400 tokens (was ~400–800).** The gatekeeper in `core/OBSIDIAN_KB.md` is now ~14 lines: a one-line Overview, a prominent `## DO NOT auto-save`, and a 5-step "when the user asks to save" pointer. The four platform trigger headers (SKILL/CLAUDE/AGENTS/mdc) were de-duplicated and tightened — same "explicit save intent only" signal, far fewer example phrases. Loading the skill now costs roughly half the previous tokens, and the first rule an agent sees is still "do not auto-save".
- **Memory quality guarantee (no factual drift, no loss).** Borrowed from high-star memory systems (Mem0 / MemGPT-Letta / Zep):
  - `conversation-digest.md` and `task-memory.md` now carry an explicit **Quality guarantee** block: capture only *grounded* facts (drop anything you can't trace to the conversation), store *atomic* decisions (not narrative — that is where drift crept in before), require non-empty `decisions`, and run a `audit_vault.py` **self-check** after writing.
  - **Conflict resolution (Mem0-style):** `update_note.py` gains `--replace-decision "OLD::NEW"` — when new info contradicts an old decision it *replaces* it instead of appending a contradictory second line; appends as new if no match (upsert, never silently drops a correction).
  - **Core vs Archival (MemGPT-style):** on handoff the incoming agent reads only the `TASK.md` **frontmatter** (core memory, tiny); the `## Log` + body prose are archival, read on demand. Provenance: every Log line is `ISO-date [agent] what` (Zep-style) so a contradiction can be traced to when it was established.

### Added

- `obsidian-update-note --replace-decision "OLD::NEW"` for conflict-resolution handoffs.

## [1.9.0] - 2026-07-09

### Added

- **Task Memory Workflow (multi-agent handoff memory)**: a new workflow in `core/OBSIDIAN_KB.md` for carrying one long task's state across agent handoffs. A single agent-agnostic `Tasks/<slug>/TASK.md` note holds `status` / `step` / `decisions` / `constraints` / `artifacts` / `open` / `agents` plus a bounded `## Log` trail. The outgoing agent updates it before yielding; the incoming agent reads it first. **Off by default** — activated per task via the `task-memory: enabled` field, with an optional global master switch `OBSIDIAN_KB_TASK_MEMORY=on|off` (default `off`). Saying "开启任务记忆 / handoff" opts in; "关闭" opts out.
- **Note updater helper (`update_note.py`)**: the constraint-based counterpart to `create_note.py` for handoffs. It edits only structured frontmatter fields and appends a timestamped line to `## Log` (capped to the last 30 entries, TTL-style) — it never clobbers prose. Upserts: if the task note is missing it is initialized from the template, so one command both starts and updates a task. Read-only by default; `--apply` to write. Installed as the `obsidian-update-note` console script.
- **`task-memory` note type** added to `create_note.py` / `process_inbox.py` (routed to `Tasks/`, with the task-memory frontmatter defaults).

### Changed

- **Task Memory spec is now lazy-loaded.** The full Task Memory Workflow (TASK.md structure, handoff protocol, `obsidian-update-note` usage) moved out of the always-loaded `core/OBSIDIAN_KB.md` body into `core/references/task-memory.md`. The body keeps only a ~5-line pointer whose heading itself states "OFF by default", so an agent learns the feature is off after one line and never pays to load the spec unless the user enables it. `build.py` ships the reference next to every generated artifact; `--check` verifies it stays in sync.
- **Skill body slimmed to a tiny gatekeeper.** `core/OBSIDIAN_KB.md` no longer inlines any heavy workflow. Every workflow (note creation, update, conversation digest, task memory, YAML standards, rules/errors, Git) lives in `core/references/*.md`, read by an agent **only when it is about to save**. The always-loaded body is ~37 lines: an Overview, a prominent **"DO NOT auto-save"** rule stating the skill never writes without explicit user intent, a 5-step "when the user asks to save" gate that points to the right reference, and bounded-scan limits. Loading the skill now costs almost no tokens, and the first real rule an agent sees is "do not auto-save". `build.py` ships `core/references/*` next to each generated artifact; `--check` verifies.

## [1.8.1] - 2026-07-09

### Added

- **Note creator helper (`create_note.py`)**: a constraint-based note creator for environments without a native file-write tool. It builds the type's required frontmatter, picks the routed folder, writes with a safe numeric suffix (never overwrites), and updates a static `INDEX.md` when applicable. Read-only by default (dry run) — pass `--apply` to write. Body comes from `--content-file` or `--stdin`; frontmatter already present in the body is merged with explicit CLI values winning. Installed as the `obsidian-create-note` console script.
- **Step 7 "tool choice" rule** in `core/OBSIDIAN_KB.md`: agents prefer their native file-write tool; when none exists they must call `scripts/create_note.py` instead of inventing a one-off script. Important Rules gains rule 13 to the same effect.

### Fixed

- **Auditor skips top-level hidden dirs too**: `_is_ignored` now checks every path segment (it previously skipped only nested hidden dirs), so a root-level hidden folder such as `.uploads` no longer triggers a false `missing-folder-index` finding.

### Changed

- **Version header corrected**: `core/OBSIDIAN_KB.md` stated a stale `1.7.0`; it now reads `1.8.1` to match the actual release line.
- **Conversation Digest redesigned for agent reuse**: the digest is now decision-dense, link-rich, and short rather than a narrative essay. Frontmatter carries a structured `decisions` list (primary field a future agent scans) plus optional `open`; the body is capped at ~250 words (TL;DR + Decisions + Open bullets) with no background/revised-ideas prose. Depth lives in linked durable notes, not the digest. The auto session-wrap-up trigger remains removed (context design still pending).

### Documentation

- README and README_EN document the new `create-note` command (console form and `scripts/create_note.py` usage), and the script count is updated to four.

## [1.8.0] - 2026-07-09

### Added

- **Vault auditor expansion (Phase A)**: `scripts/audit_vault.py` now also flags unresolved template placeholders (`unresolved-template-placeholder`), validates the `related` field format and duplicate entries (`invalid-related*`, `duplicate-related-entry`), requires non-empty Web Clip fields (`web-clip-missing-source` / `-author` / `-published`), flags empty template notes (`empty-template-note`), suggests merging near-duplicate tags (`near-duplicate-tags`), detects duplicate and fuzzy-similar note titles (`duplicate-title`, `similar-title`), and detects orphan notes via a reverse-reference index (`orphan-note`).
- **Conversation Digest template and workflow (Phase D)**: New `conversation-digest` note type with `Templates/Digest Note.md` (zh-CN + en) and a dedicated "Conversation Digest Workflow" in `core/OBSIDIAN_KB.md` for distilling chat summaries into the vault.
- **Inbox Processor (Phase B)**: New read-only-by-default `scripts/process_inbox.py` proposes (`--plan`) or applies (`--apply`) filing of quick-capture notes from `00-Inbox`, filling `date` / `type` / `tags` and appending to the destination folder's static INDEX (Folder Index and Dataview listings are never touched).
- **Link Suggestor (Phase C)**: New read-only `scripts/suggest_links.py` scans a bounded scope around a note and scores candidate wikilink targets by shared tags, matching type, and title-token overlap.
- **Console-script entry points**: `obsidian-audit-vault`, `obsidian-process-inbox`, and `obsidian-suggest-links` are installed via `[project.scripts]`, backed by `scripts.audit_vault:main`, `scripts.process_inbox:main`, and `scripts.suggest_links:main`.

### Changed

- **Python environment standardization**: Python 3.14.6 is the pinned development interpreter; Python 3.11 is now the minimum supported version.
- **Reproducible development**: Added `.python-version`, `uv.lock`, locked uv commands, and an upgraded-pip venv fallback.
- **Test entry consistency**: pytest adds the repository root explicitly, so both `pytest` and `python -m pytest` resolve local modules.
- **CI matrix**: GitHub Actions now verifies the locked environment on Python 3.11 and 3.14.
- **Packaging**: `scripts/` is now an installable package (`packages = ["scripts"]`), reversing the deliberate "disable discovery" choice from 1.6.0 so the console-script entry points resolve correctly.

### Fixed

- **Auditor no longer flags agent/tool metadata**: `_is_ignored` now skips any hidden directory (dotfile convention), so `audit_vault` won't falsely report agent working memory or AI-tool metadata folders (`.workbuddy`, `.claude`, `.cursor`, `.codebuddy`, ...) as missing frontmatter. `.workbuddy` is also listed explicitly in `IGNORED_PARTS` for visibility.

### Documentation

- README and README_EN document the auditor's skipped directories and the advisory `similar-title` threshold (0.85 in `scripts/audit_vault.py`), so the tunable knob isn't lost.

## [1.7.0] - 2026-07-08

### Added

- **Standard Agent Skill entry**: `skills/obsidian-knowledge-base/SKILL.md` is now the platform-independent, generated Skill artifact.
- **Codex user-level installation**: Codex installs to `~/.agents/skills/obsidian-knowledge-base/`, matching the user Skill discovery convention.
- **Installer coverage**: Bash smoke tests cover canonical Codex/QoderWork installation, idempotency, and sibling-safe uninstall.

### Changed

- **Explicit build targets**: `build.py` now uses explicit header and output paths and validates five generated artifacts.
- **QoderWork source**: QoderWork installation copies the standard Skill instead of the QoderWork compatibility artifact.
- **Compatibility preserved**: Existing `platforms/qoderwork/SKILL.md`, `platforms/codex/AGENTS.md`, Claude Code, and Cursor artifacts remain available.

## [1.6.0] - 2026-07-08

### Added
- Configuration-aware Folder Index graph auditing with findings for graph-incompatible custom names, missing indexes, misnamed indexes, and broken parent-child graph chains.
- Bash installer smoke tests for native Folder Index and Dataview fallback modes.
- Root-to-target graph-chain validation after note creation.
- Pre-write Git synchronization with safe fast-forward-only updates.

### Changed
- Folder Index Graph View now uses native folder-named indexes below the configured root, matching the actual Folder Index 1.0.30 graph traversal algorithm.
- Bash and PowerShell installers derive index filenames and root navigation from the enabled plugin configuration.
- Bounded wikilink search lists the target folder before parent or sibling folders.
- Template validation checks required heading order; `web-clip.source` is the canonical URL and `related` is the machine-readable semantic relationship source of truth.
- Editable development installs explicitly disable accidental setuptools package discovery in this documentation-and-script repository.

### Fixed
- Dataview fallback indexes are no longer mislabeled as Folder Index-owned notes.
- New installations now create the missing `90-Archive` index.

## [1.5.0] - 2026-07-08

### Added
- Post-write validation before confirmation, commit, or push, covering metadata, tag limits, placeholders, wikilinks, encoding, and index ownership.
- Folder Index structure auditing for missing or duplicate `folder-index-content` blocks.
- Explicit precedence for user requests, Vault-local governance files, and generic skill defaults.
- Safe optional Git post-processing that stages only task files and stops on divergence, conflicts, or INDEX conflict resolution.
- Contract tests for the governance workflow and the Chinese Web Clip interpretation guidance.

### Changed
- Full-read accounting now distinguishes content notes from short control-plane files while retaining the total 10-file scan cap.
- Batch capture defaults to one target note and requires user confirmation before creating multiple notes.
- Bounded wikilink search now uses local routing and manual parent navigation before checking high-relevance sibling folders.
- The Chinese Web Clip template renames “我的理解” to “理解与启发” and defines a concise, evidence-based output standard.

## [1.4.0] - 2026-07-07

### Added
- Folder Index-aware index strategy detection. Agents now leave plugin-generated listings untouched and create only a minimal compatible index when they create a new folder while Obsidian may be closed.
- Chinese templates as the default, with preserved English templates selectable through `--locale en` / `-Locale en`.
- A consistent `related` property for explicit semantic links, separated from structural folder relationships.
- A read-only Vault audit CLI that validates frontmatter, note types, tag hygiene, fenced code blocks, wikilinks, and duplicate folder indexes.
- Regression tests for localized templates, Folder Index ownership rules, documentation link examples, attachments, ambiguous links, and tag limits.

### Changed
- Index ownership is now exclusive: Folder Index first, Dataview second, static Markdown as the fallback. The previous unconditional two-level INDEX rule is removed.
- Note type metadata is normalized to `insight-note`, and project/person templates include `updated`.

## [1.3.1] - 2026-06-11

### Fixed
- **install.ps1 em-dash corruption on PowerShell 5.1**: The Dataview INDEX template, main INDEX bullets, and several comments contained U+2014 (em-dash). Windows PowerShell 5.1 reads `.ps1` files without a BOM using the system default codepage (GBK on Chinese Windows), which mangles UTF-8 multi-byte sequences. New `15-Daily/INDEX.md` files were generated with corrupted bytes (`e9 88 a5 3f` instead of the expected `e2 80 94`). All 10 em-dashes in `install.ps1` are now replaced with ASCII `--`, so the installer produces clean output on every Windows PowerShell version. Discovered while end-to-end testing v1.3.0 against a real vault. `install.sh` and `core/OBSIDIAN_KB.md` are unaffected because bash and the build pipeline read UTF-8 sources correctly.

## [1.3.0] - 2026-06-11

### Added
- **pytest test suite** (`tests/test_build.py`): 10 tests covering `extract_body` (line-anchored marker, false-match guard, missing marker, first-line marker) and `build_adapter` (frontmatter ordering, banner placement after `---`, plain-header banner-at-top, body verbatim, platform name in banner), plus an end-to-end test that loads the real repo files and asserts every checked-in adapter matches `build_adapter()`'s output. Tests are loaded via `importlib.util` so importing `build.py` doesn't trigger `main()`.
- **`pyproject.toml`**: Declares the project, `[project.optional-dependencies] dev = ["pytest>=7"]`, and `[tool.pytest.ini_options] testpaths = ["tests"]`. Install with `pip install -e ".[dev]"`.
- **CI runs pytest**: `.github/workflows/check.yml` installs the `dev` extra and runs `python -m pytest tests/ -v` after `build.py --check`. CI now catches both "you forgot to rebuild adapters" and "you broke the build logic" in a single push.
- **Backup requirement in the Update Workflow**: Step 5 of `core/OBSIDIAN_KB.md` now mandates copying the original file (as bytes) to `{VAULT}/.obsidian-kb-backups/YYYY-MM-DD-HHMMSS/{original-relative-path}` before any in-place edit. `.gitignore` excludes the backup folder; both installers create it during setup and a routing entry documents it in the vault structure section.
- **Dataview-first INDEX templates**: New folder `INDEX.md` files seeded by both installers now contain a `dataview` code block (auto-listing recently modified notes in that folder) wrapped by `<!-- managed by obsidian-kb-skill: dataview -->` markers, followed by a `## Manual Notes` fallback section for users without the Dataview plugin. Solves the unbounded-append problem in the previous template.
- **Dataview-aware Step 8** in `core/OBSIDIAN_KB.md`: When an INDEX already contains a dataview block (or the managed marker), the agent skips the append step entirely; only legacy / user-customized INDEX files still get a manual link appended. Eliminates duplicate entries when Dataview is in use.

### Changed
- **install.ps1 / install.sh INDEX templates**: Re-templated using single-quoted PowerShell here-strings + `.Replace()` (avoiding backtick-escape pitfalls inside `@""`) and escaped-backtick bash heredocs respectively. Output bytes verified UTF-8 (no BOM) on both platforms.
- **README.md / README_EN.md**: Bumped to v1.3.0; "Recommended Obsidian Plugins" now promotes Dataview to **strongly recommended** with explanation of the new INDEX behavior; Contributing section documents `pip install -e ".[dev]"` and `pytest`.

### Fixed
- **`extract_body` false match on quoted text**: The body marker (`## Overview`) was being matched against the first occurrence of that string anywhere in the file, including inside quoted prose. Fixed by searching for `"\n## Overview\n"` (line-anchored only), with a separate first-line acceptance for the edge case where the file starts with the marker. Covered by `TestExtractBody::test_inline_text_does_not_match`.

## [1.2.0] - 2026-06-11

### Added
- **Marker-wrapped skill blocks** in `CLAUDE.md` / `AGENTS.md`: Both installers now wrap injected content in `<!-- BEGIN obsidian-kb-skill -->` / `<!-- END obsidian-kb-skill -->` markers. Re-running the installer replaces the block in place (true upgrade), and `--uninstall` strips the block while preserving the user's other content. If the file ends up empty after strip, it's removed entirely.
- **`--Force` switch on install.ps1**: First-class upgrade flag matching install.sh's `--force`. Legacy `OBSIDIAN_KB_UPGRADE=1` env var still works.
- **15-Daily/ folder**: Daily notes, journals, and morning plans now route to their own dedicated folder instead of being mixed into 10-Work. Both installers create the folder and its INDEX, and the main INDEX has a navigation entry for it.
- **GitHub Actions workflow** (`.github/workflows/check.yml`): Runs `python build.py --check` on every push and PR. Fails CI if a contributor edited `core/OBSIDIAN_KB.md` or a platform `header.md` without re-running `build.py`.
- **Verified marker logic**: Manual round-trip tests confirm install / upgrade / append-into-existing-file / strip-keep-user-content / strip-and-delete all work correctly on both PowerShell and bash implementations.

### Changed
- **Daily Note routing**: `core/OBSIDIAN_KB.md` routing table now sends "daily, today, diary, journal, morning plan" triggers to `15-Daily/` (was `10-Work/`). Generated adapters regenerated.
- **install.ps1 refactored**: Centralized UTF-8 (no BOM) write helper; removed the brittle "is the Platforms string `--force`" sniff; consolidated marker logic into two reusable functions (`Set-MarkerBlock`, `Remove-MarkerBlock`).
- **install.sh refactored**: Mirrors the PowerShell function shape with portable awk implementations of `set_marker_block` / `remove_marker_block`. Force upgrade is now a proper `--force` flag handled at the top, not scanned from `$@` mid-loop.

### Fixed
- **Claude/Codex upgrade gap**: Previously the installer's "already installed?" check used `grep "Obsidian Personal Knowledge Base"` and silently skipped — meaning v1.0.0 → v1.1.0 upgrades never touched `CLAUDE.md` / `AGENTS.md`. Now `--force` does a real in-place replacement via markers.
- **Claude/Codex uninstall gap**: Previously the uninstaller refused to touch `CLAUDE.md` / `AGENTS.md` because it had no way to identify its own content. With markers, the skill block can be safely removed in isolation.
- **PowerShell BOM inconsistency**: All file writes in install.ps1 now go through the shared `Write-Utf8NoBom` helper; the previously stray `Add-Content` (which writes with BOM on PS 5.1) is gone.

## [1.1.0] - 2026-06-11

### Added
- **Build script architecture (`build.py`)**: Single-source-of-truth generator that produces all four platform adapters from `core/OBSIDIAN_KB.md` plus per-platform `platforms/{name}/header.md`. One edit syncs all four platforms; `--check` mode verifies generated files are in sync (suitable for CI / pre-commit).
- **Per-platform `header.md`**: Each platform now has a small `header.md` containing only its YAML frontmatter / H1 / trigger hint. The shared body lives in `core/OBSIDIAN_KB.md`.
- **Generated-file banner**: All adapter files now start with an `AUTO-GENERATED` HTML comment warning against direct edits.
- **"When NOT to Use This Skill" section**: Explicit non-triggers (casual Q&A, debugging, one-off snippets) to reduce false invocations.
- **Vault Validation step**: Verifies `.obsidian/` and `Templates/` exist before any write; refuses to write into non-vault paths.
- **"Decide First: Create vs Update" section**: Forces the agent to choose Create vs Update before acting, with explicit ambiguity-handling rules.
- **Update Existing Note Workflow** (7 steps): Locate target, read in full, pick insertion point (section-aware for `project-note` / `person-note` / `daily-note`), preserve frontmatter, report diff summary. Closes the gap where the skill only knew how to create new notes.
- **Bounded wikilink search**: Cheap-first strategy in Step 6 — read folder INDEX, list 1–2 sibling folders, read first ~20 lines of 2–5 candidates, insert at most 5 wikilinks. Replaces vague "scan the vault" instruction.
- **Cost Limits section**: Hard per-invocation caps (10 files scanned, 3 full reads, 1 note written, 2 INDEX updates, 5 wikilinks) to prevent runaway token usage.
- **Tag Hygiene section**: Reuse existing tags first (scan 5 recent notes), kebab-case only, no near-duplicates, max 5 tags per note.
- **`updated:` frontmatter field**: Added to `project-note` and `person-note` types to support the Update workflow.
- **README "Editing the Skill / Contributing" section**: Explains build script architecture in both Chinese and English READMEs.

### Changed
- **Tightened skill descriptions**: All four platforms now narrow the trigger to explicit save/append intent ("save to Obsidian", "记一下", "沉淀到知识库", etc.) and explicitly exclude casual Q&A and debugging. Reduces false positives from broad words like "notes" or "knowledge".
- **Project structure**: Four `header.md` files added; four adapter files are now generated artifacts (do not edit directly).
- **Important Rules**: Now reference both Create and Update workflows, vault validation, and cost limits.

### Notes
- The four generated adapter files (`SKILL.md`, `CLAUDE.md`, `AGENTS.md`, `obsidian-kb.mdc`) remain at their original paths, so existing installer logic and external links continue to work unchanged.
- Backward-compatible with all v1.0.0 installations — no migration required.

## [1.0.0] - 2026-06-11

### Added
- **Daily Note routing**: Added "daily, today, diary, journal, morning plan" trigger pattern to all platform adapters
- **Error handling section**: Comprehensive error handling guidelines in core instructions and all adapters
- **Template placeholder docs**: Documented `{{date}}` placeholder replacement behavior
- **Subfolder support**: Routing and INDEX update rules for topic-based subfolders (e.g. `20-Learning/Python/`)
- **Install script improvements**:
  - `-Help` / `--help` parameter with full usage documentation
  - `-Uninstall` / `--uninstall` option to cleanly remove skill files
  - `--force` upgrade mode to update existing templates
- **Cursor glob patterns**: Expanded to include `**/vault*`, `**/INDEX*`, `**/*.md`
- **`.gitignore` expanded**: Added OS artifacts (.DS_Store, Thumbs.db), editor artifacts (.vscode/, .idea/), Obsidian workspace files
- **Version identifier**: Added version `1.0.0` to core instructions and README

### Fixed
- **UTF-8 BOM on PowerShell 5.1**: Replaced `Set-Content -Encoding UTF8` with `[System.IO.File]::WriteAllText()` in install.ps1 (3 occurrences)
- **Cross-adapter consistency**: Standardized all 4 platform adapters to 9-step workflow matching core instructions
- **Template paths in Cursor**: Added `Templates/` prefix to all template references in obsidian-kb.mdc
- **"Never overwrite" rule**: Added numeric suffix guidance (`-2`, `-3`) to Codex and Cursor adapters
- **"Never hardcode date"**: Added explicit warning to Codex and Cursor adapters
- **`.env.example` comment**: Fixed misleading "should NOT be committed" message

### Changed
- Core workflow expanded from 6 steps to 9 steps (matching adapter implementations)
- All routing tables now include Daily Note as the first entry
- Rules sections now include subfolder INDEX update rule
- YAML frontmatter table now includes `daily-note` type
