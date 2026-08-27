---
name: 手游抽取建议分析器
description: 多游戏角色强度与抽取建议分析器（原神/星铁/绝区零/鸣潮/异环/终末地等）。当需要根据角色强度、配队配装、B站/NGA 证据与抽卡记录做抽取价值与优先级规划时使用。纯本地 Web 服务，核心仅用 Python 标准库。
agent_created: true
created_by: desktop/codex (session codex-desktop-20260827a1)
created_at: 2026-08-28
permalink: main/工作/项目/资产/ai-工具库/手游抽取建议分析器/skill
---

# 手游抽取建议分析器（Gacha Advisor）

## Overview
多游戏角色强度与抽取建议分析器。提供角色强度 / 抽取价值 / 配队配装建议，B站视频专栏与 NGA 社区证据检索（规则或可选 AI 分析），官方角色数据在线刷新（原神 ambr.top + api.lunaris.moe），抽卡记录导入、保底/概率计算、抽取优先级规划与导出，强度雷达图 / Tier 榜 / 横评 / 本地 AI 结果缓存。

## 用法
入口文件：`launcher.py`。

- 运行：`python launcher.py`（或 `start.bat` / `start.command` / `start.vbs`）。
- 启动后浏览器打开 `http://localhost:8787`。
- 可选系统托盘图标依赖：`pip install pystray pillow pywin32`（不装也不影响核心 Web 功能）。

## 依赖
- Python 3.10+；核心功能仅用 Python 标准库。
- 目录：`backend/` 后端服务与数据源、`frontend/` 浏览器界面、`data/` 角色与样本数据、`tools/` 维护脚本、`launcher.py` 入口。

## 注意事项 / 坑
- `config.json` 中的凭据已**脱敏为占位符**（B 站 `SESSDATA`、NGA_COOKIE、DeepSeek `api_key`）。若要启用「B站/NGA 证据检索」与「在线 AI 分析」，请把对应占位符替换为自己的凭据；不填凭据时核心强度分析/本地数据功能仍可用。
- `config.json` 在原项目 `.gitignore` 中（上游不入库）；本库为让工具开箱即跑，已 **force-add 脱敏后的 config.json** 作为模板，且其中不含任何真实密钥。你在本机填入的真实凭据不会被普通 `git add` 提交（仍受该 .gitignore 约束），请放心。
- 代码原位于本机 `E:\手游抽取建议分析器`，现整体迁入本库。跨端拉取后 `python launcher.py` 即可运行。

## 改造记录
见 `MANIFEST.json` 的 `changelog`。
