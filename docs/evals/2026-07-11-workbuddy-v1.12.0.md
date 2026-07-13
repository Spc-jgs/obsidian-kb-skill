# WorkBuddy v1.12.0 Real Evaluation

- Date: 2026-07-13
- WorkBuddy: 5.2.5
- Installed candidate commit: `4907ce38e1c845ae53a0980085e577c978314f64`
- Installed manifest version: 1.12.0
- Workspace: `my-knowledge-base`
- Setup-time Vault inventory: 246 non-`.git` files/symlinks with SHA-256 or
  link-target snapshots. The run happened two days later, after an unrelated
  2026-07-13 12:03 Vault commit, so this snapshot was not used as the sole
  post-run diff oracle.
- Old clone before digest: `fc33ce037f81d421c1dffae10bc887876cc4afaecd15b71b6d6bc25efacab94a` (299 non-`.git` entries)
- Old clone after install digest: `fc33ce037f81d421c1dffae10bc887876cc4afaecd15b71b6d6bc25efacab94a` (299 non-`.git` entries)

## Task prompt

> 请使用 obsidian-knowledge-base Skill，把下面的结论沉淀为一篇新的 insight
> note：一个可安装的 AI Skill 不仅要有说明，还要在目标运行时独立调用其
> helper；能力边界应通过真实 dry-run 和执行结果验证，而不是根据参数名猜测。
> source 设为“WorkBuddy v1.12.0 真实前向测试”，related 关联以下三篇笔记：
> “2026-07-10 obsidian-kb-skill体检报告与改进建议”、
> “2026-07-10 Helper能力边界验证-create-note摩擦点复盘”、
> “2026-07-10 obsidian-kb-skill调用失败的根因复盘”。请走正常 Skill 工作流，
> 完成后告诉我写入位置和验证结果。

## Observable execution

### Harness recovery before the run

- Direct Accessibility `set_value` changed the visible WorkBuddy Slate editor
  DOM without updating Slate's internal tree. The send action stayed inert and
  `renderer.log` recorded `Cannot resolve a Slate point from DOM point`.
- No WorkBuddy task/session existed and the Vault had not changed at that point.
- Reloading WorkBuddy and pasting the exact prompt through the native clipboard
  produced a clean editor state and a working send action. This is a confirmed
  Computer Use/Slate integration limitation, not an Obsidian Skill defect.

### Real WorkBuddy task

WorkBuddy 5.2.5 completed the task in the selected `my-knowledge-base`
workspace. The visible execution trace showed this sequence:

1. Loaded `obsidian-knowledge-base` and read `note-creation.md`,
   `yaml-standards.md`, `rules-and-errors.md`, `Insight Note.md`, and `git.md`.
2. Searched `30-Insights/2026-07-10*.md`, confirmed all three requested notes,
   and read one source note to match its tag convention.
3. Called the installed WorkBuddy helper with `create-note --stdin --json`
   without `--apply` for a real dry-run.
4. Observed that the preview contained only the template default `insight` tag,
   then corrected its input to include `ai-agent` and `skill-design`.
5. Ran the installed helper from
   `~/.workbuddy/skills/obsidian-knowledge-base/scripts/run_helper.py` with
   `create-note --stdin --json --apply --suggest-links`.
6. Reported `ok: true` and zero findings, reread the created file, checked Git
   status, and committed exactly the new insight note.
7. Presented one artifact and later wrote its normal WorkBuddy workspace memory
   entry under `.workbuddy/memory/`.

No helper exception, missing resource, path error, encoding error, broken
wikilink, or fallback to raw file writing occurred.

## Result verification

- Created note:
  `30-Insights/2026-07-13 可安装Skill能力边界须通过dry-run验证.md`
  (3,896 bytes).
- Frontmatter independently read from disk:
  - `source`: exact `WorkBuddy v1.12.0 真实前向测试`
  - `date`: `2026-07-13`
  - `type`: `insight-note`
  - `tags`: `insight`, `ai-agent`, `skill-design`
  - `related`: the exact three requested notes, each using a valid aliased
    wikilink; all three target files exist.
- The body contains the requested core conclusion and follows the Insight Note
  section structure.
- Vault commit `3295a13a411b33d84fda3ff0cddaa11e4d460a42` contains one file only:
  the new note, with 67 insertions. `git diff --check` is clean.
- Post-run Vault status contains one additional untracked runtime file:
  `.workbuddy/memory/2026-07-13.md`, born at 19:40:45, 30 seconds after the note.
  It is WorkBuddy's task memory, not a helper output and not part of the note
  commit. The workspace already had the same convention for 2026-07-09 and
  2026-07-10.
- Installed WorkBuddy `doctor --json` returned `ok: true`, version `1.12.0`,
  with manifest, payload, runtime, dependencies, and resources all healthy.
- Installed `audit-vault --json` returned 25 findings, all pointing to older
  Vault files; none references the new note. They are outside this task.
- Installed `suggest-links` independently returned the same top candidate:
  `2026-06-09 跨平台AI Agent指令的一核多适配器设计模式.md`, score 7.

