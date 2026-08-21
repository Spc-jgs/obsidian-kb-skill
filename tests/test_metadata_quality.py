"""Direct tests for the predicate shared by the create and audit paths.

Nothing tested `is_meaningful_metadata` on its own before; it was reached only
through whichever caller happened to exercise it, and every one of those passed
a quoted string.
"""
from __future__ import annotations

import datetime

from obsidian_kb_skill.scripts.metadata_quality import is_meaningful_metadata


def test_an_unquoted_yaml_date_is_a_value_not_a_placeholder():
    """Quoting a date decided whether the note was reported as missing it.

    `published: 2026-08-13` is YAML's own date syntax and parses to
    `datetime.date`; `published: '2026-08-13'` parses to `str`. The predicate
    returned False for anything that was not `str`, so two web-clips on the
    reference Vault filled `published` and `author` correctly and were reported
    as missing both — the notes written most conventionally were the penalised
    ones.
    """
    assert is_meaningful_metadata(datetime.date(2026, 8, 13)) is True
    assert is_meaningful_metadata(datetime.datetime(2026, 8, 13, 9, 30)) is True


def test_a_bare_year_carries_information_even_though_yaml_calls_it_an_int():
    """One reference-Vault clip records `published: 2025` — the year is all the source gave."""
    assert is_meaningful_metadata(2025) is True


def test_a_value_that_is_absent_stays_absent_whatever_its_type():
    assert is_meaningful_metadata(None) is False
    assert is_meaningful_metadata("") is False
    assert is_meaningful_metadata("   ") is False


def test_a_container_is_not_a_scalar_answer():
    """`author: []` is a shape mistake, not an author."""
    assert is_meaningful_metadata([]) is False
    assert is_meaningful_metadata({}) is False
    assert is_meaningful_metadata(["Jane"]) is False


def test_a_boolean_is_not_a_date_even_though_python_calls_it_an_int():
    """`published: true` is YAML accepting a typo, and `bool` is a subclass of `int`."""
    assert is_meaningful_metadata(True) is False
    assert is_meaningful_metadata(False) is False


def test_the_placeholder_words_are_still_placeholders():
    assert is_meaningful_metadata("unknown") is False
    assert is_meaningful_metadata("TBD") is False
    assert is_meaningful_metadata("{{date}}") is True  # shape checked elsewhere
    assert is_meaningful_metadata("Jane") is True
