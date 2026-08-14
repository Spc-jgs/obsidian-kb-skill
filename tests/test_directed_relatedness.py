"""Directional relatedness, scored from declared dependency (#75).

The v1.30 labels in `directed_link_eval_cases.json` were committed on
2026-08-09 with `purpose` saying "v1.30 adds no scorer" — a commitment about
what a scorer would have to achieve, made before one existed. They are the
independent half of this evaluation; everything else here was written to
satisfy them, so the tests that matter are the ones that tie the two together.

Every hard negative shares a *word* with its source and nothing else, so a
lexical scorer scores all sixteen highly. What separates the positives is that
the source note says, in its own text, what it uses the target for.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts import relatedness

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "tests" / "fixtures" / "directed_link_eval_cases.json"
CORPUS = ROOT / "tests" / "fixtures" / "directed_link_corpus.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for note in _load(CORPUS)["notes"]:
        path = vault / note["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            "type: learning-note\n"
            "date: '2026-08-01'\n"
            "tags: [design]\n"
            "---\n"
            f"# {note['title']}\n\n{note['body']}",
            encoding="utf-8",
        )
    return vault


def path_of(title: str) -> str:
    for note in _load(CORPUS)["notes"]:
        if note["title"] == title:
            return note["path"]
    raise AssertionError(f"no corpus note titled {title!r}")


def hashes(vault: Path) -> dict[str, str]:
    return {
        path.relative_to(vault).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(vault.rglob("*"))
        if path.is_file()
    }


# --- The corpus must realise the labels, not something adjacent --------------


def test_the_corpus_realises_every_label_and_invents_no_pair():
    """The corpus was written from the labels; this is what makes that checkable.

    Written first, before the scorer. A corpus that quietly drifted from the
    labels would let the scorer pass an evaluation nobody committed to — the
    labels are the only part of this not authored to make the scorer look good.
    """
    labels = _load(LABELS)
    titles = {note["title"] for note in _load(CORPUS)["notes"]}

    wanted = set()
    for case in labels["positive"] + labels["hard_negative"]:
        wanted.add(case["source"])
        wanted.add(case["target"])

    assert wanted <= titles, f"labels name notes the corpus lacks: {sorted(wanted - titles)}"
    assert titles <= wanted, f"corpus holds notes no label names: {sorted(titles - wanted)}"


def test_each_source_names_its_positive_target_and_never_its_negative():
    """The corpus's whole job, asserted rather than assumed.

    A source that linked its hard negative would make the negative a true
    positive and the evaluation meaningless; a source that did not link its
    positive target would make the positive unreachable by any honest scorer.
    """
    labels = _load(LABELS)
    bodies = {note["title"]: note["body"] for note in _load(CORPUS)["notes"]}

    for case in labels["positive"]:
        body = bodies[case["source"]]
        assert f"[[{case['target']}]]" in body, (
            f"{case['id']}: {case['source']} never names {case['target']}"
        )
    for case in labels["hard_negative"]:
        body = bodies[case["source"]]
        assert case["target"] not in body, (
            f"{case['id']}: {case['source']} names its hard negative {case['target']}"
        )


def test_each_hard_negative_really_does_collide_lexically():
    """Otherwise the negatives are easy for the wrong reason.

    Each label's `shared_topic` claims a word in common. If the corpus does not
    reproduce that overlap, the negatives are rejected because they are about
    nothing alike — which proves nothing about a scorer that had to tell a real
    collision apart.
    """
    stop = {"the", "a", "an", "and", "of", "to", "in", "is", "for", "how", "what", "this"}
    notes = {note["title"]: note["body"] for note in _load(CORPUS)["notes"]}

    def words(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in stop and len(w) > 2}

    thin = []
    for case in _load(LABELS)["hard_negative"]:
        source = words(case["source"] + " " + notes[case["source"]])
        target = words(case["target"] + " " + notes[case["target"]])
        shared = source & target
        if not shared:
            thin.append((case["id"], case["source"], case["target"]))

    assert not thin, (
        f"these hard negatives share no word with their source, so rejecting "
        f"them shows nothing: {thin}"
    )


# --- The scorer -------------------------------------------------------------


@pytest.mark.parametrize("case", _load(LABELS)["positive"], ids=lambda c: c["id"])
def test_every_positive_direction_is_found_with_traceable_evidence(tmp_path, case):
    """#75's first acceptance criterion, one test per labelled direction."""
    vault = build_vault(tmp_path)

    payload = relatedness.build(vault, note=Path(path_of(case["source"])))
    found = {item["target"]: item for item in payload["candidates"]}
    target = path_of(case["target"])

    assert target in found, (
        f"{case['id']}: {case['source']} → {case['target']} was not proposed"
    )
    candidate = found[target]
    assert candidate["evidence"].strip(), "a candidate with no evidence is a guess"
    assert candidate["line"] > 0
    lines = (vault / path_of(case["source"])).read_text(encoding="utf-8").splitlines()
    assert case["target"] in lines[candidate["line"] - 1], (
        "the cited line does not name the target"
    )