## WorkBuddy feedback

The exact Chinese follow-up from the design was sent in the same session. An
earlier semantically equivalent English version had already produced a detailed
response while the evaluation harness was working around Unicode input; the
exact Chinese question was then sent through a native paste without rerunning
the Skill. WorkBuddy gave the same conclusions in a shorter second response:

- Actual flow: Skill load; four references; template and source-note reads;
  dry-run; corrected apply; reread; Git commit; memory/present-files.
- Only actual friction: the first dry-run input omitted `tags`, so it had to
  compare the preview and add `ai-agent`/`skill-design` before apply.
- Skill issues: none. It said every documented helper option and merge rule used
  in this run behaved as documented.
- Agent judgment issues: omitted the tags despite already seeing the convention;
  also read `rules-and-errors.md` and `git.md` defensively when
  `note-creation.md` already covered the core flow.
- Experience score: **8/10**.
- Suggested enhancement: warn when input frontmatter omits tags and the result
  relies only on a template default. This is a convenience idea, not evidence
  of a failed contract in this run.

## Issue audit

### WB-001: Direct Accessibility value injection breaks WorkBuddy's Slate editor

- Observation: visible text could not be sent after direct `set_value`.
- Independent reproduction: repeated send actions stayed inert and
  `renderer.log` emitted `Cannot resolve a Slate point from DOM point`; a clean
  reload plus native paste sent successfully.
- Contract/source comparison: this occurs before Skill loading and does not
  involve any installed payload or helper.
- Classification: environment/install (evaluation harness and WorkBuddy editor)
- Severity: P2
- Decision: record the harness limitation; do not change this Skill.
- Regression test/fix commit: none; the real run used native paste.
- Live revalidation required: no, because the successful run already used the
  corrected input path.

### WB-002: First dry-run omitted the observed tag convention

- Observation: the first preview contained only the template's `insight` tag.
- Independent reproduction: the visible preview and both feedback responses
  agree; the agent added `ai-agent` and `skill-design` before `--apply`.
- Contract/source comparison: template fallback and input-frontmatter override
  behaved exactly as the documented precedence requires.
- Classification: agent judgment
- Severity: P2
- Decision: no Skill change; the dry-run served its intended purpose and no bad
  write occurred.
- Regression test/fix commit: not applicable.
- Live revalidation required: no.

### WB-003: Warn when tags come only from a valid template default

- Observation: WorkBuddy suggested this as a way to catch its own omitted tags.
- Independent reproduction: the resulting `insight` tag is valid and satisfies
  the current template and YAML contract; no warning is promised.
- Contract/source comparison: intentionally minimal templates would make such a
  warning noisy without an additional Vault policy.
- Classification: unverified observation / product enhancement idea
- Severity: P2
- Decision: defer until a concrete user rule distinguishes valid defaults from
  missing domain tags; do not expand v1.12 scope.
- Regression test/fix commit: none.
- Live revalidation required: no.

### WB-004: WorkBuddy creates a workspace memory file

- Observation: `.workbuddy/memory/2026-07-13.md` appeared after note creation.
- Independent reproduction: its birth time, content, and existing 2026-07-09
  and 2026-07-10 files identify it as WorkBuddy runtime housekeeping. It is
  untracked and absent from the helper's one-file Git commit.
- Contract/source comparison: the Obsidian Skill does not own or document
  WorkBuddy's private workspace-memory lifecycle.
- Classification: environment/install (WorkBuddy runtime behavior)
- Severity: P2
- Decision: record separately; do not attribute it to or alter this Skill.
- Regression test/fix commit: none.
- Live revalidation required: no.

### WB-005: Two defensive references were not strictly necessary

- Observation: WorkBuddy said `rules-and-errors.md` and `git.md` were extra for
  this straightforward create path.
- Independent reproduction: the visible execution trace confirms both reads;
  they caused no failure or output change.
- Contract/source comparison: lazy references may be loaded when needed, but
  the contract does not forbid defensive reads.
- Classification: agent judgment
- Severity: P2
- Decision: no Skill change.
- Regression test/fix commit: not applicable.
- Live revalidation required: no.

### WB-006: Generated background compresses historical and current evidence

- Observation: parts of the note phrase issues from the three source notes as a
  single forward-test narrative.
- Independent reproduction: the source notes support the core theme, while the
  current run itself did not reproduce helper/document mismatch or a write-time
  failure.
- Contract/source comparison: the task requested an insight note rather than a
  literal test transcript, so the requested conclusion and links are still
  present and useful; the wording is simply less precise than an execution
  report.
- Classification: agent judgment
- Severity: P2
- Decision: record the content-quality nuance; do not expand v1.12 into Vault
  content rewriting.
- Regression test/fix commit: not applicable.
- Live revalidation required: no.

The independently verified issue set contains **no known P0** in the Skill's
core function. No in-scope P0 or live-path defect was found, so no code-change
and rerun cycle was required after this pass.
