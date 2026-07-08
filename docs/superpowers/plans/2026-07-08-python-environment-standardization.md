# Python Environment Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 pyenv + uv 统一 Python 3.14.6 默认开发环境，并在 CI 中验证 Python 3.11/3.14。

**Architecture:** pyenv 只管理用户 shell 的解释器选择，uv 管理项目锁文件和 `.venv`，GitHub Actions 使用同一 lockfile 运行最低/默认版本矩阵。系统 Python 保持不动。

**Tech Stack:** CPython 3.11/3.14、pyenv、uv、pytest、GitHub Actions、Zsh

## Global Constraints

- 不覆盖 `/usr/bin/python3`。
- 默认开发版本为 3.14.6，最低支持版本为 3.11。
- 项目命令统一使用 `python` 或 `uv run python`。
- `uv.lock` 必须提交并在 CI 中以 locked 模式使用。
- Shell 配置修改前必须备份。

---

### Task 1: 项目环境契约

**Files:**
- Create: `.python-version`
- Create: `uv.lock`
- Modify: `pyproject.toml`
- Create: `tests/test_environment_contract.py`

- [ ] 先写失败测试，断言默认版本、最低版本、pytest pythonpath 和 CI matrix。
- [ ] 运行测试，确认当前缺少 `.python-version` 且版本仍为 `>=3.9`。
- [ ] 添加 `.python-version=3.14.6`，更新 `requires-python >=3.11` 和 pytest `pythonpath=["."]`。
- [ ] 运行 `uv lock` 生成 lockfile，并验证 `uv lock --check`。
- [ ] 验证 `pytest` 与 `python -m pytest` 均通过。
- [ ] 提交：`build: standardize Python project environment`。

### Task 2: CI Python 矩阵

**Files:**
- Modify: `.github/workflows/check.yml`
- Modify: `tests/test_environment_contract.py`

- [ ] 先让契约测试要求 3.11/3.14 matrix、固定 setup-uv action 和 locked sync。
- [ ] 确认测试因旧 `python-version: "3.x"` 工作流失败。
- [ ] 使用 setup-uv 固定提交，配置 3.11/3.14 matrix。
- [ ] CI 命令使用 `uv sync --locked --extra dev`、`uv run --no-sync python build.py --check` 和 `uv run --no-sync python -m pytest`。
- [ ] 运行契约测试和全量测试。
- [ ] 提交：`ci: test locked Python version matrix`。

### Task 3: 开发文档

**Files:**
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_environment_contract.py`

- [ ] 先写失败测试，禁止贡献指南使用裸 `pip install`、`pytest` 或 `python3`。
- [ ] 增加 uv 首选流程和升级 pip 的 venv 备用流程。
- [ ] 记录 Python 3.14.6 默认值、3.11 最低值和 CI matrix。
- [ ] 更新 CHANGELOG 的 Unreleased 环境标准化条目。
- [ ] 运行全量测试、构建同步和文档契约检查。
- [ ] 提交：`docs: document reproducible Python development`。

### Task 4: 合并、Shell 与本地环境

**Files:**
- Modify: `~/.zprofile`
- Modify: `~/.zshrc`
- Recreate: repository `.venv`

- [ ] 合并 feature branch 到 master 并在合并结果上复验。
- [ ] 推送 master。
- [ ] 备份 `.zprofile` 与 `.zshrc`，加入幂等 pyenv 初始化块。
- [ ] 保持 `pyenv global 3.14.6` 并执行 `pyenv rehash`。
- [ ] 用 `uv sync --extra dev --locked` 重建 `.venv`。
- [ ] 在新登录 Zsh 中验证 `python`、`python3`、pip 和 pyenv 路径一致。
- [ ] 运行 3.11/3.14 全量测试以及最终 Git/lock/build 检查。
