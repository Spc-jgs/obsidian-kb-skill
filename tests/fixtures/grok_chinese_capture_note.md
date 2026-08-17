---
source: https://eval.invalid/quartz-runner
author: 原文未署名
published: 原文未标明
capture_depth: standard
related: []
date: '2026-08-17'
type: web-clip
tags:
- web-clip
---

# Quartz Runner setup

## 来源与结论

- **原文链接**：https://eval.invalid/quartz-runner
- **作者**：原文未署名
- **发布日期**：原文未标明
- **剪藏日期**：2026-08-17
- **一句话结论**：用 Python 3.12 安装 Quartz Runner 2.4.1，执行 `quartz init demo`、将 `runner.timeout_ms` 设为 750，再运行 `quartz verify`；成功标准是 `GET /health` 返回 HTTP 200 且 `state=ready`。

## 问题、前提与适用边界

- 原文说明如何安装并验证 Quartz Runner 2.4.1。
- 环境前提：Python 3.12。
- 明确不适用：Quartz Runner 2.4.1 不支持 Python 3.10。
- 端口前提：默认会用到 8080；若被占用，将 `server.port` 设为 `0`。
- 安装介质、操作系统、包管理器、配置文件路径等原文未说明。

## 核心知识与原理

原文给出的可执行事实链是：指定版本安装 → 初始化 demo → 调整超时 → 运行验证 → 用健康检查判定就绪。

- 软件版本：Quartz Runner 2.4.1
- 语言运行时：Python 3.12
- 初始化：`quartz init demo`
- 超时配置：`runner.timeout_ms=750`
- 验证命令：`quartz verify`
- 成功判据：`GET /health` 返回 HTTP 200，且 `state=ready`
- 端口冲突处理：8080 被占用时设置 `server.port=0`
- 失败边界：2.4.1 不支持 Python 3.10

原文未解释 `runner.timeout_ms`、`server.port=0` 的语义、`/health` 的其余字段，也未说明 `quartz verify` 的内部行为。

## 具体做法与示例

按原文顺序：

1. 安装 Quartz Runner 2.4.1，并使用 Python 3.12。安装命令原文未给出。
2. 运行 `quartz init demo`。
3. 设置 `runner.timeout_ms=750`。配置落点原文未说明。
4. 执行 `quartz verify`。
5. 若 8080 被占用，设置 `server.port=0`。原文未说明该设置相对 `quartz verify` 的先后顺序。

## 验证、风险与限制

成功标准（原文）：

- `GET /health` 返回 HTTP 200
- 且 `state=ready`

失败与限制（原文）：

- Python 3.10 不被 Quartz Runner 2.4.1 支持
- 8080 被占用时需要设置 `server.port=0`

原文未提供非 200 时的排错、`state` 的其他取值，或 `quartz verify` 的退出码。

## 理解与启发

- 版本与运行时要一起钉死：原文把 2.4.1 和 Python 3.12 绑定，并单独排除 3.10。
- 验证要以可观察的健康检查为准，而不是只看命令是否跑完。
- 端口冲突是已记录的边界，用 `server.port=0` 处理，而不是假设 8080 一定可用。

## 关联笔记

当前 Vault 中没有与本主题高置信度相关的既有笔记。
