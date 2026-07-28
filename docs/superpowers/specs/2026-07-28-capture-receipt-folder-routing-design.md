# Capture Receipt and Folder Routing Design

## Goal

Make the v1.21 deep-capture semantic contract harder for an agent to skip, and
keep growing topic folders navigable without creating one directory per note.

This release responds to two observed failures:

1. A writer can mechanically pass a deep article while adding unsupported
   numerical conclusions, omitting measurement provenance, or leaving a
   profile-specific procedure incomplete.
2. Stable topic folders such as `20-Learning/AI-Agent` eventually accumulate
   enough direct children that browsing becomes noisy, while silent automatic
   subdirectory creation would fragment the Vault and make routing unstable.

## Design Principles

1. Keep semantic judgment with the writing agent, but require inspectable,
   content-bound evidence before a finished article can be created.
2. Do not present a self-attestation as proof of truth; the receipt proves that
   required review evidence was supplied and bound to the exact candidate.
3. Require the receipt only for finished source-backed articles, not quick
   Inbox captures or ordinary notes.
4. Treat folder pressure as an advisory routing signal, never as permission for
   silent mutation.
5. Prefer stable subject taxonomy over one-note directories or date-based
   folders.
6. Preserve progressive disclosure so ordinary note creation pays neither the
   deep-capture receipt cost nor the crowded-folder routing cost.

## Deep-Capture Classification

`create-note` treats a candidate as a finished deep capture when:

- `type` is `web-clip`; and
- the resolved destination is outside `00-Inbox`.

An explicitly quick, bookmark, unread, or save-for-later web clip remains in
`00-Inbox` and does not require a semantic receipt. Other note types retain
their current behavior.

Material rewrites of existing finished articles must run the same receipt
validator before the native edit workflow. The repository cannot intercept an
editor's arbitrary filesystem write, so the Skill contract must report the
receipt result alongside the post-edit mechanical audit.

## Structured Capture Receipt

Add a reusable `capture_receipt.py` module and a read-only
`capture-receipt` helper. `create-note` uses the same validator directly.

The JSON receipt schema is:

```json
{
  "schema_version": 1,
  "content_sha256": "<rendered candidate sha256>",
  "profile": "conceptual-opinion",
  "source_access": "complete",
  "primary_sources": ["https://example.com/article"],
  "supplemental_sources": [],
  "material_items": [
    {
      "id": "workflow-method",
      "kind": "procedure",
      "source": "https://example.com/article",
      "note_anchor": "### 实战工作流搭建三步法",
      "status": "resolved"
    }
  ],
  "numeric_claims": [
    {
      "note_excerpt": "项目交付周期从 12 天压缩至 5 天",
      "provenance": "source-self-report",
      "source": "https://example.com/article",
      "measurement_context": "原文未提供统计周期和项目样本"
    }
  ],
  "inferences": [
    {
      "note_excerpt": "这意味着流程设计比工具熟练度更可迁移",
      "basis": "工具变化与任务分工保持稳定的对比",
      "label": "本文推导"
    }
  ],
  "practical_artifact": {
    "kind": "application-method",
    "note_anchor": "## 具体做法与示例"
  },
  "unresolved_items": []
}
```

Supported profiles are:

- `tutorial-procedure`;
- `resource-survey`;
- `conceptual-opinion`;
- `research-evidence`.

Hybrid articles provide a sorted, non-empty `profiles` array instead of one
`profile`. Each material item has a stable ID, one allowed kind, a source URL,
an exact note anchor, and `status: resolved`.

Every receipt must:

- declare complete primary-source access;
- contain at least one primary source matching the candidate's `source`
  metadata;
- bind to the exact rendered UTF-8 content SHA-256;
- contain at least one resolved material item per selected profile;
- contain no unresolved item;
- point every material item, numerical claim, inference, and practical
  artifact to text that exists in the rendered note;
- give every numerical claim a provenance category and non-empty measurement
  context;
- label every inference and state its evidence basis;
- include one profile-appropriate practical artifact.

The validator deliberately does not claim that a URL proves a statement or
that an agent's coverage ledger is factually correct. It makes skipped review,
unbound review, unsupported numbers, and unlabeled inference visible and
machine-blocking.

## Preflight and Apply Protocol

`create-note` adds:

```text
--capture-receipt-json '<compact JSON>'
```

For a deep capture:

1. The agent drafts complete Markdown.
2. The first `--preflight-json` may omit the receipt. It returns the rendered
   content SHA-256 plus `missing-capture-receipt` and does not mutate.
3. The agent builds the receipt against that exact hash and reruns preflight.
4. Preflight validates the receipt and returns its SHA-256 under
   `semantic_receipt`.
5. Apply repeats the identical Markdown and receipt. Any body, template, or
   receipt change fails before write.

Quick Inbox captures do not return a receipt error. Supplying malformed receipt
JSON fails closed with a stable structured error.

The standalone helper supports material rewrite review:

```bash
python <skill-root>/scripts/run_helper.py capture-receipt \
  --content-file <vault-relative-note> \
  --receipt-json '<compact JSON>' \
  --json <vault>
```

