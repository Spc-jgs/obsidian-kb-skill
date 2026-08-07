# 连通性信号 — 设计

目标：`obsidian-knowledge-base` 的 `audit_vault`，基于 v1.28.0。
解决 [#57]：笔记连通性没有任何信号，`orphan-note` 结构性恒为 0。

## 先说清楚这次不做什么

[#57] 列了三条可能的做法。**第 1 条不做**，理由在下面「为什么不自动推链接」。
这份设计只做第 2 条（把可达性和连通性拆开）和第 3 条（定严重度）。

## `orphan-note` 没算错

先澄清一个容易搞反的地方：`_audit_orphans` 把「目录里有 folder-index」当作该目录
下所有笔记「已被索引」，看起来像偷懒，其实是对的。

Folder Index 插件自己维护 `folder-index-content` 块并把目录内文件全部列进去，
审计还专门禁止把这个块替换成手写列表（见 `core/references/git.md` 第 5 条）。
所以**目录有索引 ⇒ 目录内笔记可达**，这个推断成立。

`orphan-note` 测的是**可达性**：这篇笔记还能不能被翻到。参考 Vault 有 22 个
folder-index 覆盖全部管理目录，所以可达性确实处处满足，报 0 条是真实的。

问题不是它算错了，是**连通性根本没人测**。可达 ≠ 连通：一篇笔记躺在索引列表里
翻得到，和它与其他笔记有没有知识关系，是两件事。

## 实测：连通性缺口有多大

参考 Vault，用 `audit_vault` 自己的链接解析（含 alias 解析），审计候选 127 篇
（已排索引笔记、`daily-note`、模板、`95-Sources`）：

| 指标 | 篇数 | 占比 |
|---|---|---|
| 零入链 | 79 | 62% |
| 零出链 | 74 | 58% |
| **完全孤立（进出都没有）** | **57** | **45%** |
| 现有 `orphan-note` 报出 | 0 | — |

### 关键发现：一大半是日报周报

把完全孤立的 57 篇按 `type` 拆开：

| type | 篇数 |
|---|---|
| `daily-report` | 30 |
| `web-clip` | 14 |
| `weekly-report` | 6 |
| `learning-note` | 4 |
| `insight-note` | 1 |
| `project-note` | 1 |
| 无 type | 1 |

**`daily-report` + `weekly-report` = 36 篇，占 63%。** 这些是流水日志，
本来就不该有链接 —— 它们不是「信息墓碑」，它们是记录。
把周期性报告排掉，剩 **21 篇**。

这一条决定了这个功能是能用还是不能用：报 57 条是刷屏，报 21 条是清单。
现有审计一次 225 条（defect 75 / hygiene 35 / informational 115），
再加 21 条 informational 是合比例的，加 107 条不是。

剩下的 21 篇里 **14 篇是 `web-clip`** —— 剪进来、再没接上任何东西。
这正是调研里排第一的那个痛点，而且是个能一眼看完的名单。

## 设计

### 新增一条 finding

| 项 | 值 |
|---|---|
| code | `disconnected-note` |
| 严重度 | `informational` |
| 判定 | 零入链 **且** 零出链 |
| 排除 | `daily-report`、`weekly-report`，外加现有候选集已排除的那些 |
| 文案 | `note has no inbound or outbound links; it is reachable through its folder index but connected to nothing` |

**只报交集，不报单边。** 零出链 74 篇、零入链 79 篇，单独任何一边都太吵，而且
含义模糊：一篇被三处引用的概念笔记没有出链，是正常的。两边都没有才是无歧义的
「这篇和知识库其余部分没有任何关系」。

单边数字有价值，但那是度量不是缺陷 —— 需要的话之后走 `vault_info`，不进审计。

### 不改 `orphan-note`

保持原样，包括它的语义和文案。它测可达性，测得对。两个 code 各管一件事。

## 为什么不自动推链接

[#57] 的第 1 条做法是「把链接候选并进那一次发现调用」，让写入方不用主动想起来
去调 `--suggest-links`。动机是对的（#50 那条原则），但**现在不能做**。

刚结案的关联度评审给出了理由：32 对人工标注全部为负，覆盖 0–74 全部分档
（见 [`2026-08-06-relatedness-scoring-design.md`](2026-08-06-relatedness-scoring-design.md)）。
现在的 `suggest_links` 阈值 `MIN_SCORE = 3` 就是参考 Vault 上的众数，
换句话说**它推出来的东西没有经过任何验证**。

把一个未经验证的推荐器从「可选、要主动调」改成「每次写入自动出现在眼前」，
等于给每篇新笔记默认配上噪音。这正是之前那批坏链接的成因 ——
四篇毫不相干的笔记都链到 `20-Learning/Backend/` 里排序第一的文件。

**顺序应该反过来：先让缺口可见，再谈自动化。** 这份设计让 21 篇孤立笔记显形，
用户自己判断该不该连、连到哪。等到有一个过得了那 32 对回归集的推荐器，
再回来讨论要不要自动推。

## 实施要点

- `_audit_orphans` 不动；新增 `_audit_connectivity`，与它并列调用。
- 出链计数复用 `_collect_references`（已含 alias 解析），不新写一套解析。
- 周期性类型收成模块级常量 `PERIODIC_TYPES = {"daily-report", "weekly-report"}`，
  和 `INDEX_TYPES` 放一起，别散在函数里。
- `FINDING_SEVERITY` 加 `"disconnected-note": "informational"`。
- `rules-and-errors.md` 的 code 清单要同步 —— 它有 AST drift-lock 测试盯着。
  `core/` 和 `obsidian_kb_skill/scripts/resources/` 两份都要，且必须走 `build.py`
  扇出，不手改生成物。

## 测试

- 零入零出 → 报 `disconnected-note`
- 只有出链 / 只有入链 → 不报
- `daily-report`、`weekly-report` 零入零出 → 不报
- 有 folder-index 的目录下，零入零出的笔记 → 报 `disconnected-note`
  **且不报** `orphan-note`（这一条锁住「可达 ≠ 连通」）
- 通过 alias 建立的入链要算数（防止退回 #57 里 alias 那个老坑）
- 严重度是 `informational`（`test_finding_severity.py` 的口径）

## 验收

在参考 Vault 上跑 `audit_vault`：`disconnected-note` 应为 21 条，
其中 14 条是 `web-clip`；`orphan-note` 仍为 0 条。

[#57]: https://github.com/Spc-jgs/obsidian-kb-skill/issues/57
