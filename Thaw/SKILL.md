---
name: Thaw（macOS 菜单栏工具 / Ice fork）
description: macOS 菜单栏管理工具（Ice fork），本地抓取 macOS 27 预览版源码并构建发布版；本机已构建安装 Thaw Preview.app。源码随统一库版本化，各端可复用构建。
agent_created: true
created_by: mac/Codex（源码物理迁入自 ~/WorkBuddy/2026-07-21-11-46-05/Thaw/）
created_at: 2026-08-28
permalink: main/工作/项目/资产/ai-工具库/thaw/skill
---

# Thaw（macOS 菜单栏工具 / Ice fork）

> 注：本目录为**源码真源**（已排除 1.5G 的 `Build/` 构建产物与嵌套 `.git`）。本地已构建安装版见 `/Applications/Thaw Preview.app`。

## Overview
- macOS 菜单栏管理工具，**Ice 的 fork**（上游公开仓库），用于本地抓取 macOS 27 预览版源码并构建发布版。
- 技术栈：Swift / SwiftUI + Xcode + create-dmg。
- 本机状态：✅ 稳定版已构建安装（Build 47，`development` 分支；产物 `Thaw_2.0.0-rc.1.dmg` 约 8MB）。
- `feat/macos-27-experimental` 分支因编译器限制暂缓（见注意事项）。

## 用法
### A. 库内源码构建（推荐，单一真源）
```bash
cd "$LIB/Thaw/scripts/Thaw"
# 方式 1：Xcode 打开工程构建
open Thaw.xcodeproj   # 选 development 分支 → 构建
# 方式 2：未签名本地构建 + DMG + 自动安装
./scripts/build-preview.sh
```
> `$LIB` = vault 内 `工作/项目/资产/AI工具库`。

### B. 本机日常入口（macOS）
已构建安装：`/Applications/Thaw Preview.app`（来自 `~/WorkBuddy/2026-07-21-11-46-05/Thaw/` 的构建产物，本机日常用，勿删）。

## 依赖
- macOS（本机 27.0 Golden Gate, 26A5378n，Apple M1 Max）。
- Xcode 26.6（App Store 稳定版）；工具 `xcodes` / `mas` / `gh`。
- `create-dmg`（打包 DMG）；`osascript` 用于无终端取 sudo。
- Homebrew 在 macOS 27 beta 不可用（bottle 仅支持 Tahoe/26），需直接下载二进制。
- 如需正式发布：签名 / 公证（notarize）流程待完善。

## 注意事项
- ⚠️ `feat/macos-27-experimental` 在 Xcode 26.6 构建失败：AppIcon.icon 是 macOS 27 Icon Composer 格式 + PlatformRuntimeKit 的 swiftmodule 由 Swift 6.4 编译，与 26.6 的 6.3.3 不兼容。**当前用 `development` 分支**（不依赖 PlatformRuntimeKit）成功。
- 跨编译器版本不兼容：二进制 `.swiftmodule` 需 `BUILD_LIBRARY_FOR_DISTRIBUTION=YES`（提供 `.swiftinterface`）才能跨版本复用。
- 本目录仅含源码（12MB）；本机运行实例 `/Applications/Thaw Preview.app` 与 `~/WorkBuddy/.../Thaw/` 构建缓存保留原位，不进库。
- 上游为公开 Ice fork，属个人 macOS 实用工具；若仅需本机使用、不愿入统一库，可移出本目录（git revert 即可）。
