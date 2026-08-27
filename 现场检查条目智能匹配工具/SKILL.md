---
name: 现场检查条目智能匹配工具
description: 油气卡异常筛查 Web 工具：覆盖加油卡/石化钱包异常数据明细，规则引擎(A–I)智能匹配现场检查条目。Python(openpyxl)后端+HTML/JS 前端，端口 8720/8721。
agent_created: true
created_by: Hermes(软路由) / 原作 WorkBuddy(吕晨)
created_at: 2026-08-27
permalink: main/工作/项目/资产/ai-工具库/现场检查条目智能匹配工具/skill
---

# 现场检查条目智能匹配工具

## Overview
油气卡异常筛查。覆盖「加油卡异常数据明细表」(3147 笔) 与「石化钱包异常数据明细表」(98273 笔)。技术栈 Python Web（openpyxl 后端 + HTML/JS 前端），端口 8720/8721。规则 A–I 已落地（F/G/H/I 默认启用）：混用消费确认、同客户短时换牌、单次升数超常、员工异常用券等。

## 用法
1. 进入源码目录（见下「源码位置」）。
2. 运行 `server.py`（端口 8720/8721）。
3. 浏览器访问 `http://localhost:8720`（或 8721）。
4. 随机问题清单：无表头 Excel `[问题描述, 一级分类]`，须与 `_extract_rows` 严格兼容。
5. 异常筛查：规则 A–I。

## 依赖
- Python（便携版复用 WorkBuddy CPython 3.13.12）+ openpyxl。
- 前端内嵌 JS（HTML 内嵌，无需独立构建）。

## 注意事项 / 坑
- 随机补足每次一样 → 前端 `fillSig` 缓存错觉，手动点补足重排。
- DeepSeek 返回 null → 模型名非官方(`deepseek-chat`/`deepseek-reasoner`)，`_call_llm` 已显式抛错。
- 上传后数据变少 → `seen` 误跳已有条目，已修 `merged_norms`。
- 改动不生效 → 旧 server 占端口，`taskkill /f /pid <旧PID>` 重启。
- CSV 中文乱码 → GBK/GB18030，`_decode_text` 自动识别。
- 视频督导模式 `video_mode`、固定/锁定条目(📌)、上传接口 3 列 GBK 防丢、真随机校验均已落地（2026-08-27）。
- 完整坑速查与迭代要点见 `references/原笔记.md` 第三/七节。

## ⚠️ 源码位置（重要）
**源码当前不在本工具库，而在源端本机**：`D:/巡站724_便携版/`（server.py + ai_lib.py + inspector_matcher.html）。
本库只收纳文档与统一入口。若要各端可继续优化代码，需把源码目录纳入本库 `scripts/`（由源端复制进来）。

## 改造记录
见 `MANIFEST.json` 的 `changelog`。完整迭代要点与待办见 `references/原笔记.md`。