It reads only an in-Vault candidate, validates the same schema and content
binding, and performs no mutation. The update workflow must run it before a
material rewrite is applied and run the existing audit afterward.

## Folder Pressure Signal

Compact `vault-info` adds a bounded `crowded_folders` array:

```json
{
  "crowded_folders": [
    {
      "path": "20-Learning/AI-Agent",
      "direct_notes": 25,
      "threshold": 20
    }
  ]
}
```

Rules:

- scan real directories beneath managed note roots without following directory
  symlinks;
- count direct Markdown notes only;
- exclude recognized folder indexes and hidden files;
- report only folders with at least 20 direct notes;
- sort by descending count then path;
- cap the result to 20 entries.

This is a navigation-pressure threshold, not a quality failure. Full-vault
audit remains unchanged.

## Conditional Folder Routing

Add a lazy `folder-routing.md` reference. `note-creation.md` loads it only when
compact discovery reports the selected destination as crowded.

The routing contract is:

1. Reuse an existing governed child category when the note clearly belongs
   there.
2. Propose a new child only when at least five existing or imminent notes form
   a stable subject cluster.
3. Name the child by durable subject, not by date, source site, author, or the
   current article title.
4. Keep managed note paths to at most two category levels beneath the managed
   root.
5. Never create a one-note directory.
6. Show the proposed full Vault-relative path and allow the user to rename it.
7. Create it only through `create-category --preflight-json`, followed by
   `--apply --confirmed` after explicit approval.
8. If no stable cluster exists, keep the current folder and rely on its index,
   tags, links, and search.

`create-note` must not create a missing destination directory. This closes the
existing bypass where `--folder` could implicitly create parents without the
category confirmation workflow.

## Reporting

Finished deep capture completion reports:

- selected profile or profiles;
- primary and supplemental source access;
- receipt validation result and receipt SHA-256;
- unresolved material item count;
- semantic acceptance;
- mechanical audit.

Crowded-folder routing reports only when it changes the destination or needs a
user decision. Do not narrate folder pressure when the existing destination
remains correct.

## Testing

Tests cover:

- deep web clips outside Inbox require a receipt;
- quick Inbox web clips retain the existing fast path;
- malformed, stale-hash, incomplete-access, unresolved, missing-anchor,
  unprovenanced-number, unlabeled-inference, and missing-practical-artifact
  receipts fail before mutation;
- a valid receipt passes preflight and apply and returns a stable receipt hash;
- template changes invalidate content binding;
- the standalone helper validates in-Vault material-rewrite candidates and
  rejects outside paths;
- crowded folder counts exclude indexes, hidden files, nested notes, and
  symlink escapes;
- compact discovery is bounded and deterministic;
- missing create destinations fail instead of being silently created;
- lazy references load receipt rules only for deep capture and folder routing
  only for a crowded selected destination;
- built payloads, standard Skill manifests, installed runtime, hostile working
  directory, Python 3.11/3.14, and Windows smoke behavior remain valid.

Forward evaluation reuses the four v1.21 article profiles and adds the two real
failure shapes:

- an opinion article containing unsupported `60%` and `70/30` conclusions;
- a resource guide containing an invalid copyable Skill frontmatter, a
  cross-project compatibility generalization, and a project-specific metric
  presented as a universal gate.

## Rejected Alternatives

- **More prose in `deep-capture.md`**: v1.21 already stated the hard failures;
  another paragraph does not make invocation observable.
- **Persisting `quality: passed` in frontmatter**: self-attested metadata is not
  evidence and becomes stale after edits.
- **A numerical article score**: high aggregate scores can hide one fatal
  unsupported claim or unusable example.
- **Automatic LLM audit of the full Vault**: expensive, nondeterministic,
  network-dependent, and unreliable for inaccessible historical sources.
- **One directory per article**: increases path length and destroys useful
  subject grouping.
- **Silent clustering and moves**: model-generated taxonomy and link rewrites
  are too consequential to apply without a user-reviewed plan.

## Release

Release as v1.22.0:

1. implement receipt validation, deep-create enforcement, standalone rewrite
   validation, crowded-folder discovery, missing-folder protection, and lazy
   routing guidance;
2. regenerate every platform adapter, packaged runtime, Skill payload, and
   manifest from source;
3. run targeted and full tests, `build.py --check`, `uv lock --check`,
   `git diff --check`, wheel/install/runtime smoke, and forward evaluation;
4. push a feature branch, open a ready pull request, wait for all required
   checks, merge to `master`, tag the merge commit, and publish a non-draft,
   non-prerelease GitHub Release;
5. reinstall the normal local targets with explicit template replacement,
   verify v1.22.0 manifest parity and `doctor --json`, and confirm the real
   Vault reports the expected crowded-folder signal without modifying notes.

## Non-Goals

- no automatic semantic truth oracle;
- no full-Vault source fetching;
- no automatic rewrite of existing knowledge articles;
- no automatic historical folder migration or wikilink rewriting;
- no one-note subdirectories;
- no receipt requirement for quick Inbox captures or ordinary notes;
- no changes to the user's Vault during repository tests.
