"""Canonical Markdown renderers for newly initialized Vault indexes."""
from __future__ import annotations

from pathlib import Path

import yaml


def _frontmatter(note_type: str) -> str:
    metadata = yaml.safe_dump(
        {"type": note_type, "tags": ["moc"]},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return f"---\n{metadata}\n---\n"


def render_folder_index(name: str) -> str:
    """Render a Folder Index plugin-owned category index."""
    return (
        f"{_frontmatter('folder-index')}\n# {name}\n\n"
        "```folder-index-content\n"
        "```\n"
    )


def render_dataview_index(name: str, folder: Path) -> str:
    """Render a Dataview-owned category index scoped to one folder."""
    return (
        f"{_frontmatter('moc')}\n# {name}\n\n"
        "```dataview\n"
        "LIST\n"
        f'FROM "{folder.as_posix()}"\n'
        'WHERE file.name != "INDEX"\n'
        "SORT file.name ASC\n"
        "```\n"
    )


def render_static_index(name: str) -> str:
    """Render an empty manually maintained category MOC."""
    return f"{_frontmatter('moc')}\n# {name}\n"
