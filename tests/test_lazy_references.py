"""Skill body must be tiny and lazy-loaded; agent learns 'do not auto-save' fast.

The always-loaded body (core/OBSIDIAN_KB.md) is a thin gate: it states the
"do not auto-save" rule up front and points to references/*.md for the heavy
workflows. Those references are loaded only when the agent is about to save.
"""

import importlib.util
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "core" / "OBSIDIAN_KB.md"
REFERENCES_DIR = ROOT / "core" / "references"
STANDARD_SKILL = ROOT / "skills" / "obsidian-knowledge-base"

GENERATED = [
    ROOT / "skills" / "obsidian-knowledge-base" / "SKILL.md",
    ROOT / "platforms" / "qoderwork" / "SKILL.md",
    ROOT / "platforms" / "claude-code" / "CLAUDE.md",
    ROOT / "platforms" / "codex" / "AGENTS.md",
    ROOT / "platforms" / "cursor" / "obsidian-kb.mdc",
]

# The gating rule must be discoverable within the first few lines of the body.
GATING_MARKERS = [
    "DO NOT auto-save",
    "never writes to the vault on its own",
    "explicit save intent",
    "conversation-harvest.md",
    "analysis only",
]

# Pointers that MUST stay in the always-loaded body. The gate names each
# reference by bare filename (it points to `core/references/*.md` up top), so
# the markers match the trimmed phrasing — no "references/" prefix, lowercase.
POINTER_MARKERS = [
    "off by default",              # task memory is off unless enabled
    "task-memory.md",              # where the full task-memory spec lives
    "note-creation.md",            # where the create workflow lives
    "web-capture.md",              # conditional source-acquisition contract
    "deep-capture.md",             # conditional finished-article contract
    "folder-routing.md",            # conditional crowded-folder contract
    "conversation-harvest.md",      # conditional conversation value review
    "rules-and-errors.md",         # where the rules live
]

# Heavy section headings that belong ONLY in references/, never in the body.
BODY_FORBIDDEN = [
    "## Note Creation Workflow",
    "## Update Existing Note Workflow",
    "## Conversation Digest Workflow",
    "## YAML Frontmatter Standards",
    "## Cost Limits",
    "## Important Rules",
    "## Error Handling",
    "## Optional Git Post-Processing",
    "## Index Strategy Detection",
    "## Folder Structure",
    "Handoff protocol",
    "Outgoing agent (before yielding)",
    "Incoming agent (first action)",
]


def test_core_is_tiny():
    lines = CORE.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 45, f"always-loaded body is {len(lines)} lines; keep it tiny (<45)"


def test_core_gating_rule_is_up_front():
    text = CORE.read_text(encoding="utf-8")
    for m in GATING_MARKERS:
        assert m in text, f"core body missing gating marker: {m!r}"


def test_core_has_pointers_to_references():
    text = CORE.read_text(encoding="utf-8")
    for m in POINTER_MARKERS:
        assert m in text, f"core body missing pointer marker: {m!r}"


def test_core_selects_only_the_reference_for_the_requested_operation():
    text = CORE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "New note: read only `note-creation.md`",
        "also read `web-capture.md`; verified captures additionally load `deep-capture.md`",
        "also read `folder-routing.md`; uncrowded destinations do not load it",
        "Task Memory: read `task-memory.md` only after explicit opt-in",
        "YAML, rules, and Git references are troubleshooting or post-processing",
    ):
        assert marker in normalized, f"core body missing minimal-load contract: {marker!r}"


def test_core_limits_update_helper_to_task_memory_notes():
    text = CORE.read_text(encoding="utf-8")

    assert "`update-note` is only for Task Memory" in text


def test_harvest_analysis_does_not_grant_write_authority():
    text = CORE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "Write only after **explicit save intent**" in normalized
    assert "conversation-harvest.md` as analysis only" in normalized
    assert "Route analysis before Vault discovery" in normalized
    assert "stop without locating or scanning a Vault" in normalized


