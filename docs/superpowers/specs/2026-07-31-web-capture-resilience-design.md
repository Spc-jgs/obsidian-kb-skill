# Web Capture Resilience and Depth Design

## Goal

Make an ordinary “save this article” request reliable across Agents without
forcing every useful article through the expensive deep-capture workflow.

The default finished article path should capture the source faithfully and
economically. A separate verified path should retain the existing semantic
receipt and evidence discipline when the user, subject, or intended use needs
it. A failed first fetch must not be mistaken for an inaccessible source, and a
truly incomplete source must never produce a finished note.

## Evidence

The motivating case is the public Juejin article
`https://juejin.cn/post/7664407325864558628`.

The historical Vault note contains only a WAF placeholder and a generic
sentence. A current read-only comparison found that:

- the original public page returned HTTP 200;
- a Jina reader representation also returned HTTP 200;
- the reader representation preserved all 26 headings, 5 code blocks, the
  table, and both article-body images.

The defect was therefore not “Juejin cannot be captured” or “Jina loses the
valuable content.” The Agent stopped after one unsuccessful access path and
wrote an incomplete result as though capture had succeeded.

## Product Model

Source-backed captures have three distinct outcomes:

| Outcome | Meaning | Vault result |
| --- | --- | --- |
| quick or unread | bookmark or save-for-later | explicit Inbox capture |
| `standard` | ordinary finished article, source-faithful and concise | durable `web-clip`, no receipt |
| `verified` | evidence-sensitive, decision-grade, or explicitly deep capture | durable `web-clip` plus receipt |

`standard` is the default for an ordinary article that the user found useful
and asks to “沉淀”, save, or summarize into the Vault. `verified` is selected
when the user explicitly asks to verify, research deeply, reproduce results, or
support a consequential decision, and when the subject is obviously
evidence-sensitive. The Agent may recommend escalation, but an expensive
multi-source investigation or reproduction run requires user consent when the
original request was standard.

The existing Chinese and English Web Clip section structure remains shared by
both depths. Depth controls acquisition and verification effort, not the number
of headings or a minimum note length.

## Acquisition Contract

The workflow applies to public source-backed captures, not to general browsing
or unrelated question answering.

### Source Scope

The default source scope includes:

- the main article body;
- material code blocks, tables, and examples;
- article-body images and embedded media;
- attachments or linked artifacts required to understand or apply the article.

Comments are excluded unless the user explicitly asks for them or the article
itself makes them material.

Every article-body image must at least be inspected for materiality. A material
image must actually be read or understood; retaining only its URL or alt text
does not count as access.

### Safe Retrieval Alternatives

The Agent uses its native web or browser capability first. If the first result
is blocked, challenged, truncated, empty, or otherwise inadequate, it must try
at least one materially different safe access path when proportionate. Examples
include a browser-rendered page, a text or reader representation, a public
syndicated copy, or an official canonical artifact.

There is no fixed tool or fallback order. The contract defines evidence of
adequate acquisition rather than naming one mandatory service.

Public URLs may be sent to a third-party reader such as Jina. Authenticated,
private, intranet, signed, or secret-bearing URLs must not. The workflow never
bypasses login, CAPTCHA, paywalls, robots restrictions, or other access
controls.

The first retrieval failure is not a source-access conclusion. Final failure is
allowed only after reasonable safe alternatives are exhausted or prohibited.

### Acquisition Acceptance

A standard capture is adequate when:

- the correct target and canonical source are identified;
- no challenge page, truncation, or obvious extraction failure remains;
- the core argument and valuable implementation material are available;
- material body assets have been checked.

A verified capture additionally requires the complete material inventory,
coverage ledger, claim handling, and semantic receipt already defined by
`deep-capture.md`.

## Verification Policy

Standard capture preserves author claims without silently converting them into
established facts.

- Cheap verification from a direct official or primary source may run
  automatically.
- New-product setup steps, ordinary UI instructions, and similarly
  low-consequence operational details do not require a research detour by
  default.
- Scientific, evidentiary, or consequential knowledge claims should be checked
  when verification is cheap, or locally qualified and offered for escalation.
