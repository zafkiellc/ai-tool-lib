---
name: desktop__codex 迁移回报
type: note
permalink: main/工作/项目/资产/ai-工具库/迁移回报/desktop__codex
---

# desktop / codex 迁移回报

- 迁移端：desktop / codex
- 本机扫描到的成品工具：
  - `~/.codex/skills/`：claude-vision、findskills、hatch-pet、narrator-ai-cli-skill、vault-memory（均为第三方/系统自带技能，非本人成品工具，不入库）；`.system/*`（imagegen/openai-docs/plugin-creator/review-agent/skill-creator/skill-installer）为 Codex 内置技能
  - vault `私人/开发`：微信自动答题小工具（私人向）、Thaw-macOS构建（构建笔记，非工具）
  - vault `私人/游戏`：三角洲改枪码数据管理工具（私人向）
  - vault `工作/项目`：多为「已在库工具」的关联笔记（液位仪系统数据查询 / 油站损耗分析 / FSS报销系统 / SAP数据自动化导出）或文档（进销存与盘点 等），非新工具
  - `工作/项目/资产` 同级：`WorkBuddy私有Skills`（= 6 个在库工具的 WorkBuddy 私有备份，属其他端）、`Anthropic官方Skills`（官方安装脚本，第三方）
- 已迁入 AI工具库：无（本次无跨端可复用成品工具需迁入）
- 保持原位 + 双链：微信自动答题小工具、三角洲改枪码数据管理工具（两份笔记均已含 `[[AI工具库]]` 双链，无需补）
- 跳过 / 未动：
  - 3 个文档入口工具（网络学院学习小助手 / 现场检查条目智能匹配工具 / wechat-cli本地查询）缺 `scripts/`，本机无其源码 → 未补全（由其来源端 Hermes 补）
  - `WorkBuddy私有Skills`、`Anthropic官方Skills` 属其他端 / 第三方 → 不动（不替其他端）
  - `~/.codex` 自带技能 → 非本人成品，不入库
- git commit：<session 内提交后回填>
- push：gitea <待执行> / github <无 PAT，未推>
- 遗留问题：无

## 确认项
- [x] 源码已复制进 AI工具库/<工具名>/scripts/（本次无工具迁入，N/A）
- [x] 仅 `git add 迁移回报/desktop__codex.md`（未用 git add . / -A）
- [x] claim + release 锁（本次无工具迁入，未持工具锁，N/A）
- [x] 未替其他端 commit/push（工作区干净，仅提交本端回报文件）