def test_core_body_does_not_inline_heavy_specs():
    text = CORE.read_text(encoding="utf-8")
    for bad in BODY_FORBIDDEN:
        assert bad not in text, f"core body still inlines heavy spec: {bad!r}"


def test_all_reference_files_exist():
    expected = {
        "note-creation.md",
        "update-note.md",
        "conversation-digest.md",
        "conversation-harvest.md",
        "task-memory.md",
        "yaml-standards.md",
        "rules-and-errors.md",
        "git.md",
        "missing-category.md",
        "custom-template.md",
        "web-capture.md",
        "deep-capture.md",
        "folder-routing.md",
        "process-inbox.md",
        "audit-vault.md",
    }
    actual = {p.name for p in REFERENCES_DIR.iterdir() if p.is_file()}
    assert expected <= actual, f"missing reference files: {expected - actual}"


def test_references_use_the_standard_skill_runner_not_removed_script_paths():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(REFERENCES_DIR.glob("*.md"))
    )

    assert "scripts/run_helper.py" in text
    assert not re.search(r"python\s+scripts/[a-z_]+\.py", text)


def test_note_creation_routes_articles_to_progressive_capture_references():
    ordinary = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    web = (REFERENCES_DIR / "web-capture.md").read_text(encoding="utf-8")
    deep = (REFERENCES_DIR / "deep-capture.md").read_text(encoding="utf-8")
    normalized = " ".join(ordinary.split())

    for marker in (
        "complete Markdown",
        "type defaults < Vault template < input frontmatter < explicit CLI fields",
        "`web-clip` requires non-empty",
        "`--content-file` must resolve inside the Vault",
        "read only `web-capture.md`",
        "`capture_depth: standard`",
        "`capture_depth: verified`",
        "saved article",
        "quick, bookmark, save-for-later, or unread",
        "materially rewriting",
        "Use `web-clip` for a finished source-backed article",
        "Do not choose `learning-note` merely because",
    ):
        assert marker in normalized, f"note creation routing missing: {marker!r}"

    for heavy_marker in (
        "Resource Survey or Product Comparison",
        "Materiality Standard",
        "Source Inventory and Coverage Ledger",
        "Semantic Hard Failures",
    ):
        assert heavy_marker not in ordinary
        assert heavy_marker not in web
        assert heavy_marker in deep


def test_web_capture_reference_defines_resilient_standard_contract():
    text = (REFERENCES_DIR / "web-capture.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "`standard`",
        "`verified`",
        "Comments are out of scope by default",
        "main article body",
        "material body image",
        "first access path fails",
        "materially different safe path",
        "third-party reader",
        "authenticated, private, intranet, signed",
        "Never bypass login, CAPTCHA, paywalls, or access controls",
        "`source-self-report`",
        "1000 concurrent",
        "local qualification",
        "`retrieval_status`",
        "`fallback_used`",
        "`material_media_checked`",
        "zero Vault writes",
        "Never auto-downgrade",
    ):
        assert marker in normalized, f"web capture contract missing: {marker!r}"


def test_deep_capture_reference_defines_intent_profiles_and_semantic_gate():
    text = (REFERENCES_DIR / "deep-capture.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "deep knowledge capture",
        "should not need to reopen the source",
        "Do not optimize",
        "Tutorial or Technical Procedure",
        "Resource Survey or Product Comparison",
        "Conceptual or Opinion Analysis",
        "Research, Data, News, or Evidence Report",
        "hybrid",
        "Materiality Standard",
        "Source Inventory and Coverage Ledger",
        "unsupported factual claim",
        "first-party",
        "Mechanical acceptance",
        "Semantic acceptance",
        "Historical Notes",
        "`resources` array",
        "`resource_id`",
        "must occur inside `note_excerpt`",
        "Content-Bound Capture Receipt",
        "missing-capture-receipt",
        "numeric_claims",
        "capture receipt SHA-256",
    ):
        assert marker in normalized, f"deep capture contract missing: {marker!r}"


