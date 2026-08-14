"""One-hop neighbourhood from a note's declared links (#121).

The helper shows the edges a Vault already states — body wikilinks, frontmatter
`related`, and inbound backlinks. It scores nothing, suggests nothing, and
resolves no ambiguity: #75 owns discovering new candidates and #85 owns evidence
lineage, and mixing either in here would let an inference read as a declaration.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from obsidian_kb_skill.scripts import explore_neighborhood


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for folder in ("20-Learning", "30-Insights", "40-Projects", "95-Sources"):
        (vault / folder).mkdir()
    return vault


def write_note(
    path: Path,
    *,
    note_type: str = "learning-note",
    body: str = "body\n",
    aliases: list[str] | None = None,
    related: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"type: {note_type}", "date: 2026-08-01", "tags: [x]"]
    if aliases is not None:
        lines.append(f"aliases: {json.dumps(aliases, ensure_ascii=False)}")
    if related is not None:
        lines.append(f"related: {json.dumps(related, ensure_ascii=False)}")
    lines.append("---")
    path.write_text("\n".join(lines) + f"\n\n{body}", encoding="utf-8")


def hashes(vault: Path) -> dict[str, str]:
    return {
        path.relative_to(vault).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(vault.rglob("*"))
        if path.is_file()
    }


def build(vault: Path, note: str, **kwargs):
    return explore_neighborhood.build(vault, note=Path(note), **kwargs)


def test_an_outgoing_body_wikilink_is_an_edge_with_its_line(tmp_path):
    """The plainest edge, and the line is what makes it checkable."""
    vault = make_vault(tmp_path)
    write_note(
        vault / "20-Learning" / "source.md",
        body="第一行\n\n参见 [[target]] 的说明。\n",
    )
    write_note(vault / "20-Learning" / "target.md")

    payload = build(vault, "20-Learning/source.md")

    assert payload["ok"] is True
    assert payload["read_only"] is True
    assert [
        (edge["target"], edge["direction"], edge["origin"], edge["state"])
        for edge in payload["edges"]
    ] == [("20-Learning/target.md", "out", "body", "resolved")]
    assert payload["edges"][0]["line"] == 9


def test_frontmatter_related_is_a_separate_origin_from_a_body_link(tmp_path):
    """`related` is a declaration about the note; a body link is a reference.

    #110 settled that difference for the resume pack and it holds here: they are
    both explicit, and they are not the same claim, so the reader gets to see
    which one they are looking at.
    """
    vault = make_vault(tmp_path)
    write_note(
        vault / "20-Learning" / "source.md",
        related=["[[declared]]"],
        body="参见 [[mentioned]]。\n",
    )
    write_note(vault / "20-Learning" / "declared.md")
    write_note(vault / "20-Learning" / "mentioned.md")

    payload = build(vault, "20-Learning/source.md")
    by_target = {edge["target"]: edge for edge in payload["edges"]}

    assert by_target["20-Learning/declared.md"]["origin"] == "related"
    assert by_target["20-Learning/mentioned.md"]["origin"] == "body"


def test_an_inbound_link_is_an_edge_pointing_the_other_way(tmp_path):
    """A backlink is the question "who thought this was relevant"."""
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "hub.md")
    write_note(
        vault / "30-Insights" / "cites.md", body="源自 [[hub]] 的结论。\n"
    )

    payload = build(vault, "20-Learning/hub.md")

    assert [
        (edge["source"], edge["target"], edge["direction"])
        for edge in payload["edges"]
    ] == [("30-Insights/cites.md", "20-Learning/hub.md", "in")]


def test_direction_selects_which_half_of_the_neighbourhood_is_returned(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "hub.md", body="去 [[downstream]]。\n")
    write_note(vault / "20-Learning" / "downstream.md")
    write_note(vault / "30-Insights" / "upstream.md", body="来自 [[hub]]。\n")

    out = build(vault, "20-Learning/hub.md", direction="out")
    inbound = build(vault, "20-Learning/hub.md", direction="in")

    assert {edge["direction"] for edge in out["edges"]} == {"out"}
    assert {edge["direction"] for edge in inbound["edges"]} == {"in"}
    assert len(build(vault, "20-Learning/hub.md")["edges"]) == 2


def test_an_alias_link_resolves_the_way_obsidian_resolves_it(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "source.md", body="参见 [[MCP 协议]]。\n")
    write_note(
        vault / "20-Learning" / "protocol.md", aliases=["MCP 协议"]
    )

    payload = build(vault, "20-Learning/source.md")

    assert payload["edges"][0]["target"] == "20-Learning/protocol.md"
    assert payload["edges"][0]["state"] == "resolved"


def test_an_ambiguous_link_is_reported_with_every_candidate_and_used_for_none(
    tmp_path,
):
    """Same rule as #110: picking one files another note's material as this one's."""
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "source.md", body="参见 [[Notes]]。\n")
    write_note(vault / "20-Learning" / "Notes.md")
    write_note(vault / "30-Insights" / "Notes.md")

    payload = build(vault, "20-Learning/source.md")
    edge = payload["edges"][0]

    assert edge["state"] == "ambiguous"
    assert edge["target"] is None
    assert edge["candidates"] == [
        "20-Learning/Notes.md",
        "30-Insights/Notes.md",
    ]


