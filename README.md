# Obsidian Knowledge Base Skill

**让任何 AI 编程助手变成你的个人知识管理助手。**

一个跨平台 Skill，教会 AI 智能体（QoderWork、Claude Code、OpenAI Codex、Cursor）自动在你的 [Obsidian](https://obsidian.md) 知识库中创建、组织和关联笔记。

[English Version](README_EN.md)

---

## 解决什么问题

我们每天都在跟 AI 助手对话——头脑风暴、分析文章、评审会议、排查问题。这些对话会产生大量有价值的知识，但几乎总是在你关闭聊天窗口的那一刻就蒸发了。

手动把洞察复制到笔记工具里，既繁琐又不持续。摩擦成本太高：你要想清楚放在哪个文件夹、用什么格式、打什么标签、跟已有笔记怎么关联。所以大多数时候，你干脆就不记了。

## 怎么解决的

这个 Skill 通过教会 AI 智能体一整套知识管理工作流来消除这个摩擦。你只需要说「沉淀到知识库」或「记录一下这个会议」，AI 就会自动处理一切：

- 选择正确的笔记类型和模板
- 填写结构化元数据（日期、标签、来源）
- 写入 Obsidian 知识库中对应的文件夹
- 更新文件夹索引
- 用 `[[wikilinks]]` 关联相关笔记

你的知识以结构化的方式自动积累，从 10 条笔记到 10000 条都能轻松管理。

## 工作原理

```
你：「把微服务讨论的关键洞察沉淀到知识库」

AI 智能体：
  1. 从 ~/.obsidian-kb-config 读取知识库路径
  2. 从你的知识库读取「洞察笔记」模板
  3. 填写 YAML frontmatter + 分析内容
  4. 写入 30-Insights/2026-06-09 微服务架构洞察.md
  5. 在 30-Insights/INDEX.md 追加链接
  6. 确认：「已保存到 30-Insights/2026-06-09 微服务架构洞察.md」
```

这个 Skill 本质上**只是一个 Markdown 指令文件**，教会 AI 智能体你的知识管理规范。不需要插件、不需要 API、不需要服务器——你的 Obsidian 知识库就是一堆 Markdown 文件，AI 直接读写它们。

## 支持的平台

| 平台 | 配置文件 | 安装位置 |
|------|---------|---------|
| **QoderWork / Qoder CLI** | `SKILL.md` | `~/.qoderwork/skills/obsidian-knowledge-base/` |
| **Claude Code** | `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| **OpenAI Codex** | `AGENTS.md` | `~/AGENTS.md` |
| **Cursor** | `obsidian-kb.mdc` | `~/.cursor/rules/obsidian-kb.mdc` |

四个平台的文件包含**完全一致的指令**——同样的文件夹路由、同样的模板、同样的 YAML 规范、同样的标签体系。只是文件格式遵循各平台的约定。

## 快速开始

### 1. 配置知识库路径

```bash
cp .env.example .env
```

编辑 `.env`，填入你的知识库路径：

```env
OBSIDIAN_KB_VAULT=D:\MyKnowledgeBase
```

### 2. 运行安装脚本

**Windows (PowerShell)：**
```powershell
.\install.ps1
```

**macOS / Linux：**
```bash
chmod +x install.sh
./install.sh
```

安装脚本会自动完成以下工作：

- 创建知识库文件夹结构（如果不存在）
- 复制 7 个笔记模板到你的知识库
- 在每个文件夹中创建 INDEX.md 导航文件
- 将知识库路径写入 `~/.obsidian-kb-config`
- 将 Skill 文件安装到对应 AI 平台

### 3. 用 Obsidian 打开

在 Obsidian 中打开你的知识库文件夹，你会看到文件夹结构、模板和索引页都已就绪。

### 4. 开始沉淀

对你的 AI 助手说：

- 「把系统设计的讨论沉淀到知识库」
- 「记录一下 Q2 规划会议」
- 「剪藏这篇文章：https://example.com/article」
- 「创建一个仪表盘重构的项目笔记」

## 知识库结构

```
YourVault/
├── 00-Inbox/          收件箱 —— 快速捕获，稍后整理
├── 10-Work/           工作 —— 会议记录、工作文档、团队讨论
├── 20-Learning/       学习 —— 文章、笔记、网页剪藏、课程资料
├── 30-Insights/       洞察 —— 分析、想法、AI 生成的洞察
├── 40-Projects/       项目 —— 活跃项目的上下文和进展日志
├── 50-People/         人物 —— 联系人、团队成员、互动记录
├── 90-Archive/        归档 —— 已完成或不活跃的内容
├── Templates/         7 个预置笔记模板
├── Attachments/       图片和文件附件
└── INDEX.md           主导航页（Map of Content）
```

## 笔记模板

| 模板 | 使用场景 | 关键字段 |
|------|---------|---------|
| **Daily Note** | 日记、每日规划 | 今日焦点、任务、反思 |
| **Meeting Note** | 会议、站会、评审 | 参会人、议程、待办事项、决策 |
| **Learning Note** | 文章、书籍、课程 | 来源、核心收获、与工作的关联 |
| **Web Clip** | 网页、博客文章 | URL、高亮、关键引文 |
| **Insight Note** | 分析、想法、AI 对话 | 一句话洞察、上下文、影响 |
| **Project Note** | 活跃项目 | 目标、时间线、进展日志、风险 |
| **Person Note** | 联系人、团队成员 | 角色、互动日志、跟进事项 |

所有模板使用 YAML frontmatter 作为结构化元数据，便于用 Dataview 等 Obsidian 插件进行过滤、搜索和查询。

## 配置

### 知识库路径查找顺序

安装脚本和 Skill 按以下优先级查找知识库路径：

| 优先级 | 来源 | 示例 |
|--------|------|------|
| 1 | 命令行参数 | `--vault /path/to/vault` |
| 2 | `.env` 文件 | `OBSIDIAN_KB_VAULT=/path/to/vault` |
| 3 | 环境变量 | `export OBSIDIAN_KB_VAULT=/path/to/vault` |
| 4 | 配置文件 | `~/.obsidian-kb-config` |

### 修改知识库路径

编辑 `.env` 后重新运行安装脚本，或直接修改配置文件：

```bash
# macOS / Linux
echo "/新的/知识库/路径" > ~/.obsidian-kb-config

# Windows PowerShell
[System.IO.File]::WriteAllText(
    "$env:USERPROFILE\.obsidian-kb-config",
    "D:\NewVaultPath",
    (New-Object System.Text.UTF8Encoding $false)
)
```

### 只安装特定平台

```bash
# 只装 QoderWork 和 Claude Code
./install.sh --platforms qoderwork,claude-code

# 只装 Cursor
.\install.ps1 -Platforms "cursor"
```

## 分享给别人

这个 Skill 就是设计来分享的。分享给别人时：

1. 把整个 `obsidian-kb-skill/` 文件夹发给对方（或指向这个仓库）
2. **不要**包含你的 `.env` 文件（已在 `.gitignore` 中排除）
3. 对方复制 `.env.example` 为 `.env`，填自己的知识库路径，运行安装脚本

## 自定义

**添加模板：** 在知识库的 `Templates/` 文件夹中创建新的 `.md` 文件，使用相同的 YAML frontmatter 格式。

**添加文件夹：** 创建新的编号文件夹（如 `60-Research/`），在里面放一个 `INDEX.md`，AI 会自动发现。

**修改标签：** 编辑平台指令文件中的标签部分，添加领域特定的标签。

**修改路由：** 修改文件夹路由表，把特定触发词重定向到不同文件夹。

## 项目结构

```
obsidian-kb-skill/
├── .env.example                配置模板（提交到 git）
├── .env                        你的本地配置（gitignored）
├── .gitignore
├── core/
│   ├── OBSIDIAN_KB.md          通用指令（agent 无关）
│   └── templates/              7 个可移植的笔记模板
├── platforms/
│   ├── qoderwork/SKILL.md      QoderWork 适配器
│   ├── claude-code/CLAUDE.md   Claude Code 适配器
│   ├── codex/AGENTS.md         OpenAI Codex 适配器
│   └── cursor/obsidian-kb.mdc  Cursor 适配器
├── install.sh                  macOS / Linux 安装脚本
├── install.ps1                 Windows 安装脚本
└── README.md
```

## 设计原则

- **纯 Markdown。** 没有数据库、没有 API、没有厂商锁定。你的知识就是纯文本文件，比任何 App 都持久。
- **智能体无关。** 核心逻辑与平台无关。每个 AI 工具只得到一个薄薄的适配器文件。
- **约定优于配置。** 文件夹结构、命名、标签、模板都有合理的默认值。只自定义你需要的部分。
- **运行时自包含。** 安装后，每个平台文件包含所需的一切——没有外部依赖。

## 推荐的 Obsidian 插件

以下是可选的，但能增强体验：

- **[Dataview](https://github.com/blacksmithgu/obsidian-dataview)** —— 像数据库一样查询笔记（如「列出本周所有会议记录」）
- **[Calendar](https://github.com/liamcain/obsidian-calendar-plugin)** —— 日历视图浏览日记
- **[Kanban](https://github.com/mgmeyers/obsidian-kanban)** —— 读取知识库的项目看板
- **[Templater](https://github.com/SilentVoid13/Templater)** —— 高级模板处理，用于手动创建笔记

## 许可证

MIT —— 自由使用、修改、分享。