def test_deep_capture_rejects_proxy_metrics_and_requires_profile_usefulness():
    text = (REFERENCES_DIR / "deep-capture.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "word-count",
        "bullet-count",
        "link-count",
        "table-count",
        "code-block-count",
        "reproduce",
        "select",
        "apply",
        "evidence-aware decision",
        "No unresolved material item",
        "content-bound receipt",
    ):
        assert marker in normalized, f"deep capture quality rule missing: {marker!r}"


def test_note_creation_documents_the_minimal_ordinary_create_path():
    text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "one discovery call",
        "vault-info --json --compact",
        "Do not call `detect-index` during ordinary creation",
        "Do not read the template file yourself",
        "A clean compact apply audit completes verification",
        "Do not read or write `.workbuddy/memory`",
        "`crowded_folders`",
        "`--capture-receipt-json`",
        "destination directory must already exist",
    ):
        assert marker in normalized, f"note creation reference missing: {marker!r}"


def test_note_creation_loads_only_custom_template_contracts():
    ordinary_text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    custom_text = (REFERENCES_DIR / "custom-template.md").read_text(encoding="utf-8")
    normalized = " ".join((ordinary_text + "\n" + custom_text).split())
    ordinary = ordinary_text.split("## Minimal Ordinary Path", 1)[1].split(
        "## Bundled Helper Runner", 1
    )[0]

    for marker in (
        "`custom_templates`",
        "template-contract",
        "--expect-template-sha256",
        "read only `custom-template.md`",
        "prose instructions",
        "lists, tables, and labels",
        "unknown placeholders",
        "ask before apply",
        "internal coverage pass",
        "Renamed template discovery is a deferred optimization",
    ):
        assert marker in normalized, f"custom template contract missing: {marker!r}"
    assert "template-contract" not in ordinary
    assert "prose instructions" not in ordinary_text
    assert "lists, tables, and labels" not in ordinary_text


def test_note_creation_front_loads_git_and_reports_complete_heading_diagnostics():
    text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "before fetching or deeply reading source content",
        "expected headings",
        "actual headings",
        "first mismatch",
    ):
        assert marker in normalized, f"optimized workflow marker missing: {marker!r}"


def test_note_creation_documents_the_missing_category_exception():
    ordinary_text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    category_text = (REFERENCES_DIR / "missing-category.md").read_text(encoding="utf-8")
    normalized = " ".join((ordinary_text + "\n" + category_text).split())

    for marker in (
        "Missing category exception",
        "read only `missing-category.md`",
        "category path",
        "rename it",
        "whether to update the applicable `AGENTS.md`",
        "--apply --confirmed --compact-json",
        "one-off category",
        "Existing governed categories skip this entire exception",
        "README",
    ):
        assert marker in normalized, f"missing category contract: {marker!r}"
    assert "--apply --confirmed --compact-json" not in ordinary_text


def test_note_creation_routes_crowded_folders_to_one_lazy_reference():
    ordinary = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    routing = (REFERENCES_DIR / "folder-routing.md").read_text(encoding="utf-8")
    normalized = " ".join((ordinary + "\n" + routing).split())

    for marker in (
        "read only `folder-routing.md`",
        "`crowded_folders`",
        "at least five",
        "Never create a one-note directory",
        "at most two category levels",
        "--apply --confirmed --compact-json",
        "will reject a missing destination folder",
        "Do not silently create it or move historical notes",
    ):
        assert marker in normalized, f"crowded-folder contract missing: {marker!r}"
    assert "--apply --confirmed --compact-json" not in ordinary


def test_note_creation_selected_type_discovery_is_one_call_and_optional():
    text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "--json --compact --type <slug>" in normalized
    assert "omit `--type`" in normalized
    assert "omit `--type` for opted-in `task-memory`" in normalized
    # One call, because governance was read first and the call was told which
    # destination to answer about. A reroute after the fact is the one case that
    # earns a second call — a blanket ban would leave the Agent with an answer
    # about a folder it is no longer writing to.
    assert "One discovery call is enough when governance was read first" in normalized
    assert "rerun it only if the route changes" in normalized


