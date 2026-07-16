"""Shared note-type metadata used by creation and validation helpers."""
from __future__ import annotations


TYPE_TO_TEMPLATE: dict[str, str] = {
    "daily-note": "Daily Note.md",
    "meeting-note": "Meeting Note.md",
    "learning-note": "Learning Note.md",
    "web-clip": "Web Clip.md",
    "insight-note": "Insight Note.md",
    "conversation-digest": "Digest Note.md",
    "project-note": "Project Note.md",
    "person-note": "Person Note.md",
}

TYPE_TO_TEMPLATE_ASSET: dict[str, str] = {
    "daily-note": "daily-note.md",
    "meeting-note": "meeting-note.md",
    "learning-note": "learning-note.md",
    "web-clip": "web-clip.md",
    "insight-note": "insight-note.md",
    "conversation-digest": "digest-note.md",
    "project-note": "project-note.md",
    "person-note": "person-note.md",
}
