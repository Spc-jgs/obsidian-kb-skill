# WorkBuddy Distribution, Discoverability, and Live Evaluation v1.12.0 Design

## Goal

Make WorkBuddy a formally supported consumer of the complete standard Obsidian
Knowledge Base Skill, make helper capabilities discoverable without reading
source code, add deterministic installed-runtime diagnosis, and prove the
result in the real WorkBuddy application. Keep the release focused on the
Skill's core job: safely creating, organizing, and validating Obsidian notes.

The release version is 1.12.0. It is not complete until the supported
installers, source package, installed standard Skill, wheel, and real WorkBuddy
flow have no known P0 issue.

## Current Evidence

The three user-authored field reports from 2026-07-10 establish the historical
baseline:

- a manually linked WorkBuddy Skill once lacked bundled helpers and carried
  stale snake-case commands;
- `run_helper.py create-note --help` is intercepted by the launcher instead of
  reaching `create-note`;
- stdin frontmatter merging works but is not discoverable in the reference or
  the `--stdin` help text.

Current v1.11.1 verification refines that baseline:

- supported Codex/QoderWork installs now carry the complete payload and survive
  source removal;
- old snake-case helper commands are absent from current references;
- the real WorkBuddy shared payload currently matches the v1.11.1 standard
  payload byte-for-byte, excluding the standard Skill's optional OpenAI UI
  metadata;
- WorkBuddy still loads that payload through a symlink into a separate clone
  whose Git HEAD is v1.10.0 and whose v1.11.1 content is an uncommitted manual
  overlay, so it has no reliable upgrade or uninstall path;
- the helper-help interception and stdin-frontmatter documentation gap still
  reproduce on the current installed product;
- `create_note.py` has a docstring that states the wrong metadata precedence,
  and existing tests do not lock conflicting-value precedence.

## Approaches Considered

### 1. Formal WorkBuddy target plus standard payload manifest — selected

Treat WorkBuddy as another consumer of the complete standard Agent Skill. Both
installers copy the same product-owned payload to WorkBuddy's native Skill
location, while a deterministic manifest and read-only doctor diagnose drift.
This removes the unmanaged symlink without creating another instruction fork.

### 2. Generic user-configurable Agent Skill destination

A generic `--skill-destination` option would support unknown future runtimes,
but it expands deletion, validation, upgrade, and uninstall boundaries around
arbitrary paths. It also cannot encode WorkBuddy-specific smoke tests. This is
deferred until more than one additional runtime needs it.

### 3. Keep the symlink and add doctor guidance

This is rejected. A doctor bundled inside a missing or stale payload cannot
repair its own absence, and a symlink into a dirty source clone remains outside
the installer's ownership and version contract.

## Component Design

### WorkBuddy installer target

`workbuddy` becomes a valid value in Bash and PowerShell `--platforms` /
`-Platforms`. The default "all platforms" set includes WorkBuddy, consistent
with the existing behavior of installing every supported target.

The destination is:

```text
~/.workbuddy/skills/obsidian-knowledge-base
```

It receives the same complete standard payload as Codex and QoderWork. The
installer must:

- validate the platform before any Vault or home-directory mutation;
- replace an existing destination directory or symlink with a real directory;
- remove only the symlink entry, never its target clone;
- preserve sibling WorkBuddy skills;
- refresh missing files and remove stale files during upgrade;
- remove only this Skill during uninstall;
- keep the shared canonical runtime and global user settings lifecycle
  unchanged.

The local migration uses `--platforms codex,workbuddy` after release. The old
`~/.agents/obsidian-kb-skill` clone remains untouched because it is not owned by
the installer.

### Deterministic payload manifest

`build.py` creates `skills/obsidian-knowledge-base/manifest.json` after all
generated instructions, references, assets, and bundled Python modules are in
sync. The manifest contains:

```json
{
  "schema_version": 1,
  "product": "obsidian-kb-skill",
  "version": "1.12.0",
  "files": {
    "SKILL.md": "<sha256>",
    "scripts/run_helper.py": "<sha256>"
  }
}
```

