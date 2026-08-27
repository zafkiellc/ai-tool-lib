---
name: 加油机强检证书下载工具
description: 加油站强制检定证书批量下载（Windows 便携版）：登录湖北省强制检定计量器具管理信息系统，按账号密码本批量下载每站每把加油枪的强检证书 PDF。Python(Playwright)+本地 HTTP 界面。
agent_created: true
created_by: 单位端 WorkBuddy(win__workbuddy) / 吕晨
created_at: 2026-08-28
permalink: main/工作/项目/资产/ai-工具库/加油机强检证书下载工具/skill
---

# 加油机强检证书下载工具

## Overview
批量下载加油站强制检定证书 PDF。登录 `http://scjg.hubei.gov.cn/hbjl`（湖北省强制检定计量器具管理信息系统），按「账号密码本」Excel 遍历站点，逐站逐枪下载强检证书，支持断点续传、实时日志、停止。纯本地运行（端口 8766），账号密码仅用于登录政府系统不上传。

## 用法
1. 双击 `scripts\启动工具.vbs`（无黑窗）或 `scripts\启动工具.bat`。
2. 浏览器自动开 `http://127.0.0.1:8766`。
3. 选账号密码本 Excel → 勾选站点 → 开始下载。
4. 证书存 `D:/加油机强检证书/<站点名>/枪<枪号>_<证书编号>.pdf`（界面可改输出目录）。
- 首次使用参考 `scripts\账号密码本模板.xlsx`；表头：区分公司|加油站|强检申报账号|密码|...

## 依赖
- Python 3.13 + `pip install playwright openpyxl`。
- 浏览器：Playwright Chromium（设 `PLAYWRIGHT_BROWSERS_PATH` 或默认 `~/AppData/Local/ms-playwright`）；`download_certs.py` 解析 `chromium-1234/chrome-win64/chrome.exe`。
- ⚠️ 本库仅存源码，**未捆绑嵌入 Python**（原 OneDrive 副本 `python/` 含 openpyxl+playwright 便携环境可直接跑）。运行请用自备 Python 3.13 装好依赖后 `python web_launcher.py`。

## 注意事项 / 坑
- 下载中断重点「开始下载」即断点续传，已成功站点自动跳过。
- 停止请点界面「停止」（关浏览器窗口不会停下载）。
- 端口占用=已在运行，浏览器会直接打开已有页。
- 某站无证书=尚未检定/未上传，日志记"无可见证书预览图标"。

## 改造记录
见 `MANIFEST.json` 的 `changelog`。
