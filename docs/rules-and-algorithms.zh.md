# 规则与算法总览（中文）

这份文档把散落在代码里的规则、阈值和算法集中讲清楚，给人读，不给机器读。
凡是「为什么是这个数」，能说清的都说了；说不清的会明确标成「拍的，待调」。

代码是唯一事实来源，这份文档是它的说明。改了常量要回来改这里。

---

## 0. 整体结构

一套源码产出两个 Skill：

| Skill | 职责 | 能不能写 |
|---|---|---|
| `obsidian-knowledge-base` | 创建、更新、治理笔记 | 能，但必须有明确保存意图 |
| `obsidian-knowledge-retrieval` | 搜索、引用、回答 | **不能**，只读 |

指令的唯一源是 `core/OBSIDIAN_KB.md`（写入）和 `core/RETRIEVAL.md`（检索），
由 `build.py` 扇出成 6 份产物（标准 Skill ×2、QoderWork、Claude Code、Codex、
Cursor）。**不要直接改生成物**，改源再跑 `python build.py`。

两个 Skill 打包的 Python 模块不同。检索包是白名单，只有 9 个模块
（`console`、`doctor`、`frontmatter`、`note_catalog`、`query_expansion`、
`retrieval_vault_info`、`search_vault`、`text_tokens`、`vault_paths`）——
所以写入侧的东西检索侧用不了，需要共用的必须放进 `note_catalog` 这类共享域
并加进白名单。

---

## 1. 第一条规则：不主动写

Skill 永远不自己往 Vault 写东西。只有用户明确表达保存意图（"存到 Obsidian"、
"沉淀一下"、"总结存档"）才写。普通问答、debug、闲聊：什么都不做。

「评估这段对话有什么值得沉淀的」是分析，可以做，但**只分析不写**。

## 2. 成本上限（每次调用）

| 操作 | 硬上限 |
|---|---|
| 扫描的文件数 | 10 |
| 完整读取的内容笔记 | 3 |
| 写入/编辑的笔记 | 1 |
| 更新的索引文件 | 2（仅静态索引模式） |
| 单篇插入的 wikilink | 5 |

治理文件、模板、插件配置这类短的控制面文件算进「扫描 10 个」，但不算「完整
读取」。只读前 20 行不算完整读取。

确实需要超（比如批量导入 20 篇）必须先问用户。

---

## 3. 路由：笔记去哪个目录

### 3.1 类型 → 目录默认映射

| 类型 | 目录 | 默认标签 |
|---|---|---|
| `daily-note` | `15-Daily` | `daily` |
| `meeting-note` | `10-Work` | `meeting` |
| `learning-note` | `20-Learning` | `learning` |
| `web-clip` | `20-Learning` | `web-clip` |
| `insight-note` | `30-Insights` | `insight` |
| `conversation-digest` | `30-Insights` | `insight` |
| `project-note` | `40-Projects` | `project` |
| `person-note` | `50-People` | `people` |
| `task-memory` | `Tasks` | `task` |

另有 `00-Inbox`（快速捕获/未读源）、`90-Archive`（归档）、`95-Sources`（原文
存档，见第 8 节）。

### 3.2 优先级

**用户要求 > Vault 本地治理文件（根目录和目标路径的 `AGENTS.md`/`CLAUDE.md`）
> 上表默认值。**

治理必须在发现调用**之前**读。理由是实测出来的：某篇文章治理规定进
`20-Learning/AI-Agent`，如果先做发现调用再读治理，问的就是 `20-Learning`，
拿不到子目录拥挤的信号，笔记正好落进契约想拦的拥挤目录。

### 3.3 目录拥挤与拆分

| 参数 | 值 | 含义 |
|---|---|---|
| `CROWDED_FOLDER_THRESHOLD` | 20 | 直属笔记数超过它算拥挤 |
| `CLUSTER_MIN_NOTES` | 5 | 一个主题词要有这么多篇才够拆子目录 |
| `MAX_CLUSTER_TERMS` | 6 | 每个目录最多报几个主题词 |
| `MAX_CLUSTER_SCAN` | 200 | 单目录最多读多少篇的头部 |
| `MAX_CLUSTER_SCAN_TOTAL` | 1000 | **整次调用**的读取预算 |
| `MAX_CHILD_FOLDERS` | 12 | 每条拥挤记录最多列几个已有子目录 |

