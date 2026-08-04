# 故障排查

## 先运行 doctor

写入 Skill：

```bash
python <write-skill-root>/scripts/run_helper.py doctor --json
```

检索 Skill：

```bash
python <retrieval-skill-root>/scripts/run_helper.py doctor --json
```

doctor 检查：

| 检查项 | 含义 |
|---|---|
| `manifest` | manifest 结构与版本是否有效 |
| `payload` | 文件是否缺失、多余或哈希漂移 |
| `runtime` | Python 3.11+ runtime 是否可执行 |
| `dependencies` | PyYAML 与 bundled modules 是否可导入 |
| `resources` | references、runner 和模板资源是否完整 |

## `not an Obsidian Vault`

确认目标目录：

- 存在；
- 是目录而不是文件；
- 包含 `.obsidian/`；
- symlink 最终指向真实目录。

然后显式传入路径：

```bash
bash install.sh --vault "/正确的/Vault"
```

## Agent 看不到新 Skill

1. 确认使用了当前平台的正确发现目录；
2. 检查完整 Skill 目录而不是只有 `SKILL.md`；
3. 运行 installed doctor；
4. 关闭并新建一个 Agent 任务。

多数 Agent 在任务开始时加载 Skill 列表；安装后当前会话不一定热更新。

## doctor 报 payload drift

可能原因：

- 手工编辑了生成的 `SKILL.md`；
- 安装中断；
- 旧文件未清理；
- symlink 指向旧 checkout。

重新运行官方安装器。不要直接改 installed payload，也不要删除 Vault。

## Python 或 PyYAML 不可用

要求 Python 3.11+。可显式指定：

```bash
export OBSIDIAN_KB_PYTHON=/path/to/python3
bash install.sh --vault "/你的/Vault"
```

安装器会把缺失的 PyYAML 安装到 `~/.obsidian-kb-skill/vendor`，不会污染项目环境。

## 检索没有结果

依次检查：

1. `vault-info` 是否看到预期 Markdown 数量；
2. 是否错误使用了过窄 `--scope`；
3. 目标是否位于 `Templates/`、`Attachments/` 或隐藏目录；
4. 查询是否使用了笔记中实际出现的标题、别名、标签或术语；
5. `issues` 是否报告损坏或无法读取的关键笔记。

词法 v1 不保证同义词召回。详情见[只读检索](retrieval.md)。

## 检索结果看起来不相关

- `score` 是排序分，不是置信度；
- 查看 `signals` 了解命中字段；
- 优先相信直接回答问题的片段；
- 使用更具体的实体名、版本号、缩写或目录 scope；
- 不要根据一个弱结果声称“Vault 里就是这样”。

## 创建笔记被拒绝

常见原因：

- 用户没有明确写入意图；
- 目标目录不存在，需要先走 `create-category`；
- Git 分支发生分歧或冲突；
- 自定义模板在发现后又被修改；
- 深度文章来源不完整；
- frontmatter 无效；
- 目标路径越出 Vault 或经过外部 symlink。

优先读取结构化错误，不要绕过预检临时写脚本。

## `--from-preflight` 被拒绝

预检暂存的内容按渲染结果的哈希索引，正式写入前会重新渲染并重新校验，因此拒绝
说明确实发生了变化，而不是校验过严：

- `unknown-preflight-content`：条目已过期（默认 24 小时）或不在本机，按提示重传
  正文即可；
- `preflight-vault-mismatch` / `preflight-context-mismatch`：这份内容是为另一个
  Vault、另一种笔记类型或另一个标题预检的；
- `preflight-content-changed`：预检之后日期、标签或 Vault 模板变了，重跑预检并
  使用新哈希。

暂存目录默认是 `~/.obsidian-kb-preflight`，可用 `OBSIDIAN_KB_PREFLIGHT_CACHE`
指向别处；删除它是安全的，只会让下一次写入回到重传正文。

## 模板没有更新

这是默认安全行为。普通升级保留已有模板。确认要覆盖后：

```bash
bash install.sh --vault "/你的/Vault" --force
```

`--force` 会刷新模板，应先保存自己的模板改动。

## Folder Index 图谱不连通

Folder Index 1.0.30 需要受管非根目录使用目录同名索引，例如：

```text
20-Learning/20-Learning.md
```

统一使用 `INDEX.md` 或自定义同名文件可能无法形成父子图谱边。根索引仍可使用 `INDEX.md`。

## 隐私问题

helper 本身不调用云 API。检索 v1 也不使用 embedding 或持久索引。

但是云端 Agent 可能把它读取的笔记片段发送给模型提供商。需要端到端本地处理时，还必须选择本地 Agent/模型，而不只是本地 helper。

## 仍然无法解决

提交问题时请提供：

- 操作系统与 Agent 平台；
- 安装版本；
- 已脱敏的 doctor JSON；
- 执行命令和退出码；
- 是否从非仓库目录复现；
- Vault 是否使用 Folder Index、Dataview、自定义模板或 Git；
- 不包含私人笔记正文的最小复现。
