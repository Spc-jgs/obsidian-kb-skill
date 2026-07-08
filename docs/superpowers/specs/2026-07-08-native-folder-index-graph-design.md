# Folder Index 原生图谱链路与 Skill v1.6.0 设计

## 背景与根因

当前 Vault 将根目录和所有非根目录索引统一命名为 `INDEX.md`，并配置：

```json
{
  "graphOverwrite": true,
  "rootIndexFile": "INDEX.md",
  "indexFileUserSpecified": true,
  "indexFilename": "INDEX"
}
```

Folder Index 1.0.30 的页面渲染和文件夹点击逻辑支持自定义索引名，但 Graph View 重写逻辑在寻找子目录索引时固定查找 `<子目录名>.md`。因此：

- `Java/INDEX.md` 能连接同目录笔记；
- `20-Learning/INDEX.md` 无法连接 `Java/INDEX.md`；
- 根 `INDEX.md` 无法连接 `20-Learning/INDEX.md`。

这不是新笔记缺少语义 Wikilink，而是结构索引命名与插件图谱算法不兼容。

## 已选方案

采用 Folder Index 原生索引命名：

- Vault 根目录继续使用 `INDEX.md`；
- 每个受管非根目录使用 `<目录名>.md`；
- `indexFileUserSpecified` 设为 `false`；
- `autoRenameIndexFile` 设为 `true`；
- `graphOverwrite` 保持 `true`；
- Folder Index 继续作为目录成员列表的唯一所有者。

示例链路：

```text
INDEX.md
  → 20-Learning/20-Learning.md
    → 20-Learning/Java/Java.md
      → 20-Learning/Java/2026-07-08 Spring-Import与ImportResource注解源码解读.md
```

不采用以下方案：

- 不在每篇笔记中增加根目录结构链接，避免污染语义关系；
- 不手工维护父 INDEX 的目录成员列表；
- 不维护 Folder Index 私有 fork；
- 不保留同目录下 `INDEX.md` 与 `<目录名>.md` 两套索引。

## Skill v1.6.0 设计

### 1. 配置感知的 Folder Index 审计

`scripts/audit_vault.py` 读取以下控制面文件：

- `.obsidian/community-plugins.json`
- `.obsidian/plugins/obsidian-folder-index/data.json`

当 Folder Index 已启用时，审计器根据真实配置推导索引路径：

- 根目录：`rootIndexFile`；
- `indexFileUserSpecified: true`：`indexFilename + ".md"`；
- `indexFileUserSpecified: false`：`folder.name + ".md"`。

新增 finding：

- `graph-incompatible-index-config`：开启 Graph overwrite 且使用统一自定义非根索引名；
- `missing-folder-index`：受管目录缺少配置期望的索引；
- `misnamed-folder-index`：目录中存在 `type: folder-index`，但文件名不是配置期望值；
- `broken-folder-graph-chain`：根索引或父目录索引无法按 Folder Index 1.0.30 算法连接到子目录索引。

排除目录读取插件的 `excludeFolders`，并继续忽略 `.git`、`.obsidian`、`.obsidian-kb-backups`、`.venv` 与 `docs/superpowers`。

### 2. 创建与写后验收

Folder Index mode 必须读取插件配置。创建新文件夹时：

- 原生命名模式创建 `<目录名>.md`；
- 自定义模式按 `indexFilename` 创建；
- 新索引包含且只包含一个 `folder-index-content` 块。

写后验收增加完整结构链检查：从目标笔记所在目录向上逐级确认期望索引存在，直到根索引。`graphOverwrite` 为真但配置与插件图谱算法不兼容时停止并报告，不再声称结构图谱完整。

### 3. Wikilink、模板和元数据约定

- Bounded search 在读取目标 INDEX 后，必须列出目标目录文件名；只有目标目录没有高置信度候选时才查看父目录导航和 1–2 个相关兄弟目录。
- Vault 中实际选择的模板是结构权威。写后检查必需标题存在且顺序一致；允许增加用户自定义章节，不要求正文逐字匹配。
- `web-clip.source` 固定存放原文规范 URL；标题、作者、发布日期分别使用标题、`author`、`published`。
- `related` 是机器查询与图谱关系的权威列表。正文可重复同一链接，但必须补充关系说明；如果只是裸链接重复，则省略正文重复项。

