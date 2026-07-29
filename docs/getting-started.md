# 快速开始

## 1. 准备条件

- 一个 Obsidian Vault；已有 Vault 和新建空目录都可以。
- Python 3.11 或更高版本。
- Codex、QoderWork、WorkBuddy、Claude Code 或 Cursor 之一。
- 推荐让具备终端能力的 Agent 执行安装，而不是手工拼装 Skill。

## 2. 推荐：直接让 Agent 安装

把下面的提示词发给当前 Agent：

```text
请从官方仓库 https://github.com/Spc-jgs/obsidian-kb-skill 安装最新稳定版。

先阅读 README、docs/getting-started.md、安装器帮助和 CHANGELOG。
识别当前 Agent 平台与我的 Obsidian Vault 路径；不能确定时先问我。
使用官方安装器，不使用 --force，不覆盖已有模板或笔记。
安装后从非仓库目录分别运行写入与检索 Skill 的 doctor --json，
再执行一次只读 search-vault smoke test，并报告版本、路径和结果。
任何验证失败都停止，不删除或重建 Vault。
```

## 3. 手动运行官方安装器

克隆仓库：

```bash
git clone https://github.com/Spc-jgs/obsidian-kb-skill.git
cd obsidian-kb-skill
```

macOS / Linux：

```bash
bash install.sh --vault "/你的/Obsidian/Vault"
```

Windows PowerShell：

```powershell
.\install.ps1 -VaultPath "D:\YourVault"
```

安装器会：

1. 保存 Vault 路径；
2. 补齐缺失的标准目录、模板和索引，不覆盖已有笔记；
3. 安装写入与只读检索两个 Skill；
4. 配置私有 Python/PyYAML runtime；
5. 从中立工作目录运行 doctor、vault-info 和 search-vault 验证。

完整的平台位置见[平台与安装](platforms-and-installation.md)。

## 4. 验证安装

以 Codex 为例：

```bash
python ~/.agents/skills/obsidian-knowledge-base/scripts/run_helper.py \
  doctor --json

python ~/.agents/skills/obsidian-knowledge-retrieval/scripts/run_helper.py \
  doctor --json

python ~/.agents/skills/obsidian-knowledge-retrieval/scripts/run_helper.py \
  search-vault "/你的/Obsidian/Vault" \
  --query "最近关于知识库架构的决定" --top-k 5 --json
```

两个 doctor 都应满足：

- `ok: true`
- `version` 等于当前稳定版本
- `payload`、`runtime`、`dependencies`、`resources` 全部通过

## 5. 第一次使用

检索已有知识：

```text
在我的 Obsidian 里找一下，我们为什么把检索和写入拆成两个 Skill？
```

沉淀对话：

```text
把刚才关于缓存一致性的讨论沉淀到知识库，保留方案、取舍和验证步骤。
```

保存会议：

```text
记录刚才的需求评审会：参与人、决定、未决问题和行动项都要保留。
```

深度剪藏：

```text
完整读取这篇文章并沉淀到知识库。我要脱离原链接也能理解原理、
复现步骤、验证结果和限制；如果正文或关键附件不可访问就停止。
```

## 6. 升级与卸载

普通升级会更新 Skill，但保留用户模板：

```bash
bash install.sh --vault "/你的/Obsidian/Vault"
```

只有明确希望用项目模板覆盖现有模板时才使用 `--force`。

卸载 Skill、保留 Vault 和配置：

```bash
bash install.sh --vault "/你的/Obsidian/Vault" --uninstall
```

连同 Vault 路径与备份策略配置一起清理：

```bash
bash install.sh --vault "/你的/Obsidian/Vault" \
  --uninstall --purge-config
```

Windows 对应使用 `-Force`、`-Uninstall` 和 `-PurgeConfig`。

## 下一步

- 想知道“能做什么”：阅读[完整功能指南](feature-guide.md)。
- 想理解检索结果：阅读[只读检索](retrieval.md)。
- 想调整模板、路由和索引：阅读[知识沉淀与治理](capture-and-governance.md)。
