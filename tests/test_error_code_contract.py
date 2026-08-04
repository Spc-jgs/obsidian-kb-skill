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
AUDIT_MODULE = "audit_vault.py"


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _codes_in(path: Path) -> set[str]:
    """Collect structured codes from one helper module.

    Deliberately AST-based: an earlier regex sweep missed
    `UNREADABLE_FRONTMATTER = "unreadable-frontmatter"` because the code reached
    its payload through a constant rather than a literal.
    """
    found: set[str] = set()
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
            if name in ("FrontmatterIssue", "PreflightCacheError") and node.args:
                if code := _const_str(node.args[0]):
                    found.add(code)
            elif name == "_add" and len(node.args) >= 2:
                if code := _const_str(node.args[1]):
                    found.add(code)
    return found


def emitted_codes() -> tuple[set[str], set[str]]:
    """Return (refusal codes, audit finding codes) emitted by the helpers."""
    refusal: set[str] = set()
    audit: set[str] = set()
    for path in sorted(SCRIPTS.glob("*.py")):
        target = audit if path.name == AUDIT_MODULE else refusal
        target.update(_codes_in(path))
    return refusal, audit - refusal


def _refusal_rows(reference: str) -> dict[str, str]:
    """Map each refusal-table code to its documented action.

    Scoped to its own subsection: other tables in this file (finding severity,
    for one) share the row shape without listing error codes.
    """
    start = reference.index("### Refusal Codes")
    section = reference[start : reference.index("### ", start + 1)]
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

    offenders = sorted(
        code
        for code in (refusal | audit) - GRANDFATHERED_CODES
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
