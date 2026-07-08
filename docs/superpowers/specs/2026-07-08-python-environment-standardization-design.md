# Python 环境标准化设计

## 目标

消除系统 Python、pyenv Python、项目虚拟环境和 CI 之间的版本歧义，让开发者只使用一套明确命令即可重建、测试和验证项目。

## 决策

### 解释器分层

- 不修改、不删除 macOS 管理的 `/usr/bin/python3`。
- 用户 shell 由 pyenv 管理，默认版本为 CPython 3.14.6。
- 修正 Zsh 登录与交互初始化，让 pyenv shims 位于 `/usr/bin` 之前；`python` 与 `python3` 都应解析到 3.14.6。
- 项目命令统一写成 `python`；自动化与文档首选 `uv run python`，不依赖调用者 PATH 中的裸 `python3`。

### 项目版本

- 新增 `.python-version`，固定默认开发解释器为 `3.14.6`。
- `pyproject.toml` 的最低支持版本从 3.9 提升到 3.11。Python 3.9 已结束安全支持，不再作为项目兼容目标。
- CI 使用 Python 3.11 与 3.14 矩阵：3.11 验证最低版本，3.14 验证默认开发版本。

### 依赖与虚拟环境

- uv 是首选项目环境管理器。
- 提交 `uv.lock`，开发者使用 `uv sync --extra dev --locked` 创建可复现的 `.venv`。
- 测试统一使用 `uv run --locked python -m pytest`。
- 保留标准库 venv + pip 备用方案，但必须先运行
  `python -m pip install --upgrade pip setuptools wheel`，再执行 editable install。
- 本地现有 Python 3.9 `.venv` 视为可丢弃构建产物，发布后用 3.14.6 重建。

### pytest

- 在 pytest 配置中显式加入仓库根目录到 `pythonpath`。
- `pytest` 与 `python -m pytest` 两种入口都必须通过，项目文档仍使用更明确的 `python -m pytest`。

### CI

- 使用官方 `astral-sh/setup-uv` action 的固定提交，避免浮动 tag。
- matrix 中通过 action 的 `python-version` 覆盖 `.python-version`。
- 使用 `uv sync --locked --extra dev` 后执行构建同步检查与测试。

## 本机 Shell 配置

`~/.zprofile` 负责登录 shell 的 pyenv shims：

```zsh
export PYENV_ROOT="$HOME/.pyenv"
[[ -d "$PYENV_ROOT/bin" ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
```

`~/.zshrc` 保留交互式集成：

```zsh
export PYENV_ROOT="$HOME/.pyenv"
[[ -d "$PYENV_ROOT/bin" ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - zsh)"
```

修改前备份两个文件。不得添加 `alias python=...` 或覆盖系统二进制；版本选择只由 pyenv 完成。

## 验证标准

1. 新登录 Zsh 中 `python` 与 `python3` 都是 3.14.6，路径均经过 pyenv shims。
2. `uv run python --version` 返回 3.14.6。
3. `.venv/bin/python` 返回 3.14.6。
4. `pytest` 与 `python -m pytest` 均通过。
5. 显式 Python 3.11 和 3.14 环境均通过全量测试。
6. `uv lock --check`、`build.py --check`、Bash 语法检查和 Git 状态检查通过。

## 参考依据

- pyenv 官方说明：通过把 shims 放到 PATH 最前面拦截 `python`、`pip` 等命令。
- Python 官方 venv 文档：虚拟环境应可删除并重建，使用 `python -m venv` 创建。
- uv 官方项目文档：使用 `.python-version`、`uv.lock`、`uv sync` 与 `uv run` 管理可复现环境。
- GitHub 官方文档：CI 应显式设置 Python 版本，并用矩阵验证多个版本。
