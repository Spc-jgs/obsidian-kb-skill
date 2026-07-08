# 标准 Agent Skill 入口设计

## 背景

obsidian-kb-skill 当前把可发现的 `SKILL.md` 生成到
`platforms/qoderwork/SKILL.md`。Codex 本机安装为了复用该文件，将
`~/.agents/skills/obsidian-knowledge-base` 软链接到 QoderWork 适配目录。
文件格式可以工作，但目录语义不正确：平台无关的 Agent Skill 不应由某个
具体平台的适配目录充当规范入口。

Codex 的用户级 Skill 发现路径为
`~/.agents/skills/<skill-name>/SKILL.md`，并支持 Skill 目录软链接。
仓库需要提供一个符合开放 Agent Skills 格式、与具体平台无关的规范目录，
同时避免破坏现有 QoderWork、Claude Code、Codex 和 Cursor 用户。

## 目标

发布 v1.7.0，提供唯一的标准 Agent Skill 入口：

```text
skills/obsidian-knowledge-base/SKILL.md
```

该文件由 `core/OBSIDIAN_KB.md` 和专用 header 自动生成。Codex 与
QoderWork 安装器都消费这一标准产物；现有平台适配文件继续生成并保留，
作为兼容入口。完成发布后，本机共享 Skill 软链接改为指向标准目录。

## 非目标

- 本版本不把仓库改造成 Codex Plugin。
- 本版本不删除任何 `platforms/*` 适配文件。
- 本版本不改变知识沉淀、Folder Index、Dataview 或 Git 工作流。
- 本版本不把完整 Git 仓库复制进 `~/.agents/skills`。
- 本版本不承诺所有 Agent 都自动扫描 `~/.agents/skills`；发现路径仍由
  各平台决定。

## 架构

### 单一内容来源

`core/OBSIDIAN_KB.md` 继续保存共享正文。新增
`skills/obsidian-knowledge-base/header.md`，包含开放 Agent Skills 所需的
`name`、`description` 和标题。构建器将 header 与核心正文组合，生成
`skills/obsidian-knowledge-base/SKILL.md`。

`skills/obsidian-knowledge-base/SKILL.md` 是平台无关的规范 Skill 产物，
但仍是生成文件，不能直接编辑。现有四个平台适配器继续由相同核心生成。
这样不引入第二份手工维护的 Skill 正文。

### 构建模型

`build.py` 的目标模型从“平台名 + 输出文件”扩展为带有以下字段的目标：

- 目标标识，用于日志和生成注释。
- header 路径。
- 输出路径。

标准 Skill 和四个平台适配器使用同一构建函数。生成注释必须准确指出各自
header 的真实路径，不再假定 header 一定位于 `platforms/<name>/`。
`python build.py --check` 必须同时检查五个产物。

### 安装行为

#### Codex

Bash 和 PowerShell 安装器将标准 Skill 复制到：

```text
~/.agents/skills/obsidian-knowledge-base/SKILL.md
```

安装器不再默认向 `~/AGENTS.md` 注入整份 Codex 适配器。已有
`platforms/codex/AGENTS.md` 保留为手工安装与兼容产物。本版本不会主动
删除用户已有的 marker-wrapped `~/AGENTS.md` 内容，避免升级时修改用户
全局指令；卸载器仍可移除由旧版安装器创建的 marker block。

#### QoderWork

QoderWork 的目标路径保持：

```text
~/.qoderwork/skills/obsidian-knowledge-base/SKILL.md
```

但复制来源改为标准
`skills/obsidian-knowledge-base/SKILL.md`，不再复制
`platforms/qoderwork/SKILL.md`。

#### Claude Code 与 Cursor

保持当前平台安装行为，不迁移到 `~/.agents/skills`。它们继续消费各自
适配产物，避免把 Codex 的用户级发现约定误当成所有 Agent 的通用发现路径。

### 卸载行为

- 删除 `~/.agents/skills/obsidian-knowledge-base`。
- 删除 QoderWork 的对应 Skill 目录。
- 保留现有 Cursor、Claude Code 和旧 Codex marker block 清理逻辑。
- 不删除 `~/.agents`、`~/.agents/skills` 或其他 Skill。
- 不删除 Git checkout。

### 本机共享安装

发布后，完整仓库继续位于：

```text
~/.agents/obsidian-kb-skill
```

共享发现入口调整为：

```text
~/.agents/skills/obsidian-knowledge-base
  -> ../obsidian-kb-skill/skills/obsidian-knowledge-base
```

软链接目标必须检出 v1.7.0 tag 对应提交。这样两个 Codex 账号共享同一
用户级 Skill，同时仓库更新和 Skill 发现保持分离。

## 兼容性

- `platforms/qoderwork/SKILL.md` 继续生成，旧安装说明和直接引用暂时有效。
- `platforms/codex/AGENTS.md` 继续生成，手工使用者不受影响。
- 标准 Skill 与 QoderWork Skill 的正文和 frontmatter 必须等价；只允许
  生成注释中的来源路径不同。
- v1.7.0 的安装器升级必须是幂等的，重复执行不能创建嵌套目录或重复文件。
- Windows PowerShell 和 Bash 行为保持对等。

## 测试策略

### 构建测试

先增加失败测试，证明当前构建目标中不存在标准 Skill。测试覆盖：

- 标准 Skill 是 `build.py` 的正式生成目标。
- header 路径和输出路径不依赖 `platforms/<name>` 假设。
- `--check` 检测标准 Skill 漂移。
- 五个生成产物均与核心正文同步。
- 标准 Skill frontmatter 包含合法的 `name` 和 `description`。

### 安装器测试

先增加失败测试，证明当前安装器仍从 QoderWork 目录复制，并向
`~/AGENTS.md` 注入内容。测试覆盖：

- Bash Codex 安装创建 `~/.agents/skills/obsidian-knowledge-base/SKILL.md`。
- Bash QoderWork 安装复制标准 Skill。
- Bash 卸载只删除本 Skill，不影响同级 Skill。
- PowerShell 脚本静态契约与 Bash 一致。
- 重复安装结果相同。

### 发布验证

- 全部 pytest 测试通过。
- `python build.py --check` 通过。
- `bash -n install.sh` 通过。
- 在临时 HOME 中完成 Bash 安装/升级/卸载 smoke test。
- 版本字段、CHANGELOG 和中英文 README 均为 v1.7.0。
- GitHub tag、Release、远端 master 和本机共享 checkout 指向同一提交。
- 本机 `~/.agents/skills/obsidian-knowledge-base/SKILL.md` 可读，软链接目标
  不含 `platforms/qoderwork`。

## 成功标准

1. 仓库存在平台无关的标准 Skill 目录和自动生成的 `SKILL.md`。
2. Codex 和 QoderWork 安装均以标准 Skill 为来源。
3. 旧平台适配路径继续存在，不造成破坏性升级。
4. 本机共享软链接指向标准 Skill 目录。
5. v1.7.0 已测试、推送、打 tag 并发布。