def test_a_broken_link_is_an_edge_that_says_so_rather_than_a_missing_one(tmp_path):
    """Dropping it would make a note with three stale links look sparser."""
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "source.md", body="参见 [[Nothing Here]]。\n")

    payload = build(vault, "20-Learning/source.md")

    assert [(edge["name"], edge["state"], edge["target"]) for edge in payload["edges"]] == [
        ("Nothing Here", "unresolved", None)
    ]


def test_a_link_inside_a_code_fence_is_an_example_not_an_edge(tmp_path):
    """Hard negative: the Vault's own docs quote wikilink syntax constantly."""
    vault = make_vault(tmp_path)
    write_note(
        vault / "20-Learning" / "source.md",
        body="真的链接 [[real]]。\n\n```markdown\n[[fenced]]\n```\n\n行内 `[[inline]]` 示例。\n",
    )
    write_note(vault / "20-Learning" / "real.md")
    write_note(vault / "20-Learning" / "fenced.md")
    write_note(vault / "20-Learning" / "inline.md")

    payload = build(vault, "20-Learning/source.md")

    assert [edge["target"] for edge in payload["edges"]] == ["20-Learning/real.md"]


def test_structural_edges_are_excluded_unless_asked_for(tmp_path):
    """A folder index links everything in its folder, which is not a neighbourhood.

    #133 established that an index is a listing rather than material; the same
    judgement applies to an edge. A source archive is likewise evidence reached
    from the note that cites it, not a knowledge neighbour — #85's territory.
    """
    vault = make_vault(tmp_path)
    write_note(
        vault / "40-Projects" / "proj" / "proj.md",
        note_type="folder-index",
        body="# proj\n\n[[hub]]\n",
    )
    write_note(vault / "20-Learning" / "hub.md", body="见 [[95-Sources/raw]]。\n")
    write_note(vault / "95-Sources" / "raw.md", note_type="source-archive")

    payload = build(vault, "20-Learning/hub.md")

    assert payload["edges"] == []
    assert payload["excluded"] == {"index-note": 1, "source-archive": 1}

    # `neighbour` is the other end whichever way the edge points; `source` and
    # `target` describe the link as it was written, so an inbound edge's target
    # is the note being explored.
    widened = build(vault, "20-Learning/hub.md", include_structural=True)
    assert {edge["neighbour"] for edge in widened["edges"]} == {
        "40-Projects/proj/proj.md",
        "95-Sources/raw.md",
    }


def test_only_one_hop_is_walked(tmp_path):
    """A second hop is a different question and #121 defers it explicitly."""
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "a.md", body="[[b]]\n")
    write_note(vault / "20-Learning" / "b.md", body="[[c]]\n")
    write_note(vault / "20-Learning" / "c.md")

    payload = build(vault, "20-Learning/a.md")

    assert [edge["target"] for edge in payload["edges"]] == ["20-Learning/b.md"]


def test_a_cycle_terminates_and_reports_both_directions(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "a.md", body="[[b]]\n")
    write_note(vault / "20-Learning" / "b.md", body="[[a]]\n")

    payload = build(vault, "20-Learning/a.md")

    assert sorted(
        (edge["direction"], edge["neighbour"]) for edge in payload["edges"]
    ) == [("in", "20-Learning/b.md"), ("out", "20-Learning/b.md")]
    assert [node["path"] for node in payload["nodes"]] == ["20-Learning/b.md"]


def test_a_self_link_is_not_a_neighbour(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "a.md", body="见本文 [[a]]。\n")

    payload = build(vault, "20-Learning/a.md")

    assert payload["edges"] == []


def test_the_node_bound_is_enforced_and_the_truncation_is_visible(tmp_path):
    vault = make_vault(tmp_path)
    targets = [f"n{index}" for index in range(8)]
    write_note(
        vault / "20-Learning" / "hub.md",
        body="\n".join(f"[[{name}]]" for name in targets) + "\n",
    )
    for name in targets:
        write_note(vault / "20-Learning" / f"{name}.md")

    payload = build(vault, "20-Learning/hub.md", max_nodes=3)

    assert len(payload["nodes"]) == 3
    assert payload["truncated"] is True
    assert payload["summary"]["nodes_available"] == 8


def test_nodes_are_ordered_stably_so_two_runs_agree(tmp_path):
    vault = make_vault(tmp_path)
    write_note(
        vault / "20-Learning" / "hub.md",
        related=["[[zeta]]"],
        body="[[beta]]\n[[alpha]]\n",
    )
    for name in ("alpha", "beta", "zeta"):
        write_note(vault / "20-Learning" / f"{name}.md")

    first = build(vault, "20-Learning/hub.md")
    second = build(vault, "20-Learning/hub.md")

    assert first["nodes"] == second["nodes"]
    assert [node["path"] for node in first["nodes"]] == [
        "20-Learning/alpha.md",
        "20-Learning/beta.md",
        "20-Learning/zeta.md",
    ]


def test_a_missing_note_is_refused_with_a_code(tmp_path):
    vault = make_vault(tmp_path)

    payload = build(vault, "20-Learning/absent.md")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "missing-note"


def test_exploring_writes_nothing(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "a.md", body="[[b]]\n")
    write_note(vault / "20-Learning" / "b.md")
    before = hashes(vault)

    build(vault, "20-Learning/a.md")

    assert hashes(vault) == before
