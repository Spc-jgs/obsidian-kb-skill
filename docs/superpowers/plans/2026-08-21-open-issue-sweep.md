# 2026-08-21 Open-issue sweep

一次把剩余 open issue 走完的计划。**每项动工前先验它的前提**——本仓的复发缺陷
是「按描述判断，而不是按事物判断」（#133、#136、#93），而一个 issue 的正文正是
一份描述。今天已经有一条因此被推翻：#158 的核心主张。

## 纪律

1. 每项先跑「前提」栏的命令。前提不成立 → 写进「已推翻」，**停下来报告**，不
   顺着原计划改。
2. 结论涉及数量，附产出它的命令。
3. 新断言必须见过红：先写，或临时破坏它守的东西。
4. 两处必须一致的边界 → 同一次改动里加断言 + 登记
   `docs/superpowers/specs/2026-08-12-consistency-inventory.md`。

## 基线（2026-08-21 实测）

```bash
python3 skills/obsidian-knowledge-base/scripts/run_helper.py \
  audit-vault ~/Documents/my-knowledge-base --json
```

214 篇笔记，113 条 finding：49 defect / 39 hygiene / 25 informational。

## 已推翻的假设

### #158 的核心主张（2026-08-21）

issue 说「写着『原文未标明』的 web-clip 被报 `web-clip-missing-published`」。
实测 `is_meaningful_metadata('原文未标明') is True`——**它根本不报**。

被报的 14 篇实际构成，以及由此拆出的两件独立的事，见下方 158a / 158b。

连带后果：#158 验收标准第三条「一条断言：写着『原文未标明』的不报，要能在修
之前红」**写不出红的测试**，它现在就不报。

## 任务

### 158a — `is_meaningful_metadata` 对非 str 一律判为占位符 ✅ 已合并

| | |
|---|---|
| 前提 | 已验证。`published: 2026-08-13` → `datetime.date` → `False`；`'2026-08-13'` → `str` → `True` |
| 影响 | 真实 Vault 上 2 篇。YAML 标准的裸日期写法被判成占位符，**填得最规范的反而被罚** |
| 断言 | 裸日期/裸年份的 web-clip 不报 `web-clip-missing-published`；空串与模板占位符照报 |
| 停止条件 | 若发现某处依赖「非 str 即无效」，先裁定该处再动 |
| 结果 | 七个调用点无一依赖它；`capture_receipt.py:901` 的 `str(label)` 反而说明作者预期非 str 合法。真实 Vault 113 → 111，只有那两篇不再被报，其他 finding 一条未变 |

### 158b — `unknown` 算不算「明确声明缺失」🛑 已否决，不改代码

| | |
|---|---|
| 前提 | 待验。`unknown` 在 `PLACEHOLDER_VALUES` 里，`原文未标明` 不在，于是同一件事中文详述通过、英文单词被报 |
| 待答 | 这个不对称是有意设计（单词 = 工具默认值，句子 = 人查过了），还是词表的偶然产物？ |
| 证据 | 统计写 `unknown` 的笔记与写 `原文未标明` 的笔记，在生成时间/其他字段上有无系统差异 |
| 停止条件 | 证据不足以分辨两者 → 记录为无法裁定，**不改词表** |
| 结果 | 证据充分，且指向「当前行为正确」。两种写法在时间上零重叠，分界线正是 `0cfdac0`（2026-07-27）落地那天——那次提交把 `unknown` 列为占位符，并在指令里指定 `原文未标明` 作替代。规则生效后写 `unknown` 的 web-clip 为 **0 篇**。豁免 `unknown` 会撤销这次裁定。记录见 `2026-08-21-rejected-hypotheses.md` 第 2 条 |

### 156 — create-note 写后审计失败仍 exit 0 ✅ 已实现

| | |
|---|---|
| 前提 | 已复现：exit=0、文件落盘、顶层无 `ok` 字段、`audit.ok=false` |
| 修正 | issue 说「17 篇」，实测**9 篇**（两码重叠 8 篇）。且全落在 2026-07-22~26，近一个月零新增——不是活的出血点，是契约错 |
| 待验前提 | 选项 1（preflight 前拒绝）要求 preflight 阶段拿得到完整正文 |
| 停止条件 | preflight 拿不到完整正文 → 改选项 3，并写下为什么 1 不可行 |
| 结果 | 前提成立：`audit_note_text` 本就为「不落盘审计候选内容」而存在，只是两个调用点都锁在 `--preflight-json` 分支里。采用选项 1 |

**两处偏离 issue 原文，均已裁定：**

1. **拒绝集不是「全部 defect」。** 20 个 defect 码里多数描述的是 Vault 而非这篇
   笔记：`broken-wikilink` 被 #159 裁定为标准用法，按 defect 拦截会让「新建笔记
   时链接一个未来概念」变成不可能。拒绝集收窄为「只看本篇文本即可判定、且重写
   正文就能修掉」的模板未完成类两码。
2. **拒绝路径不加顶层 `ok`。** issue 要求「`--json` 都该有顶层 ok」，但
   `rules-and-errors.md` 规定 helper 拒绝用 `{"error": {...}}` 且
   `test_error_code_contract.py` 强制它。裁定：拒绝走既有 envelope + exit 2，
   顶层 `ok` 加在成功载荷上——那里此前根本没有任何字段报告判定结果。

### 157 — disconnected-note 只报不建议 ✅ 已裁定并实施

| | |
|---|---|
| 前提 | 已量：23 条中 **16 条是 web-clip**（70%），4 learning-note，1 insight-note，1 project-note，1 无 type |
| 倾向 | 数据支持 issue 自己预判的「降级或按类型豁免」，不支持「配建议」 |
| 仍需 | 验收标准要求给出 `suggest-directed-links` 在这 23 篇上的逐篇候选数 |
| 停止条件 | 若候选数意外地高，「豁免」的前提就不成立，回到「配建议」并记录 |
| 结果 | **23 篇全部 0 候选**——「配建议」这一支被数据否掉，正如 issue 自己的预判。另测得 23 篇全部 ≤44 天（中位 27），且 20/23 已被 `review-captures` 以更强的问题覆盖。裁定：豁免 web-clip。真实 Vault 111 → 95，`disconnected-note` 23 → 7 |

### 159 — 记录被数据否掉的断链假设 ✅ 已落文档

落点定为 `docs/superpowers/specs/2026-08-21-rejected-hypotheses.md`——与 158b 的否定结论同属一类，合并成一份持久记录，给未来的否定结论一个统一去处。

### 154 上半 — `receipt-candidate-mismatch` 为什么没匹配上 ✅ 已修

| | |
|---|---|
| 前提 | 需要 grok 可用（见 memory：本项目不跑 codex） |
| 纪律 | issue 自己要求「先读出实际比对的两个值再改」 |
| 停止条件 | grok 不可用 → 记录并跳过，不盲改判分器 |
| 结果 | grok 可用（1.0.5），但**最终不需要跑**。判据静态可证：`receipt_binds_note` 要求 `--from-preflight <note sha>`，而 issue 记录的命令走 `--content-file` + `--capture-receipt-file`，`None != sha` 恒真，永远 continue。假阳性用一条真实形状的断言静态复现 |

## 顺序

158a → 156 → 158b → 157 → 159 → 154上半

按「证据确定性 × 影响」排。158a 证据完整且无争议，154 上半最贵且依赖外部条件。
