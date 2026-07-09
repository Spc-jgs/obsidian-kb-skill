"""Single source of truth for note-type templates.

Every note type's template filename, default tags, extra frontmatter fields,
and body skeleton live here. `create_note.py` reads the field defaults from this
module instead of keeping its own copy, and `scaffold_templates.py` regenerates a
vault's `Templates/` from it. Because both derive from this one spec, the
frontmatter `create_note` writes and the frontmatter the templates declare can
never drift apart.

The body skeletons are stored verbatim so `scaffold_templates.py` can reproduce
the shipped templates exactly.
"""
from __future__ import annotations

NOTE_TYPES: dict[str, dict] = {
    "daily-note": {
        "filename": "Daily Note",
        "tags": ["daily"],
        "fields": {"related": []},
        "body": (
            "# {{date}} 日记\n\n"
            "## 今日焦点\n\n"
            "> 今天最重要的一件事是什么？\n\n"
            "## 今日记录\n\n"
            "## 工作与会议\n\n"
            "## 学习与思考\n\n"
            "## 待办事项\n\n"
            "- [ ]\n\n"
            "## 今日复盘\n\n"
            "## 一句话总结\n"
        ),
    },
    "meeting-note": {
        "filename": "Meeting Note",
        "tags": ["meeting"],
        "fields": {"participants": [], "project": "", "related": []},
        "body": (
            "# 会议主题\n\n"
            "## 会议信息\n\n"
            "- **日期**：{{date}}\n"
            "- **参会人**：\n"
            "- **时长**：\n\n"
            "## 会议目标\n\n"
            "## 讨论记录\n\n"
            "## 决策结论\n\n"
            "## 待办事项\n\n"
            "- [ ]\n\n"
            "## 后续跟进\n"
        ),
    },
    "learning-note": {
        "filename": "Learning Note",
        "tags": ["learning"],
        "fields": {"source": "", "category": "", "related": []},
        "body": (
            "# 学习主题\n\n"
            "> 前置知识：\n\n"
            "## 今天学了什么\n\n"
            "> 用一句话总结核心内容。\n\n"
            "## 核心知识点\n\n"
            "### 概念解释\n\n"
            "### 示例\n\n"
            "### WHY：为什么这样设计\n\n"
            "### 类比或常见错误\n\n"
            "## 易错点\n\n"
            "## 实际应用\n\n"
            "## 待解决问题\n\n"
            "## 关联笔记\n"
        ),
    },
    "web-clip": {
        "filename": "Web Clip",
        "tags": ["web-clip"],
        "fields": {"source": "", "author": "", "published": "", "related": []},
        "body": (
            "# 文章标题\n\n"
            "## 来源信息\n\n"
            "- **原文链接**：\n"
            "- **作者**：\n"
            "- **发布日期**：\n"
            "- **剪藏日期**：{{date}}\n\n"
            "## 一句话摘要\n\n"
            "## 核心观点\n\n"
            "## 重要摘录\n\n"
            "> 只保留必要的短引用。\n\n"
            "## 理解与启发\n\n"
            "<!-- 用 2–4 句话区分原文观点与自己的推论，不机械复述核心观点，"
            "也不要代替用户表达个人立场。 -->\n\n"
            "## 后续行动\n\n"
            "- [ ]\n\n"
            "## 关联笔记\n"
        ),
    },
    "insight-note": {
        "filename": "Insight Note",
        "tags": ["insight"],
        "fields": {"source": "", "related": []},
        "body": (
            "# 洞察标题\n\n"
            "## 核心洞察\n\n"
            "> 用一句话概括最重要的结论。\n\n"
            "## 背景与上下文\n\n"
            "## 分析与推导\n\n"
            "## 影响与后续行动\n\n"
            "- [ ]\n\n"
            "## 关联笔记\n"
        ),
    },
    "conversation-digest": {
        "filename": "Digest Note",
        "tags": ["insight"],
        "fields": {"source": "", "related": []},
        "body": (
            "# 对话标题\n\n"
            "## 背景\n\n"
            "> 这段对话的起因、参与方与目标。\n\n"
            "## 已确认的结论\n\n"
            "- \n\n"
            "## 推翻或修正的想法\n\n"
            "- \n\n"
            "## 后续任务\n\n"
            "- [ ] \n\n"
            "## 关联项目\n\n"
            "- \n\n"
            "## 可继续追问\n\n"
            "- \n"
        ),
    },
    "project-note": {
        "filename": "Project Note",
        "tags": ["project"],
        "fields": {"status": "active", "related": []},
        "updated": True,
        "body": (
            "# 项目名称\n\n"
            "## 项目概览\n\n"
            "- **目标**：\n"
            "- **时间范围**：\n"
            "- **参与人**：\n\n"
            "## 背景与价值\n\n"
            "## 里程碑\n\n"
            "## 进展记录\n\n"
            "| 日期 | 进展 |\n"
            "|---|---|\n"
            "| {{date}} | |\n\n"
            "## 风险与阻塞\n\n"
            "## 决策记录\n\n"
            "## 下一步行动\n\n"
            "- [ ]\n\n"
            "## 关联笔记\n"
        ),
    },
    "person-note": {
        "filename": "Person Note",
        "tags": ["people"],
        "fields": {"role": "", "organization": "", "related": []},
        "updated": True,
        "body": (
            "# 姓名\n\n"
            "## 基本信息\n\n"
            "- **角色**：\n"
            "- **组织**：\n"
            "- **联系方式**：\n\n"
            "## 关键背景\n\n"
            "## 互动记录\n\n"
            "| 日期 | 场景 | 记录 |\n"
            "|---|---|---|\n"
            "| | | |\n\n"
            "## 跟进事项\n\n"
            "- [ ]\n\n"
            "## 关联笔记\n"
        ),
    },
    "task-memory": {
        "filename": "TASK",
        "tags": ["task"],
        "fields": {
            "status": "active",
            "task-memory": "enabled",
            "agents": [],
            "decisions": [],
            "constraints": [],
            "artifacts": [],
            "open": [],
        },
        "body": (
            "## TL;DR\n"
            "<2 sentences: what this task is and where it stands>\n\n"
            "## Decisions (crystallized)\n"
            "- ...\n\n"
            "## Open\n"
            "- ...\n\n"
            "## Log\n"
        ),
    },
}

# Import-compatible views used by create_note.py / update_note.py.
EXTRA_FIELDS: dict[str, dict] = {
    name: spec["fields"] for name, spec in NOTE_TYPES.items()
}
DEFAULT_TAG_BY_TYPE: dict[str, str] = {
    name: spec["tags"][0] for name, spec in NOTE_TYPES.items()
}
# The task-memory body skeleton, also used by update_note.py's upsert init.
TASK_DEFAULT_BODY: str = NOTE_TYPES["task-memory"]["body"]
