# Obsidian KB Skill 开发路线图（评估与修正）

## 背景

就 `obsidian-kb-skill`（v1.7.0）的后续方向，用户先后征求了两轮外部评估：

1. 一轮较早的 WorkBuddy 评价，认为该 skill 在已有 `AGENTS.md` 的 vault 里偏"鸡肋"；
2. 一轮 GPT 的"Skill 开发"建议，提出从"规则包"升级到"能力包"、补 6 个方向。

本仓库（WorkBuddy 侧）对 GPT 建议做了**基于代码的核对**，发现初版 GPT 评估严重低估仓库现状；GPT 据此自纠正。本文档记录：

- 初版评估的事实错误（已修正）；
- 修正后的准确定位；
- 相对修正版的进一步架构校准；
- 后续落地路线图（Phase A–D）与明确不做的项。

---

## 一、初版评估的事实错误（已修正）

### 1.1 Vault Auditor 已存在，不是"从零待办"

- 证据：`scripts/audit_vault.py`（418 行）；`README.md` 第 444–452 行已将其文档化为标准功能：
  `python scripts/audit_vault.py /你的知识库路径 --strict`
- 已实现能力（且比 GPT 初版清单更全）：
  - frontmatter 解析与合法性；
  - `type` / `date` / `tags` 必填检查；
  - tag 数量与 kebab-case 检查（`TAG_RE`）；
  - wikilink 断裂 / 歧义检查；
  - 未闭合代码块检查（`unclosed-fence`）；
  - Folder Index 配置读取；
  - **Folder Index 图谱兼容检查**（`misnamed-folder-index` / `broken-folder-graph-chain` / `graph-incompatible-index-config`）—— GPT 初版未提及且是最难的部分；
  - 重复 folder index 检查。
- 有测试锁定：`tests/test_audit_vault.py` 第 7 行 `from scripts.audit_vault import audit_vault`，覆盖缺失 frontmatter/date/type/tags、folder-index 不要求 date、folder-index-content 缺失/重复、未闭合代码块、broken/ambiguous wikilink、duplicate folder index、attachment/heading/alias 链接解析、invalid/too-many tags、Folder Index 自定义 `INDEX.md` 图谱兼容、native folder-named index 链路等。

### 1.2 项目不是"纯 Markdown 指令文件"

- 运行时入口（`skills/obsidian-knowledge-base/SKILL.md`）主要是 Markdown 指令文件；
- 但仓库本体已有 Python 工具链：`build.py`、`install.sh` / `install.ps1`、`scripts/audit_vault.py` + `pytest`；
- `pyproject.toml`：name=`obsidian-kb-skill`，依赖 `PyYAML`，dev 依赖 `pytest`，`testpaths=["tests"]`。

准确说法：**标准 Skill 入口是 Markdown 指令文件，但仓库本体已经开始具备可执行治理能力。**

### 1.3 V1.8 治理已在做

- `docs/superpowers/post-write-governance-design.md`（2026-07-08）已设计落地：写后验收、Folder Index 结构检查、Web Clip「理解与启发」标准（区分原文观点与 Agent 推论）、有界搜索、安全 Git 后处理。
- 这意味着 GPT 当"未来方向"写的 V1.8 / V1.9 内容，仓库昨天已在推进。

---

## 二、修正后的定位

不再适合的评价：

> "还只是一个规则包，下一步才开始做工具。"

准确评价：

> **它已从规则包进入"规则 + 安装器 + 审计器 + 测试"阶段，但还没完全进入知识库管家阶段。**

建议定位语：

> **Obsidian AI Agent Knowledge Base Kit：跨 Agent 规则层 + 安装器 + 审计器 + 后续治理工具。**

---

## 三、相对 GPT 修正版的进一步架构校准

GPT 修正版方向已对，但两项建议收一下，避免脚本膨胀：

### 3.1 P2（Tag Taxonomy Cleaner）与 Content Quality Checklist 应折叠进 `audit_vault.py`

- 二者本质都是**确定性 vault 扫描**：近重复标签、低频标签、大小写/单复数/下划线冲突，以及 Web Clip 必填字段 / "理解与启发"静态检查。
- 它们与现有 `invalid-tag` / `too-many-tags` 是同一类检查；若独立成 `tag_report.py` / `quality_report.py`，会重复扫描逻辑与 finding 格式，违背"一核多适配器"的整洁哲学。
- 应作为 `audit_vault.py` 的**新 check 类别**，复用现有 `Finding` 数据类、`--strict` 退出码与 pytest 框架。

