# Obsidian Knowledge Base Skill

**v1.2.0** | **让任何 AI 编程助手变成你的个人知识管理助手。**

一个跨平台 Skill，教会 AI 智能体（QoderWork、Claude Code、OpenAI Codex、Cursor）自动在你的 [Obsidian](https://obsidian.md) 知识库中创建、组织和关联笔记。

[English Version](README_EN.md)

---

## 解决什么问题

我们每天都在跟 AI 助手对话——头脑风暴、分析文章、评审会议、排查问题。这些对话会产生大量有价值的知识，但几乎总是在你关闭聊天窗口的那一刻就蒸发了。

手动把洞察复制到笔记工具里，既繁琐又不持续。摩擦成本太高：你要想清楚放在哪个文件夹、用什么格式、打什么标签、跟已有笔记怎么关联。所以大多数时候，你干脆就不记了。

## 怎么解决的

这个 Skill 通过教会 AI 智能体一整套知识管理规范来消除这个摩擦。你只需要说「沉淀到知识库」或「记录一下这个会议」，AI 就会自动处理一切：

- 选择正确的笔记类型和模板
- 填写结构化元数据（日期、标签、来源）
- 写入 Obsidian 知识库中对应的文件夹
- 更新文件夹索引
- 用 `[[wikilinks]]` 关联相关笔记

你的知识以结构化的方式自动积累，从 10 条笔记到 10000 条都能轻松管理。

## 下载

### 方式一：Git 克隆（推荐）

```bash
git clone https://github.com/Spc-jgs/obsidian-kb-skill.git
cd obsidian-kb-skill
```

### 方式二：下载 ZIP

1. 打开 https://github.com/Spc-jgs/obsidian-kb-skill
2. 点击绿色的 **Code** 按钮
3. 选择 **Download ZIP**
4. 解压到你想要的目录

### 方式三：只拿你需要的平台文件

如果你不想克隆整个仓库，可以直接复制对应平台的指令文件：

| 你用的 AI 工具 | 需要的文件 | 直接链接 |
|--------------|-----------|---------|
| QoderWork | `platforms/qoderwork/SKILL.md` | [SKILL.md](platforms/qoderwork/SKILL.md) |
| Claude Code | `platforms/claude-code/CLAUDE.md` | [CLAUDE.md](platforms/claude-code/CLAUDE.md) |
| OpenAI Codex | `platforms/codex/AGENTS.md` | [AGENTS.md](platforms/codex/AGENTS.md) |
| Cursor | `platforms/cursor/obsidian-kb.mdc` | [obsidian-kb.mdc](platforms/cursor/obsidian-kb.mdc) |

每个平台文件都是**自包含**的——一个文件就包含了指令、模板、路由规则，复制即用。

## 使用场景

### 场景一：AI 对话中产生的知识自动沉淀

你跟 AI 讨论了一个技术方案，比如「微服务 vs 单体架构的取舍」。讨论结束后你说一句「沉淀到知识库」，AI 就会把这次讨论的核心洞察整理成结构化笔记，存入 `30-Insights/` 文件夹，自动打标签、建索引、关联已有笔记。

### 场景二：会议记录自动生成

开完一个需求评审会，你把会议要点告诉 AI：「记录一下刚才的需求评审会，参会人有张三李四，讨论了 V2 版本的用户认证方案，决定用 OAuth2」。AI 会用「会议笔记」模板创建笔记，写入 `10-Work/`，包含参会人、决策、待办事项等结构化字段。

### 场景三：网页文章一键剪藏

看到一篇好文章，把内容或链接发给 AI：「剪藏这篇文章 https://example.com/article」。AI 用「网页剪藏」模板提取要点、高亮关键内容、保存到 `20-Learning/`，并记录原始 URL。

### 场景四：学习笔记持续积累

你在学一门课程或读一本书，随时跟 AI 交流心得，然后说「记一下关于 Redis 持久化的学习笔记」。AI 用「学习笔记」模板整理核心概念、你的理解和疑问，存入 `20-Learning/`。

### 场景五：项目上下文长期跟踪

启动一个新项目时，告诉 AI「创建仪表盘重构的项目笔记」。AI 在 `40-Projects/` 创建项目笔记，包含目标、时间线、风险等字段。后续每次项目有新进展，AI 都在同一个笔记的进展日志中追加更新。

### 场景六：跨 AI 工具的统一知识库

你在公司用 Cursor 写代码，在家用 QoderWork 做研究，路上用 Claude Code 查问题——所有对话产生的知识都沉淀到**同一个 Obsidian 知识库**，用**同样的文件夹结构和模板**，不会因为换了 AI 工具就丢失或格式不一致。

## 原理

### 核心思路：用 Markdown 指令教会 AI 做事

这个 Skill 的本质是一个 **Markdown 格式的行为指令文件**。它不包含任何代码，不调用任何 API，不运行任何服务。它只是用自然语言告诉 AI 智能体：

1. 你的知识库在哪里（路径）
2. 知识库长什么样（文件夹结构）
3. 每种笔记应该怎么写（模板 + YAML frontmatter）
4. 什么内容应该放哪个文件夹（路由规则）
5. 怎么给笔记打标签（标签体系）
6. 怎么更新文件夹索引（INDEX.md 维护）

AI 智能体读完这个指令文件后，就「学会了」你的知识管理规范。当你说「沉淀到知识库」时，AI 按照指令文件中的规则，直接用文件系统读写你的 Obsidian 知识库。

### 架构：一核多适配器

```
                  ┌──────────────────────────┐
                  │  core/OBSIDIAN_KB.md     │
                  │  (通用指令，与平台无关)      │
                  └────────┬─────────────────┘
                           │
            ┌──────────────┼──────────────────┐
            │              │                  │
    ┌───────▼──────┐ ┌────▼────────┐ ┌───────▼───────┐
    │  SKILL.md    │ │ CLAUDE.md   │ │  AGENTS.md    │ ...
    │ (QoderWork)  │ │(Claude Code)│ │ (Codex)       │
    └──────────────┘ └─────────────┘ └───────────────┘
```

核心指令文件 `core/OBSIDIAN_KB.md` 是「唯一真相来源」，定义了所有知识管理规则。各平台的适配器文件从核心指令派生，包含**完全一致的规则**，只是文件格式遵循各平台的约定（QoderWork 用 YAML frontmatter 的 SKILL.md，Cursor 用 .mdc 格式，等等）。

### 为什么不需要插件或 API

Obsidian 知识库的底层就是一个**装满 .md 文件的文件夹**。没有数据库，没有私有格式。AI 智能体天然就擅长读写文件和操作文件夹。所以：

- **创建笔记** = 在指定路径写一个 .md 文件
- **更新索引** = 往 INDEX.md 追加一行链接
- **关联笔记** = 在内容里插入 `[[filename|显示文本]]`
- **结构化元数据** = 在文件头部写 YAML frontmatter

AI 做的每一件事都是标准的文件操作。这意味着零依赖、零网络请求、零额外成本。你的知识库完全在本地，隐私安全。

### 运行时流程

```
你说：「把微服务讨论的关键洞察沉淀到知识库」

AI 智能体内部执行：
  1. 读取 ~/.obsidian-kb-config → 得到知识库路径 D:\MyKnowledgeBase
  2. 识别触发词「洞察」→ 路由到 30-Insights/ 文件夹
  3. 读取 Templates/insight-note.md → 获取洞察笔记模板
  4. 填写 YAML frontmatter（日期、标签、一句话洞察）
  5. 生成正文内容（上下文、分析、影响、后续行动）
  6. 写入 30-Insights/2026-06-10 微服务架构洞察.md
  7. 读取 30-Insights/INDEX.md → 追加新笔记链接
  8. 回复你：「已保存到 30-Insights/2026-06-10 微服务架构洞察.md」
```

## 支持的平台

| 平台 | 配置文件 | 安装位置 |
|------|---------|---------|
| **QoderWork / Qoder CLI** | `SKILL.md` | `~/.qoderwork/skills/obsidian-knowledge-base/` |
| **Claude Code** | `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| **OpenAI Codex** | `AGENTS.md` | `~/AGENTS.md` |
| **Cursor** | `obsidian-kb.mdc` | `~/.cursor/rules/obsidian-kb.mdc` |

四个平台的文件包含**完全一致的指令**——同样的文件夹路由、同样的模板、同样的 YAML 规范、同样的标签体系。只是文件格式遵循各平台的约定。

## 快速开始

### 1. 下载项目

```bash
git clone https://github.com/Spc-jgs/obsidian-kb-skill.git
cd obsidian-kb-skill
```

### 2. 配置知识库路径

```bash
cp .env.example .env
```

编辑 `.env`，填入你的知识库路径：

```env
OBSIDIAN_KB_VAULT=D:\MyKnowledgeBase
```

如果你的知识库还不存在，安装脚本会自动创建完整的文件夹结构。

### 3. 运行安装脚本

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
- 将知识库路径写入 `~/.obsidian-kb-config`（运行时配置）
- 将 Skill 文件安装到对应 AI 平台的约定位置

### 4. 用 Obsidian 打开

在 Obsidian 中打开你的知识库文件夹，你会看到文件夹结构、模板和索引页都已就绪。

### 5. 开始沉淀

对你的 AI 助手说：

- 「把系统设计的讨论沉淀到知识库」
- 「记录一下 Q2 规划会议」
- 「剪藏这篇文章：https://example.com/article」
- 「创建一个仪表盘重构的项目笔记」

### 手动安装（不用安装脚本）

如果你更喜欢手动操作，或者安装脚本不满足你的需求：

```bash
# 1. 创建配置文件，写入知识库路径
echo "D:\MyKnowledgeBase" > ~/.obsidian-kb-config

# 2. 复制对应平台的指令文件到约定位置
# QoderWork:
cp platforms/qoderwork/SKILL.md ~/.qoderwork/skills/obsidian-knowledge-base/SKILL.md

# Claude Code:
cp platforms/claude-code/CLAUDE.md ~/.claude/CLAUDE.md

# Cursor:
cp platforms/cursor/obsidian-kb.mdc ~/.cursor/rules/obsidian-kb.mdc

# 3. 复制模板到知识库
cp -r core/templates/* /你的知识库路径/Templates/
```

## 知识库结构

```
YourVault/
├── 00-Inbox/          收件箱 —— 快速捕获，稍后整理
├── 10-Work/           工作 —— 会议记录、工作文档、团队讨论
├── 15-Daily/          日记 —— 每日记录、晨间规划、复盘
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

### 升级模板

重新运行安装脚本时，已有模板默认不会被覆盖。使用 `--force` 强制更新模板，并把 CLAUDE.md / AGENTS.md 里 marker 包裹的 skill 块替换成新版：

```bash
# macOS / Linux
./install.sh --force

# Windows
.\install.ps1 -Force
```

> 安装脚本会把 skill 内容放在 `<!-- BEGIN obsidian-kb-skill -->` / `<!-- END obsidian-kb-skill -->` marker 之间。再次运行安装脚本时会原地替换这段内容，不会影响你在 `CLAUDE.md` / `AGENTS.md` 里写的其他指令。

### 卸载

```bash
# macOS / Linux
./install.sh --uninstall

# Windows
.\install.ps1 -Uninstall
```

卸载会移除 QoderWork skill 目录、Cursor 规则、配置文件，并且**自动从 `CLAUDE.md` / `AGENTS.md` 中删除 marker 包裹的 skill 块**（保留你的其他内容）。Obsidian vault 文件夹和笔记内容不会被删除。

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
├── build.py                    适配器生成脚本（核心 + header → 4 个适配器）
├── core/
│   ├── OBSIDIAN_KB.md          通用指令唯一真相来源（agent 无关）
│   └── templates/              7 个可移植的笔记模板
├── platforms/
│   ├── qoderwork/
│   │   ├── header.md           QoderWork 平台头部（YAML frontmatter）
│   │   └── SKILL.md            生成产物（请勿手动编辑）
│   ├── claude-code/
│   │   ├── header.md
│   │   └── CLAUDE.md           生成产物
│   ├── codex/
│   │   ├── header.md
│   │   └── AGENTS.md           生成产物
│   └── cursor/
│       ├── header.md
│       └── obsidian-kb.mdc     生成产物
├── install.sh                  macOS / Linux 安装脚本
├── install.ps1                 Windows 安装脚本
├── CHANGELOG.md
└── README.md
```

## 修改 Skill / 贡献代码

四个平台的指令文件由 `build.py` 从单一源头生成。**不要直接编辑 `platforms/*/SKILL.md` 等生成产物**，否则下次构建会覆盖你的改动。

```bash
# 1. 修改通用规则
$EDITOR core/OBSIDIAN_KB.md

# 2. 或修改某平台的头部（YAML frontmatter / trigger 描述）
$EDITOR platforms/qoderwork/header.md

# 3. 重新生成四个适配器
python build.py

# 4. 校验产物与源头一致（CI / pre-commit 用）
python build.py --check
```

这样一处改动，四个平台自动同步，避免「改一处忘三处」的维护噩梦。

## 设计原则

- **纯 Markdown。** 没有数据库、没有 API、没有厂商锁定。你的知识就是纯文本文件，比任何 App 都持久。
- **智能体无关。** 核心逻辑与平台无关。每个 AI 工具只得到一个薄薄的适配器文件。
- **约定优于配置。** 文件夹结构、命名、标签、模板都有合理的默认值。只自定义你需要的部分。
- **运行时自包含。** 安装后，每个平台文件包含所需的一切——没有外部依赖。
- **本地优先。** 所有数据都在你的机器上，不经过任何云服务，隐私完全可控。

## 常见问题

**Q：我需要付费使用 Obsidian 吗？**
A：不需要。Obsidian 对个人使用完全免费。

**Q：AI 读写我的文件安全吗？**
A：AI 只在你指定的知识库路径下操作，不会触碰其他文件。所有操作都在本地完成。

**Q：我可以同时用多个 AI 工具吗？**
A：可以。这正是这个项目的设计目标——所有 AI 工具共享同一个知识库，使用同样的规范。

**Q：安装脚本会不会覆盖我已有的笔记？**
A：不会。安装脚本只创建缺失的文件夹和文件，不会修改已有内容。

## 推荐的 Obsidian 插件

以下是可选的，但能增强体验：

- **[Dataview](https://github.com/blacksmithgu/obsidian-dataview)** —— 像数据库一样查询笔记（如「列出本周所有会议记录」）
- **[Calendar](https://github.com/liamcain/obsidian-calendar-plugin)** —— 日历视图浏览日记
- **[Kanban](https://github.com/mgmeyers/obsidian-kanban)** —— 读取知识库的项目看板
- **[Templater](https://github.com/SilentVoid13/Templater)** —— 高级模板处理，用于手动创建笔记

## 许可证

MIT —— 自由使用、修改、分享。
