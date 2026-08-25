#!/usr/bin/env python3
"""Which section of a note holds the things its author still means to do.

Every note template puts exactly one `- [ ]` under exactly one heading. That
placement *is* the declaration: the template author decided that this section,
and no other, holds action items. This module restates those headings so the
retrieval bundle can read them without shipping the templates themselves.

**This is a mirror, and mirrors drift**, so
`test_the_action_headings_match_the_templates_that_declare_them` derives the
same set from `core/templates/**.md` and asserts equality. Adding a heading
here without adding it to a template fails, and so does the reverse — which is
the case that matters, because a new template section would otherwise be
invisible to the queue with nothing saying so.

Deliberately not a variants table. `deep_capture_contract` maps one locale to
one ordered list because it grades a *document's* structure; here the question
is only "is this heading an action section", so the locales collapse into one
set. `Action Items` appears in two templates and is one entry.
"""
from __future__ import annotations


# heading -> the templates that declare it, kept so a reader can see why a
# heading is in the set without opening every template.
ACTION_HEADINGS: dict[str, tuple[str, ...]] = {
    "待办事项": ("daily-note", "meeting-note"),
    "影响与后续行动": ("insight-note",),
    "跟进事项": ("person-note",),
    "下一步行动": ("project-note",),
    "后续行动": ("web-clip",),
    "Tasks": ("en/daily-note",),
    "Implications and Actions": ("en/insight-note",),
    "Action Items": ("en/meeting-note", "en/web-clip"),
    "Follow-up Items": ("en/person-note",),
    "Next Actions": ("en/project-note",),
}


def is_action_heading(heading: str) -> bool:
    """Whether a heading is one a template declared as holding action items.

    Exact match, not a substring or fuzzy test. `可复用的项目落地检查表` on the
    reference Vault holds fifteen `- [ ]` entries that are a reusable question
    list rather than tasks — they end in `；` and can never be ticked — and any
    looser predicate that reaches them would be reporting a note's prose as
    the author's open work.
    """
    return heading in ACTION_HEADINGS
