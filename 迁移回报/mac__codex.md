---
name: mac__codex 迁移回报
type: note
permalink: main/工作/项目/资产/ai-工具库/迁移回报/mac__codex
---

# mac / codex 迁移回报

- 迁移端：mac / codex
- 本机扫描到的成品工具：
  - Thaw：`~/WorkBuddy/2026-07-21-11-46-05/Thaw/`（本机已构建安装 `Thaw Preview.app`；整目录含 `Build/` 约 1.5G，纯源码约 12MB）
  - wechat-cli：`~/WorkBuddy/...` node workspace 内 `@canghe_ai/wechat-cli`（日常用）——但已由 mac__workbuddy 整目录迁入，本次跳过避免重复
  - 三壳工具 compress-pdf-folder / organize-personal-folder / sap-zhqr023-loss-pipeline：本机无源码（源码端未知），未动
  - 微信答题 / 三角洲：私人向工具，本机无源码（仅他端双链），未动
- 已迁入 AI工具库：
  - Thaw → `AI工具库/Thaw/`（含源码：是；含 scripts：是）
    - 源码位置：`scripts/Thaw/`（物理迁入自 `~/WorkBuddy/2026-07-21-11-46-05/Thaw/`，296 文件 / 206 Swift 源 / `Thaw.xcodeproj` + `scripts/build-preview.sh`）
    - 排除：1.5G 的 `Build/` 构建产物 + 嵌套 `.git`
    - 入口：`scripts/Thaw/Thaw.xcodeproj`（Xcode 打开构建）或 `scripts/Thaw/scripts/build-preview.sh`（未签名本地构建 + DMG + 自动安装）
    - 验证：`bash -n` 通过；`Thaw.xcodeproj` 存在；206 个 Swift 源（未做完整 Xcode 编译，需 GUI）
    - 补：`MANIFEST.json`（status: beta, lock: null）+ `SKILL.md`
- 保持原位 + 双链：无新增（私人向微信答题/三角洲本机无源码；Thaw 运行实例与 WorkBuddy 缓存保留原位不删）
- 跳过 / 未动：
  - wechat-cli本地查询：已由 mac__workbuddy 整目录迁入，跳过避免重复
  - compress-pdf-folder / organize-personal-folder / sap-zhqr023-loss-pipeline：三壳，源码端未知，本机无，未动
  - 微信答题 / 三角洲：私人向，本机无源码，仅他端双链
  - 现场检查条目智能匹配工具/scripts/README.md 未提交改动：属其他端（win/workbuddy）改动，按 push 边界未碰
- git commit：b00ef77（add Thaw: 整目录物理迁入 macOS 菜单栏工具（Ice fork 源码 12MB，排除 Build 1.5G 产物与嵌套 .git））
- push：gitea-pub ✅ 已推送成功（b00ef77 → master，已确认 `gitea-pub/master = b00ef77`）/ 内网 gitea 192.168.100.1:3000 ❌ Mac 端超时不可达（不在该局域网，仅 gitea-pub 公网通道可用）/ github 本次未推送（Thaw 含完整 Swift 源码，公网 GitHub 无可用 PAT；与 mac__workbuddy 一致先不暴露）
- 遗留问题：
  1. 本机运行实例 `/Applications/Thaw Preview.app` 与 `~/WorkBuddy/.../Thaw/` 构建缓存保留原位未删（日常用），库内为唯一源码真源
  2. 分支 `feat/macos-27-experimental` 因 Xcode 26.6 与 macOS 27 编译器不兼容暂缓，当前 `development` 分支可构建
  3. Homebrew 在 macOS 27 beta 不可用（bottle 仅支持 Tahoe/26），依赖需直接下载二进制

## 确认项
- [x] 源码已复制进 AI工具库/Thaw/scripts/（非仅文档入口：206 Swift 源 + xcodeproj + build-preview.sh）
- [x] 已 `git add Thaw/`（未用 git add . / -A；其他端改动未碰）
- [x] 已 claim + release 锁（mac/codex）
- [x] 未替其他端 commit/push
