"""Cross-lingual query expansion: the lexicon's rules, and what it may not do."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.query_expansion import (
    AMBIGUOUS_TERMS,
    BUILTIN_CONCEPTS,
    LEXICON_FOLDER,
    LEXICON_STOPWORDS,
    MAX_EXPANSION_CONCEPTS,
    MAX_EXPANSION_TOKENS,
    MAX_TERM_CHARS,
    MIN_TERM_CHARS,
    Concept,
    LexiconError,
    duplicate_terms,
    expand_query,
    load_lexicon,
    validate_concepts,
)
from obsidian_kb_skill.scripts.search_vault import search_vault


ROOT = Path(__file__).resolve().parent.parent
# The six no-answer queries from the versioned retrieval corpus. A lexicon that
# fires on any of them has stopped being domain vocabulary.
NO_ANSWER_QUERIES = (
    "quantum ledger consensus",
    "火星土壤光谱校准",
    "COBOL payroll compiler",
    "蛋白质折叠冷冻电镜",
    "satellite orbital decay",
    "古希腊陶器年代测定",
)


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    return vault


def _note(vault: Path, name: str, *, title: str, body: str) -> Path:
    path = vault / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntype: learning-note\ndate: 2026-08-11\naliases: []\ntags: []\n---\n"
        f"# {title}\n\n{body}\n",
        encoding="utf-8",
    )
    return path


def _write_lexicon(vault: Path, document: object) -> Path:
    folder = vault / LEXICON_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "retrieval-lexicon.json"
    path.write_text(
        document
        if isinstance(document, str)
        else json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


# --- the shipped lexicon is held to the rules a user's file is held to -------


def test_builtin_lexicon_satisfies_its_own_structural_rules():
    concepts = validate_concepts(BUILTIN_CONCEPTS, source="built-in lexicon")

    assert concepts
    assert len(concepts) == len({concept.id for concept in concepts})


def test_builtin_lexicon_carries_no_general_language():
    """The one rule that decides whether expansion is signal or noise."""
    offenders = sorted(
        term
        for concept in BUILTIN_CONCEPTS
        for term in concept.terms
        if term.casefold() in LEXICON_STOPWORDS
    )

    assert not offenders


def test_every_shared_term_is_a_declared_ambiguity():
    """A term two concepts claim is either deliberate or an editing accident."""
    assert set(duplicate_terms(BUILTIN_CONCEPTS)) == set(AMBIGUOUS_TERMS)


def test_declared_ambiguity_expands_both_readings_and_says_so():
    """代理 is an agent and a network proxy. Silently picking one is a lie."""
    expansion = expand_query("这个代理怎么配置")

    fired = {concept.id for concept in expansion.concepts}
    assert {"agent", "proxy"} <= fired


@pytest.mark.parametrize("query", NO_ANSWER_QUERIES)
def test_no_answer_queries_expand_to_nothing(query):
    """Expansion is the likeliest way to break no-answer precision."""
    expansion = expand_query(query)

    assert expansion.tokens == ()
    assert expansion.concepts == ()


# --- matching -----------------------------------------------------------------


def test_cjk_terms_match_as_substrings_because_chinese_has_no_delimiter():
    expansion = expand_query("怎么避免缓存击穿")

    assert "cache" in expansion.tokens
    assert "stampede" in expansion.tokens


def test_latin_terms_need_a_consecutive_run_not_two_scattered_words():
    matched = expand_query("cache stampede in production")
    scattered = expand_query("the stampede of users emptied the cache of tickets")

    assert "缓存" in matched.tokens
    assert "thundering" in matched.tokens
    # `cache` and `stampede` both appear, so a bag-of-words matcher would fire
    # the compound concept here and expand a crowd of users into a cache bug.
    assert "thundering" not in scattered.tokens


def test_a_typed_token_is_never_re_added_as_an_expansion():
    expansion = expand_query("cache 缓存")

    assert "cache" not in expansion.tokens


def test_expansion_is_bounded_and_reports_its_own_truncation():
    concepts = [
        Concept(id=f"filler-{index:02d}", terms=(f"概念{index:02d}", f"filler{index:02d}"))
        for index in range(20)
    ]
    query = "".join(f"概念{index:02d}" for index in range(20))

    expansion = expand_query(query, concepts)

    assert len(expansion.concepts) <= MAX_EXPANSION_CONCEPTS
    assert len(expansion.tokens) <= MAX_EXPANSION_TOKENS
    assert expansion.truncated is True


def test_expansion_order_is_stable_across_runs():
    first = expand_query("检索权限和缓存过期")
    second = expand_query("检索权限和缓存过期")

    assert first.tokens == second.tokens
    assert [c.id for c in first.concepts] == [c.id for c in second.concepts]


# --- what the search does with it -----------------------------------------------


def test_a_chinese_question_reaches_an_english_only_note(tmp_path):
    """The whole point: before this, the same search returned nothing at all."""
    vault = _vault(tmp_path)
    _note(
        vault,
        "20-Learning/cache-stampede.md",
        title="Cache stampede control",
        body=(
            "Synchronized expiry causes concurrent misses and duplicate backend "
            "recomputation."
        ),
    )

    expanded = search_vault(vault, "怎样避免缓存同时过期造成重复回算")
    literal = search_vault(vault, "怎样避免缓存同时过期造成重复回算", expand=False)

    assert [item["path"] for item in expanded["results"]] == [
        "20-Learning/cache-stampede.md"
    ]
    assert literal["results"] == []


def test_only_notes_the_expansion_reached_carry_an_expansion_signal(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault,
        "20-Learning/expiry.md",
        title="Expiry",
        body="A key past its expiry is recomputed on the next read.",
    )
    _note(
        vault,
        "20-Learning/other.md",
        title="过期策略",
        body="讨论过期时间怎么定。",
    )

    payload = search_vault(vault, "过期")

    signals = {
        item["path"]: {signal["kind"] for signal in item["signals"]}
        for item in payload["results"]
    }
    assert "expansion" in signals["20-Learning/expiry.md"]
    assert "expansion" not in signals["20-Learning/other.md"]


def test_a_direct_signal_never_names_a_word_the_reader_did_not_type(tmp_path):
    vault = _vault(tmp_path)
    _note(
        vault,
        "20-Learning/expiry.md",
        title="Expiry",
        body="A key past its expiry is recomputed on the next read.",
    )

    payload = search_vault(vault, "过期")

    direct = [
        signal
        for signal in payload["results"][0]["signals"]
        if signal["kind"] != "expansion"
    ]
    assert all("expiry" not in signal["detail"] for signal in direct)


def test_a_typed_word_outranks_the_same_word_merely_expanded(tmp_path):
    """Evidence beats a hypothesis, even when both point at the same token."""
    vault = _vault(tmp_path)
    _note(vault, "20-Learning/typed.md", title="过期 策略", body="过期 过期 过期")
    _note(vault, "20-Learning/guessed.md", title="Expiry policy", body="expiry expiry")

    payload = search_vault(vault, "过期")

    assert payload["results"][0]["path"] == "20-Learning/typed.md"


def test_a_query_no_concept_matches_carries_no_expansion_block(tmp_path):
    vault = _vault(tmp_path)
    _note(vault, "20-Learning/pottery.md", title="Pottery", body="Greek pottery.")

    payload = search_vault(vault, "古希腊陶器年代测定")

    assert "expansion" not in payload


# --- validation ---------------------------------------------------------------


@pytest.mark.parametrize(
    "concept, fragment",
    [
        (Concept(id="Bad Id", terms=("检索", "search")), "concept id"),
        (Concept(id="lonely", terms=("检索",)), "2 to"),
        (Concept(id="repeats", terms=("检索", "检索")), "repeats a term"),
        (Concept(id="short", terms=("检", "search")), "characters"),
        (Concept(id="long", terms=("x" * (MAX_TERM_CHARS + 1), "search")), "characters"),
        (Concept(id="general", terms=("方法", "method")), "general language"),
        (Concept(id="untrimmed", terms=(" 检索 ", "search")), "untrimmed"),
    ],
)
def test_validate_concepts_refuses_a_malformed_entry(concept, fragment):
    with pytest.raises(LexiconError) as error:
        validate_concepts([concept], source="test")

    assert fragment in str(error.value)


def test_minimum_term_length_is_two_characters():
    assert MIN_TERM_CHARS == 2


# --- the Vault's own lexicon ---------------------------------------------------


def test_absent_lexicon_leaves_the_builtins_alone(tmp_path):
    vault = _vault(tmp_path)

    assert load_lexicon(vault) == validate_concepts(
        BUILTIN_CONCEPTS, source="built-in lexicon"
    )


def test_a_vault_can_teach_the_search_its_own_vocabulary(tmp_path):
    vault = _vault(tmp_path)
    _write_lexicon(
        vault,
        {
            "schema_version": 1,
            "concepts": [{"id": "generics", "terms": ["泛型", "generics"]}],
        },
    )
    _note(
        vault,
        "20-Learning/java-generics.md",
        title="Type erasure",
        body="Java generics are erased at compile time.",
    )

    payload = search_vault(vault, "泛型是怎么实现的")

    assert [item["path"] for item in payload["results"]] == [
        "20-Learning/java-generics.md"
    ]
    assert payload["expansion"]["concepts"][0]["id"] == "generics"


def test_the_lexicon_file_is_configuration_and_never_a_search_result(tmp_path):
    vault = _vault(tmp_path)
    _write_lexicon(
        vault,
        {
            "schema_version": 1,
            "concepts": [{"id": "generics", "terms": ["泛型", "generics"]}],
        },
    )

    payload = search_vault(vault, "generics")

    assert payload["results"] == []
    assert payload["scanned"]["files"] == 0


@pytest.mark.parametrize(
    "document, fragment",
    [
        ("{ not json", "not valid JSON"),
        ([], "must be an object"),
        ({"concepts": []}, "schema_version"),
        ({"schema_version": 2, "concepts": []}, "schema_version"),
        ({"schema_version": 1, "concepts": {}}, "must be a list"),
        ({"schema_version": 1, "concepts": [[]]}, "must be an object"),
        ({"schema_version": 1, "concepts": [{"terms": ["泛型", "generics"]}]}, "'id'"),
        ({"schema_version": 1, "concepts": [{"id": "x", "terms": "泛型"}]}, "'terms'"),
        (
            {"schema_version": 1, "concepts": [{"id": "retrieval", "terms": ["查", "x"]}]},
            "already a built-in concept",
        ),
    ],
)
def test_a_malformed_lexicon_refuses_rather_than_degrading_silently(
    tmp_path, document, fragment
):
    vault = _vault(tmp_path)
    _write_lexicon(vault, document)

    with pytest.raises(LexiconError) as error:
        load_lexicon(vault)

    assert fragment in str(error.value)


def test_an_oversized_lexicon_is_refused_by_size_before_it_is_parsed(tmp_path):
    vault = _vault(tmp_path)
    _write_lexicon(vault, "x" * (64 * 1024 + 1))

    with pytest.raises(LexiconError) as error:
        load_lexicon(vault)

    assert "exceeds" in str(error.value)


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlink creation needs elevation on Windows"
)
def test_a_symlinked_lexicon_is_refused(tmp_path):
    vault = _vault(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text('{"schema_version": 1, "concepts": []}', encoding="utf-8")
    folder = vault / LEXICON_FOLDER
    folder.mkdir()
    (folder / "retrieval-lexicon.json").symlink_to(outside)

    with pytest.raises(LexiconError) as error:
        load_lexicon(vault)

    assert "regular file" in str(error.value)


def test_the_cli_refuses_a_broken_lexicon_with_a_documented_code(tmp_path):
    vault = _vault(tmp_path)
    _write_lexicon(vault, "{ not json")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "obsidian_kb_skill.scripts.search_vault",
            str(vault),
            "--query",
            "缓存",
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout)["error"]["code"] == "invalid-lexicon"


def test_no_expand_ignores_a_broken_lexicon_because_it_reads_no_lexicon(tmp_path):
    vault = _vault(tmp_path)
    _write_lexicon(vault, "{ not json")
    _note(vault, "20-Learning/cache.md", title="Cache", body="Cache notes.")

    payload = search_vault(vault, "cache", expand=False)

    assert [item["path"] for item in payload["results"]] == ["20-Learning/cache.md"]
    assert "expansion" not in payload
