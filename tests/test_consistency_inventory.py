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
