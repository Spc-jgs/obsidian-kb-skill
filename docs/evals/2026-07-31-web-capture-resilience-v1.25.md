# Web Capture Resilience v1.25 Evaluation

## Scope

This evaluation checks the first-stage contract for choosing standard versus
verified capture, recovering from an inadequate first access path, protecting
private URLs, inspecting material media, qualifying unsupported empirical
claims, and stopping with zero writes when material source access remains
incomplete.

It combines deterministic tool-neutral fixtures with one read-only live
regression. It does not write to the real Vault and does not claim that static
tests can prove arbitrary Agent behavior or source truth.

## Reusable Fixture Coverage

`tests/fixtures/web_capture_resilience_eval_cases.json` contains eight cases:

| Case | Expected decision |
| --- | --- |
| direct public success | standard write after preflight |
| first path blocked, complete public alternative | standard write after fallback and preflight |
| authenticated/private URL | no third-party reader; stop if native access stays partial |
| material unread image | stop until the image is actually understood |
| all safe paths incomplete | zero writes |
| unsupported empirical number | standard write with local `source-self-report` qualification |
| explicit decision-grade research | verified path and receipt |
| expensive escalation discovered during standard capture | ask before escalation |

The fixtures name decisions and evidence conditions, not particular browser
brands or commands. Deterministic tests require every case to be reachable from
the lazy `web-capture.md` and `deep-capture.md` contracts.

## Live Juejin Regression

Date: 2026-07-31, Asia/Shanghai.

Target:
`https://juejin.cn/post/7664407325864558628`

The in-app text extraction returned only `Please wait...`, which is an
inadequate first representation rather than evidence that the public source is
unavailable.

A materially different direct public HTML request returned HTTP 200 and
132,637 bytes. Inside the article viewer it contained:

- 26 headings;
- 5 code blocks;
- 1 table;
- 2 article-body images.

The public Jina reader representation returned HTTP 200 and 14,626 bytes of
Markdown. It preserved:

- all 26 headings;
- 10 code-fence lines, representing 5 fenced code blocks;
- the comparison table;
- both article-body image references.

Both images were fetched and visually inspected. They are material architecture
diagrams rather than decoration:

1. the Feign path shows the interface, JDK dynamic proxy, Spring Cloud
   LoadBalancer, underlying HTTP client, and blocking I/O chain;
2. the `@HttpExchange` path shows `HttpServiceProxyFactory`, return-type
   branching, the asynchronous `WebClient` route, the synchronous `RestClient`
   route, and their execution-model boundaries.

Result: a first-path challenge must not lead to a placeholder note. The source
was recoverable through safe public alternatives, and the reader representation
retained the valuable text, code, table, and material image references.

## Claim Handling Walkthrough

The fixture statement “at 1000 concurrent requests, A is 40% faster than B”
cannot become an established comparison without sample, environment,
measurement method, and benchmark evidence. In standard capture it remains a
locally qualified `source-self-report`. Reproducing or independently
researching the result is a verified escalation and requires user consent when
the original request was ordinary capture.

## Zero-Write Walkthrough

When a required code sample, table, image, attachment, or linked artifact
remains partial after reasonable safe alternatives:

- `retrieval_status` cannot become `adequate`;
- create-note apply is not called;
- no placeholder or guessed summary is written;
- the report names the missing material, attempted safe paths, and user choices;
- Inbox capture occurs only after the user explicitly chooses that different
  outcome.

## Limits

- HTTP status and extraction quality may change over time.
- Structural counts establish coverage signals, not factual correctness.
- Jina is one permissible public representation, not a dependency or fixed
  fallback.
- The live regression does not modify or semantically upgrade the historical
  Vault note.

