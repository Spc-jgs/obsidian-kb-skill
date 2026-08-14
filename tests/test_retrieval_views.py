"""Declarative read-only retrieval views (#122).

A view is a search the user has already agreed on, written down so it runs the
same way twice. It declares structured fields and nothing else — no command, no
template, no interpolation — and it can only reach parameters `search-vault`
already validates. The point is reproducibility, so the helper resolves a plan
and shows it, and running that plan directly must give the same answer.
"""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts import retrieval_views
from obsidian_kb_skill.scripts.search_vault import search_vault

AS_OF = datetime.date(2026, 8, 14)


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    for folder in ("20-Learning", "30-Insights", "40-Projects"):
        (vault / folder).mkdir()
    return vault


def write_note(
    path: Path,
    *,
    note_type: str = "learning-note",
    date: str = "2026-08-12",
    updated: str | None = None,
    tags: list[str] | None = None,
    body: str = "退避上限与重试策略。\n",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"type: {note_type}", f"date: '{date}'"]
    if updated is not None:
        lines.append(f"updated: '{updated}'")
    lines.append(f"tags: {json.dumps(tags or ['x'], ensure_ascii=False)}")
    lines.append("---")
    path.write_text("\n".join(lines) + f"\n\n# {path.stem}\n\n{body}", encoding="utf-8")


def write_views(vault: Path, document: dict | str) -> None:
    folder = vault / retrieval_views.VIEWS_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    raw = document if isinstance(document, str) else json.dumps(
        document, ensure_ascii=False
    )
    (folder / retrieval_views.VIEWS_FILENAME).write_text(raw, encoding="utf-8")


def one_view(**overrides) -> dict:
    view = {
        "id": "recent-learning",
        "query": "退避上限",
        "types": ["learning-note"],
        "scope": "20-Learning",
        "date_field": "date",
        "window_days": 7,
        "top_k": 10,
    }
    view.update(overrides)
    return {"schema_version": 1, "views": [view]}


def hashes(vault: Path) -> dict[str, str]:
    return {
        path.relative_to(vault).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(vault.rglob("*"))
        if path.is_file()
    }


def run(vault: Path, view: str = "recent-learning", **kwargs):
    kwargs.setdefault("as_of", AS_OF)
    return retrieval_views.build(vault, view=view, **kwargs)


def test_a_view_runs_the_search_it_declares(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "recent.md", date="2026-08-12")
    write_note(vault / "20-Learning" / "old.md", date="2026-01-01")
    write_note(vault / "30-Insights" / "elsewhere.md", date="2026-08-12")
    write_views(vault, one_view())

    payload = run(vault)

    assert payload["ok"] is True
    assert payload["read_only"] is True
    assert [item["path"] for item in payload["results"]] == ["20-Learning/recent.md"]


def test_the_resolved_plan_is_shown_and_reproduces_the_same_results(tmp_path):
    """#122's own bar: the plan is not a summary, it is the call that was made.

    A plan a reader cannot re-run is decoration. Running it through
    `search-vault` directly has to give the same answer, or the view is doing
    something the plan does not say.
    """
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "recent.md", date="2026-08-12")
    write_note(vault / "20-Learning" / "edge.md", date="2026-08-08")
    write_note(vault / "20-Learning" / "outside.md", date="2026-08-07")
    write_views(vault, one_view())

    payload = run(vault)
    plan = payload["plan"]

    assert plan == {
        "query": "退避上限",
        "types": ["learning-note"],
        "tags": [],
        "scope": "20-Learning",
        "top_k": 10,
        "after": "2026-08-08",
        "before": "2026-08-14",
        "updated_after": None,
        "updated_before": None,
    }
    direct = search_vault(
        vault,
        plan["query"],
        types=plan["types"],
        tags=plan["tags"],
        scope=Path(plan["scope"]),
        top_k=plan["top_k"],
        after=plan["after"],
        before=plan["before"],
    )
    assert [item["path"] for item in payload["results"]] == [
        item["path"] for item in direct["results"]
    ]


def test_the_window_is_inclusive_and_counted_from_as_of(tmp_path):
    """`window_days: 7` means seven days including today, not eight."""
    vault = make_vault(tmp_path)
    write_views(vault, one_view(window_days=7))

    plan = run(vault)["plan"]

    assert plan["after"] == "2026-08-08"
    assert plan["before"] == "2026-08-14"


def test_date_field_updated_maps_to_the_other_pair_of_filters(tmp_path):
    """Row 28's distinction, reachable from a view without being blurred."""
    vault = make_vault(tmp_path)
    write_views(vault, one_view(date_field="updated"))

    plan = run(vault)["plan"]

    assert plan["after"] is None and plan["before"] is None
    assert plan["updated_after"] == "2026-08-08"
    assert plan["updated_before"] == "2026-08-14"


def test_as_of_is_required_because_a_window_must_be_reproducible(tmp_path):
    """Reading the clock would make the same view give different answers."""
    vault = make_vault(tmp_path)
    write_views(vault, one_view())

    with pytest.raises(TypeError):
        retrieval_views.build(vault, view="recent-learning")


def test_a_view_without_a_window_needs_no_date_filter(tmp_path):
    vault = make_vault(tmp_path)
    write_views(vault, one_view(window_days=None, date_field=None))

    plan = run(vault)["plan"]

    assert plan["after"] is None and plan["before"] is None


def test_an_unknown_view_is_refused_and_names_what_exists(tmp_path):
    vault = make_vault(tmp_path)
    write_views(vault, one_view())

    payload = run(vault, view="nope")

    assert payload["ok"] is False
    assert payload["error"]["code"] == "unknown-view"
    assert "recent-learning" in payload["error"]["message"]


