# 平台与安装

## 安装布局

```mermaid
flowchart TD
    I["官方安装器"] --> C["~/.obsidian-kb-skill"]
    C --> W["skill/ 写入标准载荷"]
    C --> R["retrieval-skill/ 只读检索载荷"]
    C --> P["runtime.json + 私有 vendor"]

    W --> A["各平台写入入口"]
    R --> B["各平台检索 Skill"]
    P --> A
    P --> B
```

## 平台矩阵

| 平台 | 写入入口 | 检索入口 |
|---|---|---|
| QoderWork / Qoder CLI | `~/.qoderwork/skills/obsidian-knowledge-base/` | `~/.qoderwork/skills/obsidian-knowledge-retrieval/` |
| OpenAI Codex | `~/.agents/skills/obsidian-knowledge-base/` | `~/.agents/skills/obsidian-knowledge-retrieval/` |
| WorkBuddy | `~/.workbuddy/skills/obsidian-knowledge-base/` | `~/.workbuddy/skills/obsidian-knowledge-retrieval/` |
| Claude Code | `~/.claude/skills/obsidian-knowledge-base/` | `~/.claude/skills/obsidian-knowledge-retrieval/` |
| Cursor | `~/.cursor/rules/obsidian-kb.mdc` | `~/.cursor/skills/obsidian-knowledge-retrieval/` |

除 Cursor 外，所有平台的写入与检索都使用原生标准 Skill 目录，按需加载。Cursor 的写入入口仍是常驻规则文件（`.mdc`），因为它没有等价的 Skill 发现机制。

Claude Code 自 v1.26.0 起改为原生 Skill 交付。此前写入 Skill 是 `~/.claude/CLAUDE.md` 里的标记块，会在**每一次对话**中无条件加载完整指令，与惰性加载的设计目标相悖。升级安装会自动移除该遗留块，并保留你自己在该文件中的其他内容；若标记块残缺不全，安装会中止且不修改文件。

## Vault 路径查找顺序

安装器按以下优先级查找：

1. `--vault` / `-VaultPath`
2. 仓库 `.env` 中的 `OBSIDIAN_KB_VAULT`
3. 环境变量 `OBSIDIAN_KB_VAULT`
4. `~/.obsidian-kb-config`

无法可靠确定时，应询问用户，不猜路径。

## 选择平台

macOS / Linux：

```bash
bash install.sh \
  --vault "/你的/Vault" \
  --platforms codex,workbuddy
```

Windows：

```powershell
.\install.ps1 `
  -VaultPath "D:\YourVault" `
  -Platforms "codex,workbuddy"
```

合法平台值：

```text
qoderwork,claude-code,codex,cursor,workbuddy
```

## 选择模板语言

```bash
bash install.sh --vault "/你的/Vault" --locale zh-CN
bash install.sh --vault "/你的/Vault" --locale en
```

Windows 使用 `-Locale zh-CN` 或 `-Locale en`。

已有模板默认保留，因此仅切换 locale 不会覆盖它们。确实需要替换时显式使用 `--force` / `-Force`，并先备份自己的模板修改。

## 安装器会修改什么

用户目录：

- `~/.obsidian-kb-config`
- `~/.obsidian-kb-settings.json`（仅首次创建）
- `~/.obsidian-kb-skill/`
- 所选平台的 Skill 或兼容入口

Vault：

- 创建缺失的标准目录；
- 创建缺失的八个模板；
- 创建缺失的根索引和受管目录索引；
- 创建缺失的 `.obsidian/app.json`。

默认升级不会覆盖已有模板、笔记或用户配置。安装器会从中立目录验证两个 Skill。

## 为什么不建议只复制一个 SKILL.md

标准 Skill 还依赖：

- `references/`
- `scripts/run_helper.py`
- bundled Python modules
- `manifest.json`
- 写入 Skill 的模板 assets

单独复制一个指令文件既不是完整标准 Skill，也不会初始化 Vault。需要手工安装时，应复制完整 Skill 目录并自行保证 Python 3.11+ 与 PyYAML 可用；更推荐官方安装器。

## 升级

```bash
git pull --ff-only
bash install.sh --vault "/你的/Vault"
```

升级后验证：

```bash
python ~/.agents/skills/obsidian-knowledge-base/scripts/run_helper.py \
  doctor --json
python ~/.agents/skills/obsidian-knowledge-retrieval/scripts/run_helper.py \
  doctor --json
```

## 卸载边界

默认卸载：

- 删除产品拥有的 Skill 目录和兼容入口；
- 删除私有 support runtime；
- 安全移除 Claude Code / 旧 AGENTS marker block；
- 保留 Vault、笔记、Vault 路径配置和备份策略配置；
- 保留同级的其他 Skill。

WorkBuddy 卸载只删除产品拥有的 WorkBuddy Skill 目录，不处理其他 Skill。只有显式 config purge 才删除 `~/.obsidian-kb-config` 和 `~/.obsidian-kb-settings.json`。
