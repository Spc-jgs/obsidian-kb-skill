# 对话上下文恢复与知识萃取设计

## 状态

- 对话确认：2026-07-29
- 开发分支：`feature/conversation-context-harvest`
- 发布状态：`Unreleased`
- 产品形态：升级现有 `conversation-digest`，新增按需加载的
  `conversation-harvest` 工作流，暂不新增笔记类型

## 目标

让一次 AI 对话可以产生两种职责明确、不会互相污染的资产：

1. **上下文资产**：未来读者快速理解目标、当前状态、决定、证据和下一步；
2. **知识候选**：识别本次对话中的问题、可复用知识、反思和设计经验，并判断
   哪些值得长期保存。

“30 秒恢复上下文”继续作为 `conversation-digest` 的首屏目标，但不再用约
250 词限制整篇笔记。知识萃取采用价值判断和候选分流，不把四个分析维度直接
实现为四个强制栏目或四篇笔记。

## 问题

### Conversation Digest 规范没有落实到实际产物

当前 lazy reference 要求 `TL;DR / Decisions / Open`，并要求在 frontmatter
和正文中重复 `decisions`、`open`。实际中英文 Digest 模板仍然使用更早的
“背景 / 已确认结论 / 推翻或修正的想法 / 后续任务”结构。

现有测试只检查 reference 中是否出现若干字符串；审计器接受
`conversation-digest` 类型，却没有独立验证：

- 是否存在可在 30 秒内扫描的恢复卡片；
- 是否记录边界、约束、证据和关键产物；
- 是否区分已验证、推断和开放状态；
- 是否给出可执行的下一步或明确说明对话已经关闭；
- 标准 Vault 模板是否仍然停留在旧结构。

### 三类意图容易互相覆盖

当前“沉淀这段对话”可能指：

- 保存一次讨论，未来恢复其结论与推理；
- 把当前长任务交给另一个 Agent 继续执行；
- 判断这次对话产生了哪些值得长期保存的知识。

如果三类意图都路由为 Digest，笔记会同时承担快照、运行状态和知识文章职责，
最终既不短，也不可靠。

## 产品边界

### Conversation Digest v2

`conversation-digest` 是一次连贯对话的**不可变快照**。它记录当时的目标、
状态、边界、决定、依据、证据、未决事项和下一步。它不持续承担活跃任务状态，
也不自动把对话改写成长期知识文章。

适用表达：

- “总结并归档这次讨论，方便以后继续”
- “保存这次架构讨论的结论和依据”
- “把这段对话做成上下文摘要”

### Task Memory

`task-memory` 是一个仍在进行中的任务的**可变当前态**。它由显式 opt-in
开启，持续维护 `status / step / decisions / constraints / artifacts / open`
和日志。

适用表达：

- “开启任务记忆”
- “把这个任务交接给另一个 Agent”
- “记录当前进度，下次从这里继续执行”

当一个活跃任务已有 `TASK.md` 时，Digest 可以链接它，但不能复制并竞争当前态。

### Conversation Harvest

`conversation-harvest` 是一个**分析与路由工作流**，不是 v1 的新笔记类型。
它审视整段对话，识别候选项，给出证据状态和未来用途，并主动丢弃低价值内容。

适用表达：

- “这次对话有哪些值得沉淀的问题和知识？”
- “复盘本次对话里的反思和好设计”
- “从这段聊天中找出以后还能复用的内容”

只要求分析时，它不写 Vault。用户同时明确要求保存时：

1. 只有一个高价值、目标类型明确的候选项：路由到现有
   `learning-note`、`insight-note`、`project-note` 或其他合适类型；
2. 有多个独立候选项：先展示候选清单并让用户选择，本轮不绕过“一次最多一篇”
   的写入边界；
3. 没有足够价值的候选项：说明原因，不为了完成动作而写一篇空洞笔记。

## Conversation Digest v2 信息结构

### Frontmatter

frontmatter 只承担身份、路由和检索，不与正文重复保存决定：

```yaml
---
date: "{{date}}"
type: conversation-digest
tags: [insight]
source: ""
project: ""
related: []
---
```

### 正文

标准中英文模板固定五个二级章节：

1. `恢复卡片 / Resume Card`
2. `边界与约束 / Scope and Constraints`
3. `决策与依据 / Decisions and Rationale`
4. `证据与产物 / Evidence and Artifacts`
5. `未决事项与下一步 / Open Questions and Next Actions`

恢复卡片必须包含非空的：

