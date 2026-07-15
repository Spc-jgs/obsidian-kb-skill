"""Plan and initialize one user-confirmed category inside an Obsidian Vault."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from obsidian_kb_skill.scripts.audit_vault import (
    _folder_index_config,
    _is_folder_index_excluded,
    expected_folder_index,
)
from obsidian_kb_skill.scripts.detect_index import detect
from obsidian_kb_skill.scripts.index_templates import (
    render_dataview_index,
    render_folder_index,
    render_static_index,
)
from obsidian_kb_skill.scripts.vault_paths import validate_vault_root


@dataclass(frozen=True)
class PlannedChange:
    kind: str
    path: Path


@dataclass(frozen=True)
class CategoryPlan:
    vault: Path
    folder: Path
    parent: Path
    category: str
    exists: bool
    index_mode: str
    index_path: Path
    planned_changes: tuple[PlannedChange, ...]
    governance_reminders: tuple[str, ...]
    warnings: tuple[str, ...]


def _reminders(vault: Path) -> tuple[str, ...]:
    return tuple(
        name for name in ("AGENTS.md", "README.md") if (vault / name).is_file()
    )


def plan_category(vault: Path, folder: str) -> CategoryPlan:
    """Return the deterministic index plan for one category path."""
    root = validate_vault_root(vault)
    relative = Path(folder)
    parent = relative.parent
    target = root / relative
    config = _folder_index_config(root)
    parent_info = detect(root, parent.as_posix())
    warnings = tuple(parent_info.get("warnings", ()))

    if config.enabled and not _is_folder_index_excluded(relative, config):
        mode = "folder-index"
        index = expected_folder_index(target, root, config).relative_to(root)
    else:
        mode = "dataview" if parent_info["mode"] == "dataview" else "static"
        index = relative / "INDEX.md"

    exists = target.is_dir()
    changes = () if exists else (
        PlannedChange("directory", relative),
        PlannedChange("index", index),
    )
    return CategoryPlan(
        vault=root,
        folder=relative,
        parent=parent,
        category=relative.name,
        exists=exists,
        index_mode=mode,
        index_path=index,
        planned_changes=changes,
        governance_reminders=_reminders(root),
        warnings=warnings,
    )


def render_category_index(plan: CategoryPlan) -> str:
    """Render the index selected by ``plan_category``."""
    if plan.index_mode == "folder-index":
        return render_folder_index(plan.category)
    if plan.index_mode == "dataview":
        return render_dataview_index(plan.category, plan.folder)
    return render_static_index(plan.category)
