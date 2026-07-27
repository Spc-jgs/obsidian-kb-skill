"""Skill body must be tiny and lazy-loaded; agent learns 'do not auto-save' fast.

The always-loaded body (core/OBSIDIAN_KB.md) is a thin gate: it states the
"do not auto-save" rule up front and points to references/*.md for the heavy
workflows. Those references are loaded only when the agent is about to save.
"""

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE = ROOT / "core" / "OBSIDIAN_KB.md"
REFERENCES_DIR = ROOT / "core" / "references"

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
]

# Pointers that MUST stay in the always-loaded body. The gate names each
# reference by bare filename (it points to `core/references/*.md` up top), so
# the markers match the trimmed phrasing — no "references/" prefix, lowercase.
POINTER_MARKERS = [
    "off by default",              # task memory is off unless enabled
    "task-memory.md",              # where the full task-memory spec lives
    "note-creation.md",            # where the create workflow lives
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
        "Task Memory: read `task-memory.md` only after explicit opt-in",
        "YAML, rules, and Git references are troubleshooting or post-processing",
    ):
        assert marker in normalized, f"core body missing minimal-load contract: {marker!r}"


def test_core_limits_update_helper_to_task_memory_notes():
    text = CORE.read_text(encoding="utf-8")

    assert "`update-note` is only for Task Memory" in text


def test_core_body_does_not_inline_heavy_specs():
    text = CORE.read_text(encoding="utf-8")
    for bad in BODY_FORBIDDEN:
        assert bad not in text, f"core body still inlines heavy spec: {bad!r}"


def test_all_reference_files_exist():
    expected = {
        "note-creation.md",
        "update-note.md",
        "conversation-digest.md",
        "task-memory.md",
        "yaml-standards.md",
        "rules-and-errors.md",
        "git.md",
        "missing-category.md",
        "custom-template.md",
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


def test_note_creation_documents_complete_markdown_and_web_clip_preflight():
    text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")

    for marker in (
        "complete Markdown",
        "type defaults < Vault template < input frontmatter < explicit CLI fields",
        "`web-clip` requires non-empty",
        "`--content-file` must resolve inside the Vault",
        "deep knowledge capture",
        "should not need to reopen the source",
        "Do not optimize the finished note",
        "source-coverage pass",
        "Never substitute a concept summary",
        "Mechanical audit does not prove semantic depth",
    ):
        assert marker in text, f"note creation reference missing: {marker!r}"


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


def test_note_creation_selected_type_discovery_is_one_call_and_optional():
    text = (REFERENCES_DIR / "note-creation.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    assert "--json --compact --type <slug>" in normalized
    assert "omit `--type`" in normalized
    assert "omit `--type` for opted-in `task-memory`" in normalized
    assert "Do not run a second discovery call" in normalized


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
