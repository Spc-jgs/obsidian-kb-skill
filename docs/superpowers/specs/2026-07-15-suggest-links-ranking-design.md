# Suggest-links Ranking Design

## Goal

Improve deterministic link suggestions for Chinese and mixed-language notes without embeddings, network calls, new dependencies, or automatic note mutation.

## Non-goals

- Do not add semantic models or build a Vault-wide index.
- Do not insert links automatically.
- Do not weaken the existing bounded, read-only workflow.

## Candidate scope

The note's own folder remains in scope. Up to two sibling folders may be added only when their normalized folder-name tokens overlap the target note's meaningful title or tag tokens. Alphabetical order alone must never make a sibling eligible. A note at the Vault root also keeps root-level notes in scope and applies the same relevance rule to child folders.

## Signals and scoring

1. Normalize Latin/digit runs case-insensitively. Keep runs of two or more characters.
2. Tokenize contiguous CJK text into overlapping bigrams, so titles such as `电子合同签章` and `电子签章方案` share useful local tokens.
3. Compute tag document frequency inside the bounded candidate set. Tags present on at least half the candidates (with at least two occurrences), structural note-kind tags such as `web-clip`, and the known overly broad `java` domain tag are generic and contribute no score.
4. Each specific shared tag contributes 3 points.
5. Each shared title token contributes 2 points, capped at 6 points to prevent long near-duplicate titles from dominating.
6. Matching note type contributes 1 supporting point.
7. Return a candidate only when its total score is at least 3. Same type, structural tags, or other weak signals alone therefore produce no suggestion.

Reasons must report only signals that contributed points. Ordering stays deterministic: descending score, then path.

## Compatibility and safety

- Keep the current CLI and JSON schema.
- Keep `top_n` behavior.
- Continue excluding the source note, indexes, templates, exempt files, and existing `related` targets.
- Read each candidate at most once during one suggestion run.
- Update packaged resources through the normal build process.

## Acceptance cases

- A Chinese title match is discoverable without tags.
- A Spring Boot candidate outranks a Java/web-clip-only candidate.
- Candidates sharing only type or generic tags are suppressed.
- An unrelated alphabetically early sibling folder is not scanned.
- Existing read-only, exclusion, CLI, JSON, and `top_n` behavior remains covered.
