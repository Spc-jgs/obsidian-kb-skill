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

The canonical dict is one set, not a per-locale variant table.
`deep_capture_contract` maps one locale to one ordered list because it grades a
*document's* structure; here the locales collapse into one set. `Action Items`
appears in two templates and is one entry.

`ACTION_HEADING_SYNONYMS` is a separate, checked widening. Those headings are
collected even though no template declares them, and each value must be a key
of `ACTION_HEADINGS`. This overturns the earlier "do not widen this tool" rule
for this fixed list only. A heading in neither table is still ignored. The
values all name `待办事项` (the daily and meeting action section). They do not
retarget a project note's `下一步行动` or an English template's `Tasks`; a
caller who wants those sections names them.
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

# Common user/runtime variants mapped to canonical template action headings.
# Decoupled from ACTION_HEADINGS to maintain the 1:1 template invariant required
# by consistency inventory tests.
ACTION_HEADING_SYNONYMS: dict[str, str] = {
    "今日待办": "待办事项",
    "待办清单": "待办事项",
    "临时任务": "待办事项",
    "TODO": "待办事项",
    "Todo": "待办事项",
    "Todos": "待办事项",
    "备忘事项": "待办事项",
}


def is_action_heading(heading: str) -> bool:
    """Whether a heading is one a template declared as holding action items,
    or a known synonym thereof.
    """
    return heading in ACTION_HEADINGS or heading in ACTION_HEADING_SYNONYMS


def resolve_action_heading(heading: str) -> str | None:
    """Resolve an action heading (or synonym) to its canonical template heading."""
    if heading in ACTION_HEADINGS:
        return heading
    return ACTION_HEADING_SYNONYMS.get(heading)