拥挤了不等于要拆。**必须存在一个 ≥5 篇的稳定主题词**才提议建子目录，否则
「拥挤但没东西可拆」也是个正当答案。

主题词从标签和标题 token 一起统计，类型默认标签（`learning` 这种）先剔除，
否则 `20-Learning` 整个目录看起来就是一个大簇。

聚类要读笔记头部，所以有整次调用的总预算：目标目录一定分析，其余按拥挤度
补满预算，超出的只报数量不报主题词。

#### 什么词不算候选

达标（≥5 篇）只是第一道门。下面两类词描述的是**目录本身**，不是目录里的子主题，
直接剔除而不是排到后面 —— `MAX_CLUSTER_TERMS = 6` 这 6 个名额才是稀缺资源。

**一、拆不动的词。** 拆出去的和留下的都得能独立成夹，而原来只查了前者：

- `直属篇数 - 覆盖篇数 < CLUSTER_MIN_NOTES` → 剔除
- `词 == 目录名`（按标签归一化比较）→ 剔除，不看比例

用**余数**而不是百分比是刻意的：不需要引入第二个魔法数字，复用已有的
`CLUSTER_MIN_NOTES`，而且随目录大小自动缩放 —— 7 篇里覆盖 6 篇和 200 篇里覆盖
172 篇都是 86%，但完全不是同一个决定。

第二条单独存在，是因为余数规则漏得掉同义反复：`ai-agent` 在
`20-Learning/AI-Agent` 覆盖 25/34，余 9 篇够建目录，但
`20-Learning/AI-Agent/ai-agent/` 是给目录改名，不是拆分。

**二、标题里的标签碎片。** 把每个已计数标签按连字符拆开，其组成部分不再单独上榜：
`ai-agent` → `ai`、`agent` 都不算独立主题。按连字符分段而不是子串匹配，
否则会误伤无关词。原来只挡「和标签完全同名」，所以碎片全部漏网。

