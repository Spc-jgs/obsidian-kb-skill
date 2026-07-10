#!/usr/bin/env python3
"""Single source of truth for locating the skill's bundled runtime resources.

This module is the ONLY place that resolves where ``templates/`` and
``references/`` come from. No other script may build these paths by hand.

Resolution order (see the v1.11.0 distribution contract):

1. ``--skill-root`` (explicit CLI argument) — MUST be either a standard Skill
   root containing ``assets/templates/`` and ``references/`` or the legacy
   development resource root containing ``templates/`` and ``references/``.
   If it is given but invalid, we RAISE immediately and never silently fall back.
2. ``OBSIDIAN_KB_SKILL_ROOT`` (environment variable) — same validity rule.
3. ``importlib.resources`` — the bundled copy shipped inside the installed
   wheel (``scripts/resources/`` as package data). This is the DEFAULT for a
   real installation and does NOT depend on ``__file__`` heuristics.
4. Source-tree relative path (``{repo}/core``) — ONLY for running the scripts
   directly from a cloned repository during development. It must never be the
   implicit premise of a real install.

The CLI entry points and console scripts should therefore work out of an
``importlib.resources`` install with zero extra configuration.
"""
from __future__ import annotations

import importlib.resources as _ilr
import os
from pathlib import Path
from typing import Optional


# Package name that carries the bundled resources when installed from a wheel.
_RESOURCE_PACKAGE = "obsidian_kb_skill.scripts.resources"

# Only these sub-trees are considered "the bundled runtime resources".
_TEMPLATE_SUBDIR = "templates"
_REFERENCE_SUBDIR = "references"


class ResourceError(RuntimeError):
    """Raised when an explicit resource root is supplied but unusable."""


class SkillResources:
    """Resolved locations of the skill's bundled templates and references."""

    def __init__(self, source: str, templates_dir: Path, references_dir: Path) -> None:
        self.source = source
        self.templates_dir = templates_dir
        self.references_dir = references_dir

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"SkillResources(source={self.source!r})"


def _templates_under(root: Path) -> Path:
    standard = root / "assets" / _TEMPLATE_SUBDIR
    if standard.is_dir():
        return standard
    return root / _TEMPLATE_SUBDIR


def _is_valid_root(root: Path) -> bool:
    """A usable root exposes templates and references in a supported layout."""
    return _templates_under(root).is_dir() and (root / _REFERENCE_SUBDIR).is_dir()


def _from_explicit_root(root: Path, label: str) -> SkillResources:
    root = root.expanduser().resolve()
    if not root.is_dir() or not _is_valid_root(root):
        raise ResourceError(
            f"{label} does not point at a valid skill root "
            f"(need assets/{_TEMPLATE_SUBDIR}/ + {_REFERENCE_SUBDIR}/, or the "
            f"legacy {_TEMPLATE_SUBDIR}/ + {_REFERENCE_SUBDIR}/ layout): {root}"
        )
    return SkillResources(
        source=label,
        templates_dir=_templates_under(root),
        references_dir=root / _REFERENCE_SUBDIR,
    )


def _from_importlib() -> Optional[SkillResources]:
    """Read the bundled package-data copy (the installed-wheel default)."""
    try:
        base = _ilr.files(_RESOURCE_PACKAGE)
    except (ModuleNotFoundError, ValueError, OSError):
        return None
    try:
        templates_dir = Path(base.joinpath(_TEMPLATE_SUBDIR))
        references_dir = Path(base.joinpath(_REFERENCE_SUBDIR))
    except (ValueError, OSError):
        return None
    # importlib.resources traversals resolve lazily; confirm real files exist.
    try:
        if not any(True for _ in templates_dir.iterdir()):
            return None
        if not any(True for _ in references_dir.iterdir()):
            return None
    except (OSError, FileNotFoundError):
        return None
    return SkillResources(
        source="importlib.resources",
        templates_dir=templates_dir,
        references_dir=references_dir,
    )


def _from_source_tree() -> Optional[SkillResources]:
    """Dev-only fallback: a cloned repo with ``core/templates`` and ``core/references``."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    core = repo_root / "core"
    if _is_valid_root(core):
        return SkillResources(
            source="source-tree",
            templates_dir=core / _TEMPLATE_SUBDIR,
            references_dir=core / _REFERENCE_SUBDIR,
        )
    return None


def locate_skill_resources(
    *,
    skill_root: Optional[Path] = None,
    env_var: str = "OBSIDIAN_KB_SKILL_ROOT",
) -> SkillResources:
    """Resolve the skill's bundled resources.

    Explicit arguments win and are validated strictly. An invalid explicit root
    is an error, never a silent fallback.
    """
    if skill_root is not None:
        return _from_explicit_root(Path(skill_root), "skill-root")

    env_value = os.environ.get(env_var)
    if env_value:
        return _from_explicit_root(Path(env_value), f"${env_var}")

    bundled = _from_importlib()
    if bundled is not None:
        return bundled

    source = _from_source_tree()
    if source is not None:
        return source

    raise ResourceError(
        "Could not locate the skill's bundled templates/references. "
        "Run from an installed wheel, set --skill-root, or set "
        f"{env_var}. Development checkout fallback also failed."
    )


def template_dir(
    *,
    skill_root: Optional[Path] = None,
    env_var: str = "OBSIDIAN_KB_SKILL_ROOT",
) -> Path:
    """Convenience: just the bundled templates directory."""
    return locate_skill_resources(skill_root=skill_root, env_var=env_var).templates_dir


def reference_dir(
    *,
    skill_root: Optional[Path] = None,
    env_var: str = "OBSIDIAN_KB_SKILL_ROOT",
) -> Path:
    """Convenience: just the bundled references directory."""
    return locate_skill_resources(skill_root=skill_root, env_var=env_var).references_dir
