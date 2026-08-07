# 聚类词质量 — 设计

目标：`obsidian-knowledge-base` 的 `vault_info.subject_clusters()`，基于 v1.29.0。
解决 [#55]：聚类词覆盖整个目录时应该降权或剔除。

## 先说一个和 issue 不一致的结论

[#55] 提的办法是「对 `notes / direct_notes` 超过某个比例（例如 90%）的词降权或剔除」。
**实测下来，90% 阈值修不了 issue 自己举的那个案例。**

`20-Learning/AI-Agent` 里 `ai-agent` 覆盖 25/34 = **74%**，过不了 90% 的线，
剔不掉；它照样占着第 1 位。issue 想救的 `vibe-coding` 仍然被截断。

比例不是病根。下面是实测出来的病根。

## 实测：前 6 名里有 4 个是噪音

`20-Learning/AI-Agent`，34 篇，达标词 11 个，`MAX_CLUSTER_TERMS = 6` 只报前 6：

| # | 计数 | 余 | 类型 | 词 | 是什么 |
|---|---|---|---|---|---|
| 1 | 25 | 9 | tag | `ai-agent` | **就是目录名** |
| 2 | 14 | 20 | title | `ai` | **`ai-agent` 的一半** |
| 3 | 6 | 28 | title | `agent` | **`ai-agent` 的另一半** |
| 4 | 6 | 28 | title | `文章` | **通用词** |
| 5 | 5 | 29 | tag | `ai-harness` | 真候选 |
| 6 | 5 | 29 | tag | `llm` | 真候选 |
| 7 | 5 | 29 | tag | `llm-engineering` | 真候选 ← 被截断 |
| 8 | 5 | 29 | tag | `vibe-coding` | 真候选 ← 被截断 |
| 9 | 5 | 29 | title | `harness` | `ai-harness` 的一半 ← 被截断 |
| 10 | 5 | 29 | title | `企业级落地` | ← 被截断 |
| 11 | 5 | 29 | title | `掘金文` | 来源名碎片 ← 被截断 |

四个真候选里两个被挤掉了，而挤掉它们的是目录名本身、目录名的两个碎片、和一个通用词。

全库 25 个目录扫下来，19 个达标词里有 7 个覆盖 ≥90%，全部集中在
`10-Work/日报`（4 个 100%/97%）、`10-Work/周报`（3 个 100%）和
`20-Learning/Python`（`python` 89%）。

## 设计

两条规则，都在 `subject_clusters()` 里，**剔除而不是降权**。

### 规则 A：不能拆的词不是候选

一个词要成为拆分候选，**拆出去的那部分和留下的那部分都得能独立成夹**。
现在只检查了前者（`CLUSTER_MIN_NOTES`），后者没查。补上，用同一个常量：

```
剔除条件一：scanned - notes < CLUSTER_MIN_NOTES     # 余数撑不起一个目录
剔除条件二：normalize(term) == normalize(folder.name)  # 词就是目录名
```

**为什么用余数而不是比例。** issue 特别要求「明确决定」并考虑小目录 —— 余数规则
天然就是答案：它不需要新的魔法数字，直接复用已有的 `CLUSTER_MIN_NOTES`，
而且随目录大小自动缩放。7 篇的目录里覆盖 6 篇（86%）和 200 篇里覆盖 172 篇（86%）
是完全不同的两件事，比例阈值分不出来，余数分得出来。

**为什么还要条件二。** 余数规则漏掉 `ai-agent`（余 9 ≥ 5）。但在名为 `AI-Agent`
的目录下建一个 `ai-agent/` 子目录是同义反复，不管余数多少都不可执行。
这是两种不同的「不可拆」，各管各的。

**为什么剔除而不是排到最后。** 排到最后仍然占用 `MAX_CLUSTER_TERMS` 的名额，
而名额正是稀缺资源 —— 上表里被挤掉的就是真候选。一个不可执行的词占位没有价值。
空列表是合法答案：它说的是「这个目录没有可拆的子主题」，和本项目在关联笔记那里
已经确立的「零候选是答案，不是待填的空缺」是同一条原则。

### 规则 B：标题碎片不算独立主题

现有代码已经会丢掉「和某个 tag 完全同名」的标题词（`term in tags`），
但 `ai` ≠ `ai-agent`，所以碎片全都漏网。

把每个已计数 tag 按 `-` 拆开，其组成部分视为已被该 tag 代表：

```
ai-agent    → {ai, agent}
ai-harness  → {ai, harness}
```

于是 `ai`、`agent`、`harness` 三个标题词不再单独上榜。
按连字符分段而不是按子串匹配 —— 子串会误伤无关词。

## 实测效果

| 目录 | 现状 | 只加 A | 加 A + B |
|---|---|---|---|
| `20-Learning/AI-Agent` (34) | `ai-agent(25), ai(14), agent(6), 文章(6), ai-harness(5), llm(5)` | `ai(14), agent(6), 文章(6), ai-harness(5), llm(5), llm-engineering(5)` | **`文章(6), ai-harness(5), llm(5), llm-engineering(5), vibe-coding(5), 企业级落地(5)`** |
| `10-Work/日报` (31) | `daily-report(31), work(31), 日报(31), etianqu(30)` | 空 | 空 |
| `10-Work/周报` (7) | `weekly-report(7), work(7), 周报(7), etianqu(6)` | 空 | 空 |
| `30-Insights` (13) | `ai-agent(9), skill-design(6)` | `skill-design(6)` | `skill-design(6)` |
| `20-Learning/Java` (13) | `spring-boot(5)` | `spring-boot(5)` | `spring-boot(5)` |
| `20-Learning/Python` (9) | `python(8)` | 空 | 空 |

四个真候选全部浮出来。`spring-boot`（5/13，余 8）这种正当的大集群照常上报，
正是 issue 验收要求的第二条。

## 明确不做

`文章`、`掘金文`、`企业级落地` 这类通用/来源词还在榜上。它们属于
`GENERIC_TITLE_TOKENS` 的覆盖面问题，是另一条线 —— 往那个集合里加词是词表维护，
不是算法修改，混进来会让这次改动的效果说不清。单独开。

另外记一笔：`subject_clusters()` 用的还是硬编码的 `GENERIC_TAGS`（里面错误地含
`java`、缺 `people`），而 `tag_vocabulary()` 早就改用 Vault 自己的模板了
（v1.28.0）。这个不一致该收敛，但同样不在本次范围。

## 实施要点

- 只改 `subject_clusters()`，签名要多收一个目录名 —— 现在只传 `notes`。
  调用处 `finding["path"]` 就是路径，取 basename 传进去。
- 归一化复用 `note_catalog.normalize_tag_key`，不要再写一套。
- 两条规则的理由写进代码注释，issue 明确要求了。
- `subject_clusters` 在写入 Skill 和检索 Skill 是否都出现，要确认扇出。

## 测试

`tests/test_vault_info.py` 补：

- 一个词覆盖全部笔记 → 不上报，且不占用有区分度的词的名额（issue 验收一）
- 一个 60% 左右的正当大集群 → 照常上报（issue 验收二）
- 余数不足 `CLUSTER_MIN_NOTES` → 剔除（小目录路径）
- 词等于目录名但余数充足 → 仍然剔除（`ai-agent` 那一类）
- 标题词是某个 tag 的连字符组成部分 → 不单独上报
- 标题词只是某个 tag 的子串但不是组成部分 → 仍然上报（防止误伤）

## 验收

参考 Vault 上 `vault-info`：`20-Learning/AI-Agent` 的 6 个名额里至少有 4 个是
真候选标签（`ai-harness`、`llm`、`llm-engineering`、`vibe-coding`）；
`10-Work/日报` 的 `clusters` 为空。

[#55]: https://github.com/Spc-jgs/obsidian-kb-skill/issues/55