def test_a_missing_config_is_refused_rather_than_treated_as_no_views(tmp_path):
    vault = make_vault(tmp_path)

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "missing-view-config"


def test_corrupt_json_refuses_instead_of_running_a_different_search(tmp_path):
    """The lexicon's rule: a config that half-parsed is a search nobody can reproduce."""
    vault = make_vault(tmp_path)
    write_views(vault, '{"schema_version": 1, "views": [')

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid-view-config"


def test_an_unknown_field_is_refused_rather_than_ignored(tmp_path):
    """Silently dropping a field runs a search the file does not describe."""
    vault = make_vault(tmp_path)
    write_views(vault, one_view(shell="rm -rf /"))

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid-view-config"
    assert "shell" in payload["error"]["message"]


def test_a_duplicate_id_is_refused_because_neither_view_is_the_view(tmp_path):
    vault = make_vault(tmp_path)
    document = one_view()
    document["views"].append(dict(document["views"][0], query="别的"))
    write_views(vault, document)

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid-view-config"
    assert "recent-learning" in payload["error"]["message"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"top_k": 0},
        {"top_k": retrieval_views.MAX_TOP_K + 1},
        {"window_days": 0},
        {"window_days": retrieval_views.MAX_WINDOW_DAYS + 1},
        {"id": "x" * (retrieval_views.MAX_VIEW_ID_CHARS + 1)},
        {"query": ""},
        {"date_field": "created"},
        {"types": "learning-note"},
    ],
)
def test_out_of_range_declarations_are_refused(tmp_path, overrides):
    vault = make_vault(tmp_path)
    write_views(vault, one_view(**overrides))

    payload = run(vault)

    assert payload["ok"] is False, f"{overrides} was accepted"
    assert payload["error"]["code"] == "invalid-view-config"


def test_a_scope_that_no_longer_exists_says_so_instead_of_widening(tmp_path):
    """A moved folder must not quietly become "the whole Vault".

    That is the failure #122 calls out by name: the view keeps working, returns
    more than it ever did, and nothing says the boundary is gone.
    """
    vault = make_vault(tmp_path)
    write_note(vault / "30-Insights" / "elsewhere.md")
    write_views(vault, one_view(scope="20-Renamed"))

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid-view-scope"
    assert payload.get("results") is None


def test_a_scope_outside_the_vault_is_refused(tmp_path):
    vault = make_vault(tmp_path)
    write_views(vault, one_view(scope="../../etc"))

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] in {"invalid-view-config", "invalid-view-scope"}


def test_an_oversized_config_is_refused(tmp_path):
    vault = make_vault(tmp_path)
    write_views(vault, "x" * (retrieval_views.MAX_VIEWS_BYTES + 1))

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid-view-config"


def test_too_many_views_are_refused(tmp_path):
    vault = make_vault(tmp_path)
    document = {
        "schema_version": 1,
        "views": [
            {"id": f"v{index}", "query": "退避"}
            for index in range(retrieval_views.MAX_VIEWS + 1)
        ],
    }
    write_views(vault, document)

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid-view-config"


def test_the_config_folder_is_never_itself_searched(tmp_path):
    """`.obsidian-kb/` is configuration, not knowledge — the lexicon's rule."""
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "note.md")
    write_views(vault, one_view(scope=None, types=None, window_days=None, date_field=None))

    payload = run(vault)

    assert all(
        not item["path"].startswith(retrieval_views.VIEWS_FOLDER)
        for item in payload["results"]
    )


def test_only_one_view_runs_per_call(tmp_path):
    """MVP bound: batching several views is unbounded output by another name."""
    vault = make_vault(tmp_path)
    document = one_view()
    document["views"].append({"id": "second", "query": "别的"})
    write_views(vault, document)

    payload = run(vault)

    assert payload["view"] == "recent-learning"
    assert "results" in payload and isinstance(payload["results"], list)


def test_every_view_field_maps_to_a_parameter_search_vault_really_has(tmp_path):
    """The consistency boundary #122 asks for, asserted rather than assumed.

    A view schema is a second spelling of `search_vault`'s signature. Renaming a
    parameter there would leave the mapping pointing at nothing, and the view
    would fail at call time in a user's Vault rather than here.
    """
    import inspect

    parameters = set(inspect.signature(search_vault).parameters)

    assert retrieval_views.VIEW_TO_SEARCH, "the mapping is empty"
    for view_field, search_parameter in retrieval_views.VIEW_TO_SEARCH.items():
        assert search_parameter in parameters, (
            f"view field {view_field!r} maps to {search_parameter!r}, which "
            "search_vault does not accept"
        )
    for pair in retrieval_views.DATE_FIELDS.values():
        for name in pair:
            assert name in parameters, (
                f"date field maps to {name!r}, which search_vault does not accept"
            )


def test_running_a_view_writes_nothing(tmp_path):
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "note.md")
    write_views(vault, one_view())
    before = hashes(vault)

    run(vault)

    assert hashes(vault) == before


def test_a_scope_pointing_at_a_file_is_refused_too(tmp_path):
    """The other half of `invalid-view-scope`, which has two causes.

    A scope that vanished is caught by the path guard; a scope that still exists
    but is a note rather than a folder reaches the helper's own check. Both must
    refuse, and only writing the first test would leave the second branch
    running on nobody's evidence.
    """
    vault = make_vault(tmp_path)
    write_note(vault / "20-Learning" / "note.md")
    write_views(vault, one_view(scope="20-Learning/note.md"))

    payload = run(vault)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid-view-scope"
    assert "not a directory" in payload["error"]["message"]