def test_missing_category_exception_does_not_expand_the_ordinary_path():
    text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    ordinary = text.split("## Minimal Ordinary Path", 1)[1].split(
        "## Bundled Helper Runner", 1
    )[0]

    assert "vault-info --json" in ordinary
    assert "create-note --preflight-json" in ordinary
    assert "--apply --compact-json" in ordinary
    assert "create-category" not in ordinary


def test_task_memory_reference_carries_full_spec():
    ref = REFERENCES_DIR / "task-memory.md"
    text = ref.read_text(encoding="utf-8")
    for need in ("Handoff protocol", "Outgoing agent (before yielding)", "obsidian-update-note"):
        assert need in text, f"task-memory reference missing: {need!r}"
    assert "normalized lowercase operational path" in text
    assert "does not permit ordinary notes to create categories" in text


def test_material_article_rewrite_routes_through_capture_receipt():
    text = (REFERENCES_DIR / "update-note.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "material rewrite of a finished source-backed article",
        "`deep-capture.md`",
        "`capture-receipt`",
        "content-bound receipt passes",
    ):
        assert marker in normalized


def test_note_creation_reference_exposes_frontmatter_input_contract():
    text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for marker in (
        "type defaults < Vault template < input frontmatter < explicit CLI fields",
        "source:",
        "related:",
        "--stdin",
        "--content-file",
        "must resolve inside the Vault",
        "external or transient content through `--stdin`",
    ):
        assert marker in normalized, f"note creation reference missing: {marker!r}"


def test_generated_artifacts_match_pointers_and_not_heavy_spec():
    for path in GENERATED:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in POINTER_MARKERS:
            assert m in text, f"{path.name} missing pointer {m!r} (build out of sync?)"
        for bad in BODY_FORBIDDEN:
            assert bad not in text, f"{path.name} inlines heavy spec {bad!r} (build out of sync?)"


