# Resilient Web Capture (conditional reference)

Load this reference only for a finished source-backed capture or a material
rewrite of one. Quick, unread, bookmark, and link-only captures remain explicit
Inbox items and do not load this workflow.

## Choose Capture Depth

Persist exactly one depth in the Web Clip frontmatter:

```yaml
capture_depth: standard
```

or:

```yaml
capture_depth: verified
```

`standard` is the default finished capture for an ordinary article the user
found useful and asks to save, summarize, or “沉淀”. It should be concise when
the source permits, source-faithful, independently understandable, and cheap to
produce. It does not require a capture receipt.

Select `verified` when the user explicitly asks to verify, research deeply,
reproduce results, compare evidence for a consequential decision, or when
scientific or other high-risk knowledge clearly needs the stronger evidence
path. Then load `deep-capture.md` and follow its complete material inventory,
coverage, claim, and content-bound capture receipt contract.

When a standard capture discovers that adequate verification needs expensive
multi-source research, a new benchmark, or reproduction, escalation to verified
requires user consent. Do not silently spend the extra effort or silently claim
the result is verified.

Both depths use the same Web Clip template. Depth changes acquisition and
verification effort, not the required number of headings, words, bullets,
links, tables, or code blocks.

`verified` is a finished knowledge outcome and must not target `00-Inbox`.
Inbox bookmarks remain receipt-free and must not claim verified depth.

## Define Source Scope

The default scope includes the main article body and every material code block,
table, example, embedded medium, attachment, or linked artifact needed to
understand or apply it.

Comments are out of scope by default. Include them only when the user asks or
the article itself makes a specific comment material.

Inspect every article-body image for materiality. If a material body image
contains a diagram, label, value, sequence, comparison, or other information
needed by the note, actually read and understand it. A URL or alt text alone
does not count as access. Decorative images may be omitted after inspection.

## Acquire Resiliently

1. Use the Agent's available native web or browser capability to access the
   intended canonical source.
2. Check the result before interpreting it: confirm the target, article body,
   expected structure, and material assets are present, with no challenge page,
   login interstitial, empty shell, or obvious truncation.
3. If the first access path fails or is inadequate, do not conclude that the
   source is unavailable. Try at least one materially different safe path when
   proportionate, such as browser-rendered content, a public text or reader
   representation, an official artifact, or a public syndicated copy.
4. Compare representations against visible structure and material artifacts.
   A fallback succeeds because it is adequate, not merely because it returned
   text.

There is no fixed tool or fallback order. Do not claim that every Agent has the
same browser or fetcher.

A public URL may be sent to a third-party reader such as Jina. URLs that are
authenticated, private, intranet, signed, secret-bearing, or otherwise
non-public must not be sent to a third-party reader. Never bypass login, CAPTCHA, paywalls, or
access controls, and never describe an access-control evasion as a fallback.

## Decide Whether Acquisition Is Adequate

A standard capture may proceed only when:

- the intended source and canonical URL are known;
- `retrieval_status: adequate`;
- the result is not challenged, truncated, empty, or obviously mismatched;
- the core argument and valuable implementation material are available;
- every body image was checked and every material image was read;
- unsupported or uncertain material claims can be represented honestly.

Verified capture also requires every source and evidence condition in
`deep-capture.md`.

Treat `partial`, `blocked`, and `uncertain` as failure states for a finished
capture whenever the missing material could change the conclusion, application,
limitations, or evidence. Do not let a complete-looking introduction hide a
missing table, code sample, attachment, or diagram.

## Verify Proportionately

For standard capture, preserve the author's claims without upgrading them into
established facts.

- Perform cheap verification when a direct official or primary source is
  readily available.
- Ordinary new-product setup steps, UI instructions, and low-consequence usage
  details do not require a research detour by default.
- For scientific, evidentiary, or consequential knowledge claims, use cheap
  primary verification when available; otherwise qualify the claim and offer a
  verified escalation.
- A claim such as “at 1000 concurrent requests, A is 40% faster than B” is a
  `source-self-report` when its sample, environment, measurement method, and
  comparison are not independently supported. It is not merely author opinion.
- Put a local qualification next to the affected claim, for example “作者自测；
  原文未提供样本、环境或基准方法”. A remote disclaimer is insufficient.

Expensive multi-source research, benchmarking, or reproduction belongs to the
verified path and requires user consent when the original request was standard.

Clearly distinguish source facts, source self-reports, first-party
supplementation, and Agent inference. Do not fabricate a missing step or let a
heading force unsupported filler.

## Bounded In-Run Self-Check

Keep this small working state while acquiring and drafting; do not persist it as
telemetry or expose chain-of-thought:

The fields are `capture_depth`, `retrieval_status`, `fallback_used`,
`material_media_checked`, `verification_state`, and `write_state`.

```text
capture_depth: standard | verified
retrieval_status: adequate | partial | blocked | uncertain
fallback_used: yes | no
material_media_checked: yes | no
verification_state: adequate | qualified | escalation-needed
write_state: not-started | preflighted | applied | stopped
```

Before preflight, check:

1. Did I reach the intended source rather than a challenge or placeholder?
2. Did I inspect every material source form, including body images?
3. Does the candidate preserve valuable content at the selected depth?
4. Are empirical numbers, source self-reports, and my inferences labeled where
   a reader encounters them?
5. Is `retrieval_status` truly `adequate`, or must the workflow stop?

Use the state to catch failures during the run. Do not create a persistent log,
browser history, token record, or long-lived monitoring system.

## Terminal Failure Means Zero Writes

When material access remains `partial`, `blocked`, or `uncertain` after
reasonable safe alternatives, perform zero Vault writes for the finished
capture. Do not call create-note apply, do not save a placeholder, and do not
summarize the access error as knowledge.

Report:

- the exact material still unavailable;
- the safe access paths attempted;
- why other paths are unsafe, unavailable, or disproportionate;
- the user's next choices, such as providing the content or explicitly asking
  for an incomplete Inbox bookmark.

Never auto-downgrade a failed finished capture to Inbox. The user must choose
that different product explicitly.

## Preflight and Completion

For standard capture, pass complete Markdown with
`capture_depth: standard` through the normal create-note preflight and apply
flow. Do not supply a capture receipt.

For verified capture, set `capture_depth: verified`, load `deep-capture.md`,
and use its receipt-bound preflight and apply flow.

Report the selected depth, source coverage, whether a fallback was used,
material-media status, verification or qualification status, and mechanical
audit. Verified completion additionally reports receipt identity and unresolved
item count under the deep contract.