`files` contains every installable regular file except `header.md`, the manifest
itself, and housekeeping artifacts (`.DS_Store`, `__pycache__`, `.pyc`, `.pyo`).
Paths are POSIX-relative and sorted; JSON output is deterministic. The manifest
includes `agents/openai.yaml`: identical standard payloads are simpler and more
testable than per-runtime filtering, and non-OpenAI runtimes may ignore optional
metadata.

`build.py --check` fails on a missing, stale, or extra manifest entry. Installed
product tests compare the manifest and actual payload after the release source
is removed.

### Read-only doctor/version helper

Add `obsidian_kb_skill.scripts.doctor` and expose it through:

```text
python <skill-root>/scripts/run_helper.py doctor [--json]
```

Doctor is standard-library-only so it can diagnose a missing PyYAML dependency.
It reads `OBSIDIAN_KB_SKILL_ROOT`, the bundled manifest, and the user's runtime
record. It performs these checks:

1. manifest schema, product, and version are supported;
2. every manifest file exists, is regular, and matches SHA-256;
3. no unexpected installable file exists outside the manifest, excluding the
   manifest itself and the same housekeeping artifacts used at build time;
4. `runtime.json` is valid and selects an existing Python 3.11+ interpreter;
5. the selected environment can import PyYAML and every helper module;
6. templates and lazy references required by the standard Skill are present.

Human output gives a compact PASS/FAIL line per check. JSON output is one object:

```json
{
  "schema_version": "1.0",
  "ok": true,
  "version": "1.12.0",
  "checks": [
    {"name": "payload", "ok": true, "details": {}}
  ]
}
```

Exit code is 0 when healthy and 1 when any diagnostic check fails. Usage errors
remain argparse exit 2. No doctor action writes, repairs, downloads, installs,
or deletes anything.

`run_helper.py doctor` uses its current interpreter and Skill-local path even
when `runtime.json` is invalid or points to a missing executable; doctor must be
able to report that failure. Normal helpers continue using the installer-selected
runtime. Doctor complements installer verification but is not described as a
self-repair mechanism when the launcher itself is absent.

### Helper argument forwarding

The launcher treats a valid first token as the helper and forwards every
remaining token verbatim. Therefore:

```text
run_helper.py create-note --help
```

shows `create-note` help, while `run_helper.py --help` keeps showing launcher
help. The implementation must not duplicate each helper's argparse definition
inside subparsers. All nine helpers, including doctor, get forwarding tests for
`--help`, normal arguments, unknown helper rejection, and `--` compatibility.

### Frontmatter input contract

The public creation reference and CLI help state that `--stdin` and
`--content-file` accept complete Markdown with optional YAML frontmatter. The
frontmatter is separated and merged; the remainder is the body. Conflicting
values obey this tested order:

```text
type safety defaults < Vault template < input frontmatter < explicit CLI fields
```

The reference includes one dry-run stdin example setting `source` and
`related`. It also states that `--content-file` must be inside the canonical
Vault boundary; external or transient content should use stdin. No dedicated
`--source`, `--related`, or generic metadata flag is added in this release.

The incorrect `build_note()` docstring is corrected and direct unit tests lock
the precedence rather than relying only on prose.

## Real WorkBuddy Evaluation

The historical reports are the pre-change baseline. After local gates pass, the
new build is installed formally to the real WorkBuddy target. The evaluation
uses WorkBuddy v5.2.5 in the user's `my-knowledge-base` workspace and sends this
task without mentioning expected bugs or implementation details:

> 请使用 obsidian-knowledge-base Skill，把下面的结论沉淀为一篇新的 insight
> note：一个可安装的 AI Skill 不仅要有说明，还要在目标运行时独立调用其
> helper；能力边界应通过真实 dry-run 和执行结果验证，而不是根据参数名猜测。
> source 设为“WorkBuddy v1.12.0 真实前向测试”，related 关联以下三篇笔记：
> “2026-07-10 obsidian-kb-skill体检报告与改进建议”、
> “2026-07-10 Helper能力边界验证-create-note摩擦点复盘”、
> “2026-07-10 obsidian-kb-skill调用失败的根因复盘”。请走正常 Skill 工作流，
> 完成后告诉我写入位置和验证结果。

