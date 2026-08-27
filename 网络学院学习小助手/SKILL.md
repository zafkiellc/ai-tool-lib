---
name: 网络学院学习小助手
description: 本地网页版多账号自动学习工具（SIA 中石化网络学院等）：批量账号+课程链接，自动登录、自动播放、断点续播、实时进度日志。用于批量刷课自动化。
agent_created: true
created_by: Hermes(软路由) / 原作 WorkBuddy(吕晨)
created_at: 2026-08-27
permalink: main/工作/项目/资产/ai-工具库/网络学院学习小助手/skill
---

# 网络学院学习小助手

## Overview
本地网页版多账号自动学习工具：批量账号 + 课程链接，自动登录、自动播放、实时日志。技术栈 Node.js + Express + Playwright，纯本地运行（端口 3000，被占用自动换）。核心能力：多账号批量刷课、SIA 中石化网络学院模板、自动/手动登录、播放进度日志（30s/10%）、单节最长、定时滚动防掉线、视频断点续播自动识别、已通过课程智能跳过。

## 用法
- 启动：双击 `start.bat`（自动开 `http://127.0.0.1:3000`）；异常先跑 `check-env.bat` → `smoke-test.cmd`。
- 分发：`outputs\网络学院学习小助手-windows.zip`（38.3MB 减包版，解压即用）。
- 配置：账号/课程存 `data\tasks.json`（仅本地）；SIA 课程链接直接粘贴播放页 URL。
- 任务配置项（tasks.json）：`name`/`loginUrl`/`loginMode`/`headless`/`videoSelector`/`maxMinutesPerLesson`/`autoNext`/`keepAlive`/`accounts[]`/`courses[]`。详见 `references/原笔记.md` 的「配置手册」节。

## 依赖
- Node.js 20.19.3（内置）+ Express + Playwright 1.62.1。
- 浏览器：默认 auto = 优先系统 Edge → 回退内置 Chromium（减包后本机走系统 Edge，zip -89%）。
- ⚠️ `accounts[].password` 明文存本机，不要外传。

## 注意事项 / 坑
- 已通过课程重头学 bug 已修（首检+30s 复核，累计时长达标即提前完成）。
- 非 SIA 平台依赖通用选择器，跨平台使用前先验证。
- 长期运行需自己双击 start.bat（WorkBuddy 会话结束后台服务会停）。
- 同事电脑若装 Chrome 可手动指定「系统 Chrome」通道。

## ⚠️ 源码位置（已入册，2026-08-28）
源码已由 **单位端 WorkBuddy(win__workbuddy)** 从 `C:\Users\zafki\OneDrive\工作\工作工具\网络学院学习小助手` 复制进本库 `scripts/`（Node 源码 + 启动脚本；`node_modules`/`outputs` 未入库，运行前需 `npm install`）。
- **启动**：`scripts\start.bat`（自动开 `http://127.0.0.1:3000`）；异常先 `check-env.bat` → `smoke-test.cmd`。
- **依赖**：Node.js 20 + `npm install`（Express + Playwright）；浏览器走系统 Edge / 内置 Chromium。
- 本机 OneDrive 副本保留为日常运行副本。

## 改造记录
见 `MANIFEST.json` 的 `changelog`。完整历史与改进思路见 `references/原笔记.md`。
