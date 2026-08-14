"""Compatibility exports for historical note-type metadata imports."""

from obsidian_kb_skill.scripts.note_catalog import (
    TYPE_TO_TEMPLATE,
    TYPE_TO_TEMPLATE_ASSET,
)

# Declared so the re-export is intent rather than an import that looks unused.
__all__ = ["TYPE_TO_TEMPLATE", "TYPE_TO_TEMPLATE_ASSET"]
