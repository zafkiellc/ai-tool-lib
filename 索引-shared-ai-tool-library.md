---
tags:
- 索引
- 工具库
- Hermes-skill
- 跨AI
created: 2026-08-27
status: ✅
permalink: main/工作/项目/资产/ai-工具库/索引-shared-ai-tool-library
---

# 索引：Hermes 自建 skill — shared-ai-tool-library

> 本笔记是**索引**，不复制框架代码。Hermes 框架自带 skill 必须留在 `/data/.hermes/skills/` 原路径（agent 从固定路径加载），只在此建索引指向，避免污染 [[AI工具库]]。

## 它是什么
- 位置：`/data/.hermes/skills/software-development/shared-ai-tool-library/`（Hermes 框架 skills 目录内，属用户自建、带 `agent_created` 标记）
- 作用：早期探索"在 vault 内建同步+git 版本化的 AI 工具库"的 skill，与 [[AI工具库]] 思路一致。
- 内含：`SKILL.md`、`templates/`(SKILL.md+MANIFEST.json)、`scripts/sessionctl.py`、`references/`(verysync-git-coexist / session-index / cross-endpoint-access / endpoint-path-and-verify-pitfalls)。

## 与 AI工具库 的关系
- **理念已固化**：其设计（verysync 工作区 + 本地 git、`.git` 忽略、认领锁、跨端接入）已被我们在 [[AI工具库]] 真正落地并验证（含真·DSH 跨端实测）。
- **不复制进库**：框架层 skill 保留原位，本库只收"可复用工具成品"。此索引用于追溯来源、避免重复造轮子。
- 若将来要增强 `sessionctl.py`，可回看它的 `references/session-index.md` 等设计文档取长补短。

## 关联
- [[AI工具库/README]]
- [[SESSIONS]]（共享会话索引，已落地版）
- [[协作协议]]