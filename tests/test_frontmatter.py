import datetime

from obsidian_kb_skill.scripts.frontmatter import (
    parse_frontmatter,
    portable_yaml_scalars,
)


def test_parse_normalizes_bom_crlf_and_dates():
    result = parse_frontmatter(
        "\ufeff---\r\npublished: 2026-07-13\r\n---\r\n# Body\r\n",
        source="stdin",
    )
    assert result.present is True
    assert result.issue is None
    assert result.metadata == {"published": datetime.date(2026, 7, 13)}
    assert result.body == "# Body\n"


def test_parse_reports_malformed_yaml_without_discarding_original_text():
    source = "---\ntags: [broken\n---\n# Body\n"
    result = parse_frontmatter(source, source="Inbox/bad.md")
    assert result.metadata is None
    assert result.body == source
    assert result.issue.code == "invalid-frontmatter"
    assert result.issue.source == "Inbox/bad.md"
    assert result.issue.line == 2


def test_parse_reports_unclosed_and_non_mapping_blocks():
    unclosed = parse_frontmatter("---\ntype: insight-note\n# Body\n")
    scalar = parse_frontmatter("---\nscalar\n---\n# Body\n")
    assert unclosed.issue.code == "unclosed-frontmatter"
    assert unclosed.body.startswith("---\n")
    assert scalar.issue.code == "frontmatter-not-mapping"
    assert scalar.body.startswith("---\n")


def test_missing_frontmatter_is_not_an_error():
    result = parse_frontmatter("# Body\n")
    assert result.present is False
    assert result.metadata is None
    assert result.issue is None
    assert result.body == "# Body\n"


def test_portable_scalars_convert_nested_dates_and_tuples():
    value = {
        "when": datetime.date(2026, 7, 13),
        "items": (datetime.datetime(2026, 7, 13, 1, 2),),
    }
    assert portable_yaml_scalars(value) == {
        "when": "2026-07-13",
        "items": ["2026-07-13T01:02:00"],
    }
