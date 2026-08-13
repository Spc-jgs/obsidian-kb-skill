"""Assertions over relations that must hold between two places at once.

This file exists because the same defect kept recurring: something is stated in
two places, nothing checks they agree, and the failure is silent. #90 shipped
two helpers nothing referenced. #91 keeps twenty hand-copied installer paths.
#103 let one runner report a real capability as nonexistent. #108 shipped a
bundle whose import graph did not resolve while three separate checks passed.

The registry these assertions belong to is
`docs/superpowers/specs/2026-08-12-consistency-inventory.md`. Guards live where
they are most readable — several predate this file and stay put — so the
registry, not this module, is the complete list.

New assertions belong here when they guard a relation with no other natural
home. Do not add tests *about* the other guards: a guard for the guards is the
next hand-kept mirror.
"""
from __future__ import annotations

import importlib.util
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STANDARD_RUNNER = ROOT / "skills" / "obsidian-knowledge-base" / "scripts" / "run_helper.py"
RETRIEVAL_RUNNER = (
    ROOT / "skills" / "obsidian-knowledge-retrieval" / "scripts" / "run_helper.py"
)
FEATURE_GUIDE = ROOT / "docs" / "feature-guide.md"

# `doctor` diagnoses an installation, so it is reached through the bundled
# runner during troubleshooting and never as a standalone console command. The
# exemption is listed rather than assumed, so the next reader can tell a
# decision from an oversight.
CONSOLE_SCRIPT_EXEMPT = frozenset({"doctor"})


