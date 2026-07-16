# Obsidian Knowledge Base Skill

**v1.19.0** | **让任何 AI 编程助手变成你的个人知识管理助手。**

一个跨平台 Skill，教会 AI 智能体（QoderWork、Claude Code、OpenAI Codex、Cursor、WorkBuddy）自动在你的 [Obsidian](https://obsidian.md) 知识库中创建、组织和关联笔记。

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
- 按 Folder Index、Dataview 或静态列表策略处理文件夹索引
- 用 `[[wikilinks]]` 关联相关笔记

你的知识以结构化的方式自动积累，从 10 条笔记到 10000 条都能轻松管理。

## v1.19 新增的能力

v1.19 让普通沉淀在起草前拿到必要的模板结构，同时把低频异常说明移出常规上下文：

- `vault-info --compact --type <slug>` 只返回所选标准模板的路径和有序二级标题，不返回模板正文或 frontmatter。
- 普通路径一次发现即可完成 Vault、索引、模板定制状态和标题骨架确认；类型尚不明确时仍可省略 `--type`，由预检兜底。
- 缺分类与自定义模板的详细说明改为命中后按需加载；预检、正式写入、自动审计、Git 治理与模板 SHA 防漂移保持不变。
- 普通 Skill 指令面由 2716 降至 2296 `o200k_base` tokens，低频异常说明不再影响每次调用。

完整改动见 [CHANGELOG.md](CHANGELOG.md) 的 `[1.19.0]` 段。

## v1.18 新增的能力

v1.18 让用户修改后的模板真正参与笔记质量控制，同时保持默认路径轻量：

- `vault-info --compact` 只报告发生变化的模板类型；默认模板不会触发模板契约读取，也不会把模板正文加入模型上下文。
- 自定义模板只读取当前笔记类型的一份契约；标题下的自然语言说明会被执行，标题、列表、表格、标签式字段和示例会作为结构与深度要求保留。
- `create-note --expect-template-sha256` 会在预检和正式写入前拒绝已经变化的模板，避免按陈旧说明创建笔记或修改索引。
- 未知模板占位符会在生成前明确报错；模板重命名支持保留为后续优化，本版不做猜测式匹配。

完整改动见 [CHANGELOG.md](CHANGELOG.md) 的 `[1.18.0]` 段。

## v1.17 新增的能力

v1.17 在不削减治理和质量步骤的前提下压缩普通沉淀路径：

- `vault-info --compact` 省略普通创建不需要的目录笔记文件名数组，保留索引模式、所有权和 Vault 有效性信息。
- 模板标题缺失或乱序时，一次返回期望顺序、实际顺序和首个错位点，避免逐项修复和多轮预检。
- Vault 要求 Git 时，会在抓取或深读文章来源前完成安全检查；预检、正式写入和自动审计保持不变。

完整改动见 [CHANGELOG.md](CHANGELOG.md) 的 `[1.17.0]` 段。

## v1.16 新增的能力

v1.16 为新增知识领域提供受控的分类初始化能力，同时保持已有分类的普通沉淀路径不变：

- 模型发现明确的新主题时，先建议完整分类路径并提醒用户可以自行命名；未经确认不会创建目录。
- 是否把新路由写入 Vault 的 `AGENTS.md` 是独立选择；拒绝时仍可创建一次性分类，后续再次遇到该主题会重新询问。
- `create-category` 使用结构化预检和 `--confirmed` 写入门，按 Vault 当前模式创建 Folder Index、Dataview 或静态索引并执行结构审计。
- README 等 Vault 本地结构治理仍然生效；已有受管分类不会增加提示、helper 调用或语义模型成本。

完整改动见 [CHANGELOG.md](CHANGELOG.md) 的 `[1.16.0]` 段。

## v1.15 新增的能力

v1.15 提升本地链接建议的精度，不引入语义模型或外部依赖：

- 中文标题使用连续双字词匹配，具体标签和标题关联能够进入候选。
- 高频标签、结构性标签和宽泛的 `java` 标签不再主导排序，同类型只作为辅助信号。
- 低于置信阈值的弱关联直接省略，兄弟目录只有名称相关时才进入有限候选范围。
- 链接建议继续只读、由人确认，并将每个候选的正文读取从两次降为一次。
- v1.15.1 会直接报告输入 YAML 的准确行列，不再静默回退；同时过滤“详解/指南/教程”等泛化标题词。

完整改动见 [CHANGELOG.md](CHANGELOG.md) 的 `[1.15.1]` 段。

## v1.14 新增的能力

v1.14 在不减少质量检查的前提下压缩预览响应，并补强写入边界：

- `create-note --preflight-json` 返回最终 frontmatter、目标路径、正文 SHA-256/大小和完整单笔记校验，但不重复回显正文，也不修改 Vault。
- 预检与写后 audit 共用同一套规则；正式写入仍使用 `--apply --compact-json`，保留明确的两阶段控制点。
- 相对 `--content-file` 读取经过验证的 Vault 路径；并发同名创建使用排他写入与后缀重试，JSON 错误和模板正文警告也已修正。
- 原有完整 `--json` dry-run、`--apply --json` 和 v1.13 compact apply 契约保持兼容。

完整改动见 [CHANGELOG.md](CHANGELOG.md) 的 `[1.14.1]` 段。详细用法在 `core/references/note-creation.md` 里按需加载。

## v1.13 新增的能力

v1.13 减少长笔记在正式写入阶段的重复回显，同时保持机器可读的审计结果：

- `create-note --apply --compact-json` 返回落盘路径、audit 和链接建议，但不重复返回完整 `rendered` 正文。
- dry-run 继续使用完整 `--json` 预览；原有 `--apply --json` 契约保持不变，已有调用方无需迁移。
- canonical reference、所有平台适配产物和标准 Skill manifest 已同步更新。

完整改动见 [CHANGELOG.md](CHANGELOG.md) 的 `[1.13.0]` 段。详细用法在 `core/references/note-creation.md` 里按需加载。

## v1.12 新增的能力

v1.12 把完整标准 Skill 正式接入 WorkBuddy，并让安装状态可以独立诊断：

- Bash 与 PowerShell 会把同一份完整 payload 安装到 `~/.workbuddy/skills/obsidian-knowledge-base/`；升级替换旧 symlink 入口但不修改其 clone 目标，卸载保留同级其他 Skill。
- 标准 Skill 带确定性的 `manifest.json`；只读 `doctor --json` 会核对 payload、runtime、依赖和关键 resources，不执行修复或删除。
- `run_helper.py <helper> --help` 现在直接转发到所有 helper；坏掉的 `runtime.json` 也不会阻止 doctor 给出诊断。
- `create-note` 的 stdin/content-file frontmatter 合并与优先级已进入 CLI help、reference 和回归测试，`source`、`related` 不再需要靠猜参数发现。
- 安装产品测试会在删除 release 源目录后，从 WorkBuddy 副本运行 doctor 与核心 helper；发布前还要完成真实 WorkBuddy 前向任务和 P0 审计。

v1.12 的完整改动见 [CHANGELOG.md](CHANGELOG.md) 的 `[1.12.1]` 段。

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

### 方式三：只拿标准 Skill 目录或平台兼容文件

如果你已经有知识库结构和模板，可以只复制对应平台的指令文件：

| 你用的 AI 工具 | 需要的文件 | 直接链接 |
|--------------|-----------|---------|
| Agent Skills / Codex / QoderWork | 完整的 `skills/obsidian-knowledge-base/` | [Skill 入口](skills/obsidian-knowledge-base/SKILL.md) |
| Claude Code | `platforms/claude-code/CLAUDE.md` | [CLAUDE.md](platforms/claude-code/CLAUDE.md) |
| OpenAI Codex（兼容入口） | `platforms/codex/AGENTS.md` | [AGENTS.md](platforms/codex/AGENTS.md) |
| Cursor | `platforms/cursor/obsidian-kb.mdc` | [obsidian-kb.mdc](platforms/cursor/obsidian-kb.mdc) |

兼容文件只提供入口规则；references、assets 和 helpers 来自安装器创建的 `~/.obsidian-kb-skill/skill/`。**单独复制一个指令文件既不是完整标准 Skill，也不会初始化 Vault**。首次使用和跨平台兼容入口都建议运行安装脚本。

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

这个项目以 **Markdown 行为指令**为规则层，并附带本地 Python helper 处理容易出错的确定性步骤。它不调用云 API、不运行常驻服务；规则告诉 AI 智能体如何工作，脚本负责路径校验、模板脚手架、写入、索引检测和审计：

1. 你的知识库在哪里（路径）
2. 知识库长什么样（文件夹结构）
3. 每种笔记应该怎么写（模板 + YAML frontmatter）
4. 什么内容应该放哪个文件夹（路由规则）
5. 怎么给笔记打标签（标签体系）
6. 怎么识别并遵守 Folder Index、Dataview 或静态索引策略

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
    │ 标准 SKILL.md │ │ CLAUDE.md   │ │  AGENTS.md    │ ...
    │Codex/QoderWork│ │(Claude Code)│ │ (兼容入口)      │
    └──────────────┘ └─────────────┘ └───────────────┘
```

核心指令文件 `core/OBSIDIAN_KB.md` 是「唯一真相来源」。它是一个极小的「门禁」（源文件 **21 行**，生成的 `SKILL.md` **25 行**），第一条规则是显眼的 **DO NOT auto-save**，并指向 `core/references/*` 里的完整工作流；agent 加载技能几乎零 token 成本，只有真正准备落盘时才会按指针去读对应 references。平台无关的标准入口是 `skills/obsidian-knowledge-base/SKILL.md`；`platforms/*` 保留各平台兼容产物。所有产物（含每个平台自带的 `references/`）都由 `build.py` 生成。

### 为什么不需要插件或 API

Obsidian 知识库的底层就是一个**装满 .md 文件的文件夹**。没有数据库，没有私有格式。AI 智能体天然就擅长读写文件和操作文件夹。所以：

- **创建笔记** = 在指定路径写一个 .md 文件
- **处理索引** = 插件接管时不修改；仅在静态模式下追加链接
- **关联笔记** = 在内容里插入 `[[filename|显示文本]]`
- **结构化元数据** = 在文件头部写 YAML frontmatter

运行时只做本地文件操作。规则层没有服务依赖；helper 需要 Python 3.11+ 和 PyYAML，安装器会把缺失的 PyYAML 放进 Skill 私有目录。知识库内容不会发送到云端。

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
  7. 检测索引策略 → Folder Index / Dataview 模式不修改，静态模式才追加链接
  8. 回复你：「已保存到 30-Insights/2026-06-10 微服务架构洞察.md」
```

## 支持的平台

| 平台 | 配置文件 | 安装位置 |
|------|---------|---------|
| **QoderWork / Qoder CLI** | `SKILL.md` | `~/.qoderwork/skills/obsidian-knowledge-base/` |
| **Claude Code** | `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| **OpenAI Codex** | 标准 `SKILL.md` | `~/.agents/skills/obsidian-knowledge-base/` |
| **WorkBuddy** | 标准 `SKILL.md` | `~/.workbuddy/skills/obsidian-knowledge-base/` |
| **Cursor** | `obsidian-kb.mdc` | `~/.cursor/rules/obsidian-kb.mdc` |

标准 Skill 与平台兼容产物包含**完全一致的核心指令**。注意：`~/.agents/skills` 是 Codex 用户级发现路径，不代表所有 Agent 都会自动扫描该目录。

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
- 复制 8 个笔记模板到你的知识库
- 根据 Folder Index 配置创建目录同名索引，未使用插件时创建 `INDEX.md` 导航文件
- 将知识库路径写入 `~/.obsidian-kb-config`（运行时配置）
- 首次创建全局 `~/.obsidian-kb-settings.json`；`backup.keep_per_note` 默认是 `1`，可配置为 1–1000
- 将完整标准 Skill 载荷安装到对应 AI 平台的约定位置
- 配置私有 helper runtime，并从中立目录运行 `vault-info` 做安装后验收

默认会安装所有平台入口。其中 Codex、QoderWork 和 WorkBuddy 使用同一
标准 Skill 的完整副本；WorkBuddy 的位置是
`~/.workbuddy/skills/obsidian-knowledge-base`。Claude Code 和 Cursor 使用各自兼容文件。

可随时从任意工作目录运行只读诊断：

```bash
python ~/.workbuddy/skills/obsidian-knowledge-base/scripts/run_helper.py doctor --json
```

### 4. 用 Obsidian 打开

在 Obsidian 中打开你的知识库文件夹，你会看到文件夹结构、模板和索引页都已就绪。

### 5. 开始沉淀

对你的 AI 助手说：

- 「把系统设计的讨论沉淀到知识库」
- 「记录一下 Q2 规划会议」
- 「剪藏这篇文章：https://example.com/article」
- 「创建一个仪表盘重构的项目笔记」

### 手动安装（不用安装脚本）

标准 Skill 不再是单个 `SKILL.md`，还包含按需 references、helper code 和模板 assets。最安全的手动方式是复制完整目录；Python 环境需自行保证能导入 PyYAML：

```bash
# 1. 创建配置文件，写入知识库路径
echo "D:\MyKnowledgeBase" > ~/.obsidian-kb-config

# 2. 复制完整标准 Skill 目录到约定位置，并移除构建用 header.md
# QoderWork:
cp -R skills/obsidian-knowledge-base ~/.qoderwork/skills/
rm ~/.qoderwork/skills/obsidian-knowledge-base/header.md

# OpenAI Codex:
cp -R skills/obsidian-knowledge-base ~/.agents/skills/
rm ~/.agents/skills/obsidian-knowledge-base/header.md

# Claude Code：
# 为避免覆盖已有 ~/.claude/CLAUDE.md，建议使用安装脚本的 marker 安装方式。
./install.sh --platforms claude-code

# Cursor:
cp platforms/cursor/obsidian-kb.mdc ~/.cursor/rules/obsidian-kb.mdc

# 3. 首次填充模板（不会覆盖已有模板）
python ~/.agents/skills/obsidian-knowledge-base/scripts/run_helper.py \
  scaffold-templates /你的知识库路径 --apply
```

## 知识库结构

```
YourVault/
├── 00-Inbox/          收件箱 —— 原生 Folder Index 使用 00-Inbox.md
├── 10-Work/           工作 —— 会议记录、工作文档、团队讨论
├── 15-Daily/          日记 —— 每日记录、晨间规划、复盘
├── 20-Learning/       学习 —— 文章、笔记、网页剪藏、课程资料
├── 30-Insights/       洞察 —— 分析、想法、AI 生成的洞察
├── 40-Projects/       项目 —— 活跃项目的上下文和进展日志
├── 50-People/         人物 —— 联系人、团队成员、互动记录
├── 90-Archive/        归档 —— 已完成或不活跃的内容
├── Templates/         8 个预置笔记模板
├── Attachments/       图片和文件附件
└── INDEX.md           根目录主导航页（非根目录使用目录同名索引）
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
| **对话摘要** | 沉淀 AI 对话摘要 | 背景、已确认结论、推翻或修正的想法、后续任务 |

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

# 只装 WorkBuddy
./install.sh --platforms workbuddy

# 只装 Cursor
.\install.ps1 -Platforms "cursor"
```

### 选择模板语言

安装器默认使用中文模板，也可以显式选择英文：

```bash
./install.sh --locale zh-CN
./install.sh --locale en
```

Windows PowerShell 使用 `-Locale zh-CN` 或 `-Locale en`。已有模板不会被覆盖；切换语言时需要同时使用 `--force` / `-Force`。

### 升级 Skill 和模板

重新运行安装脚本会幂等更新 Codex/QoderWork/WorkBuddy Skill。已有模板默认不会被覆盖；使用 `--force` 强制更新模板，并替换 Claude Code 文件中 marker 包裹的 skill 块：

```bash
# macOS / Linux
./install.sh --force

# Windows
.\install.ps1 -Force
```

> Claude Code 仍使用 marker block。升级不会主动删除旧版留在 `~/AGENTS.md` 的 marker block；卸载时会安全清理它。

### 卸载

```bash
# macOS / Linux
./install.sh --uninstall

# Windows
.\install.ps1 -Uninstall
```

卸载会移除 Codex/QoderWork Skill、仅移除 WorkBuddy 自己的 `obsidian-knowledge-base` 目录、Cursor 规则、私有 runtime，并且**自动从 `CLAUDE.md` / 旧版 `AGENTS.md` 中删除 marker block**。WorkBuddy 和其他平台的同级 Skill、旧 symlink 指向的 Git checkout、Obsidian Vault、笔记、`~/.obsidian-kb-config` 和 `~/.obsidian-kb-settings.json` 默认保留；升级和默认卸载都会保留用户的备份数量配置。需要同时清除这两份配置时使用 `./install.sh --uninstall --purge-config` 或 `.\install.ps1 -Uninstall -PurgeConfig`。

## 分享给别人

这个 Skill 就是设计来分享的。分享给别人时：

1. 把整个 `obsidian-kb-skill/` 文件夹发给对方（或指向这个仓库）
2. **不要**包含你的 `.env` 文件（已在 `.gitignore` 中排除）
3. 对方复制 `.env.example` 为 `.env`，填自己的知识库路径，运行安装脚本

## 自定义

**添加模板：** 在知识库的 `Templates/` 文件夹中创建新的 `.md` 文件，使用相同的 YAML frontmatter 格式。

**添加文件夹：** 创建新的编号文件夹（如 `60-Research/`）。Folder Index 原生模式会创建 `60-Research/60-Research.md`；未使用插件时才使用 `INDEX.md` fallback。

**修改标签：** 个人知识库优先在 Vault 的 `AGENTS.md` 中维护标签规范；修改项目默认值时编辑 `core/OBSIDIAN_KB.md`，然后运行 `python build.py`。

**修改路由：** 个人知识库优先修改 Vault 的 `AGENTS.md` 路由表；只有希望改变所有新安装的默认行为时，才修改 `core/OBSIDIAN_KB.md`。

## 项目结构

```
obsidian-kb-skill/
├── .python-version             默认开发解释器：Python 3.14.6
├── uv.lock                     可复现依赖锁文件
├── .env.example                配置模板（提交到 git）
├── .env                        你的本地配置（gitignored）
├── .gitignore
├── build.py                    生成脚本（核心 + header → 5 个产物）
├── core/
│   ├── OBSIDIAN_KB.md          「门禁」（源 21 行 / 生成 25 行）：显眼的 DO NOT auto-save + references/ 指针
│   ├── references/             完整工作流规范（懒加载：agent 准备落盘时才读）
│   │   ├── conversation-digest.md
│   │   ├── git.md
│   │   ├── note-creation.md    完整创建流程与 installed runner 用法
│   │   ├── rules-and-errors.md
│   │   ├── task-memory.md
│   │   ├── update-note.md
│   │   └── yaml-standards.md
│   └── templates/              8 个默认中文模板（含对话摘要）+ en/ 英文模板
├── obsidian_kb_skill/
│   └── scripts/                8 个可打包 CLI、路径安全层与 wheel resources
├── tests/                      build、安装器、路径安全、CLI、wheel 与真实运行测试
├── skills/
│   └── obsidian-knowledge-base/
│       ├── header.md           标准 Agent Skill 头部
│       ├── agents/             Codex UI 元数据
│       ├── references/         懒加载 references（由 build.py 复制）
│       ├── scripts/            launcher + bundled helper package
│       ├── assets/templates/   中英文模板 assets
│       └── SKILL.md            平台无关的标准生成入口
├── platforms/
│   ├── qoderwork/
│   │   ├── references/
│   │   └── SKILL.md            标准 Skill 的兼容镜像
│   ├── claude-code/
│   │   ├── header.md
│   │   ├── references/
│   │   └── CLAUDE.md           生成产物
│   ├── codex/
│   │   ├── header.md
│   │   ├── references/
│   │   └── AGENTS.md           生成产物
│   └── cursor/
│       ├── header.md
│       ├── references/
│       └── obsidian-kb.mdc     生成产物
├── install.sh                  macOS / Linux 安装脚本
├── install.ps1                 Windows 安装脚本
├── CHANGELOG.md
└── README.md
```

## 修改 Skill / 贡献代码

标准 Skill 和四个平台兼容文件由 `build.py` 从单一源头生成。**不要直接编辑生成的 `SKILL.md`、`CLAUDE.md`、`AGENTS.md` 或 `.mdc` 文件**。

项目默认使用 Python 3.14.6，最低支持 Python 3.11。推荐使用
[uv](https://docs.astral.sh/uv/) 创建和同步环境：

```bash
# 1. 按 uv.lock 创建 Python 3.14.6 的 .venv
uv sync --locked --extra dev

# 2. 修改通用规则
$EDITOR core/OBSIDIAN_KB.md

# 3. 或修改标准 Skill 头部（YAML frontmatter / trigger 描述）
$EDITOR skills/obsidian-knowledge-base/header.md

# 4. 重新生成并校验五个产物
uv run --no-sync python build.py
uv run --no-sync python build.py --check

# 5. 运行测试
uv run --no-sync python -m pytest
```

没有 uv 时可以使用标准 venv，但必须先升级安装工具：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
python -m pytest
```

CI 使用同一 lockfile，分别在 Python 3.11 和 3.14 上运行构建检查与测试。

安装 `.[dev]` 或 wheel 后，9 个业务 helper 以控制台命令形式提供，另有安装诊断 `doctor`。通过安装脚本部署的标准 Skill 则使用 `<skill-root>/scripts/run_helper.py`；两种入口调用同一套 Python 实现：

```bash
obsidian-audit-vault        /你的知识库路径 --strict
obsidian-process-inbox      /你的知识库路径 --apply
obsidian-suggest-links      /你的知识库路径 --note 30-Insights/某笔记.md
obsidian-create-category   /你的知识库路径 --folder 20-Learning/Rust --preflight-json
obsidian-create-note        /你的知识库路径 --type insight-note --title "短标题" --content-file 正文.md --apply
obsidian-update-note        /你的知识库路径 --note Tasks/某任务/TASK.md --step "..." --by Codex --log "完成 X，交接给 WorkBuddy" --apply
obsidian-vault-info         /你的知识库路径 --json
obsidian-detect-index       /你的知识库路径 --folder 30-Insights --json
obsidian-scaffold-templates /你的知识库路径 --apply
```

任何脚本加 `--json` 都输出机器可读的 JSON 文档（schema 见各脚本的 `--help`），方便 agent / 其他工具直接消费而无需解析人类文本。

### 审计现有知识库

使用只读审计器检查必填 frontmatter、笔记类型、未闭合代码块、断裂或歧义 wikilink，以及重复文件夹索引：

```bash
obsidian-audit-vault /你的知识库路径 --strict
```

无问题时退出码为 `0`；发现问题时为 `1`；路径不是 Obsidian Vault 时为 `2`。审计器不会修改任何文件。

> **审计范围与可调项**
> - 审计器会自动跳过**隐藏目录**（以 `.` 开头的文件夹）和已知工具元数据目录（`.git`、`.obsidian`、`.venv`、`.workbuddy` 等），这些目录里的文件不会被当作笔记检查。因此放在 `.workbuddy/` 下的 agent 工作记忆、`.claude/`、`.cursor/` 等 AI 工具元数据不会误报。
> - `similar-title`（相似标题）与 `orphan-note`（孤立笔记）等属于**建议性**检查，不强制、不改文件。`similar-title` 用 `difflib` 相似度阈值 **0.85** 判定（源码位于 `obsidian_kb_skill/scripts/audit_vault.py` 的 `_audit_titles`：`ratio >= 0.85`）。若你的 vault 里大量标题只是日期前缀不同、觉得噪声太吵，可把阈值上调到 `0.90` 等来降噪——代价是可能漏掉真正该合并的近重复标题。

### 归档 Inbox 收件箱

`process_inbox.py` 把 `00-Inbox/` 里的速记/待处理笔记归类、填入缺失的 `date`/`type`/`tags` 并移动到推断出的目标文件夹。默认只输出计划，不改动任何文件：

```bash
obsidian-process-inbox /你的知识库路径 --plan     # 只读预览
obsidian-process-inbox /你的知识库路径 --apply    # 执行归档（绝不覆盖已存在文件）
```

目标文件夹由笔记 `type` 或正文关键词推断（与 `core/OBSIDIAN_KB.md` 的路由表一致）；当 Folder Index 插件未启用时，会向目标文件夹的静态 `INDEX.md` 追加一条链接。

### 建议链接

`suggest_links.py` 针对单篇笔记，在受限范围内（笔记所在文件夹 + 最多 2 个兄弟文件夹）按共享标签、相同类型、标题词重叠打分，只输出候选与理由，永不写入文件：

```bash
obsidian-suggest-links /你的知识库路径 --note 30-Insights/某笔记.md --top-n 10
```

人审后自行决定是否插入，避免自动改动知识库。

### 创建笔记（无原生写工具时）

`create-note` helper 是**约束型笔记创建器**：当运行环境没有原生写文件工具（部分纯 CLI 智能体）时，调用它而非自己临时写一段 Python/Shell 脚本来做文件 I/O。默认只打印将要写入的路径与内容（dry-run），加 `--apply` 才真正落盘；遇到同名文件会自动加 `-2`/`-3` 后缀，**绝不覆盖**。

```bash
obsidian-create-note /你的知识库路径 \
    --type insight-note --title "短标题" \
    --content-file 正文.md --preflight-json
obsidian-create-note /你的知识库路径 \
    --type insight-note --title "短标题" \
    --content-file 正文.md --apply --compact-json
```

- `--type`：笔记类型（与路由表一致）；`--title` 即文件名。
- `--content-file`：正文 `.md` 路径（若里面已含 frontmatter，会被合并，显式值优先）；也可用 `--stdin` 从标准输入读取正文。
- `--tags`：覆盖类型默认标签；`--date`：覆盖日期（默认今天）；`--folder`：覆盖路由到的目标文件夹。
- `--preflight-json`：返回最终 frontmatter、路径、正文哈希/大小和写前校验，不回显正文、不写文件；`--json`：完整 dry-run 或兼容写入 JSON，包含 `rendered` 正文；`--apply --compact-json`：省略 `rendered`、但保留路径、audit 和链接建议的正式写入结果。
- 写入后会按当前索引策略更新静态 `INDEX.md`（Folder Index / Dataview 管理的列表不会被改动）。
- 这与 `core/OBSIDIAN_KB.md` 的 Step 7「工具选择」约定配套：智能体优先用原生写工具，否则用本脚本，而不是临时造脚本。

### 任务记忆（多 agent 长任务切换）— 默认关，按需开启

`core/references/task-memory.md` 里的 **Task Memory Workflow** 解决多 agent 接力时的记忆断层（出棒更新 `Tasks/<slug>/TASK.md`、入棒先读）。它**默认关闭**：全局 `OBSIDIAN_KB_TASK_MEMORY=off`（默认）、单任务靠 `task-memory: enabled` 字段开启，会话里说「开启任务记忆 / handoff」即激活。

> 为省 token，**所有完整工作流（含本段）都不内联在主文件**：`core/OBSIDIAN_KB.md` 只是一个 **21 行**的「门禁」——显眼的 `DO NOT auto-save` + 指向 `core/references/*` 的指针。agent 加载技能几乎零 token 成本；只有真正准备落盘时，才按指针去读对应 references 文件。

`obsidian-update-note` 是配套的约束型更新器（写前备份、只改 frontmatter + 追加带时间戳的 Log、绝不覆盖散文、Log 截断到 30 条、默认 dry-run）。完整用法见 `core/references/task-memory.md`。

## 设计原则

- **Markdown 数据层。** 没有数据库、没有云 API、没有厂商锁定；知识本身始终是纯文本文件。
- **智能体无关。** 核心逻辑与平台无关。每个 AI 工具只得到一个薄薄的适配器文件。
- **约定优于配置。** 文件夹结构、命名、标签、模板都有合理的默认值。只自定义你需要的部分。
- **安装后自包含。** 标准 Skill 带 references、scripts 和 assets；helper 的 Python/PyYAML 边界由安装器显式配置和验收。
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

- **[Folder Index](https://github.com/turulix/obsidian-folder-index)** —— 希望手动创建文件夹或笔记时自动生成目录、并在图谱中显示完整文件夹层级时推荐。请启用 Graph View 覆盖，并使用插件原生的目录同名索引（关闭自定义索引文件名）；Folder Index 1.0.30 的图谱代码无法用统一的 `INDEX.md` 连接父子目录。根索引仍可配置为 `INDEX.md`。
- **[Dataview](https://github.com/blacksmithgu/obsidian-dataview)** —— 用于按属性生成统计表、仪表盘和动态视图。未使用 Folder Index 时，安装器生成的 `INDEX.md` 查询可以自动列出笔记。Dataview 渲染出的链接不作为持久语义关系，因此相关概念仍应使用正文或 `related` 属性中的 `[[wikilink]]`。
- **[Calendar](https://github.com/liamcain/obsidian-calendar-plugin)** —— 日历视图浏览 `15-Daily/` 下的日记
- **[Kanban](https://github.com/mgmeyers/obsidian-kanban)** —— 读取知识库的项目看板
- **[Templater](https://github.com/SilentVoid13/Templater)** —— 高级模板处理，用于手动创建笔记

## 许可证

MIT —— 自由使用、修改、分享。
