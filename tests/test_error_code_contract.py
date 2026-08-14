"""Keep the documented error-code contract in step with what helpers emit.

The reference file is what an Agent reads when a helper refuses. A code that
exists in the helpers but not in the reference leaves the Agent to improvise at
exactly the moment improvising is most expensive — the usual improvisation
being to bypass the helper and write the file directly.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "obsidian_kb_skill" / "scripts"
REFERENCE = ROOT / "core" / "references" / "rules-and-errors.md"
# Helpers only the retrieval Skill can call. Its bundle never ships
# `core/references/`, so documenting its refusals there would put the answer
# where that Agent cannot read it. Kept in step with build.py's
# RETRIEVAL_HELPER_FILES and the retrieval run_helper's HELPERS by a test below.
RETRIEVAL_REFERENCE_DIR = ROOT / "core" / "retrieval-references"
# Which reference answers for which helper. Mapped rather than concatenated: the
# Skill sends the Agent to exactly one of these files per task ("read only
# references/search.md"), so a search refusal documented in the review reference
# is still documented where that Agent will not look. Concatenating the two
# would accept precisely the arrangement this test exists to reject.
RETRIEVAL_MODULES = {
    "explore_neighborhood.py": RETRIEVAL_REFERENCE_DIR / "explore-neighborhood.md",
    "resume_project.py": RETRIEVAL_REFERENCE_DIR / "resume-project.md",
    "retrieval_vault_info.py": RETRIEVAL_REFERENCE_DIR / "search.md",
    "review_projects.py": RETRIEVAL_REFERENCE_DIR / "review-projects.md",
    "search_vault.py": RETRIEVAL_REFERENCE_DIR / "search.md",
}
# Modules both bundles ship, so both Agents can receive their codes. The write
# reference owns the rows; build.py fans the marked block out to this file.
SHARED_MODULES = frozenset({"vault_paths.py", "frontmatter.py"})
SHARED_REFERENCE = ROOT / "core" / "retrieval-references" / "shared-errors.md"
# Findings are reported, not refused, wherever they are constructed.
FINDING_FACTORIES = frozenset({"Finding", "_add"})


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dataclass_fields(node: ast.ClassDef) -> list[str]:
    return [
        item.target.id
        for item in node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    ]


def _code_parameters() -> dict[str, int]:
    """Map every callable that takes a `code` to the position it takes it at.

    Derived from the source rather than listed by hand. Three named exceptions
    used to be hardcoded here, and the two error classes nobody thought to add
    (`CaptureReceiptError`, `CategoryValidationError`) stayed invisible — 29
    codes' worth. Anything the helpers call a `code` is now a code, including
    classes added later.
    """
    positions: dict[str, int] = {}
    for path in sorted(SCRIPTS.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef):
                # `__init__` is reached through its class, where `self` is not
                # part of the call signature.
                if node.name == "__init__":
                    continue
                names = [argument.arg for argument in node.args.args]
                if "code" in names:
                    positions.setdefault(node.name, names.index("code"))
            elif isinstance(node, ast.ClassDef):
                initializer = next(
                    (
                        item
                        for item in node.body
                        if isinstance(item, ast.FunctionDef) and item.name == "__init__"
                    ),
                    None,
                )
                fields = (
                    [argument.arg for argument in initializer.args.args][1:]
                    if initializer is not None
                    else _dataclass_fields(node)
                )
                if "code" in fields:
                    positions.setdefault(node.name, fields.index("code"))
    return positions


CODE_PARAMETERS = _code_parameters()


def _codes_in(path: Path) -> tuple[set[str], set[str]]:
    """Collect one module's (refusal, finding) codes.

    Deliberately AST-based: an earlier regex sweep missed
    `UNREADABLE_FRONTMATTER = "unreadable-frontmatter"` because the code reached
    its payload through a constant rather than a literal.
    """
    found: set[str] = set()
    findings: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if _const_str(key) == "code" and (code := _const_str(value)):
                    found.add(code)
        elif isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            # code = "A" if ... else ("B" if ... else "C")
            if isinstance(node.value, ast.IfExp) and any(
                t.id == "code" for t in targets
            ):
                found.update(
                    code
                    for sub in ast.walk(node.value)
                    if (code := _const_str(sub))
                )
                continue
            if not (value := _const_str(node.value)):
                continue
            for target in targets:
                if target.id == "code" or target.id.endswith("_CODE"):
                    found.add(value)
                elif (
                    target.id.isupper()
                    and target.id.lower().replace("_", "-") == value
                ):
                    found.add(value)
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            position = CODE_PARAMETERS.get(name)
            if position is None:
                continue
            argument: ast.AST | None = None
            if len(node.args) > position:
                argument = node.args[position]
            else:
                argument = next(
                    (kw.value for kw in node.keywords if kw.arg == "code"), None
                )
            if argument is not None and (code := _const_str(argument)):
                (findings if name in FINDING_FACTORIES else found).add(code)
    return found, findings


def emitted_codes() -> tuple[set[str], set[str]]:
    """Return the write Skill's (refusal codes, audit finding codes).

    Split by how a code reaches the Agent, not by which module holds it. The
    module heuristic filed `create-category`'s six post-apply findings as
    refusals, which would have demanded a "what to do next" row for something
    that is reported rather than refused.
    """
    refusal: set[str] = set()
    audit: set[str] = set()
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name in RETRIEVAL_MODULES:
            continue
        module_refusal, module_findings = _codes_in(path)
        refusal.update(module_refusal)
        audit.update(module_findings)
    return refusal, audit - refusal


def retrieval_codes() -> dict[str, set[str]]:
    """Return codes only a retrieval-Skill Agent can receive, per module."""
    codes: dict[str, set[str]] = {}
    for name in sorted(RETRIEVAL_MODULES):
        module_refusal, module_findings = _codes_in(SCRIPTS / name)
        codes[name] = module_refusal | module_findings
    return codes


def _refusal_rows(reference: str) -> dict[str, str]:
    """Map each refusal-table code to its documented action.

    Bounded by the two headings that delimit the refusals, not by "the next
    heading of any depth": the refusals are grouped into `####` subsections, and
    other tables in this file (finding severity, for one) share the row shape
    without listing error codes.
    """
    start = reference.index("### Refusal Codes")
    section = reference[start : reference.index("### Audit Findings", start)]
    rows = {}
    for line in section.splitlines():
        if line.startswith("| `") and line.count("|") >= 4:
            cells = line.split("|")
            rows[cells[1].strip().strip("`")] = cells[3].strip()
    return rows


def _documented_codes(reference: str) -> set[str]:
    """Codes the reference actually enumerates, ignoring prose vocabulary."""
    documented = set(_refusal_rows(reference))
    start = reference.index("### Audit Findings")
    # Stop at the next subsection: only the grouped lists enumerate codes.
    end = reference.index("### ", start + 1)
    for token in reference[start:end].replace(",", " ").replace(".", " ").split():
        if token.startswith("`") and token.endswith("`"):
            documented.add(token.strip("`"))
    return documented


def test_every_emitted_code_is_documented():
    refusal, audit = emitted_codes()
    reference = REFERENCE.read_text(encoding="utf-8")

    undocumented = sorted(
        code for code in refusal | audit if f"`{code}`" not in reference
    )

    assert not undocumented, (
        "these codes are emitted by helpers but absent from "
        f"core/references/rules-and-errors.md: {undocumented}. "
        "An Agent that receives one has no documented next step."
    )


def test_retrieval_codes_are_documented_where_that_agent_can_read_them():
    """A retrieval Agent never receives `core/references/` — and reads one file.

    Each helper's codes must appear in the reference the Skill sends the Agent to
    for that helper. Searching every retrieval reference at once would pass a
    `search-vault` refusal documented only in `review-projects.md`, which the
    searching Agent is explicitly told not to open.
    """
    undocumented: dict[str, list[str]] = {}
    for module, codes in retrieval_codes().items():
        reference = RETRIEVAL_MODULES[module]
        text = reference.read_text(encoding="utf-8")
        missing = sorted(code for code in codes if f"`{code}`" not in text)
        if missing:
            undocumented[f"{module} -> {reference.name}"] = missing

    assert not undocumented, (
        "these codes are emitted by retrieval-only helpers but absent from the "
        f"reference their Agent is told to read: {undocumented}. Documenting "
        "them in the write Skill's reference does not help — that file is not "
        "in the retrieval bundle — and neither does documenting them in the "
        "other retrieval reference."
    )


def test_codes_from_shared_modules_reach_both_bundles():
    """Both Agents can receive these, so both references must carry them."""
    shared: set[str] = set()
    for name in sorted(SHARED_MODULES):
        module_refusal, module_findings = _codes_in(SCRIPTS / name)
        shared |= module_refusal | module_findings
    write_rows = set(_refusal_rows(REFERENCE.read_text(encoding="utf-8")))
    fanned_out = SHARED_REFERENCE.read_text(encoding="utf-8")

    assert not sorted(shared - write_rows), (
        f"shared codes missing from the write reference: {sorted(shared - write_rows)}"
    )
    missing = sorted(code for code in shared if f"`{code}`" not in fanned_out)
    assert not missing, (
        f"shared codes missing from {SHARED_REFERENCE.name}: {missing}. Move the "
        "rows inside the shared-refusals markers in rules-and-errors.md, then run "
        "python build.py — do not maintain a second copy by hand."
    )


def test_shared_reference_is_generated_not_hand_written():
    """The fanned-out copy must stay derived from the write reference."""
    import build  # noqa: PLC0415 — the builder is the contract under test

    expected = build.build_shared_errors(
        REFERENCE.read_text(encoding="utf-8")
    )

    assert SHARED_REFERENCE.read_text(encoding="utf-8") == expected, (
        "core/retrieval-references/shared-errors.md is out of sync; run "
        "python build.py"
    )
    assert "DO NOT EDIT DIRECTLY" in expected


def test_retrieval_module_list_matches_the_shipped_bundle():
    """Keep the module split honest against build.py, not against memory."""
    build = (ROOT / "build.py").read_text(encoding="utf-8")
    bundle = build[build.index("RETRIEVAL_HELPER_FILES") :]
    bundle = bundle[: bundle.index("\n)")]

    for name in RETRIEVAL_MODULES:
        assert f'Path("scripts/{name}")' in bundle, (
            f"{name} is no longer in the retrieval bundle; move its codes back "
            "into the write Skill's reference"
        )


def test_reference_documents_no_codes_the_helpers_never_emit():
    """Catch the opposite drift: entries left behind by a removed code."""
    refusal, audit = emitted_codes()
    emitted = refusal | audit
    reference = REFERENCE.read_text(encoding="utf-8")

    # Read only the places that enumerate codes — the refusal table's first
    # column and the audit-findings lists. Scanning prose would pick up
    # vocabulary like `kebab-case` that is not a code at all.
    documented = _documented_codes(reference)

    stale = sorted(code for code in documented if code not in emitted)

    assert not stale, (
        f"documented but no longer emitted: {stale}. Remove the stale rows so "
        "the reference cannot describe behaviour that does not exist."
    )


def test_refusal_codes_carry_an_action_column():
    """A code without a next step does not help an Agent decide anything."""
    refusal, _ = emitted_codes()
    reference = REFERENCE.read_text(encoding="utf-8")

    documented_rows = _refusal_rows(reference)

    for code in sorted(refusal):
        assert code in documented_rows, f"{code} has no row in the refusal table"
        assert len(documented_rows[code]) > 15, (
            f"{code} has no usable action; write what the Agent should do next"
        )


# Codes that predate the kebab-case convention. Three are the Vault containment
# boundary and one is the update-note backup failure. They are pinned by
# existing output tests and are deliberately not renamed; reading `error.code`
# works regardless of spelling.
GRANDFATHERED_CODES = frozenset(
    {"PATH_OUTSIDE_VAULT", "PATH_NOT_FOUND", "INVALID_VAULT_ROOT", "BACKUP_FAILED"}
)

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def test_new_codes_follow_the_kebab_case_convention():
    """Stop the naming split from growing past the grandfathered four."""
    refusal, audit = emitted_codes()

    retrieval = set().union(*retrieval_codes().values())

    offenders = sorted(
        code
        for code in (refusal | audit | retrieval) - GRANDFATHERED_CODES
        if not KEBAB.fullmatch(code)
    )

    assert not offenders, (
        f"these codes are not kebab-case: {offenders}. New codes use kebab-case "
        "and the bare {'error': {...}} envelope; see the convention in "
        "core/references/rules-and-errors.md."
    )


def test_grandfathered_codes_are_all_still_emitted():
    """Shrink the exemption list when a legacy code disappears."""
    refusal, audit = emitted_codes()
    emitted = refusal | audit

    unused = sorted(GRANDFATHERED_CODES - emitted)

    assert not unused, (
        f"no longer emitted, so the exemption is stale: {unused}. Remove them "
        "from GRANDFATHERED_CODES and from the reference."
    )


def test_shared_note_judgements_have_exactly_one_definition():
    """Both Skills judge the same Vault; two definitions would drift apart.

    `EXEMPT_NAMES` says what is not a note and `normalize_tag_key` says when two
    tags are the same tag. The audit and retrieval must answer both identically,
    so each is defined once in the shared note domain and imported everywhere
    else.
    """
    definitions: dict[str, list[str]] = {"EXEMPT_NAMES": [], "normalize_tag_key": []}
    for path in sorted(SCRIPTS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in definitions:
                definitions[node.name].append(path.name)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in definitions:
                        definitions[target.id].append(path.name)

    assert definitions["EXEMPT_NAMES"] == ["note_catalog.py"]
    assert definitions["normalize_tag_key"] == ["note_catalog.py"]
