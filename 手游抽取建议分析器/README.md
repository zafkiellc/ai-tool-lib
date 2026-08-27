---
title: README
type: note
permalink: main/工作/项目/资产/ai-工具库/手游抽取建议分析器/readme
---

# 手游抽取建议分析器（Gacha Advisor）

多游戏角色强度与抽取建议分析器，覆盖原神、崩坏星穹铁道、绝区零、鸣潮、异环、终末地等手游。

## 声明

本项目为纯 AI（Codex）制作。作者不保证能够及时更新或修复 Bug（作者本人不会编写代码）。

## 功能

- 角色强度、抽取价值、配队与配装建议
- B 站视频/专栏与 NGA 社区证据检索，支持规则分析或可选 AI 分析
- 官方角色数据在线刷新（原神 → ambr.top + api.lunaris.moe，更新后自动补齐最新角色数值）
- 抽卡记录自动导入、保底/概率计算、抽取优先级规划与导出
- 强度雷达图、Tier 榜、多角色横评、本地 AI 结果缓存

## 运行

需要 Python 3.10+，核心功能只使用 Python 标准库。

Windows：

```bat
start.bat
```

macOS：

```bash
./start.command
```

也可以直接运行：

```bash
python launcher.py
```

然后浏览器打开 `http://localhost:8787`。

可选托盘图标依赖：

```bash
pip install pystray pillow pywin32
```

## 目录

```text
backend/   后端服务、数据刷新与各游戏数据源
frontend/  浏览器端界面
data/      角色/官方属性/样本数据
tools/     数据库与打包维护脚本
launcher.py
start.bat / start.command / start.vbs
```

`config.json` 保存在本地，包含 B 站/NGA Cookie 与 AI API Key，已在 `.gitignore` 中排除，不会进入仓库。