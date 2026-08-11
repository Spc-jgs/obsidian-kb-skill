# Project Revival Radar Design

## 动机

当前 Skill 擅长把知识写进去、按主题找出来、检查结构是否健康，但它仍然需要用户先想起
某个项目。真实知识库更常见的失败不是“搜不到”，而是一个仍有价值的项目逐渐离开注意力，
直到未完成事项、阻塞原因和已经做过的决定都被遗忘。

我希望补上一种不同于搜索的入口：用户不提供主题，只问“我现在有哪些项目值得捡起来？”。
Project Revival Radar 将长期未活动或明确受阻的项目整理成一个短小、可解释、完全只读的
复盘队列。它不是任务管理器，也不修改项目状态；它只负责把已存在的事实重新送回人的视野。

## 产品边界

新增 `review-projects` helper 和 `obsidian-review-projects` CLI。它只扫描
`type: project-note` 的 Markdown 笔记，并返回：

- 项目路径、标题和状态；
- 最近活动日期及距 `--as-of` 的天数；
- 未完成 checkbox 数量；
- 最先可执行的下一步；
- 进入队列的明确原因。

默认以 30 天作为失温阈值，最多返回 10 项。`--as-of YYYY-MM-DD` 是显式输入，既让测试
可复现，也允许 Agent 正确处理用户所在时区。`--scope` 只能是 Vault 内目录。

以下内容不在本次范围内：

- 不写入 `reviewed_at`、`next_review` 或任何生命周期字段；
- 不自动恢复、归档、关闭或重排项目；
- 不联网、不调用模型、不创建索引或缓存；
- 不推断优先级、商业价值、负责人或截止日期；
- 不把普通笔记中的 `TODO` 猜成项目。

## 候选与排序规则

项目的活动日期依次取合法的 `updated`、`date`。完成态
`done/completed/closed/archived/cancelled/canceled` 永不进入队列。

其余项目满足任一条件时成为候选：

1. `status: blocked`，无论距上次更新多久；
2. 没有可用活动日期，需要人工确认它是否仍然活跃；
3. 距活动日期不少于 `--stale-days`。

排序不制造看似精确的综合分数，而使用稳定的业务元组：

1. 受阻项目；
2. 缺失活动日期的项目；
3. 有未完成事项的失温项目；
4. 其他失温项目；
5. 同组内按失温天数降序、未完成事项数降序、相对路径升序。

每项以 `blocked`、`missing-activity-date`、`stale:N-days`、
`open-tasks:N` 等机器稳定 reason 表达为什么出现。reason 是观察结果，不是可信度。

## 下一步提取

只读取可见 Markdown：HTML 注释和 fenced code 中伪造的 checkbox 不计数。优先从
`下一步行动`、`Next Actions` 或 `Next Steps` 章节取第一条未完成 checkbox；若标准章节
为空，再退回整篇笔记的第一条未完成 checkbox。输出移除 checkbox 标记并限制为 200 个
字符，避免一次复盘把整篇笔记送入上下文。

## JSON 与失败契约

成功响应使用单一 JSON 文档：

```json
{
  "schema_version": "1.0",
  "ok": true,
  "command": "review-projects",
  "read_only": true,
  "as_of": "2026-08-10",
  "stale_days": 30,
  "summary": {"projects": 4, "candidates": 2, "returned": 2},
  "items": [],
  "issues": []
}
```

无候选是成功空结果。非法 Vault、越界 scope、非法参数日期、超界阈值和超界 `top-k`
返回稳定 error code；共享路径错误沿用安全退出码 3。单篇笔记 frontmatter 损坏或活动日期
晚于 `--as-of` 时跳过该文件并加入有界 `issues`，不让一个坏文件阻断整个复盘。CLI 运行
前后不得改变 Vault 的文件集合、内容或修改时间。

## Skill 交互

当用户问“有哪些项目搁置了”“该复盘什么”“帮我恢复一个旧项目”时，Retrieval Skill
先运行 `review-projects --json`。Agent 展示短队列；只有用户选中某项后，才读取那篇项目
笔记及最多三篇直接相关的 Digest/会议记录来恢复上下文。任何更新仍需切换到写入 Skill，
重新取得独立授权。

## TDD 与验收

实现顺序严格由失败测试驱动：

1. 候选边界、日期优先级、完成态排除和稳定排序的单元测试；
2. checkbox 可见性、章节优先和长度上限测试；
3. JSON schema、错误码、scope containment 和零写入 CLI 测试；
4. build 生成物、retrieval bundle、wheel entry point 和文档契约测试；
5. 定向测试转绿后运行完整 pytest、`build.py --check`、`uv lock --check` 和 diff 检查。

成功标准不是“列出旧文件”，而是返回一个小而可信的复盘入口：每个项目都能解释为何出现、
指出已有的下一步，同时不替用户做任何生命周期决定。