**三、类型默认标签 —— 从本 Vault 的模板读，不是写死的表。** 这里原来引用
`suggest_links.GENERIC_TAGS`，和 `tag_vocabulary` 用两份数据回答同一个问题。
那份硬编码表把 `java` 当通用词（参考 Vault 里 12 篇的真实主题，只要某个拥挤目录
攒够 5 篇，该拆的那个词就会被静默丢掉），又在模板从 `person` 改成 `people` 之后
继续留着一条谁也保护不了的死条目。现在两处同源，`collect()` 读一次模板传下去。
（[#69](https://github.com/Spc-jgs/obsidian-kb-skill/issues/69)）

**四、描述「一篇东西」而不是主题的词。** `GENERIC_TITLE_TOKENS` 原来只覆盖体裁
（指南/教程/guide），漏了「文章」这一类词本身。参考 Vault 上 `文章` 占掉 6 个名额
里的一个，挤掉了 `llm-engineering` 和 `vibe-coding`。已补：`文章` `笔记` `记录`
`整理` `汇总` `合集` `系列` `article` `note` `notes` `post` `summary`。

**五、来源站点名 —— 由 Vault 自己声明，不写进代码。**
`2026-07-24 掘金文章-Jackson3升级指南` 这种剪藏命名约定，会让 `掘金文`
（`掘金`+`金文` 合并出来的）长期占名额。但这件事没有全局答案：对做剪藏的 Vault
它是噪声，对写「掘金这个平台」的人它是正当主题，对不剪藏的 Vault 它是死代码。
所以不硬编码、也不上没测过的启发式（比如「出现在标题前缀位置」——
真实主题同样会打头），而是让 Vault 自己说：

```json
{"schema_version": 1, "non_subject_terms": ["掘金文章", "微信公众号"]}
```

放在 `.obsidian-kb/vault-vocabulary.json`。每条声明按标题同样的方式分词，
**产出的全部词元一起剔除** —— `掘金文章` 会同时去掉 `掘金`、`金文`、`文章`；
只去掉最后一个，前两个会重新合并成 `掘金文`，也就是原来占名额的那个词。
上限 16 KiB / 100 条 / 每条 2–40 字符；文件坏了用 `invalid-vault-vocabulary`
拒绝而不是忽略 —— 忽略等于把配置说过不算主题的词重新当建议报出去。
（[#68](https://github.com/Spc-jgs/obsidian-kb-skill/issues/68)）

> 修复前，`20-Learning/AI-Agent`（34 篇，11 个达标词）报出来的前 6 名里有 4 个是
> 噪音：`ai-agent`（目录名）、`ai` 和 `agent`（目录名的两半）、`文章`（通用词），
> 而 `llm-engineering` 和 `vibe-coding` 两个真候选被截断。修复后 4 个真候选标签
> 全部进榜；`10-Work/日报` 的主题词清空 —— 空列表是合法答案，它说的是
> 「这个目录没有可拆的子主题」。（[#55](https://github.com/Spc-jgs/obsidian-kb-skill/issues/55)）

---

## 4. 元数据规则

### 4.1 frontmatter

- 必须是 UTF-8 无 BOM
- 必须是 YAML 映射（不能是列表）
- 日期用系统当前日期，不许硬编码
- 读取上限 `FRONTMATTER_SCAN_LIMIT = 256 KB`，按 8 KB 分块读到块闭合为止

  > 这里原来是固定 4096 字符，超过就静默当成「没有 frontmatter」——
  > 标签从聚类里消失、别名从链接解析里消失，没有任何报错。已修。

### 4.2 标签

1. **从发现调用返回的 `tag_vocabulary` 里选。** 那是全库在用的标签，按频次排序，
   附 `distinct` 总数。词表里没有合适的才造新词，并说明拒绝了哪个已有词。
2. **只用 kebab-case**：小写、连字符分隔。
3. **不许近重复**：`ai-agents` / `ai-agent`、`springboot` / `spring-boot`、
   `frontEnd` / `front_end` 都算同一个标签。
4. **每篇最多 5 个。**
5. 标准标签（始终可用）：`daily` `meeting` `learning` `web-clip` `insight`
   `project` `people` `ai-generated` `todo`

规则 1 原来是「扫目标目录最近 5 篇笔记」—— 用局部样本回答全局问题。参考 Vault
实测：**170 篇笔记 169 个不同标签，63% 只用过一次**，5 篇的窗口命中率极低，
造新词又让下次更命不中，是个正反馈。现在改成返回全库词表。

**标签同一性判定**（`note_catalog.normalize_tag_key`）：小写 → 去掉 `_`、`-`、
空格 → 去掉结尾的 `s`。审计用它报近重复，检索用它匹配 `--tag`。

参数上限：
- `MAX_VOCABULARY_TERMS = 40`（返回多少个词）
- `MAX_VOCABULARY_SCAN = 1000`（按修改时间倒序扫多少篇）

类型默认标签**从本 Vault 自己的 `Templates/*.md` 读**，不是写死的列表 ——
Vault 把 `person` 改成 `people` 能跟上，`java` 这种真实主题也不会被当通用词丢掉。

---

## 5. 写入流程：预检 → 应用

### 5.1 内容绑定

创建笔记是两步：`--preflight-json` 校验，然后 `--apply` 写。两步必须是**同一份
内容**，靠 SHA-256 绑定。

预检会把校验过的原始输入按渲染后的 SHA-256 暂存到 **Vault 之外**
（`~/.obsidian-kb-preflight`，可用 `OBSIDIAN_KB_PREFLIGHT_CACHE` 覆盖），
应用时用 `--from-preflight <sha256>` 引用，不用重新传一遍正文。

这比重传**更严**不是更松：重传什么都证明不了，而引用会被重新渲染、重新哈希，
对不上就报 `preflight-content-changed` 拒绝写入。

缓存参数：
| 参数 | 值 |
|---|---|
| `ENTRY_TTL_SECONDS` | 24 小时 |
| `MAX_ENTRIES` | 64 条 |
| `MAX_TOTAL_BYTES` | 32 MB |

> 条数单独限制不了任何东西 —— 笔记没有大小上限，64 条也没有。所以同时限字节。

### 5.2 标题层级修复

模板要求的段落都在、只是 ATX 层级错了，预检会给出 `validation.suggested_fix`，
`--fix-heading-levels` 可以只调层级。**故意做得很窄**：只移动层级，只对文字
已经和契约一致的标题，且结果必须满足契约。段落缺失、改名、顺序错都是内容问题，
工具不猜。

而且 `--fix-heading-levels` 只能配合 `--preflight-json` —— 内容不会在通往磁盘的
路上被静默改写。

### 5.3 命名与冲突

- 非法字符 `/ \ : * ? " < > |` 一律替换成 `_`
- 永不覆盖：重名加数字后缀 `-2`、`-3`
- Windows 保留名（`CON`、`PRN` 等）单独拦

### 5.4 写后校验

写完必须重读目标文件跑审计，修掉元数据、占位符、链接、索引违规再报成功。
校验没过：不确认、不提交、不推送。

---

## 6. 审计规则

`audit-vault` 只读，输出按路径、代码、消息排序，结果确定。

### 6.1 三级严重度

分级的理由：原来 39 种问题平铺输出，一条真断链和一条风格化的近似标题并排，
整个列表读起来就是噪声（参考 Vault 上 180 条）。

| 级别 | 含义 | 数量 |
|---|---|---|
| **defect** | 笔记或 Vault 已经坏了：导航、渲染或工具链已失效，或者半成品脚手架被写进去了 | 21 种 |
| **hygiene** | 一致性和完整性问题，方便的时候修 | 18 种 |
| **informational** | 观察项，往往完全正常 | 4 种 |

**defect（21）**：`missing-frontmatter` `invalid-frontmatter` `missing-type`
`invalid-type` `missing-date` `unclosed-fence` `empty-template-note`
`residual-template-instruction` `unresolved-template-placeholder`
`outdated-deep-capture-template` `outdated-conversation-digest-template`
`broken-wikilink` `invalid-related` `invalid-related-entry`
`duplicate-project-note` `duplicate-folder-index`
`duplicate-folder-index-content` `graph-incompatible-index-config`
`broken-folder-graph-chain` `web-clip-invalid-capture-depth`
`web-clip-captured-nothing`

**hygiene（18）**：`missing-tags` `invalid-tag` `too-many-tags`
`near-duplicate-tags` `duplicate-related-entry` `ambiguous-wikilink`
`duplicate-title` `missing-template-heading` `missing-deep-capture-heading`
`missing-conversation-digest-heading` `conversation-digest-missing-resume-field`
`conversation-digest-resume-card-too-long` `missing-folder-index`
`misnamed-folder-index` `missing-folder-index-content` `web-clip-missing-source`
`web-clip-missing-author` `web-clip-missing-published`

**informational（4）**：`orphan-note` `disconnected-note` `similar-title`
`link-to-unwritten-note`

### 6.2 链接解析

wikilink 按这个顺序解析：**文件名 → 词干（stem）→ 声明的 aliases**。
别名映射**只在前两步都失败时才构建**，所以链接全都能解析的 Vault，每次写入都跑
的单篇审计开销不变。

> 两个修过的坑：一是审计原来不认 aliases，一条能用的别名链接会同时产生一个
> `broken-wikilink`（最高严重度）和一个针对目标笔记的 `orphan-note`；二是
> `Path("Qwen3.6-27B实战").suffix` 在 pathlib 眼里是 `.6-27B实战`，于是
> 「看起来没有扩展名」那道门对任何含点标题都关上了。

### 6.3 不受笔记契约约束的东西

| 对象 | 为什么豁免 |
|---|---|
| `README.md` `AGENTS.md` `CLAUDE.md`（任意层级） | 是给人和 agent 看的脚手架，不是知识 |
| `Templates/` | 模板本来就带占位符 |
| `95-Sources/` | 存档是证据，它的标题和标签属于原作者 |

`95-Sources/` 还额外豁免 folder-index 要求 —— 存档是从引用它的笔记进去的，
不靠浏览。

### 6.4 可达性和连通性是两件事

`orphan-note` 测的是**可达性**：这篇笔记还能不能被翻到。只要目录存在
folder-index，该目录下所有笔记就算已被索引 —— 这个推断是对的，因为 Folder Index
插件自己按目录内容生成列表，审计还禁止把它换成手写列表。参考 Vault 有 22 个
folder-index 覆盖全部管理目录，所以它报 0 条是真实的，不是漏报。

但可达 ≠ 连通。躺在索引列表里翻得到，和与其他笔记有没有知识关系，是两回事。
`disconnected-note`（[#57](https://github.com/Spc-jgs/obsidian-kb-skill/issues/57)）
补的就是这个缺口：**零入链且零出链**。

**只报交集。** 实测参考 Vault 审计候选 127 篇里，零入链 79 篇、零出链 74 篇 ——
任何单边都太吵，含义还模糊：一篇被三处引用的概念笔记没有出链是正常的。
两边都没有才是无歧义的「和知识库其余部分没有任何关系」。

**周期性日志豁免。** `daily-report` 和 `weekly-report` 不参与判定 —— 流水日志不
链东西是本分。完全孤立的 57 篇里它们占 36 篇（63%），不排掉就会把真正值得看的
21 篇埋了。

实测输出：21 条，其中 **14 条是 `web-clip`** —— 剪进来再没接上任何东西，
正是调研里排第一的那个痛点。严重度 `informational`：孤立不是缺陷，
而且**不要为了消掉它去编一条链接**，不相干的链接比没有更糟。

---

## 7. 检索算法

只读、纯本地、不发网络请求、不写索引不写缓存。

### 7.1 排序：Okapi BM25

参数 `k1 = 1.5`、`b = 0.75`（工业标准值，和 Elasticsearch 一致）。

**字段权重**：

| 字段 | 权重 |
|---|---|
| 标题 | 6.0 |
| 别名 | 5.0 |
| 标签 | 3.0 |
| 各级标题 | 2.0 |
| wikilink 文字 | 2.0 |
| 正文 | 1.0 |

分数**只用于排序，不是置信度也不是真值**。

### 7.2 分词

- 拉丁：`[A-Za-z0-9]+` 转小写
- CJK：**重叠 bigram**。`知识库检索` → `知识` `识库` `库检` `检索`

  > 副作用：一个中文词会膨胀成多个 token。`企业级落地` 变成 4 个。做聚类标签
  > 和关联度打分时必须先合回词，否则一个词会被当成 4 条独立证据。
  > `vault_info._merge_overlapping_runs` 干的就是这件事。

### 7.3 跨语言查询扩展

**要解决的事**：中文查询和英文笔记**一个词元都不共享**。看 7.2 —— 拉丁词元和
CJK bigram 是两套字母表。所以在中英混写的 Vault 里用中文问一篇英文笔记，BM25
拿不到任何可排的东西，返回的是**零结果**，不是排错。v1.30 的评测里 8 条语义改写
只命中 3 条，其中 5 条失败全是零结果；3 条命中全靠笔记自己带了中文别名。

**做法**：一份人工整理的**概念词表**，每个概念是若干跨语言同义说法。匹配原始
查询，命中就把该概念其余说法的词元一起加进检索，权重打折。

匹配规则按语言分：

- **中文词条按子串匹配**。中文没有词边界，只有子串能在 `避免缓存击穿的方案`
  里找到 `击穿`。
- **拉丁词条按连续词元串匹配**。`cache stampede` 命中 `cache stampede control`，
  但不命中「一群用户挤爆了售票缓存」这种两个词各自出现、隔着一句话的句子。

**用户打过的词永远是 1.0**，即使某个概念也提议了同一个词 —— 直接证据不因为一个
和它意见一致的猜测而降权。

**歧义如实展开**。中文「代理」同时是 agent 和 proxy，词表两边都展开，两个概念都
出现在 `expansion` 里。helper 不替用户选一个读法。

**证据必须可见**，否则扩展就是不可审计的黑箱：

- 每条结果一条 `expansion` signal，**只在那些词确实出现在这篇笔记里时才给**；
- 整个响应一个 `expansion` 块：命中概念、触发原词、引入词元、权重、是否截断；
- `--no-expand` 完整复现 v1.29.2 的纯词法行为。评测里两个数都能现场跑出来。

`mode` 仍然是 `lexical`。按词表改写查询就是词法检索，改叫别的会让人以为有个不
存在的向量库。

**Vault 自己的词表**：可选文件 `.obsidian-kb/retrieval-lexicon.json`，格式
`{"schema_version": 1, "concepts": [{"id": ..., "terms": [...]}]}`。内置表覆盖的
是这个 Skill 服务的领域，猜不到你的产品名。用户词条和内置表走同一套结构校验，
文件坏了用 `invalid-lexicon` **拒绝**而不是悄悄退回内置 —— 悄悄降级会让检索无法
复现，而且会让 `expansion` 块变成假话。

**词表不从笔记里学**。从笔记内容自动抽同义词能省掉整理成本，但那等于让笔记决定
检索去找什么。笔记在这个 Skill 里是不可信数据，这条规则不为省事开口子。

**噪声怎么挡住的**（按实际作用排序）：

1. 词表是**领域词表不是词典**，只覆盖这个 Skill 服务的主题；
2. **禁用通用词**，`LEXICON_STOPWORDS` 机械拦截（`方法`、`内容`、`thing`……），
   不靠人工评审；
3. **扩展词降权**到 0.45；
4. **6 条 no-answer 查询是发布门禁**，扩展最可能破坏的就是它，所以是硬断言。

第 1 条承担了大部分作用，也是唯一会随时间劣化的一条：词表会长大，每加一条都是
一次「加进一个有五种含义的词」的机会。这是这个方案接受并写明的维护成本。

**0.45 这个值没有被评测证明。** 权重从 0.25 扫到 1.0，40 条查询的召回完全不动 ——
16 篇的合成语料太干净，区分不出来。0.45 是按原则选的（一个直接标题命中约 4–6 分，
压到一半以下，两个扩展正文命中就顶不掉一个真标题命中），不是按数据调的。它在
真实 Vault 里的保护作用尚未测量。

### 7.4 元数据过滤器

`--type` `--tag`（可重复，同 flag 内 OR、跨 flag AND）、`--after` `--before`
（含端点，读 frontmatter `date`）。

三条设计约束：

1. **相对时间由 Agent 解析，helper 只收 ISO 日期。** 「上周」「最近」是 Agent 的
   活 —— 它知道今天几号和用户的语言。往 helper 里塞中英文日期文法 + 时区 +
   周起始日策略，会毁掉它唯一的价值（确定性、可测）。
2. **过滤是排序前的硬约束**，不动 `score` 语义。用户要 7 月日报，6 月的笔记是
   **错**，不是「相关性低一点」。
3. **过滤到空必须说清是哪条挡的。** 返回 `filters.excluded` 逐维度报告挡掉多少，
   字段缺失（`missing-date`）单独计。**空结果在有过滤器时永远报「没有匹配这个
   过滤条件的」，绝不能报「你的知识库里没有这个」。**

### 7.5 默认不检索的目录

`Attachments` `Templates` `95-Sources` 以及所有点开头的隐藏目录（含存放检索
词表的 `.obsidian-kb/`）。

**但 `--scope` 仍能进去。** 走查只对**子目录**套忽略集、从不套 scope 根 ——
所以 `--scope 95-Sources` 能搜原文存档。这个性质有专门的测试守着。

### 7.6 上限

| 参数 | 值 |
|---|---|
| `MAX_QUERY_CHARS` | 500 |
| `MAX_TOP_K` | 20 |
| `MAX_FILE_BYTES` | 2 MB |
| `MAX_SNIPPET_CHARS` | 480 |
| `MAX_ISSUES` | 20 |
| `MAX_EXPANSION_CONCEPTS` | 8 |
| `MAX_EXPANSION_TOKENS` | 24 |
| 词表文件上限 | 64 KiB / 200 概念 |

---

## 8. 原文存档

用户要保留原文时，**存档，绝不追加到笔记末尾**。

- 位置：`95-Sources/<YYYY-MM>/`
- 逐字保留：不改标题层级、不套模板、不截断、不重排
- 按**字节**读写，所以 CRLF 能活下来（`parse_frontmatter` 会把它归一化，所以
  存档不走它）
- `sha256` **只哈希原文本身**，不含 frontmatter —— frontmatter 是关于这次捕获的
  元数据，不是证据的一部分
- 双向链接：笔记加 `source_archive` 字段 + 一行可点击入口；存档 frontmatter
  回指笔记。用 wikilink，删掉存档会被审计报 `broken-wikilink`

为什么不能追加进笔记（实测）：那篇 56 KB 的笔记里沉淀 7.6 KB、原文 35 KB，
**占 82%**。12 次搜索命中里 **3 次（25%）引用落在原作者的正文里** —— 用户问
自己的知识库，被引到别人的博客原话。另外 BM25 按文档长度归一化，超长文档让
自己的沉淀掉了 20–30% 的分（不过实测名次只变了一个，所以稀释是趋势，引用错位
才是当下的实害）。

---

## 9. 关联度（wikilink 建议）

> **重做已结案：不改了。** 见
> `docs/superpowers/specs/2026-08-06-relatedness-scoring-design.md`。
> 原计划换成 BM25 + 标签 Jaccard、阈值 45；32 对人工标注全部为负（覆盖 0–74
> 全部分档），说明这组信号测的是「像不像」，而用户要的是「走过去能不能学到东西」。
> 换权重、换阈值都解决不了。**下面这套现状规则继续用**，它的问题（9.2）
> 已知且未修；真正的缺口在沉淀时该建的链接没建成（[#57]），不在事后打分。

### 9.1 现在怎么算

无上界整数累加：

| 信号 | 分值 |
|---|---|
| 每个共享的非通用标签 | +3，无上限 |
| 类型相同 | +1 |
| 标题 token 重叠 | +min(6, 2 × token 数) |

阈值 `MIN_SCORE = 3`。

### 9.2 现状的问题

- **阈值就是众数。** 参考 Vault 上最常见的分数正好是 3（最低分）。两个标题
  token 就能过关 —— `AI-Agent` 这个目录索引靠「agent, ai」配上了四篇笔记。
- **没有可以说「60 分」的标尺。** 实测分数 3–30，30 的含义是「这俩基本是同一篇」。
- **不读正文。** 只看 frontmatter 标签和标题。

### 9.3 已经修掉的相关缺陷

`deep_capture_contract` 强制 web-clip 必须有 `## 关联笔记` 标题，而指令说 links
可以「skip them」—— **必填的段落没法 skip**。同一句话还写着 helper 会「列出目标
目录的文件名」，等于把原始文件名列表递过去。结果：四篇毫不相干的笔记（Fluss
存储、SQL 优化器、RAG 流式、Zig Coding Agent）都链到了同一篇，就因为它是
`20-Learning/Backend/` 里排序第一的文件。`suggest-links` 对它们一个都没推荐过。

现在的规则：**零候选是答案，不是待填的空缺**；没有可信关联时用一行说明写满该
段落；**邻近不是关系** —— 同目录、同类型、同大方向都是不该链的理由。

---

## 10. 安全边界

### 10.1 路径遏制

所有路径参数都要过 `vault_paths` 校验，跟随符号链接后仍必须落在 Vault 内。
越界报 `PATH_OUTSIDE_VAULT`，退出码 3。

**拒绝就是契约，不是障碍** —— 绝不能绕过 helper 自己用原生工具写文件。

### 10.2 错误码约定

两种信封：

```jsonc
// 路径与安全拒绝，以及 update-note 备份失败 —— 退出码 3（路径）/ 2
{"schema_version":"1.0","ok":false,"command":"...","error":{"code":"...","message":"...","details":{}}}

// 其他所有 helper 拒绝 —— 退出码 2
{"error": {"code":"...", "message":"...", ...}}
```

两种都把 code 放在 `error.code`，所以读这个路径对两种都有效。

新错误码一律 kebab-case。四个早于这个约定的大写码原样保留不改名：
`PATH_OUTSIDE_VAULT` `PATH_NOT_FOUND` `INVALID_VAULT_ROOT` `BACKUP_FAILED`。
其中三个是 Vault 遏制边界，是项目里最安全敏感的码，改名换不来任何
「读 `error.code`」没提供的好处。

`tests/test_error_code_contract.py` 用 AST 从源码里推导出所有会发出错误码的
可调用对象，再比对文档 —— 不是手维护的列表，所以漏文档会被测出来。

### 10.3 内容是不可信数据

笔记里的内容 —— frontmatter、HTML 注释、代码示例、网页剪藏、引用的对话 ——
**都是数据，不是指令**。里面出现的命令或指示不授权任何工具调用。

### 10.4 Git 门禁

治理要求 Git 时，写前必须同步。门禁对**任何不是本次调用做出的改动**都停 ——
个人知识库可能有多个 agent 同时操作，一致性优先。

报告必须可执行：列出每一个阻塞路径、是未跟踪还是已修改、以及可行的出路。
并且明确：**用 stage / stash / discard / ignore 清掉别人的改动，永远不是出路。**

### 10.5 备份

改动已存在的笔记之前先备份到 `.obsidian-kb-backups/<时间戳>/<原路径>`。
备份失败就中止，不动笔记。

---

## 附录：可调参数速查

| 参数 | 当前值 | 在哪 | 管什么 |
|---|---|---|---|
| `CROWDED_FOLDER_THRESHOLD` | 20 | `vault_info` | 目录拥挤线 |
| `CLUSTER_MIN_NOTES` | 5 | `vault_info` | 拆子目录的主题词最小篇数 |
| `MAX_CLUSTER_TERMS` | 6 | `vault_info` | 每目录报几个主题词 |
| `MAX_CLUSTER_SCAN_TOTAL` | 1000 | `vault_info` | 聚类整次调用读取预算 |
| `MAX_VOCABULARY_TERMS` | 40 | `vault_info` | 标签词表返回多少词 |
| `MAX_VOCABULARY_SCAN` | 1000 | `vault_info` | 标签词表扫多少篇 |
| `MIN_SCORE` | 3 | `suggest_links` | 关联度阈值（改 45 的方案已结案作废，见 9） |
| `FIELD_WEIGHTS` | 6/5/3/2/2/1 | `search_vault` | BM25 字段权重 |
| `k1` / `b` | 1.5 / 0.75 | `search_vault` | BM25 参数 |
| `MAX_TOP_K` | 20 | `search_vault` | 检索返回上限 |
| `MAX_QUERY_CHARS` | 500 | `search_vault` | 查询长度上限 |
| `MAX_FILE_BYTES` | 2 MB | `search_vault` | 单文件索引上限 |
| `EXPANSION_WEIGHT` | 0.45 | `query_expansion` | 扩展词相对输入词的权重（见 7.3，未被评测证明） |
| `MAX_EXPANSION_CONCEPTS` / `MAX_EXPANSION_TOKENS` | 8 / 24 | `query_expansion` | 单次查询扩展上限 |
| `FRONTMATTER_SCAN_LIMIT` | 256 KB | `frontmatter` | frontmatter 读取上限 |
| `ENTRY_TTL_SECONDS` | 24 小时 | `preflight_cache` | 预检缓存过期 |
| `MAX_ENTRIES` / `MAX_TOTAL_BYTES` | 64 / 32 MB | `preflight_cache` | 预检缓存容量 |
| `MAX_RECEIPT_BYTES` | 1 MB | `capture_receipt` | 捕获回执上限 |

---

## 附录：已知未修的问题

| 问题 | 证据 | 状态 |
|---|---|---|
| `suggest_links` 仍用硬编码 `GENERIC_TAGS` | 聚类那侧已改读模板（[#69](https://github.com/Spc-jgs/obsidian-kb-skill/issues/69)），链接打分这侧没动 | 有意留下：那是相对噪声过滤 + 动态补充，是另一件事，改它要连打分一起测，归 [#75](https://github.com/Spc-jgs/obsidian-kb-skill/issues/75) |
| `企业级落地` 这类词仍可能占名额 | 既不是体裁也不是「一篇东西」，是这个 Vault 的口头禅 | 用 `.obsidian-kb/vault-vocabulary.json` 声明；不打算继续往内置表里塞 |
| 关联度没有可用标尺 | 分数 3–30 无上界，阈值 3 就是众数 | 重做已否决（32/32 负例），维持现状 |
| 连通性无信号 | 127 篇候选里零入链 79、零出链 74，审计只报可达性 | 已修：`disconnected-note`（[#57](https://github.com/Spc-jgs/obsidian-kb-skill/issues/57)），见 6.4 |
| 21 篇笔记完全孤立 | 其中 14 篇 web-clip，剪进来没接上任何东西 | 信号已可见，怎么处理是用户的判断 |
| 同质笔记互相推荐 | 30 篇日报彼此雷同，各自推出另外 29 篇，占过线对数的 77% | 靠 top-N 兜住，未单独修 |
