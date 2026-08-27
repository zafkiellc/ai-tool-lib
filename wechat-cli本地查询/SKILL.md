---
name: wechat-cli 本地微信数据查询
description: macOS 上查询本地微信数据（聊天记录检索等）的 CLI 工具，用于工作核查。直接读本地微信数据库，无需联网/登录态。
agent_created: true
created_by: Hermes(软路由) / 原作 WorkBuddy(吕晨)
created_at: 2026-08-27
permalink: main/工作/项目/资产/ai-工具库/wechat-cli本地查询/skill
---

# wechat-cli 本地微信数据查询

## Overview
在 macOS 上查询本地微信数据（聊天记录检索等），用于工作核查。版本 v0.2.4，pip 安装于 `~/.local/venvs/wechat-cli-arm64/`，平台 macOS（Apple Silicon / arm64）。直接读本地微信数据，无需联网/登录态。已在多次核查任务中复用（如厕所水枪安装核实）。

## 用法
1. 激活 venv：`source ~/.local/venvs/wechat-cli-arm64/bin/activate`
2. 运行 wechat-cli 查询命令（具体子命令待补充）。
3. 常用：检索聊天关键词（如核查「水枪」安装安排）、导出聊天记录。

## 依赖
- Python venv `~/.local/venvs/wechat-cli-arm64/`
- 安装：`pip install wechat-cli==0.2.4`（于上述 venv）
- 平台：macOS arm64

## 注意事项 / 坑
- 具体子命令与微信数据库解密/权限问题待补充（见 `references/原笔记.md` 待办）。
- 待封装为更顺手的入口（原笔记建议封装为 WorkBuddy skill 便于一句话触发）。

## ⚠️ 源码位置（重要）
**本工具是 pip 安装的第三方包（wechat-cli），不在本工具库**，安装在 Mac 端 venv。本库只收纳使用说明与统一入口。若要各端复用，在各自 Mac 装同包即可。

## 改造记录
见 `MANIFEST.json` 的 `changelog`。