def test_build_check_still_passes():
    """build --check must pass after the reference-shipping change."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "build.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"build --check failed:\n{result.stdout}\n{result.stderr}"
    )


def test_retrieval_doc_lists_only_directories_the_scanner_skips():
    """The doc claimed "virtual environments"; the scanner only skips `.venv`."""
    from obsidian_kb_skill.scripts.search_vault import IGNORED_DIRECTORY_NAMES

    text = (ROOT / "docs" / "retrieval.md").read_text(encoding="utf-8")
    assert "虚拟环境" not in text, (
        "plain `venv/` and `env/` are not skipped; name the real entries"
    )
    for name in ("node_modules", "__pycache__", ".venv"):
        assert name in IGNORED_DIRECTORY_NAMES, f"{name} left the ignore set"
        assert name in text, f"{name} is skipped but undocumented"


def test_feature_guide_separates_vault_info_from_governance_reading():
    text = (ROOT / "docs" / "feature-guide.md").read_text(encoding="utf-8")
    assert "Vault 治理读取" in text
    assert "Agent 自行读取，非 helper" in text


def test_feature_guide_uses_registered_note_type_slugs():
    from obsidian_kb_skill.scripts.note_catalog import VALID_NOTE_TYPES

    text = (ROOT / "docs" / "feature-guide.md").read_text(encoding="utf-8")
    assert "digest-note" not in text, "digest-note.md is a template asset, not a --type"
    assert "conversation-digest" in VALID_NOTE_TYPES


def test_write_state_machine_marks_git_precheck_conditional():
    text = (ROOT / "docs" / "capture-and-governance.md").read_text(encoding="utf-8")
    assert "Discover --> GitCheck: " in text, "Git precheck must be a guarded edge"
    assert "Discover --> Route: " in text, "the non-Git path must exist"


def test_governance_is_read_before_the_discovery_call():
    """Discovery can only answer about a destination it was given.

    A crowded child folder does not make its parent look crowded, and the route
    to that child lives in the Vault's own governance. With discovery first, an
    Agent asks about `20-Learning`, gets no `folder-routing.md`, reads the
    governance that routes to `20-Learning/AI-Agent`, and files into the crowded
    folder the contract exists to catch. Governance costs one read and needs
    nothing from the helper, so it goes first.
    """
    text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    ordinary = text.split("## Minimal Ordinary Path", 1)[1].split(
        "## Bundled Helper Runner", 1
    )[0]

    governance = ordinary.index("governance")
    discovery = ordinary.index("vault-info")
    assert governance < discovery, (
        "the minimal path runs discovery before reading governance, so the "
        "crowded-destination answer is about the type default rather than the "
        "folder the note will reach"
    )

    normalized = " ".join(text.split())
    assert "--folder <governed-route>" in normalized, (
        "the discovery call must show the governed route being passed"
    )
    assert "crowded child" in normalized, (
        "explain why the parent folder is the wrong thing to ask about"
    )


# Helpers that ship inside the bundle but are deliberately not selectable from
# the instructions. Each entry needs a reason, because an entry here is the
# difference between a decision and an oversight.
UNROUTED_HELPERS = {
    "doctor": "installer and troubleshooting tool, not a Vault operation",
    "suggest-links": (
        "not a standalone entrypoint: the instructions reach it as "
        "`create-note --suggest-links`, so it has no invocation of its own to show"
    ),
}


def _shows_invocation(helper: str, text: str) -> bool:
    """Does the text demonstrate running this helper, rather than name it?

    Naming is not reachability. A line telling an Agent *not* to use a helper
    contains its name exactly as a line telling it how would, and #90 was a
    helper nothing named at all — a guard that accepts any mention would have
    stayed green through the fix and through its own regression.

    Two shapes count, both of which an Agent can act on:

    * `run_helper.py <helper>` — the bundled runner, how the body says to
      invoke anything.
    * `` `<helper> <arg>` `` — the helper named with its arguments, used where
      a reference shows a command without repeating the runner prefix.

    A bare `` `<helper>` `` does not count, and neither does a flag that
    happens to embed the name, such as `--suggest-links`.
    """
    name = re.escape(helper)
    return bool(
        re.search(rf"run_helper\.py\s+{name}\b", text)
        or re.search(rf"(?<![-\w]){name}\s+[<-]", text)
    )


def _instruction_text() -> str:
    """Every word an Agent can actually reach: the body plus all references."""
    parts = [CORE.read_text(encoding="utf-8")]
    parts.extend(
        path.read_text(encoding="utf-8")
        for path in sorted(REFERENCES_DIR.glob("*.md"))
    )
    return "\n".join(parts)


def test_naming_a_helper_is_not_the_same_as_showing_how_to_run_it():
    """The reachability check must not accept a mention, only an invocation.

    A line forbidding a helper contains its name just as surely as a line
    invoking it. Under a bare substring test, adding "never invoke
    `process-inbox` during conversation harvest" to any reference would turn
    the guard green while no branch selects it — reproducing #90 with the guard
    reporting success.
    """
    from tests.test_lazy_references import _shows_invocation

    assert not _shows_invocation(
        "process-inbox", "never invoke `process-inbox` during conversation harvest"
    )
    assert not _shows_invocation("suggest-links", "pass `--suggest-links` to enable")
    assert _shows_invocation(
        "process-inbox",
        "python <skill-root>/scripts/run_helper.py process-inbox <vault> --plan",
    )
    assert _shows_invocation(
        "scaffold-templates", "run `scaffold-templates <vault> --apply` first"
    )


def _bundled_helpers() -> set[str]:
    spec = importlib.util.spec_from_file_location(
        "standard_run_helper", STANDARD_SKILL / "scripts" / "run_helper.py"
    )
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return set(runner.HELPERS)


def test_every_bundled_helper_is_reachable_from_the_instructions():
    """A helper can be implemented, tested, shipped — and still be dead code.

    `process-inbox` was implemented, covered by tests, registered in
    `[project.scripts]`, listed in the runner's `HELPERS`, and advertised in
    `docs/feature-guide.md`, while `core/` never named it once. It reached
    every user's disk and no Agent could ever select it. Shipping is not
    reachability, and only an explicit check can tell them apart.

    Reachability means the instructions show how to run it — see
    `_shows_invocation`. Accepting a bare mention would let a line forbidding a
    helper satisfy the guard that exists to catch helpers nothing invokes.
    """
    instructions = _instruction_text()
    unreachable = {
        helper
        for helper in _bundled_helpers()
        if not _shows_invocation(helper, instructions)
    }

    assert unreachable <= set(UNROUTED_HELPERS), (
        "bundled helper ships but no instruction names it: "
        f"{sorted(unreachable - set(UNROUTED_HELPERS))}"
    )


def test_inbox_filing_is_selectable_from_the_routing_table_itself():
    """Being named somewhere is weak; being routed is the actual contract.

    The reachability check above accepts a helper mentioned anywhere in the
    instruction text. This one pins the branch that makes filing selectable: the
    routing table has to point at the workflow, and the two refusal codes an
    Agent will actually meet have to be interpretable from the workflow itself
    rather than from a file that never documented them.
    """
    body = CORE.read_text(encoding="utf-8")
    reference = " ".join(
        (REFERENCES_DIR / "process-inbox.md").read_text(encoding="utf-8").split()
    )

    assert "process-inbox.md" in body, (
        "filing has no branch in the routing table; naming the helper elsewhere "
        "does not make it selectable"
    )
    for code in ("unknown-target", "unreadable-frontmatter", "unsafe-inbox-entry"):
        assert code in reference, f"filing refusal code is uninterpretable: {code!r}"


def test_inbox_filing_reports_refusals_from_the_right_channel():
    """A refusal the Agent cannot find is a refusal it will report as success.

    Refusals are fields on a plan entry, never a top-level error. An Agent told
    the wrong shape checks for an `error` key, finds none, and presents notes
    that will never move as part of an approved plan.
    """
    reference = " ".join(
        (REFERENCES_DIR / "process-inbox.md").read_text(encoding="utf-8").split()
    )

    for marker in (
        "refuses **per note**, not per run",
        "never a top-level error",
        "There is no top-level `error` key to check",
        "`skip_code` is what you act on",
    ):
        assert marker in reference, f"refusal channel contract missing: {marker!r}"


def test_partial_apply_is_not_documented_as_an_ordinary_skip():
    """One filing refusal leaves the Vault changed; it must not read like the rest.

    Every other refusal means nothing happened. `partial-apply` means the note
    is now in two places. An Agent that treats them alike reports a clean skip
    over a split note — or worse, deletes a copy to tidy the result.
    """
    reference = " ".join(
        (REFERENCES_DIR / "process-inbox.md").read_text(encoding="utf-8").split()
    )

    for marker in (
        "the copy survived and the note now exists in both places",
        "the only filing refusal that leaves the Vault changed",
        "never delete either copy yourself",
    ):
        assert marker in reference, f"partial-apply contract missing: {marker!r}"


def test_filing_does_not_inherit_the_authoring_rename_rule():
    """`-2` on clash is an authoring rule; filing leaves the note where it is."""
    reference = " ".join(
        (REFERENCES_DIR / "process-inbox.md").read_text(encoding="utf-8").split()
    )

    assert "does **not** apply the body's `-2` rename rule" in reference, (
        "the body's global clash rule contradicts filing and nothing reconciles them"
    )
    assert "the note stays in the Inbox" in reference


def test_unrouted_helper_list_does_not_outlive_its_reason():
    """Once a helper is routed, its exemption is a lie that hides the next one."""
    instructions = _instruction_text()
    stale = {
        helper
        for helper in UNROUTED_HELPERS
        if _shows_invocation(helper, instructions)
    }

    assert not stale, f"UNROUTED_HELPERS still lists reachable helpers: {sorted(stale)}"


def test_inbox_filing_never_applies_without_a_confirmed_plan():
    """`--apply` moves files. The plan is what the user actually authorizes.

    Intent to file an Inbox is not consent to a specific set of moves nobody has
    read yet — destinations are inferred, and keyword inference is exactly what
    a user needs to be able to overrule. The plan step is the veto.
    """
    normalized = " ".join(
        (REFERENCES_DIR / "process-inbox.md").read_text(encoding="utf-8").split()
    )

    for marker in (
        "`--plan` is read-only and is the default",
        "Wait for the user to confirm this plan",
        "intent to file, not consent",
        "never write to the Vault on its own",
        "do not hand-roll a partial apply",
    ):
        assert marker in normalized, f"two-phase filing contract missing: {marker!r}"

    assert normalized.index("--plan") < normalized.index("--apply"), (
        "the apply command is shown before the plan that authorizes it"
    )


def test_inbox_filing_does_not_erode_the_authoring_bound():
    """The `≤1 note written` bound must survive filing, not bend to accommodate it.

    Filing one Inbox can touch thirty notes, which reads like a violation. The
    resolution is that filing authors nothing — not that the bound is negotiable.
    A future reader who misses that distinction will loosen a real safety limit
    to make filing fit under it.
    """
    body = CORE.read_text(encoding="utf-8")
    reference = " ".join(
        (REFERENCES_DIR / "process-inbox.md").read_text(encoding="utf-8").split()
    )

    assert "≤1 note written" in body, "the authoring bound was removed, not explained"

    for marker in (
        "Filing never authors a note",
        "`≤1 note written` bound does not apply",
        "holds exactly as many notes after the run as before",
        "The bound that does apply is the Inbox itself",
    ):
        assert marker in reference, f"filing/authoring distinction missing: {marker!r}"


def test_crowding_contract_states_which_folder_kind_it_governs():
    """A rule that never named its scope got applied where it does not belong.

    These thresholds solve "too many notes to navigate" — subject clustering.
    Read as universal, they forbid an entity folder's correct structure: a
    project directory starts with one note and holds documents that share no
    subject. That misreading is #95, not a hypothetical.
    """
    text = " ".join(
        (REFERENCES_DIR / "folder-routing.md").read_text(encoding="utf-8").split()
    )

    for marker in (
        "**Taxonomy folders**",
        "**Entity folders are excluded.**",
        "A project starts with exactly one note",
        "An instance directory exists because the project exists",
    ):
        assert marker in text, f"crowding scope statement missing: {marker!r}"


def test_reporting_a_finding_does_not_authorize_fixing_it():
    """An audit answers "what is wrong", not "go change it".

    This is where a read-only capability most easily leaks into a write: the
    finding is specific, the fix looks trivial, and nobody said stop. A missing
    `date` is one edit away, which is exactly why the boundary has to be stated
    rather than left to judgement.
    """
    reference = " ".join(
        (REFERENCES_DIR / "audit-vault.md").read_text(encoding="utf-8").split()
    )

    for marker in (
        "never repairs a note",
        "does not grant authority to fix it",
        "separate request",
        "Never repair a note to make a finding disappear",
        "`≤1 note written` bound still applies",
    ):
        assert marker in reference, f"audit read-only contract missing: {marker!r}"


def test_audit_findings_are_not_verdicts_about_a_note():
    """Some findings describe legitimate states, and the audit cannot tell.

    `disconnected-note` on a standalone note is not a defect; reporting it as
    one pushes the user to link notes that were never meant to link, which is
    how a Vault accumulates exactly the weak relationships the rest of this
    Skill refuses to create.
    """
    reference = " ".join(
        (REFERENCES_DIR / "audit-vault.md").read_text(encoding="utf-8").split()
    )

    for marker in (
        "legitimate states, not errors",
        "let the user judge",
        "do not translate a finding into a verdict",
        "by kind rather than listing every occurrence",
    ):
        assert marker in reference, f"audit reporting contract missing: {marker!r}"


def test_skill_description_can_trigger_on_vault_audit():
    """Same failure as the Inbox branch: a correct route nobody can reach.

    "帮我体检一下 Vault" matches none of save/create/update/archive/remember,
    so without audit vocabulary in the description the routing branch added
    here is unreachable from outside no matter how correct it is.
    """
    header = (STANDARD_SKILL / "header.md").read_text(encoding="utf-8")
    description = header.split("description:", 1)[1].split("\n", 1)[0].lower()

    assert "audit" in description, (
        f"description cannot trigger on an audit request: {description.strip()!r}"
    )
    assert "read-only" in description, (
        "the description must not imply an audit writes to the Vault"
    )


def test_skill_description_can_trigger_on_inbox_filing():
    """Routing a helper is useless if the Skill never activates in the first place.

    The description is the only thing an Agent sees before deciding whether this
    Skill is relevant. A user asking to sort out their Inbox matches none of
    save/create/update/archive/remember, so the routing branch behind those
    words is unreachable from the outside no matter how correct it is.
    """
    header = (STANDARD_SKILL / "header.md").read_text(encoding="utf-8")
    description = header.split("description:", 1)[1].split("\n", 1)[0].lower()

    assert "inbox" in description, (
        "description cannot trigger on an Inbox filing request: "
        f"{description.strip()!r}"
    )


def test_git_precheck_reports_something_the_user_can_act_on():
    """A bare 'the worktree is dirty' makes the user go run git status."""
    text = " ".join((REFERENCES_DIR / "git.md").read_text(encoding="utf-8").split())

    for marker in (
        "untracked or modified",
        "waive the Git requirement",
        "Never stage, stash, discard, commit",
    ):
        assert marker in text, f"git reference missing: {marker!r}"


RETRIEVAL_CORE = ROOT / "core" / "RETRIEVAL.md"


def test_retrieval_core_body_is_bounded_too():
    """The other always-loaded body had no ceiling at all.

    `test_core_is_tiny` holds `OBSIDIAN_KB.md` under 45 lines. `RETRIEVAL.md`
    is loaded on exactly the same terms — every invocation of that Skill pays
    for it — and nothing bounded it, so the asymmetry was the defect rather
    than the size.

    The number is today's value, not a measured optimum. Holding it at exactly
    the current count, with no slack, means a growing body has to change this
    line — which is the point, because adding to an always-loaded file is a
    decision about every future call and should not happen by accident. Raise
    it deliberately, or move the material into a reference.

    Raised 129 -> 138 for `review-open-loops` (#87). The eight added lines are
    a routing pointer — which reference to read, which helper to run, and the
    one rule the agent must not break (do not grade the items) — not an inlined
    spec; the spec is the 60-line `review-open-loops.md`, which loads only when
    that question is asked. That is the trade this bound exists to make
    explicit, and it was made rather than skipped.
    """
    lines = RETRIEVAL_CORE.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 138, (
        f"always-loaded retrieval body is {len(lines)} lines, was 138. Every "
        "call pays this. Move the new material into references/, or raise this "
        "number deliberately and say why in the commit."
    )


def test_retrieval_core_keeps_its_operations_in_reference_pointers():
    """Each section routes to one reference rather than inlining it.

    The bound above is only meaningful while the sections stay pointers. A
    section that starts explaining what a reference explains will pass a line
    count for a while and then fail it all at once.
    """
    text = RETRIEVAL_CORE.read_text(encoding="utf-8")
    sections = [line for line in text.splitlines() if line.startswith("## When ")]
    assert len(sections) >= 6, "the operation sections vanished; this guard is stale"
    for marker in (
        "read only `references/search.md`",
        "Read only `references/review-captures.md`",
        "Read only `references/review-open-loops.md`",
    ):
        assert marker in text, f"retrieval core stopped routing to a reference: {marker!r}"