### 4. Git 预同步

当用户或 Vault 规则要求 Git 时，在写入前先执行只读 fetch：

- 工作区干净且仅落后远端：允许 `merge --ff-only`；
- 仅本地领先：继续写入；
- 已分叉、工作区有无关改动或 fast-forward 失败：停止并报告。

写入并提交后再次 fetch。只有远端未领先且未分叉时才 push。任何内容冲突仍禁止自动解决。

### 5. 安装器

Bash 与 PowerShell 安装器检测 Folder Index 配置：

- Folder Index 原生模式：创建目录同名索引和 `folder-index-content`；
- Folder Index 自定义模式：创建配置指定的索引并明确警告 Graph View 层级限制；
- 无 Folder Index：维持 `INDEX.md` + Dataview/static fallback。

安装器不得在原生模式下额外创建 `INDEX.md`，避免重复索引所有者。

## Vault 迁移设计

### 迁移前保护

1. 确保本地 `master` 与远端同步且工作区干净；
2. 退出 Obsidian，防止插件缓存旧配置或同时创建文件；
3. 将插件配置、17 个非根 INDEX、AGENTS、CLAUDE、README 备份到带时间戳的 `.obsidian-kb-backups/`；
4. 记录迁移前文件清单、SHA-256 和严格审计结果。

### 原子迁移

把以下模式统一转换：

```text
<folder>/INDEX.md → <folder>/<folder-name>.md
```

根 `INDEX.md` 不变。索引正文、frontmatter、人工说明、学习进度和导航内容按字节保留，只改变路径。随后更新插件配置和治理文档。

### 迁移后验收

- 所有受管非根目录恰有一个同名 folder index；
- 非根目录不存在遗留 `INDEX.md`；
- 严格审计为 0 findings；
- Graph 算法模拟证明每个受管目录都能从根索引到达；
- 每篇非索引 Markdown 笔记都能从所在目录索引到达；
- `.obsidian/workspace.json` 未修改；
- 重新打开 Obsidian 后插件不创建重复索引，配置保持预期值。

## 发布、共享安装与真实捕获

### 发布

- 版本提升到 `1.6.0`；
- 更新中英文 README、CHANGELOG 和四个平台生成适配器；
- 完整 pytest、build check、安装器 smoke test 和 Vault fixture 审计通过；
- 合并并推送 `master`；
- 创建 annotated tag `v1.6.0` 和正式 GitHub Release。

### 共享安装

将发布 tag 克隆到：

```text
/Users/shaopc/.agents/obsidian-kb-skill
```

创建共享技能入口：

```text
/Users/shaopc/.agents/skills/obsidian-knowledge-base
  → ../obsidian-kb-skill/platforms/qoderwork
```

使用相对软链接，确保不同 Codex/Qoder 账号可以读取同一 `SKILL.md`。

### 真实文章沉淀

使用共享安装后的 `SKILL.md`，把 Folder Index 官方实现与本次图谱断链分析沉淀为一篇中文 Web Clip：

```text
20-Learning/Obsidian/
├── Obsidian.md
└── 2026-07-08 Folder Index自定义索引名导致图谱断链.md
```

这一步同时验证：

- Agent 创建新主题目录时使用同名索引；
- Web Clip 模板、source、related 和正文关系说明符合 v1.6.0；
- 根 `INDEX.md → 20-Learning.md → Obsidian.md → 新文章` 完整可达；
- README 因新增主题目录而同步；
- 写后审计、Git 预同步、提交和推送完整执行。

## 成功标准

只有同时满足以下条件才算完成：

1. Skill v1.6.0 已发布且 tag、Release、远端提交一致；
2. Vault 已迁移并推送，严格审计为 0 findings；
3. 图谱算法验证所有受管目录和笔记均可从根索引到达；
4. 共享 `.agents` 安装可读且指向 v1.6.0；
5. 使用共享 Skill 创建的真实文章存在、已推送并具有完整根路径；
6. 两个仓库最终工作区干净、本地与远端分歧均为 0/0。
