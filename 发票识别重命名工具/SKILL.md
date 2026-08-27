---
name: 发票识别重命名工具
description: 电子发票 PDF/XML 批量识别与配对重命名（Windows/Mac 便携版）：从备注栏识别站点+项目、识别价税合计与发票号，按"备注名_总金额_发票号"统一重命名，支持 ZIP 混合包解压重命名。Node.js 本地服务。
agent_created: true
created_by: 单位端 WorkBuddy(win__workbuddy) / 吕晨
created_at: 2026-08-28
permalink: main/工作/项目/资产/ai-工具库/发票识别重命名工具/skill
---

# 发票识别重命名工具

## Overview
批量识别电子发票：从发票备注栏识别"xx加油站/xx充电站"和项目内容，识别价税合计总金额与发票号码，按发票号码把 PDF/XML/单文件 ZIP 配对，统一重命名为"备注名_总金额_发票号"。支持文件夹/文件选择、扫描预览、人工确认黄色"需确认"项、原位置重命名或输出到文件夹、重复执行跳过已存在文件。Node.js 本地服务（端口 27180）。

## 用法
- Windows：双击 `scripts\启动工具.bat`（自动开 `http://127.0.0.1:27180`）。
- Mac：双击 `scripts\启动工具.command`（或 `mac版/发票识别重命名工具.app`）。
- 选文件夹/文件 → 开始扫描 → 预览 → 执行重命名。
- 命名模板 `{remark}_{amount}_{invoice}`（变量 remark/station/project/amount/invoice 可在界面改）。

## 依赖
- Node.js 20（本库未捆绑 `runtime/` 便携 node；原 OneDrive 副本含 `runtime/win/node.exe` 可直接跑 Windows 版）。
- `npm install`（adm-zip / iconv-lite / pdf-parse，纯 JS 小依赖；运行前 `npm install` 即可）。
- ⚠️ 面向文字版电子发票，扫描图片发票需先 OCR。

## 注意事项 / 坑
- 重复执行默认跳过内容相同的已存在文件（防生成"名称 (2)"）。
- 执行前再次确认；建议用"输出到文件夹"模式保留原始数据。
- 窗口一闪而过→确认 `runtime\win\node.exe` 与 `app\server.js` 存在（完整解压）。

## 改造记录
见 `MANIFEST.json` 的 `changelog`。
