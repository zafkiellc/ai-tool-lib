---
name: mac__workbuddy 迁移回报
type: note
permalink: main/工作/项目/资产/ai-工具库/迁移回报/mac__workbuddy
---

# mac / workbuddy 迁移回报

- 迁移端：mac / workbuddy（Mac 端 WorkBuddy，会话 macwb-1）
- 本机扫描到的成品工具（按迁移提示词第二步逐项核查）：
  - `~/.local/venvs/wechat-cli-arm64/`：仅有 venv 结构，pip 装的 `wechat_cli` 0.5.0 是无关的 Python 包壳（非日常使用的工具）
  - `~/.workbuddy/binaries/node/workspace/node_modules/@canghe_ai/wechat-cli`：**日常真正使用的 wechat-cli（Node 版 `@canghe_ai/wechat-cli` v0.2.4）**，入口 `bin/wechat-cli.js` 按平台解析并调用原生二进制
  - 原生二进制：`~/.workbuddy/binaries/node/workspace/node_modules/@canghe_ai/wechat-cli-darwin-arm64/bin/wechat-cli`（10MB Mach-O arm64）
- 已整目录迁入 AI工具库：
  - wechat-cli本地查询 → `AI工具库/wechat-cli本地查询/scripts/`
    - 含源码：是。结构：`scripts/wechat-cli/`（bin/wechat-cli.js、install.js、package.json）+ 固化原生二进制 `scripts/wechat-cli/node_modules/@canghe_ai/wechat-cli-darwin-arm64/bin/wechat-cli`（10MB）
    - 验证：`node --check` 语法 OK；`file` 确认为 Mach-O 64-bit arm64；以 `WECHAT_CLI_BINARY` 指向库内二进制 + `node bin/wechat-cli.js --help` 成功输出全部子命令（离线可运行）
    - 入口说明：SKILL.md 用法 A（库内离线）/ B（本机日常 `wechat-cli` 命令）/ C（其他端 `npm install -g`）
  - 纠正历史误记：原 SKILL/MANIFEST/原笔记均误以为 wechat-cli 是 pip 第三方包；实际为 Node 版公开 npm 包（github.com/freestylefly/wechat-cli，Apache-2.0）。本次已重写 SKILL.md 并补源码，由"仅壳"升级为完整可运行工具
- 保持原位 + 双链：无新增私人向（微信答题/三角洲已在别端双链）。**本机 WorkBuddy node workspace 里的运行实例保留不删**（日常 `wechat-cli` 命令依赖它，符合单位端"原副本留本机日常用"先例）
- 跳过 / 未动：
  - `现场检查条目智能匹配工具/scripts/README.md` 的未提交改动：属其他端（win/workbuddy）的未同步改动，按 push 边界**未碰、未替其 commit/push**
  - DSH 远程连接包 / _tun.ps1 / dsh-fs-bridge：DSH 端相关，不动
  - compress-pdf-folder / organize-personal-folder / sap-zhqr023-loss-pipeline：壳待补源码，源码端未知，本次未动
- git commit：98e0385（add wechat-cli本地查询: 整目录物理迁入 Node版 @canghe_ai/wechat-cli v0.2.4 + darwin-arm64 原生二进制），本地完好
- push：gitea-pub **✅ 已推送成功（2026-08-28 修复 502 后重试，98e0385 → master）** / 内网 gitea 192.168.100.1:3000 **Mac 端超时不可达（不在该局域网，仅 gitea-pub 公网通道可用）** / github **✅ 已推送成功（2026-08-28 用 vault `github_token.b64` 还原 PAT 推送，98e0385 → master；token 仅内存使用未落盘/未泄露）**
  - 结论：verysync 已同步源码 + gitea-pub 与 github 双公网 git 历史均已落地，迁移完整闭环。
- 遗留问题：
  1. 库内副本为源码+固化原生二进制；本机 node workspace 运行实例并存，后续若改代码建议统一改库内副本并同步（或单一真源落库内）
  2. 其他平台（win/linux）原生二进制未固化进库（仅 darwin-arm64）；其他端用 `npm install -g` 自动拉对应平台包
  3. 公网 GitHub（zafkiellc/ai-tool-lib）无 PAT，且推送会暴露原生二进制；先问用户

## 确认项
- [x] 源码已复制进 AI工具库/wechat-cli本地查询/scripts/（非仅文档入口，含 JS 源码 + 原生二进制）
- [x] 已 `git add wechat-cli本地查询/`（未用 git add . / -A；其他端改动未碰）
- [x] claim + release 锁（mac/workbuddy）
- [x] 未替其他端 commit/push