- 目标；
- 状态；
- 当前结论；
- 下一步；
- 关键产物。

它最多包含 12 个非空可见行。这个上限保护“30 秒扫描”目标，但不限制后续章节
的必要细节。

详细章节遵循以下规则：

- 用原子化事实和短段落，不复述聊天时间线；
- 决定包含必要理由；只有会阻止重复劳动时才记录被放弃方案；
- 证据说明验证命令、结果、路径、提交、日志或明确的待验证边界；
- 探索性对话允许“尚无最终决定”，但必须写清当前认识和开放问题；
- 已完成的对话允许“无下一步”，但必须明确说明关闭原因；
- 事实状态使用 `verified / inferred / open` 或等价的读者可见表达；
- 不复制活跃 Task Memory 的当前状态。

## Conversation Harvest 价值判断

### 候选维度

- **问题**：现象、上下文、原因或假设、处理、验证、状态；
- **知识**：结论、原理、适用场景、边界、例子、证据；
- **反思**：发生了什么、原做法的问题、以后具体改变什么；
- **设计**：解决的问题、核心机制、取舍、复用条件；
- **决定与开放项**：已确认结果、阻塞项和仍需验证的问题。

这些是分析视角，不是必须填满的模板章节。

### 价值门槛

候选项至少满足以下条件中的两个，才建议长期保存：

1. 未来可能再次遇到或主动搜索；
2. 重新推导的成本较高；
3. 能说明适用条件和不适用边界；
4. 有对话证据、代码、测试或结果支持；
5. 会改变未来操作、判断或设计。

每个候选项标记：

- `verified`：已经由对话中的证据验证；
- `inferred`：根据对话推导，尚非已验证事实；
- `open`：仍未解决或需要外部确认；
- `skip`：不值得保存，并说明原因。

### 必须排除

- 原始聊天记录和逐轮叙事；
- 一次性、低成本、未来不可检索的信息；
- 没有机制和适用边界的泛泛“好设计”；
- “以后更细心”一类没有具体行为变化的反思；
- 为填满栏目而生成的内容；
- 无法从当前对话追溯的第三方总结或推测。

## 确定性实现

### 新增版本化 Digest 合同

新增 `conversation_digest_contract.py`，集中定义：

- 合同版本；
- 中英文标准二级标题；
- 恢复卡片必需标签；
- 标题匹配和诊断文本。

### 审计

`audit-vault` 和候选笔记预检增加：

- `missing-conversation-digest-heading`
- `outdated-conversation-digest-template`
- `conversation-digest-missing-resume-field`
- `conversation-digest-resume-card-too-long`

结构审计不声称能证明自然语言事实正确。语义 grounding 仍由工作流自检和真实
冷启动验收承担。

### 渐进加载

始终加载的 `core/OBSIDIAN_KB.md` 只保留意图分流指针：

- 对话快照 → `conversation-digest.md`
- 对话知识复盘 → `conversation-harvest.md`
- 活跃任务交接 → `task-memory.md`

完整规则保持在一个层级的 lazy references 中，不增加普通笔记创建路径的上下文
成本。

## 验收场景

### 架构讨论

必须恢复目标、已确认决定、理由、关键约束、被放弃方案和下一步。

### Bug 排查

必须恢复现象、根因或当前假设、修复、验证证据、残留风险；失败尝试只在能防止
重复劳动时保留。

### 开放探索

没有最终决定时不能错误拒绝。Digest 明确标记状态为探索中，记录当前认识、开放
问题和下一次收敛动作。

### 活跃任务交接

必须路由到 `task-memory`，Digest 只能作为不可变讨论快照或链接，不得竞争
`TASK.md` 的当前态。

### 知识萃取

必须生成带价值判断和证据状态的候选项；低价值项进入 `skip`，多个独立候选项
不能绕过单笔记写入边界。

## 完成标准

- 中英文 Digest 模板与 reference 一致；
- 源码、wheel 资源、标准 Skill、平台适配器和 manifests 构建同步；
- 旧模板和不完整恢复卡片被稳定诊断；
- Harvest reference 能区分分析、单候选保存、多候选确认和无价值退出；
- README、文档首页、功能指南、沉淀治理指南和 CHANGELOG 同步；
- 定向测试、完整测试、`build.py --check`、`uv lock --check`、Skill Creator
  validation 和安装态 `doctor --json` 通过；
- 在隔离 Vault 中完成 Digest preflight/apply/audit smoke test；
- 不修改真实 Vault 业务笔记。
