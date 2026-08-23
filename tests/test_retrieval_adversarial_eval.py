"""Adversarial retrieval evaluation (#117).

The stable corpus in `retrieval_eval_cases.json` is 16 short, clean notes. The
v1.31 cross-lingual report said outright that it cannot choose an expansion
weight: results were identical from `EXPANSION_WEIGHT` 0.25 through 1.00. **An
evaluation set that cannot fail is a guard that was green from birth**, one
corpus wide — it certifies whatever the ranker currently does.

This set exists to make the ranker wrong on purpose, in five ways the real
Vault produces:

1. **dilution** — the same evidence paragraph in a 0.2 KB and a 30 KB note.
   `SearchDocument.weighted_length` sums every field over the whole document,
   so BM25 charges the long note for text the query never asked about.
2. **crowding** — five near-identical dailies and one insight note holding the
   conclusion. Nothing in Top-K selection considers redundancy.
3. **ambiguity** — `代理` is in `AMBIGUOUS_TERMS` and expands into *both* the
   `agent` and `proxy` concepts, so the surrounding words have to decide.
4. **field** — a stub whose title matches against a long note whose body holds
   the answer, with `FIELD_WEIGHTS["title"]` at 6x body.
5. **no-answer** — a shared strong term is not evidence.

Every family carries a control case that must keep passing, so no fix can be a
blanket rule in the other direction: a length bonus, a short-note demotion, or
a duplicate penalty would each break its own family's control.

**This file does not change ranking and does not assert that the current
behaviour is correct.** It records what the ranker does today, per case, and
fails when that changes — including when it changes for the better. A candidate
implementation is expected to update the baseline deliberately, in its own
commit, with the diff visible.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections import Counter
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.search_vault import CONFIDENCE_LEVELS, search_vault

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "retrieval_adversarial_cases.json"
BASELINE = ROOT / "tests" / "fixtures" / "retrieval_adversarial_baseline.json"

TOP_K = 5

# Filler is Latin so it cannot collide with a query token, a Chinese bigram, or
# any lexicon concept — its only job is to add length. Held to one line per
# paragraph so a note's size is a readable function of `filler_paragraphs`.
FILLER_WORDS = (
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua enim ad minim veniam "
    "quis nostrud exercitation ullamco laboris nisi aliquip ex ea commodo"
).split()


def _filler(paragraphs: int) -> str:
    """Deterministic neutral text. Same input, same bytes, every run."""
    lines = []
    for index in range(paragraphs):
        start = (index * 7) % len(FILLER_WORDS)
        rotated = FILLER_WORDS[start:] + FILLER_WORDS[:start]
        lines.append(" ".join(rotated * 3))
    return "\n\n".join(lines)


def _filler_heading(index: int) -> str:
    """A section title drawn from the filler, so it answers no query either.

    A heading built from meaningful words would hand the sectioned note a
    `FIELD_WEIGHTS["headings"]` boost its unstructured twin does not have, and
    the pair would then differ in two ways instead of one. Structure is the
    variable under test; everything else is held equal.
    """
    start = (index * 5) % len(FILLER_WORDS)
    return " ".join((FILLER_WORDS[start:] + FILLER_WORDS[:start])[:4])


def _sectioned_body(note: dict) -> str:
    """A long note shaped the way the reference Vault's long notes are shaped.

    The evidence sits in its own section, the filler is distributed over
    `filler_sections` further sections, and `late_body` — when present — goes in
    the last one, so a query for it has to reach past everything else.
    """
    paragraphs = _filler(note.get("filler_paragraphs", 0)).split("\n\n")
    sections = note["filler_sections"]
    per_section = max(len(paragraphs) // sections, 1)
    blocks = [f"## {_filler_heading(0)}\n\n{note['body']}"]
    for index in range(sections):
        chunk = paragraphs[index * per_section:(index + 1) * per_section]
        if not chunk:
            continue
        blocks.append(f"## {_filler_heading(index + 1)}\n\n" + "\n\n".join(chunk))
    if note.get("late_body"):
        blocks.append(f"## {_filler_heading(sections + 1)}\n\n{note['late_body']}")
    return "\n\n".join(blocks)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _build_vault(tmp_path: Path, fixture: dict) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for note in fixture["notes"]:
        path = vault / note["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if note.get("filler_sections"):
            body = _sectioned_body(note)
        else:
            filler = _filler(note.get("filler_paragraphs", 0))
            body = note["body"] if not filler else f"{note['body']}\n\n{filler}"
        path.write_text(
            "---\n"
            f'date: "{note["date"]}"\n'
            f"type: {note['type']}\n"
            f"aliases: {json.dumps(note['aliases'], ensure_ascii=False)}\n"
            f"tags: {json.dumps(note['tags'], ensure_ascii=False)}\n"
            "---\n"
            f"# {note['title']}\n\n{body}\n",
            encoding="utf-8",
        )
    return vault


def _families(fixture: dict) -> dict[str, str]:
    return {note["path"]: note["family"] for note in fixture["notes"]}


def _run(vault: Path, fixture: dict) -> tuple[list[dict], list[float]]:
    """Per-case outcome plus per-query wall time.

    The outcome is deliberately coarse — rank, misses, hits, occupancy — so the
    baseline records what a reader would act on rather than float scores that
    move on every tie-break.
    """
    family_of = _families(fixture)
    report: list[dict] = []
    latencies: list[float] = []
    for case in fixture["queries"]:
        started = time.perf_counter()
        payload = search_vault(vault, case["query"], top_k=TOP_K, expand=True)
        latencies.append((time.perf_counter() - started) * 1000)
        paths = [item["path"] for item in payload["results"]]

        expected = set(case["expected"])
        rank = next(
            (i for i, path in enumerate(paths, start=1) if path in expected),
            None,
        )
        occupancy = Counter(
            family_of[path] for path in paths if path in family_of
        )
        report.append(
            {
                "id": case["id"],
                "group": case["group"],
                "returned": len(paths),
                "rank": rank,
                "must_see_missing": sorted(
                    set(case["must_see"]) - set(paths)
                ),
                # Where, not just whether. Dilution shows up as an ordering
                # change long before it shows up as an exclusion, and a
                # baseline that only recorded presence would call that no
                # movement at all.
                "must_see_ranks": {
                    path: (paths.index(path) + 1 if path in paths else None)
                    for path in sorted(case["must_see"])
                },
                "hard_negative_hits": sorted(
                    set(case["hard_negatives"]) & set(paths)
                ),
                "family_occupancy": dict(sorted(occupancy.items())),
            }
        )
    return report, latencies


def _aggregate(report: list[dict]) -> dict:
    """Group metrics, reported beside the per-case rows and never instead.

    #117 requires both: aggregates make a trend legible, and per-case rows stop
    an aggregate from hiding one hard negative. A set whose mean improved while
    one no-answer case started returning a note has got worse.
    """
    by_group: dict[str, list[dict]] = {}
    for case in report:
        by_group.setdefault(case["group"], []).append(case)

    groups: dict[str, dict] = {}
    for group, cases in sorted(by_group.items()):
        answerable = [case for case in cases if case["rank"] is not None or True]
        # `no-answer` cases have no rank to average; their metric is the false
        # positive, counted below.
        ranked = [case for case in cases if case["group"] != "no-answer"]
        groups[group] = {
            "cases": len(cases),
            "recall_at_5": (
                round(
                    sum(1 for case in ranked if case["rank"] is not None)
                    / len(ranked),
                    3,
                )
                if ranked
                else None
            ),
            "mrr": (
                round(
                    sum(
                        1 / case["rank"] if case["rank"] else 0.0
                        for case in ranked
                    )
                    / len(ranked),
                    3,
                )
                if ranked
                else None
            ),
            "must_see_misses": sum(
                len(case["must_see_missing"]) for case in answerable
            ),
            "hard_negative_hits": sum(
                len(case["hard_negative_hits"]) for case in cases
            ),
        }

    no_answer = [case for case in report if case["group"] == "no-answer"]
    return {
        "groups": groups,
        "no_answer_false_positive_rate": (
            round(
                sum(1 for case in no_answer if case["returned"]) / len(no_answer),
                3,
            )
            if no_answer
            else None
        ),
        "cases_reproducing_a_limitation": sum(
            1
            for case in report
            if case["must_see_missing"] or case["hard_negative_hits"]
        ),
        "cases": len(report),
    }


# --- Fixture shape ----------------------------------------------------------


def test_the_adversarial_set_has_the_shape_the_issue_asked_for():
    fixture = _load(FIXTURE)
    queries = fixture["queries"]
    groups = Counter(case["group"] for case in queries)

    assert fixture["schema_version"] == 1
    assert len(queries) >= 20, "#117 asks for at least twenty adversarial queries"
    assert len({case["id"] for case in queries}) == len(queries)
    assert set(groups) == {
        "dilution",
        "crowding",
        "ambiguity",
        "field",
        "no-answer",
    }
    # Paired samples: every family needs both a case that should succeed and a
    # case that guards the opposite error.
    for group in groups:
        cases = [case for case in queries if case["group"] == group]
        assert len(cases) >= 4, f"{group} has too few cases to be paired"
    assert all(
        not case["expected"] for case in queries if case["group"] == "no-answer"
    )
    # A negative may live inside any family — #117 asks for paired positive and
    # negative samples per family, so `ambiguity` carries its own no-answer
    # case. What must hold is that an empty `expected` is deliberate: it names
    # what must *not* come back, rather than simply expecting nothing.
    for case in queries:
        if not case["expected"]:
            assert case["hard_negatives"], (
                f"{case['id']} expects nothing but names no hard negative, so "
                "an empty result and a wrong result score the same"
            )
    assert all(case.get("demonstrates") for case in queries), (
        "a case that does not say what it demonstrates cannot be reviewed"
    )


def test_the_adversarial_set_carries_no_private_content():
    serialized = FIXTURE.read_text(encoding="utf-8")

    for forbidden in (
        "/Users/",
        "my-knowledge-base",
        "shaopc",
        "Spc-jgs",
        "juejin.cn",
        "zhihu.com",
    ):
        assert forbidden not in serialized


def test_filler_cannot_answer_a_query():
    """Length must be the only thing filler contributes.

    A filler word that collided with a query token would make the long notes
    win for the wrong reason, and the dilution family would measure nothing.
    """
    from obsidian_kb_skill.scripts.text_tokens import tokenize

    fixture = _load(FIXTURE)
    filler_tokens = set(tokenize(_filler(3)))
    assert filler_tokens, "the filler generator produced no tokens"

    for case in fixture["queries"]:
        overlap = filler_tokens & set(tokenize(case["query"]))
        assert not overlap, f"{case['id']} shares tokens with filler: {overlap}"


def test_the_long_notes_are_actually_long(tmp_path):
    """The dilution family is meaningless if the pair is the same size."""
    fixture = _load(FIXTURE)
    vault = _build_vault(tmp_path, fixture)

    compact = (vault / "20-Learning/retry/backoff-compact.md").stat().st_size
    handbook = (vault / "20-Learning/retry/backoff-handbook.md").stat().st_size

    assert handbook > 25_000, f"handbook is only {handbook} bytes"
    assert handbook > compact * 50


# Real long notes are long *because they have many sections*. Measured on the
# reference Vault (186 notes, excluding `95-Sources`, `Templates` and
# `Attachments`): of the 19 notes at or above 10 KB, the fewest headings any of
# them carries is 12, the median is 30, the most is 100, and **not one** has a
# single heading. The three longest are 55.3 KB / 30 headings, 31.8 KB / 14, and
# 31.7 KB / 55.
#
# The set shipped with only the other shape — one heading and a wall of filler —
# which does occur (an archived clipping can be unstructured) but cannot stand
# for "a long note". The consequence was concrete: a passage-ranking candidate
# scored byte-identically to master on this set, because a note with one heading
# has exactly one passage and any heading-based split is a no-op on it. The set
# could not answer the question #118 exists to ask.
MIN_REAL_LONG_NOTE_HEADINGS = 12


def _heading_count(path: Path) -> int:
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#") and line.lstrip("#").startswith((" ", "\t"))
    )


def test_a_long_note_is_long_the_way_real_long_notes_are(tmp_path):
    """Both shapes of long note, because they fail differently.

    A structurally long note is the one the real Vault has, and it is the only
    one on which section-level ranking can be measured at all. The unstructured
    one stays: it is a real boundary case, and keeping both is what lets a
    result say *which* shape a change helped.
    """
    fixture = _load(FIXTURE)
    vault = _build_vault(tmp_path, fixture)

    structured = vault / "20-Learning/retry/backoff-manual.md"
    unstructured = vault / "20-Learning/retry/backoff-handbook.md"

    assert structured.is_file(), (
        "the dilution family has no structurally long note, so it cannot "
        "measure section-level ranking — see #136"
    )
    assert _heading_count(structured) >= MIN_REAL_LONG_NOTE_HEADINGS, (
        f"{structured.name} carries {_heading_count(structured)} headings; the "
        f"least any real long note has is {MIN_REAL_LONG_NOTE_HEADINGS}"
    )
    assert structured.stat().st_size > 25_000, "the structured note is not long"
    assert _heading_count(unstructured) <= 1, (
        "the unstructured shape is gone; both shapes must be present or a "
        "result cannot say which one a change helped"
    )


# BM25 penalises a document by its length *relative to the corpus mean*, so the
# mean decides which notes are penalised at all. Measured on the reference Vault
# (193 notes, excluding `95-Sources`, `Templates` and the backup directory): mean
# 4247 bytes, median 2390, and 84% of notes under 8 KB. The set shipped with three
# notes at or above 25 KB holding 97.9% of its bytes — the two 76 KB ones alone were
# 83.8% — which put its mean at 9170, more than double the real one. Every
# everyday note then sat far below the mean and took no penalty, which is why
# `adv-dilution-06` could not be observed here at all: it ranked first in the
# set while its real-Vault counterpart ranked second. The set now means 5010.
MAX_CORPUS_MEAN_BYTES = 6_000


def test_the_corpus_mean_length_stays_near_the_reference_vault(tmp_path):
    """A mean far above the real one silently disables the length penalty.

    This is not about any one case. The mean is global, so a corpus built around
    outliers measures a ranker nobody runs — every note under it is graded as if
    length normalisation were off.
    """
    fixture = _load(FIXTURE)
    vault = _build_vault(tmp_path, fixture)

    sizes = [path.stat().st_size for path in vault.rglob("*.md")]
    mean = sum(sizes) // len(sizes)

    assert mean <= MAX_CORPUS_MEAN_BYTES, (
        f"corpus mean is {mean} bytes against the reference Vault's 4247; above "
        f"{MAX_CORPUS_MEAN_BYTES} the everyday 2-8 KB notes stop being penalised "
        "and this set can no longer observe how they rank"
    )


# --- The frozen baseline ----------------------------------------------------


def test_the_recorded_baseline_still_describes_this_ranker(tmp_path):
    """Golden per-case outcomes. Failing here is a signal, not a verdict.

    A ranking change is supposed to move these numbers. Update the baseline in
    the same commit that changes the ranker, and say in the message which cases
    moved and why — the point of the file is that the movement is visible.
    """
    fixture = _load(FIXTURE)
    vault = _build_vault(tmp_path, fixture)
    before = _snapshot(vault)

    report, _ = _run(vault, fixture)

    assert _snapshot(vault) == before, "retrieval wrote to the Vault"
    recorded = _load(BASELINE)["cases"]
    by_id = {case["id"]: case for case in report}
    # The comparison below walks the *recorded* cases, so a query added to the
    # fixture without a baseline row would be checked by nothing at all — it
    # would look frozen while being free. Found when #136 added
    # `adv-dilution-05`, whose row nothing would have missed.
    unrecorded = sorted(set(by_id) - {case["id"] for case in recorded})
    assert not unrecorded, (
        f"these cases run but are not in the baseline: {unrecorded}. A case "
        "outside the frozen file is not held to anything."
    )
    drifted = [
        case_id
        for case_id, expected in {c["id"]: c for c in recorded}.items()
        if by_id.get(case_id) != expected
    ]
    assert not drifted, (
        "these cases no longer match the recorded baseline: "
        f"{drifted}\ncurrent: "
        + json.dumps(
            [by_id.get(case_id) for case_id in drifted],
            ensure_ascii=False,
        )
    )
    # The aggregate is checked too, and against a recomputation rather than a
    # second hand-kept copy: a recorded mean that no longer follows from the
    # recorded rows would make the summary and the detail disagree, which is
    # the shape the consistency registry exists for.
    assert _aggregate(report) == _load(BASELINE)["aggregate"]


def test_the_set_reproduces_at_least_one_real_limitation():
    """#117's own bar: a set that everything passes has taught us nothing.

    Read from the recorded baseline rather than a live run, so the claim is
    reviewable in the diff instead of depending on this machine.
    """
    recorded = _load(BASELINE)
    failing = [
        case
        for case in recorded["cases"]
        if case["must_see_missing"] or case["hard_negative_hits"]
    ]

    assert failing, (
        "no adversarial case fails against the current ranker, so this set "
        "provides no information the stable corpus did not already give"
    )
    # Named in the baseline so a future reader can tell a known limitation from
    # a regression that crept in.
    assert recorded["known_limitations"], "the failures are unexplained"


def test_the_control_cases_pass_today(tmp_path):
    """The other half of the bar: the set must not be uniformly red either.

    Each family's control asserts the error a naive fix would introduce. If
    these were failing too, the set would not distinguish a fix from a swap of
    one bias for another.
    """
    fixture = _load(FIXTURE)
    vault = _build_vault(tmp_path, fixture)
    report, _ = _run(vault, fixture)

    controls = {
        "adv-dilution-04",
        "adv-crowding-04",
        "adv-ambiguity-03",
        "adv-field-04",
    }
    for case in report:
        if case["id"] in controls:
            assert case["rank"] == 1, (
                f"{case['id']} is a control and must rank its note first, "
                f"got {case['rank']}"
            )


def test_the_adversarial_run_stays_inside_a_latency_budget(tmp_path):
    """A 30 KB note must not make retrieval feel different from a short one."""
    fixture = _load(FIXTURE)
    vault = _build_vault(tmp_path, fixture)

    _, latencies = _run(vault, fixture)

    p50 = statistics.median(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1]
    assert p50 < 400, f"P50 {p50:.0f}ms"
    assert p95 < 1200, f"P95 {p95:.0f}ms"


# --- Operator-run mode: a real Vault, nothing committed ---------------------


def test_a_real_vault_run_reports_without_exposing_it(tmp_path):
    """Point `OBSIDIAN_KB_EVAL_CASES` at your own annotated cases to run this.

    The operator's file stays in the operator's directory. Nothing about it is
    written back here: the assertion is on the shape of the report, and what a
    reader records in the repo is the aggregate plus a redacted failure kind.
    """
    import os

    cases_path = os.environ.get("OBSIDIAN_KB_EVAL_CASES")
    vault_path = os.environ.get("OBSIDIAN_KB_EVAL_VAULT")
    if not cases_path or not vault_path:
        pytest.skip(
            "set OBSIDIAN_KB_EVAL_CASES and OBSIDIAN_KB_EVAL_VAULT to run "
            "against a real Vault"
        )

    fixture = _load(Path(cases_path))
    vault = Path(vault_path).expanduser().resolve()
    before = _snapshot(vault)

    report, latencies = _run(vault, fixture)

    assert _snapshot(vault) == before, "retrieval wrote to the real Vault"
    assert len(report) == len(fixture["queries"])
    print(
        json.dumps(
            {
                "queries": len(report),
                "cases_with_missing_must_see": sum(
                    1 for case in report if case["must_see_missing"]
                ),
                "cases_with_hard_negative_hits": sum(
                    1 for case in report if case["hard_negative_hits"]
                ),
                "p50_ms": round(statistics.median(latencies)),
            },
            ensure_ascii=False,
        )
    )


def test_a_no_answer_query_is_reported_as_carrying_no_evidence(tmp_path):
    """#170: sharing common words with a note is not having an answer.

    The frozen baseline already names this, as `term-overlap-is-treated-as-
    evidence`: every no-answer case returns hits, and they carry a score, a
    heading and a snippet — the shape of a successful search. A caller cannot
    tell "the Vault answered" from "the Vault had nothing", so an Agent cites a
    Python note for a Feign question, or, worse, concludes the topic is already
    covered and never captures it.

    The statistic is how much of the **typed** query the winner matched,
    weighted by IDF, which makes "informative" countable without a stop-word
    list — a list would need a countable source, which #147 and #75 both
    settled that it must have, and question frames like 有什么 have none.

    **This catches four of the six, and the exemptions are the point.** On the
    reference Vault the signal separates nothing cleanly: 22 queries with no
    answer score 0.09–0.54 and 16 correctly-answered questions score 0.32–0.64,
    ranges that overlap. 0.30 is chosen because it demotes none of the 16 while
    catching 20 of the 22 — not because it draws a line.

    So the exempt pair is asserted by name rather than tolerated by a count. If
    a change catches `adv-noanswer-02`, this test fails and the person who made
    it gets to say so deliberately; if a change loses one of the four, it fails
    the same way. A `>= 4` assertion would have hidden both.
    """
    fixture = _load(FIXTURE)
    vault = _build_vault(tmp_path, fixture)
    cases = [case for case in fixture["queries"] if case["group"] == "no-answer"]
    assert cases, "the no-answer family disappeared from the fixture"

    # Measured at 0.32 and 0.35 against a floor of 0.30. Both are near-misses of
    # the kind the reference Vault also leaks: they share an informative term
    # with a note that does not answer them.
    KNOWN_LEAKS = {"adv-noanswer-04", "adv-noanswer-02"}

    leaked = set()
    for case in cases:
        payload = search_vault(vault, case["query"], top_k=TOP_K)
        confidence = payload.get("confidence")
        assert confidence is not None, (
            f"{case['id']}: the payload carries no `confidence`, so a caller "
            "still cannot tell an answer from lexical noise"
        )
        assert confidence["level"] in CONFIDENCE_LEVELS, confidence["level"]
        if confidence["level"] != "none":
            leaked.add(case["id"])

    assert leaked == KNOWN_LEAKS, (
        f"no-answer cases reported as carrying evidence changed: {sorted(leaked)}, "
        f"recorded {sorted(KNOWN_LEAKS)}"
    )