@pytest.mark.parametrize(
    "case", _load(LABELS)["hard_negative"], ids=lambda c: c["id"]
)
def test_every_hard_negative_is_rejected(tmp_path, case):
    """#75's second: sharing a folder, a type or a broad topic must not pass."""
    vault = build_vault(tmp_path)

    payload = relatedness.build(vault, note=Path(path_of(case["source"])))
    proposed = {item["target"] for item in payload["candidates"]}

    assert path_of(case["target"]) not in proposed, (
        f"{case['id']}: {case['target']} was proposed for {case['source']}, "
        f"but shares only: {case['shared_topic']}"
    )


def test_the_relation_is_directional_and_not_assumed_symmetric(tmp_path):
    """A→B says nothing about B→A, and the corpus is built so it cannot.

    The positive targets never link back. If the scorer returned the reverse
    direction it would be inventing a claim the Vault does not make.
    """
    vault = build_vault(tmp_path)
    forward = relatedness.build(vault, note=Path(path_of("Retry Policy")))
    backward = relatedness.build(vault, note=Path(path_of("Backoff Measurements")))

    assert path_of("Backoff Measurements") in {
        item["target"] for item in forward["candidates"]
    }
    assert path_of("Retry Policy") not in {
        item["target"] for item in backward["candidates"]
    }


def test_a_bare_mention_without_a_dependency_is_not_a_candidate(tmp_path):
    """Hard negative for the criterion itself: a link is not a dependency.

    `explore-neighborhood` (#121) already shows every declared link. This
    scorer earns its place only by saying which of them the source note depends
    on, so a link with nothing said about it must not be proposed.
    """
    vault = build_vault(tmp_path)
    source = vault / "20-Learning" / "design" / "Bare-Mention.md"
    source.write_text(
        "---\ntype: learning-note\ndate: '2026-08-01'\ntags: [design]\n---\n"
        "# Bare Mention\n\n## What this decides\n\nNothing much.\n\n"
        "## See also\n\n[[Backoff Measurements]]\n",
        encoding="utf-8",
    )

    payload = relatedness.build(vault, note=Path("20-Learning/design/Bare-Mention.md"))

    assert payload["candidates"] == []


def test_scoring_writes_nothing(tmp_path):
    vault = build_vault(tmp_path)
    before = hashes(vault)

    relatedness.build(vault, note=Path(path_of("Retry Policy")))

    assert hashes(vault) == before


def test_two_runs_agree_exactly(tmp_path):
    vault = build_vault(tmp_path)

    first = relatedness.build(vault, note=Path(path_of("Release Quality Gate")))
    second = relatedness.build(vault, note=Path(path_of("Release Quality Gate")))

    assert first == second


def test_a_missing_note_is_refused_with_a_code(tmp_path):
    vault = build_vault(tmp_path)

    payload = relatedness.build(vault, note=Path("20-Learning/design/absent.md"))

    assert payload["ok"] is False
    assert payload["error"]["code"] == "missing-note"


def test_a_dependency_phrase_elsewhere_in_the_note_does_not_qualify_a_link(tmp_path):
    """The same-sentence rule, which was unguarded until this test existed.

    Found by breaking it: replacing the sentence window with the whole note
    failed nothing, so the constraint was doing no work that anything checked.
    A note whose opening says "follows" and whose last line links something
    unrelated has declared nothing about that link.
    """
    vault = build_vault(tmp_path)
    source = vault / "20-Learning" / "design" / "Split Claim.md"
    source.write_text(
        "---\ntype: learning-note\ndate: '2026-08-01'\ntags: [design]\n---\n"
        "# Split Claim\n\n"
        "## Method\n\nCandidate priority follows the categories agreed last quarter.\n\n"
        "## See also\n\n[[Backoff Measurements]]\n",
        encoding="utf-8",
    )

    payload = relatedness.build(vault, note=Path("20-Learning/design/Split Claim.md"))

    assert payload["candidates"] == [], (
        "a dependency phrase in another section qualified an unrelated link"
    )
    assert payload["summary"]["links_without_a_dependency"] == 1


def test_the_hard_negatives_do_not_exercise_the_dependency_requirement(tmp_path):
    """What the 16 labelled negatives actually prove, stated so nobody overreads it.

    Each hard negative is a note the source never links to, so rejecting it
    needs no notion of dependency at all — removing the marker requirement
    entirely still rejects all sixteen. They guard against inferring a relation
    from a shared word, which is real and is what they were written for.

    The marker requirement is guarded by the two tests above instead. Recording
    the distinction here keeps "16/16 negatives rejected" from being read as
    evidence for a claim it does not support.
    """
    vault = build_vault(tmp_path)
    labels = _load(LABELS)

    for case in labels["hard_negative"]:
        body = (vault / path_of(case["source"])).read_text(encoding="utf-8")
        assert case["target"] not in body, (
            f"{case['id']} would exercise the dependency rule, not just the "
            "shared-word rule; the eval report says otherwise"
        )
