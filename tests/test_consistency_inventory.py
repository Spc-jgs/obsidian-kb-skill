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


def test_both_skills_mean_the_same_thing_by_an_index_note():
    """One concept, one set — and `VALID_NOTE_TYPES` derives rather than repeats.

    `{"folder-index", "moc"}` existed twice: `audit_vault.INDEX_TYPES` exempting
    them from the note contract, the connectivity candidates and the title
    index, while `note_catalog.VALID_NOTE_TYPES` spelled the same two literals
    out inline. Nothing tied them together, and #133 made retrieval a third
    place that needs the judgement — a resume pack must not offer a project's
    own directory listing as material.

    Identity, not equality: two sets that happen to agree today can drift apart
    and back without anyone knowing which one was right in between.
    """
    from obsidian_kb_skill.scripts import audit_vault, note_catalog, resume_project

    shared = note_catalog.INDEX_TYPES
    assert shared, "no type marks a note as an index at all"
    assert audit_vault.INDEX_TYPES is shared, (
        "the audit holds its own copy of what an index is"
    )
    assert resume_project.INDEX_TYPES is shared, (
        "the resume pack holds its own copy of what an index is"
    )
    assert shared <= note_catalog.VALID_NOTE_TYPES, (
        "an index type the audit honours would be reported as `invalid-type`"
    )


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


def test_every_resume_origin_is_ranked_in_the_reference():
    """An origin the reference does not rank cannot be weighed by a reader.

    The field exists so a weaker membership claim does not look as reliable as
    a directory. An origin shipped without its trust level stated leaves the
    Agent to treat them as equal, which is the field's own defeat.
    """
    from obsidian_kb_skill.scripts.resume_project import ORIGIN_TRUST

    reference = (
        ROOT / "core" / "retrieval-references" / "resume-project.md"
    ).read_text(encoding="utf-8")

    assert len(ORIGIN_TRUST) == len(set(ORIGIN_TRUST)), "duplicate origin"
    for origin in ORIGIN_TRUST:
        assert f"`{origin}`" in reference, f"unranked resume origin: {origin}"


