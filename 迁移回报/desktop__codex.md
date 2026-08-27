---
name: desktop__codex 迁移回报
type: note
permalink: main/工作/项目/资产/ai-工具库/迁移回报/desktop__codex
---

# desktop / codex 迁移回报

- 迁移端：desktop / codex
- 本机扫描到的成品工具：
  - 微信自动答题小工具（本机原目录 `E:\自动答题助手`，约 13600 文件）— 私人向
  - 三角洲改枪码数据管理工具（本机原目录 `E:\三角洲坝业`，约 3072 文件）— 私人向
  - 手游抽取建议分析器（本机原目录 `E:\手游抽取建议分析器`，约 5847 文件）— 跨端可复用
- 已迁入 AI工具库：
  - 手游抽取建议分析器 → `AI工具库/手游抽取建议分析器/`（含源码：是；入口文件：`launcher.py`；启动：`python launcher.py` 或 `start.bat`/`start.command`/`start.vbs`，浏览器开 `http://localhost:8787`；已验证可运行：`py_compile launcher.py` + 全部 `backend/*.py` 通过；本机原路径 `E:\手游抽取建议分析器`）
- 保持原位 + 双链：
  - 微信自动答题小工具（私人向，按 `各端工具迁移提示词.md` 第二步不进库，仅加 `[[AI工具库]]` 双链，原目录 `E:\自动答题助手` 保留）
  - 三角洲改枪码数据管理工具（私人向，同上，原目录 `E:\三角洲坝业` 保留）
- 跳过 / 未动：
  - 微信自动答题小工具、三角洲改枪码数据管理工具：规范明确为私人向小工具，保持原位 + 双链，不进库。
  - 此前误将微信/三角洲整目录迁入库内的副本已删除（仅删 AI工具库 内副本，未动本机原目录，遵守"不删库"护栏）。
  - 其他端（win/workbuddy 等）的未提交改动（scripts/、迁移回报等）一律未触碰、未替其 commit/push。
- git commit：`7606b5b` add 手游抽取建议分析器 : 整目录物理迁入 AI工具库（desktop/codex 迁移）
- push：gitea 成功（gitea-pub = git.zafkiel.com.cn）；github 跳过（本机无 PAT）
- 遗留问题：无。config.json 已脱敏为 `<FILL_IN_...>` 占位符并 force-add 作为模板，不含任何真实密钥。

## 确认项
- [x] 源码已复制进 `AI工具库/手游抽取建议分析器/`（backend/frontend/data/tools + launcher.py，非仅文档入口）
- [x] 已 `git add 手游抽取建议分析器/`（含 `git add -f config.json`），未用 `git add .` / `-A`
- [x] 已 claim + release 跨端锁（sessionctl：desktop/codex 认领后释放；MANIFEST.json.lock = null）
- [x] 未替其他端 commit/push