- Numerical empirical claims such as “at 1000 concurrency, A is 40% faster than
  B” are source self-reports unless supported by inspectable methods and
  evidence. They are not merely author opinion.
- Expensive cross-source research, benchmarking, or reproduction requires
  escalation from standard to verified with user consent.

The qualification belongs next to the affected claim. A remote disclaimer does
not protect a reader who encounters the number in isolation.

## Bounded In-Run Self-Check

The Agent maintains a small working-state checklist while capturing:

- `capture_depth`: `standard` or `verified`;
- `retrieval_status`: `adequate`, `partial`, `blocked`, or `uncertain`;
- whether a fallback path was used;
- whether material media was checked;
- verification state for material claims;
- write state: not started, preflighted, applied, or stopped.

This state is operational working context, not persistent telemetry. It must not
store chain-of-thought, browser histories, tokens, or a long-term run log.

Before preflight the Agent asks:

1. Did I reach the intended source rather than a challenge or placeholder?
2. Did I inspect all material source forms, including images?
3. Are material claims represented faithfully at the selected depth?
4. Are unsupported numbers and inferences labeled where they appear?
5. Is the candidate complete enough to write, or must the workflow stop?

## Failure and Write Boundary

If the source remains partial, blocked, or uncertain for material content, the
finished capture performs zero Vault writes. It reports:

- which material content is unavailable;
- which safe retrieval alternatives were attempted;
- why the remaining alternatives are unsafe, unavailable, or disproportionate;
- the choices available to the user, such as supplying the content or
  explicitly saving an incomplete Inbox bookmark.

The workflow never auto-downgrades a failed finished capture to Inbox and never
writes a placeholder, access-error summary, or guessed concept note.

## Deterministic Helper Contract

New Web Clips persist:

```yaml
capture_depth: standard
```

or:

```yaml
capture_depth: verified
```

The shipped templates and fallback metadata default new Web Clips to
`standard`. Candidate input may explicitly override the field to `verified`.
Any other value fails preflight before mutation.

Only `verified` Web Clips outside `00-Inbox` require the existing content-bound
capture receipt. A standard Web Clip rejects a supplied receipt so receipt use
cannot disagree with the persisted depth. Inbox routing remains receipt-free.

Historical Web Clips without `capture_depth` are not retroactively classified
or made invalid by full-Vault audit. A material rewrite must choose and persist
one of the current depths.

Python remains deterministic and offline. It validates metadata and receipt
consistency, but it does not fetch webpages, choose browser tools, score truth,
or pretend to prove semantic quality.

## Progressive Disclosure

Add one lazy `web-capture.md` reference for all finished source-backed
captures. It owns depth routing, acquisition resilience, source scope,
verification policy, self-check, and zero-write failure.

Keep `deep-capture.md` as the additional verified-only contract. Ordinary notes,
quick Inbox bookmarks, and non-source captures load neither article contract.
Standard captures pay only the lighter web-capture context cost.

## Forward Evaluation

Add bounded, tool-neutral fixtures covering:

1. direct public acquisition succeeds;
2. the first path is challenged but a different public representation is
   complete;
3. an authenticated or signed URL forbids third-party fallback;
4. a body image carries material information;
5. all safe paths remain incomplete and the only valid result is zero writes;
6. an ordinary useful article selects standard;
7. an empirical numerical claim is locally marked as source self-report;
8. an explicit research request selects verified and requires a receipt.

Static tests prove that each fixture is routed to an explicit contract and that
generated Skill payloads include the same references. They do not claim to
prove arbitrary Agent behavior or source truth.

The release evaluation also repeats the motivating public Juejin acquisition
read-only and records the observed coverage. It must not edit the real Vault.

## Compatibility and Non-Goals

- No new Web Clip template or article heading set.
- No comments capture by default.
- No built-in network fetcher or mandatory Jina dependency.
- No anti-bot, login, CAPTCHA, paywall, or access-control bypass.
- No automatic rewrite or reclassification of historical notes.
- No persistent telemetry, lifecycle status engine, or model quality score.
- No global rule that constrains browsing outside an explicit source capture.