def _runner(path: Path):
    spec = importlib.util.spec_from_file_location(f"runner_{path.parent.parent.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _all_helpers() -> set[str]:
    return set(_runner(STANDARD_RUNNER).HELPERS) | set(_runner(RETRIEVAL_RUNNER).HELPERS)


def test_the_write_test_helper_list_matches_its_runner():
    """The retrieval side has had this assertion; the write side never did.

    Both test files parametrise over a hand-written tuple of helper names. The
    retrieval one is pinned to its runner; the write one was pinned to nothing,
    so a helper could be added to the runner and silently never exercised by
    the tests that iterate that tuple.
    """
    from tests.test_skill_runtime import HELPERS

    assert set(HELPERS) == set(_runner(STANDARD_RUNNER).HELPERS), (
        "tests/test_skill_runtime.py HELPERS no longer matches the write runner"
    )


def test_every_helper_has_a_console_script_or_a_stated_exemption():
    """`[project.scripts]` and the runners describe the same capability set.

    A helper reachable through only one of them is reachable in only one
    context: the wheel's console commands and the bundled Skill runner are
    different entry points for the same code.
    """
    declared = set(
        re.findall(
            r"^obsidian-([a-z-]+) =",
            (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
            re.M,
        )
    )
    helpers = _all_helpers()

    assert declared <= helpers, (
        f"console scripts naming helpers that do not exist: {sorted(declared - helpers)}"
    )
    assert helpers - declared == CONSOLE_SCRIPT_EXEMPT, (
        "a helper gained or lost a console script without updating the stated "
        f"exemption: {sorted((helpers - declared) ^ CONSOLE_SCRIPT_EXEMPT)}"
    )


def test_the_feature_guide_only_advertises_helpers_that_exist():
    """Documentation is where #90 hid: the capability table promised what
    `core/` never routed, and the promise made the gap harder to notice.

    Reachability is guarded elsewhere. This guards the weaker but unchecked
    direction — that the table does not name a helper the project does not
    have at all, which would send a reader looking for something that was
    renamed or removed.
    """
    text = FEATURE_GUIDE.read_text(encoding="utf-8")
    helpers = _all_helpers()
    # Only the capability table's implementation column, which is where the
    # document promises a capability exists. Scanning the whole file was the
    # first attempt and it was wrong: prose legitimately names workflows and
    # note types in backticks, and the exemption list needed to tell them apart
    # kept growing — a sign the predicate, not the document, was at fault.
    #
    # A cell naming something other than a helper says so in words (e.g.
    # "写入 Skill", "`conversation-harvest.md` 工作流，非 helper"), and those do
    # not match the bare-identifier shape.
    cited = {
        match.group(1)
        for line in text.splitlines()
        if line.startswith("|") and line.count("|") >= 4
        for match in [re.fullmatch(r"`([a-z][a-z-]{3,})`", line.split("|")[-2].strip())]
        if match
    }

    # The column cites three kinds of implementation: a helper, a note type, or
    # a whole Skill. Both non-helper kinds are sets the project already defines,
    # so excluding them costs no hand-maintained list.
    from obsidian_kb_skill.scripts.note_catalog import VALID_NOTE_TYPES

    skills = {path.name for path in (ROOT / "skills").iterdir() if path.is_dir()}
    cited -= set(VALID_NOTE_TYPES) | skills

    assert cited, "the capability table cites no helpers at all"
    assert cited <= helpers, (
        f"the feature guide advertises helpers that do not exist: "
        f"{sorted(cited - helpers)}"
    )


def test_the_filing_reference_names_the_draft_tag_the_code_defaults_to():
    """The reference tells an Agent what runs when it passes no `--draft-tag`.

    The default is a Vault vocabulary this Skill does not own, so the reference
    has to state it — an Agent that reads `incomplete` here and finds the code
    checking something else would tell the user their drafts are protected when
    they are not. The CLI help derives its text from the constant; prose cannot,
    so it is asserted instead.
    """
    from obsidian_kb_skill.scripts.process_inbox import DEFAULT_DRAFT_TAGS

    reference = (
        ROOT / "core" / "references" / "process-inbox.md"
    ).read_text(encoding="utf-8")

    assert DEFAULT_DRAFT_TAGS, "filing checks for no draft tag at all"
    for tag in DEFAULT_DRAFT_TAGS:
        assert f"`{tag}`" in reference, (
            f"the reference never names the default draft tag {tag!r}, so an "
            "Agent cannot know what it checks when passing nothing"
        )


def test_both_retrieval_helpers_mean_the_same_thing_by_next_actions():
    """One concept, one vocabulary — asserted by identity, not by equality.

    `review-projects` finds a project's next action and `resume-project`
    extracts the same section; each held its own literal set. #125 widened only
    the resume side with `后续行动`, and nothing noticed: on the reference Vault
    that note's seven checkboxes all sit under that heading, so scoping the
    radar's task count to the section would have silently zeroed it out.

    Sharing the tuple makes the agreement structural. Equality would let the
    two drift apart and back into step without anyone knowing which is right.
    """
    from obsidian_kb_skill.scripts import note_catalog, resume_project, review_projects

    shared = note_catalog.PROJECT_NOTE_NEXT_ACTION_HEADINGS
    assert shared, "no next-action heading is recognised at all"
    assert (
        resume_project.RESUME_SECTIONS["next_actions"]["project-note"] is shared
    ), "the resume contract restates the headings instead of deriving them"
    assert review_projects.NEXT_ACTION_HEADINGS == {
        heading.lower() for heading in shared
    }, "the radar's heading set is not the shared one"


def test_every_bash_invoking_installer_test_is_named_for_the_windows_skip():
    """The Windows skip is a name prefix, and nothing checked that it was used.

    `tests/test_installers.py` exempts bash lifecycle tests on Windows with an
    autouse fixture keyed on `test_bash_`. A test that runs `install.sh` under
    any other name runs on Windows, where POSIX path semantics do not hold, and
    fails in CI — which is how this assertion came to exist. A convention that
    only a reviewer enforces is the shape the registry exists for.

    Reading `install.sh` as text is fine anywhere; only invoking it is not, so
    the predicate looks for the `"bash"` argument rather than the filename.
    """
    import ast

    source = (ROOT / "tests" / "test_installers.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    def spawns_bash(node) -> bool:
        return any(
            isinstance(child, ast.Constant) and child.value == "bash"
            for child in ast.walk(node)
        )

    helpers = {
        node.name
        for node in functions
        if not node.name.startswith("test_") and spawns_bash(node)
    }
    assert helpers, "no bash-spawning helper found; the predicate has gone stale"

    def calls_a_helper(node) -> bool:
        return any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id in helpers
            for child in ast.walk(node)
        )

    offenders = sorted(
        node.name
        for node in functions
        if node.name.startswith("test_")
        and not node.name.startswith("test_bash_")
        and (spawns_bash(node) or calls_a_helper(node))
    )

    assert not offenders, (
        "these tests run install.sh but are not named `test_bash_*`, so the "
        f"Windows skip does not cover them: {offenders}"
    )


def test_every_zero_result_reason_is_documented_for_the_agent_that_reads_it():
    """A reason code an Agent cannot look up is a code it will paraphrase.

    The retrieval Skill ships `search.md` and nothing else about these; a code
    present in the helper but absent there leaves the Agent to invent what it
    means, which for `no-token-overlap` means telling the user their Vault is
    empty — the exact reading the code exists to prevent.
    """
    from obsidian_kb_skill.scripts.search_vault import ZERO_RESULT_REASONS

    reference = (
        ROOT / "core" / "retrieval-references" / "search.md"
    ).read_text(encoding="utf-8")

    assert ZERO_RESULT_REASONS, "the helper diagnoses nothing at all"
    for code in ZERO_RESULT_REASONS:
        assert f"`{code}`" in reference, f"undocumented zero-result reason: {code}"


def test_the_two_activity_semantics_are_documented_as_different():
    """Two helpers answer "recent" differently, and that is deliberate.

    `search-vault --updated-after` reads `updated` only; `review-projects`
    reads `updated` falling back to `date`. Registry row 28 records the pair
    because the danger is not the difference — it is a reader assuming there is
    only one answer. #119 asked for exactly this row, so the reference has to
    keep saying which is which.
    """
    reference = (
        ROOT / "core" / "retrieval-references" / "search.md"
    ).read_text(encoding="utf-8")

    assert "`--updated-after`" in reference
    assert "review-projects" in reference, (
        "the reference never mentions the other activity semantics, so an "
        "Agent cannot know the two differ"
    )
    # The fallback must be described as belonging to the other helper, never
    # as something this one does.
    assert "falling back to `date`" in reference
