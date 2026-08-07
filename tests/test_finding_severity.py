"""Every audit finding must declare how much it actually costs the reader.

The audit reported 39 kinds of problem flatly, so a broken link sat beside a
stylistic near-duplicate title. On the reference Vault that produced 180
findings in one undifferentiated list, which is a list nobody reads.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from obsidian_kb_skill.scripts.audit_vault import (
    FINDING_SEVERITY,
    SEVERITY_ORDER,
    finding_severity,
)

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "obsidian_kb_skill" / "scripts" / "audit_vault.py"


def emitted_codes() -> set[str]:
    """Codes passed to _add, including the f-string web-clip family."""
    tree = ast.parse(AUDIT.read_text(encoding="utf-8"))
    codes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if name != "_add" or len(node.args) < 2:
            continue
        argument = node.args[1]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            codes.add(argument.value)
        elif isinstance(argument, ast.JoinedStr):
            # f"web-clip-missing-{field}" over a literal tuple of fields.
            prefix = "".join(
                part.value
                for part in argument.values
                if isinstance(part, ast.Constant)
            )
            for loop in ast.walk(tree):
                if not isinstance(loop, ast.For) or not isinstance(
                    loop.iter, ast.Tuple
                ):
                    continue
                fields = [
                    element.value
                    for element in loop.iter.elts
                    if isinstance(element, ast.Constant)
                ]
                if fields and any(
                    argument is inner for inner in ast.walk(loop)
                ):
                    codes.update(f"{prefix}{field}" for field in fields)
    return codes


def test_every_emitted_finding_declares_a_severity():
    undeclared = sorted(emitted_codes() - set(FINDING_SEVERITY))

    assert not undeclared, (
        f"these findings have no severity: {undeclared}. Classify them in "
        "FINDING_SEVERITY so the audit output stays readable."
    )


def test_no_severity_is_declared_for_a_finding_that_is_gone():
    stale = sorted(set(FINDING_SEVERITY) - emitted_codes())

    assert not stale, f"declared but no longer emitted: {stale}"


@pytest.mark.parametrize("severity", FINDING_SEVERITY.values())
def test_every_severity_is_a_known_tier(severity):
    assert severity in SEVERITY_ORDER


def test_unknown_code_falls_back_to_the_middle_tier():
    """A new finding must not silently become invisible or alarming."""
    assert finding_severity("a-code-that-does-not-exist") == "hygiene"


def test_the_damaging_findings_are_defects():
    """Anchor the classifications that motivated the tiers."""
    for code in (
        "broken-wikilink",
        "unresolved-template-placeholder",
        "residual-template-instruction",
        "outdated-deep-capture-template",
    ):
        assert finding_severity(code) == "defect", code


def test_the_often_fine_findings_are_informational():
    for code in ("similar-title", "orphan-note", "disconnected-note"):
        assert finding_severity(code) == "informational", code