### 3.2 Conversation Digest 更像是工作流而非 Python 工具

- 它的输入是对话文本、不扫描 vault、不依赖 vault 状态，本质是"对话 → 笔记"的转换。
- 按 Markdown-first 哲学，最自然的 first implementation 是：
  - `core/templates/digest-note.md` 新模板；
  - `core/OBSIDIAN_KB.md` 加 Digest 工作流与触发词（如"沉淀这段对话"）+ 路由到 `30-Insights/` 或 `40-Projects/`；
  - 重跑 `build.py` 同步 5 产物。
- Python 版（`scripts/conversation_digest.py`）仅在你需**批量 / 命令行**处理历史对话时才需要。

### 3.3 真正独立成脚本的只有三个

| 脚本 | 理由 |
|---|---|
| `scripts/process_inbox.py` | 会改文件，需 dry-run（`--plan` / `--apply`） |
| `scripts/suggest_links.py` | 低频重度匹配，补捕获时有界搜索的短板 |
| `scripts/conversation_digest.py` | 仅批量场景需要；模板+工作流优先 |

---

## 四、路线图

### Phase A — Auditor 增量增强（扩展 `audit_vault.py`）

新增确定性 check 类别，按难度递增：

1. `{{date}}` / 模板占位符残留（正则，最简单，用于跑通贡献节奏）；
2. `related` 字段合法性（必须是合法 wikilink、去重、无裸链接）；
3. Web Clip 必填字段（`source` / `author` / `published` 非空）；
4. 空模板笔记（只有 frontmatter + 标题，body 实质为空）；
5. 近重复标签（小写化、去复数 `s`、下划线→连字符后比对，输出合并建议）；
6. 重复 / 近似标题（同目录或跨库同 `stem`）；
7. 孤立笔记（不被任何 wikilink 引用、也不在任何 INDEX 导航里）。

**每项交付节奏**：新增 `_audit_xxx` 函数 + finding code + `tests/test_audit_vault.py` 用例 → 运行 `python build.py --check` → `pytest`。单独 commit。

### Phase B — Inbox Processor（独立脚本）

- `scripts/process_inbox.py /vault --plan`：默认只输出迁移计划（目标目录 / 建议 tags / 建议 related）；
- `--apply` 才移动文件；
- 用现有路由表（SKILL.md 的 Trigger Pattern→Folder）推断目标目录；
- 复用 `audit_vault.py` 的 vault 解析 / 合法性逻辑，不重写；
- 推荐 related 轻量（同目录 + 父 INDEX），不暴力全库；
- 移动后只更新静态索引，Folder Index / Dataview 不动。

### Phase C — Link Suggestor（独立脚本）

- `scripts/suggest_links.py /vault --note <path>`：只输出候选 + 理由，不写文件；
- 用标题 / tags / frontmatter / 已有 related 粗匹配；
- 扫描范围受控（目标目录 + 1–2 兄弟目录），符合成本上限哲学；
- 人审后决定，永不自动插入。

### Phase D — Conversation Digest（先 Markdown，后 CLI）

- 加 `core/templates/digest-note.md`（背景 / 已确认结论 / 推翻的想法 / 后续任务 / 关联项目 / 可继续追问）；
- 在 `core/OBSIDIAN_KB.md` 加 Digest 工作流 + 触发词 + 路由；
- 重跑 `build.py` 同步 5 产物；
- 仅批量需求出现时再做 `scripts/conversation_digest.py`。

---

## 五、明确不做

- 不从零重写 Vault Auditor；
- 不堆模板（保持现有 7 个 + 新增 1 个 digest）；
- 不默认全库扫描 / 默认 Git；
- Content Quality 只做**静态 checklist**（并进 auditor），**不做 LLM 评分器**（破坏"本地、确定性、零服务"哲学）；
- 不把目录重构成 `rules/tools/fixtures`——当前 `core+skills+platforms`（规则层）/ `scripts`（工具层）/ `tests`（测试层）已是对的结构。

---

## 六、建议起点

- **Phase A 第 1 项 `{{date}}` 残留检查**：半小时量级、零设计风险、立刻跑通"增量增强"贡献节奏（改脚本 → 加测试 → `build.py --check` → `pytest`），直接兑现"auditor 增量而非从零建设"的修正结论。
- **Phase D 模板部分**可穿插先做：纯 Markdown、立刻能在 Agent 里用"沉淀这段对话"触发，是你日常最有感的能力。

具体从哪一步开工，由用户在当前会话确定。