def test_no_module_declares_a_dependency_it_does_not_use():
    """An import block is a claim about what a module needs.

    Extracting `LinkIndex` into `link_graph` (#121) left five names imported
    into `audit_vault` and used nowhere — `INLINE_CODE_RE`, `declared_aliases`,
    `Iterable`, `defaultdict`, `read_frontmatter_head`. Nothing failed, and the
    reader is told the module still depends on things it no longer touches,
    which is exactly the wrong map to hand someone deciding what may move next.

    `__future__` is excluded because its effect is not a name, and anything a
    module re-exports through `__all__` is a deliberate pass-through.
    """
    import ast

    scripts = ROOT / "obsidian_kb_skill" / "scripts"
    unused: dict[str, list[str]] = {}
    for path in sorted(scripts.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        bound: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    bound[name] = node.lineno
        if not bound:
            continue
        used = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {
            node.value.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
        } | {
            element.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
            and isinstance(node.value, (ast.List, ast.Tuple))
            for element in node.value.elts
            if isinstance(element, ast.Constant)
        }
        dead = sorted(name for name in bound if name not in used)
        if dead:
            unused[path.name] = dead

    assert not unused, (
        f"these modules import names they never use: {unused}. An import block "
        "that outlived its use tells the next reader the module still depends "
        "on something it does not."
    )


def test_no_helper_can_reach_the_network():
    """A helper only ever sees the text the Agent typed.

    Registry row 66. #193 asked whether `create-note` could be made to refuse a
    capture whose fetch had failed, so that `web-capture.md`'s `Terminal Failure
    Means Zero Writes` would be enforced rather than only written down. It
    cannot: nothing in this package performs network I/O, so the fetch belongs
    entirely to the Agent and the only account of it a helper ever receives is
    the Agent's own. `2026-08-21-rejected-hypotheses.md` §7 closes the route on
    that fact, and the fact holds only while this stays true.

    Two halves, because either alone is bypassable. The runtime dependency set
    is read from `pyproject.toml` rather than restated, so adding an HTTP client
    fails here before any module imports it. And no module may import a
    network-capable standard-library module — a closed set, unlike the open one
    of third-party clients, which is why the dependency half carries that side.

    `urllib.parse` is not on the list and must not be: `capture_receipt` splits
    a source URL with it, which is string work and reaches nothing.
    """
    import ast

    network_stdlib = (
        "socket", "socketserver", "ssl", "http", "xmlrpc",
        "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "nntplib",
        "urllib.request", "urllib.error",
    )

    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = {
        re.split(r"[<>=!~\[;\s]", dependency, maxsplit=1)[0].strip().lower()
        for dependency in manifest["project"]["dependencies"]
    }
    assert runtime == {"pyyaml"}, (
        f"the runtime dependency set is now {sorted(runtime)}. A helper that "
        "can fetch would make §7's conclusion false, and the whole shape of "
        "#193 changes; state the reason for the new dependency here rather "
        "than widening this set silently."
    )

    def _forbidden(name: str | None) -> str | None:
        if not name:
            return None
        return next(
            (
                module
                for module in network_stdlib
                if name == module or name.startswith(f"{module}.")
            ),
            None,
        )

    reached: dict[str, list[str]] = {}
    for path in sorted((ROOT / "obsidian_kb_skill").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module]
            else:
                continue
            for hit in filter(None, (_forbidden(name) for name in names)):
                key = path.relative_to(ROOT).as_posix()
                reached.setdefault(key, []).append(f"{hit}:{node.lineno}")

    assert not reached, (
        f"these modules can reach the network: {reached}. The Agent fetches and "
        "the helper receives text — that asymmetry is what closed #193's "
        "prevention route, and a helper that fetches reopens it."
    )


def test_every_confidence_level_is_documented_for_the_agent_that_reads_it():
    """A level an Agent cannot look up is a level it will guess the meaning of.

    Registry row 37. `none` is the only finding `confidence` makes, and acting
    on it means declining to cite results that are sitting right there — an
    Agent that has not read what the level means will not do that. `evidence`
    needs documenting for the opposite reason: it is the *absence* of a finding
    and says nothing about correctness, which is exactly what an undocumented
    positive-sounding word gets read as.
    """
    from obsidian_kb_skill.scripts.search_vault import CONFIDENCE_LEVELS

    reference = (
        ROOT / "core" / "retrieval-references" / "search.md"
    ).read_text(encoding="utf-8")

    assert CONFIDENCE_LEVELS, "the helper reports no confidence at all"
    for level in CONFIDENCE_LEVELS:
        assert f"`{level}`" in reference, f"undocumented confidence level: {level}"


def test_the_confidence_floor_is_stated_where_it_was_measured():
    """The threshold and the measurement that produced it must not drift apart.

    0.30 is not a round number someone liked: it is the one cut that demotes
    none of the 16 correct answers measured while catching 20 of the 22 queries
    with no answer. A later reader who finds the constant alone will assume it
    is adjustable, and #170's first implementation shows what that costs — 0.60
    looked equally defensible and flagged 12 of those 16.
    """
    from obsidian_kb_skill.scripts.search_vault import CONFIDENCE_FLOOR

    design = (
        ROOT / "docs" / "superpowers" / "specs"
        / "2026-08-23-answer-confidence-design.md"
    ).read_text(encoding="utf-8")
    reference = (
        ROOT / "core" / "retrieval-references" / "search.md"
    ).read_text(encoding="utf-8")

    assert str(CONFIDENCE_FLOOR) in design, (
        f"the design does not state the floor the code uses ({CONFIDENCE_FLOOR})"
    )
    assert str(CONFIDENCE_FLOOR) in reference, (
        f"the Agent's reference does not state the floor ({CONFIDENCE_FLOOR})"
    )


def test_the_content_floor_is_the_value_the_distribution_supports():
    """Registry row 67. A floor is a claim about a corpus, not a taste.

    `WEB_CLIP_MIN_CONTENT_CHARS` was chosen from the reference Vault's measured
    distribution: shells at 100 and 220 content characters, self-declared drafts
    at 329 and 383, and the smallest real capture at 799. The number only means
    anything while it sits strictly between the largest shell and the smallest
    real capture, so moving it without re-measuring fails here rather than
    quietly starting to accuse real notes.

    The endpoints are asserted as the design records them. If a re-measurement
    moves them, this test and
    `2026-08-24-shell-capture-detection-design.md` change together.
    """
    from obsidian_kb_skill.scripts.audit_vault import WEB_CLIP_MIN_CONTENT_CHARS

    LARGEST_SHELL = 220
    SMALLEST_REAL_CAPTURE = 799

    assert LARGEST_SHELL < WEB_CLIP_MIN_CONTENT_CHARS < SMALLEST_REAL_CAPTURE, (
        f"the floor is {WEB_CLIP_MIN_CONTENT_CHARS}, outside the measured gap "
        f"{LARGEST_SHELL}–{SMALLEST_REAL_CAPTURE}. Below the gap it stops "
        "catching the shells it was built for; above it, it reports the "
        "smallest real capture the reference Vault holds."
    )

    design = (
        ROOT / "docs" / "superpowers" / "specs"
        / "2026-08-24-shell-capture-detection-design.md"
    ).read_text(encoding="utf-8")
    for number in (WEB_CLIP_MIN_CONTENT_CHARS, LARGEST_SHELL, SMALLEST_REAL_CAPTURE):
        assert str(number) in design, (
            f"the design does not state {number}, so the constant here cites a "
            "measurement a reader cannot find"
        )


def test_both_emptiness_findings_read_the_same_content_count():
    """Registry row 68. Two findings, one answer to "what is content".

    `empty-template-note` asks whether a note has any body at all and
    `web-clip-captured-nothing` whether it has enough of one. They are the same
    question at two thresholds, so a second counting loop would be free to
    answer it differently — headings counted here and not there, whitespace
    treated one way and then another.

    Asserting both call the shared helper is not enough on its own: a copy can
    be added beside the call. So the accumulator itself is counted, and there
    must be exactly one in the module.
    """
    import ast

    source = (
        ROOT / "obsidian_kb_skill" / "scripts" / "audit_vault.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }

    for name in ("_audit_empty_template", "_audit_shell_capture"):
        calls = {
            node.func.id
            for node in ast.walk(functions[name])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "_body_content_chars" in calls, (
            f"{name} no longer reads the shared count; the two findings can now "
            "disagree about what a note's content is"
        )

    accumulators = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "content_chars"
    ]
    assert len(accumulators) == 1, (
        f"{len(accumulators)} places accumulate `content_chars`; the count "
        "belongs to `_body_content_chars` alone, and a copy beside the call is "
        "how the two findings come to mean different things by content"
    )


def test_the_audit_skips_the_draft_tag_filing_files_on():
    """Registry row 69. One draft vocabulary, shared by object.

    `process_inbox` refuses to file a note carrying this tag; the audit skips
    the same note when judging whether a web-clip captured anything. If those
    two lists could drift, a Vault would get a note that filing calls a draft
    and the audit calls a defect — contradictory advice about one note.

    Neither module can import the other (`process_inbox` already imports
    `_note_title` from `audit_vault`), so the constant lives in the shared note
    domain and both read that object rather than restating it.
    """
    from obsidian_kb_skill.scripts import audit_vault, note_catalog, process_inbox

    assert audit_vault.DEFAULT_DRAFT_TAGS is note_catalog.DEFAULT_DRAFT_TAGS
    assert process_inbox.DEFAULT_DRAFT_TAGS is note_catalog.DEFAULT_DRAFT_TAGS


def test_the_unseen_term_floor_is_the_value_the_sweep_chose():
    """Registry row 70. A minimum length is a claim about a corpus.

    `UNSEEN_TERM_MIN_CHARS` was chosen from a sweep over the 42-case annotated
    set: every variant demotes 0 of the 16 correct answers, and the catch rate
    on the 22 no-answer queries is 14 at length 2, 13 at 3, and 10 at 4. Moving
    it without re-running that sweep would change the signal's reach with
    nothing saying so, so the design must keep stating the numbers this asserts.
    """
    from obsidian_kb_skill.scripts.search_vault import UNSEEN_TERM_MIN_CHARS

    assert UNSEEN_TERM_MIN_CHARS == 3, (
        f"the floor is {UNSEEN_TERM_MIN_CHARS}; the sweep that justified 3 is "
        "in 2026-08-24-unseen-terms-signal-design.md, and a different value "
        "needs that table re-run rather than an edit here"
    )

    design = (
        ROOT / "docs" / "superpowers" / "specs"
        / "2026-08-24-unseen-terms-signal-design.md"
    ).read_text(encoding="utf-8")
    for marker in ("len≥2", "len≥3", "len≥4", "0/16", "13/22"):
        assert marker in design, (
            f"the design no longer states {marker!r}, so this constant cites a "
            "sweep a reader cannot check"
        )


def test_every_link_token_is_also_a_body_token(tmp_path):
    """Registry row 71. `FIELD_WEIGHTS["links"]` is not the multiplier it reads as.

    `_wikilink_text` feeds a link's visible text into the *citing* note, and
    that text is already body text there, because the link markup is in the
    body. So the field is a duplicate count: on the reference Vault 1331 of 1331
    link-token instances are also body tokens, and on the 42-case annotated set
    no query has a token matched by `links` and by no other field. That is why
    #194 measured weights 0.0 through 2.0 as indistinguishable — and why raising
    the weight is not the fix either, since it would rank by how many links a
    note carries.

    The consequence a reader needs: link text scores at **3x**, not the 2x the
    table shows — 1x in `body` plus 2x again in `links`. If the duplication ever
    ends, this fails, and at that point the field is a real signal whose weight
    is worth tuning. Removal was measured and rejected; the reasoning is in
    `2026-08-24-unseen-terms-signal-design.md`.
    """
    from obsidian_kb_skill.scripts.search_vault import _load_documents

    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "target.md").write_text(
        "---\ntype: insight-note\ndate: 2026-08-24\ntags: [x]\n---\n"
        "# 组合优化的一种启发式解法\n\n把问题映射成能量最低态的搜索。\n",
        encoding="utf-8",
    )
    (vault / "citing.md").write_text(
        "---\ntype: learning-note\ndate: 2026-08-24\ntags: [x]\n---\n"
        "# 读书笔记\n\n记录在 "
        "[[组合优化的一种启发式解法|量子退火在组合优化中的应用]] 里。\n\n"
        "## 关联笔记\n\n- [[组合优化的一种启发式解法]]\n",
        encoding="utf-8",
    )

    documents, _scanned, _issues = _load_documents(vault, vault)
    assert documents, "the fixture produced no documents"

    orphaned: dict[str, list[str]] = {}
    for document in documents:
        body = document.field_tokens.get("body") or {}
        missing = sorted(
            token
            for token in (document.field_tokens.get("links") or {})
            if token not in body
        )
        if missing:
            orphaned[document.relative] = missing

    assert not orphaned, (
        f"these link tokens are not in their note's body: {orphaned}. The field "
        "has stopped being a duplicate, so it now carries signal of its own and "
        "its weight means what the table says — re-run #194's sweep and decide "
        "the value deliberately."
    )


def test_the_capture_reference_documents_the_evidence_fields_the_helper_emits(tmp_path):
    """The page tells an Agent which field to quote; the helper must emit it.

    `evidence` is a single word for a decision made per note, so it can be true
    and misleading at once — and was. The reference page now instructs the
    reader to quote `evidence_coverage` instead, which only helps while the
    field exists. Nothing else relates the two: the page is prose shipped in a
    Skill bundle, and the helper is Python in another.
    """
    import datetime
    import subprocess

    from obsidian_kb_skill.scripts.review_captures import review_captures

    reference = (
        ROOT / "core" / "retrieval-references" / "review-captures.md"
    ).read_text(encoding="utf-8")
    promised = set(re.findall(r"`(evidence(?:_[a-z]+)*)`", reference))
    assert "evidence_coverage" in promised, (
        "the page stopped naming evidence_coverage; either it regressed to "
        "quoting the one-word summary, or this guard is watching the wrong page"
    )

    vault = tmp_path / "vault"
    (vault / "20-Learning").mkdir(parents=True)
    (vault / ".obsidian").mkdir()
    note = vault / "20-Learning" / "中文剪藏.md"
    note.write_text(
        "---\ntype: web-clip\ndate: '2026-06-01'\ntags:\n- x\n---\n\n# 标题\n\n正文。\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=vault, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=vault, check=True)
    subprocess.run(["git", "add", "-A"], cwd=vault, check=True)
    subprocess.run(["git", "commit", "-qm", "add"], cwd=vault, check=True)

    report = review_captures(vault, as_of=datetime.date(2026, 8, 18))

    missing = sorted(field for field in promised if field not in report)
    assert not missing, (
        f"the reference names {missing}, which review-captures does not emit. "
        "An Agent told to quote a field that is absent will quote the one-word "
        "summary instead, which is the failure this pair exists to prevent."
    )
    assert sum(report["evidence_coverage"].values()) == report["summary"]["captures"]


def test_link_history_matches_the_keys_the_link_index_resolves_by(tmp_path):
    """History must ask the same question of the past that the index asks of now.

    Both sides produce well-formed findings whichever way they disagree, so a
    drift here is invisible: a target the index would have resolved, that
    history does not recognise, is silently reported as never written.
    """
    import subprocess

    from obsidian_kb_skill.scripts.audit_vault import LinkHistory
    from obsidian_kb_skill.scripts.link_graph import build_link_index

    vault = tmp_path / "vault"
    (vault / "20-Learning").mkdir(parents=True)
    (vault / ".obsidian").mkdir()
    names = [
        "20-Learning/CQRS.md",
        "20-Learning/2026-06-10 概念笔记.md",
        "20-Learning/带空格 的 名字.md",
    ]
    for name in names:
        (vault / name).write_text("---\ntype: learning-note\n---\nx\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.invalid"], cwd=vault, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=vault, check=True)
    subprocess.run(["git", "add", "-A"], cwd=vault, check=True)
    subprocess.run(["git", "commit", "-qm", "add"], cwd=vault, check=True)

    index = build_link_index([vault / name for name in names])
    history = LinkHistory(vault)
    assert history.available(), "the fixture is a repository; history must load"

    resolvable = set(index.by_name) | set(index.by_stem)
    for path in (vault / name for name in names):
        undated = re.sub(r"^\d{4}-\d{2}-\d{2}\s+", "", path.stem)
        if undated != path.stem:
            resolvable.add(undated)

    missing = sorted(key for key in resolvable if not history.ever_existed(key))
    assert not missing, (
        f"the index resolves {missing}, which history does not recognise. A "
        "target the index would have found is then reported as never written."
    )


def test_the_algorithms_doc_lists_the_severities_the_code_assigns():
    """A hand-kept mirror of `FINDING_SEVERITY`, with counts, and it had drifted.

    `docs/rules-and-algorithms.zh.md` enumerates every finding code under its
    severity and states how many there are. Nothing checked it, so two codes
    added in earlier releases — `duplicate-project-note` and
    `web-clip-captured-nothing` — were missing while the stated count still
    read as authoritative. The count is the part that makes it look checked.
    """
    from obsidian_kb_skill.scripts.audit_vault import FINDING_SEVERITY

    doc = (ROOT / "docs" / "rules-and-algorithms.zh.md").read_text(encoding="utf-8")
    actual: dict[str, set[str]] = {}
    for code, severity in FINDING_SEVERITY.items():
        actual.setdefault(severity, set()).add(code)

    problems: list[str] = []
    for severity, codes in sorted(actual.items()):
        match = re.search(
            rf"\*\*{severity}（(\d+)）\*\*：(.+?)(?=\n\n)", doc, re.S
        )
        if match is None:
            problems.append(f"{severity}: no section in the document")
            continue
        listed = set(re.findall(r"`([a-z0-9-]+)`", match.group(2)))
        # The summary table above states the same count a third time.
        summary = re.search(rf"\| \*\*{severity}\*\* \|[^|]+\| (\d+) 种 \|", doc)
        if summary is None:
            problems.append(f"{severity}: no row in the summary table")
        elif int(summary.group(1)) != len(codes):
            problems.append(
                f"{severity}: summary table says {summary.group(1)}, "
                f"code assigns {len(codes)}"
            )
        if int(match.group(1)) != len(codes):
            problems.append(
                f"{severity}: document says {match.group(1)}, code assigns {len(codes)}"
            )
        if listed != codes:
            problems.append(
                f"{severity}: missing {sorted(codes - listed)}, "
                f"stale {sorted(listed - codes)}"
            )

    assert not problems, (
        "docs/rules-and-algorithms.zh.md no longer matches FINDING_SEVERITY: "
        + "; ".join(problems)
    )