The run must be observed from prompt through final response. Evidence includes
which Skill/reference files WorkBuddy reads, helper commands and outputs,
fallbacks, the created note, audit result, and suggested-link behavior.

After completion, send this separate feedback request:

> 只回顾刚才的真实执行过程，不要做泛化评审。请按“实际步骤、实际失败或摩擦、
> 采取的回退、哪些属于 Skill 问题、哪些属于你的判断问题、0–10 使用感受评分”
> 输出；没有发生的问题不要猜。

Record prompts, observable actions, errors, results, and feedback in
`docs/evals/2026-07-11-workbuddy-v1.12.0.md`. Do not include credentials,
private unrelated Vault content, or hidden reasoning. The new note is a useful
project insight, not disposable test data, and remains in the Vault.

For every reported or observed problem:

1. reproduce it independently outside WorkBuddy;
2. compare it with the documented contract and current source;
3. classify it as Skill defect, environment/install defect, agent judgment, or
   unverified observation;
4. assign P0/P1/P2 only after evidence exists;
5. for a confirmed in-scope defect, add a failing automated test before fixing;
6. reinstall and repeat the real WorkBuddy flow when the fix could affect the
   observed path.

One successful real run is required. Additional real runs occur only when a
confirmed P0 or a fix touching the live path requires revalidation, so the Vault
does not accumulate artificial test notes.

## Severity and Stop Conditions

P0 for this release means any of:

- note loss or corruption;
- a read, write, move, or delete outside the canonical Vault boundary;
- installer deletion of a sibling Skill, the old symlink target clone, or
  unrelated user configuration;
- a formally installed WorkBuddy payload that cannot run the core create,
  audit, link, or doctor path;
- a release payload or manifest that is incomplete or cannot run without the
  source checkout.

P1 includes helper capability that is materially undiscoverable, wrong
frontmatter precedence, inaccurate diagnostics, or non-destructive installation
drift. P2 includes cosmetic output, optional metadata filtering, and internal
refactoring with no user-visible failure.

Do not tag v1.12.0 while any known P0 is open, any real WorkBuddy P0 observation
is unverified, or required Linux/Windows jobs are pending or failing.

## Test and Release Gates

Automated tests must prove:

- Bash and PowerShell recognize WorkBuddy and install identical complete
  payloads;
- an existing WorkBuddy symlink is replaced without modifying its target;
- upgrade restores missing files, removes stale owned files, and preserves
  sibling WorkBuddy skills;
- default uninstall and explicit purge retain their existing configuration
  semantics;
- installed WorkBuddy helpers and doctor run from a neutral directory after
  source removal;
- manifest generation is deterministic and detects missing, changed, and extra
  installed files;
- doctor reports healthy, malformed manifest, hash drift, missing runtime,
  invalid runtime, missing dependency, and missing helper cases without writes;
- launcher and each helper expose the correct help;
- stdin/content-file frontmatter and precedence behave as documented;
- generated references and platform copies remain exact.

Before release, run Skill quick validation, build and lock checks, compileall,
Bash syntax, the full pytest suite, wheel isolation, disposable Bash install,
Windows PowerShell smoke, and the real WorkBuddy evaluation. Push a PR and
require Linux Python 3.11, Linux Python 3.14, and Windows PowerShell/Python 3.11.
After merge, require the same master push gate before tagging v1.12.0.

After release, formally synchronize local Codex and WorkBuddy, compare both
installed payloads and the canonical support copy against the released manifest,
run doctor from neutral directories, and confirm the old manual clone is
unchanged.

## Explicitly Out of Scope

To avoid drifting from the Skill's knowledge-management core, v1.12.0 does not:

- add another AI platform adapter beyond the standard WorkBuddy install target;
- add arbitrary installation destinations;
- add dedicated CLI flags for every frontmatter field;
- add background services, telemetry, automatic repair, or update polling;
- redesign ordinary-note editing, backup atomicity, or TOCTOU handling;
- unify all helper JSON envelopes;
- refactor `audit_vault.py` or add unrelated Obsidian features.
