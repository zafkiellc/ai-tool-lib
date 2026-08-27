---
name: win__workbuddy 迁移回报
type: note
permalink: main/工作/项目/资产/ai-工具库/迁移回报/win__workbuddy
---

# win / workbuddy 迁移回报

- 迁移端：win / workbuddy（单位端 WorkBuddy，会话 1961dae08f5f）
- 本机扫描到的成品工具：
  - `~/.workbuddy/skills/`：sinopec-oa-qianbao-draft（自建 OA 签报 skill，未入库）
  - `D:/巡站724_便携版/`：现场检查条目智能匹配工具（运行副本，库内原是文档壳）
  - `C:\Users\zafki\OneDrive\工作\工作工具\`：网络学院学习小助手（库内原是文档壳）、加油机强检证书下载工具、发票识别重命名工具、微信自动答题小工具、三角洲改枪码、网络代理工具包、任务完成标记看板等
  - 库内已有 9 工具中，3 个文档壳（现场检查/网络学院/wechat-cli）源码待补；其中现场检查+网络学院源码在本机，由本端补
- 已整目录迁入 AI工具库：
  - 现场检查条目智能匹配工具 → `AI工具库/现场检查条目智能匹配工具/scripts/`（含源码：是；启动 `scripts\启动.vbs`；已 `py_compile` 验证）
  - 网络学院学习小助手 → `AI工具库/网络学院学习小助手/scripts/`（含源码：是；启动 `scripts\start.bat`；已 `node --check` 验证；`node_modules` 未入，需 `npm install`）
  - 加油机强检证书下载工具 → `AI工具库/加油机强检证书下载工具/`（含源码：是；启动 `scripts\启动工具.vbs`；已 `py_compile` 验证；嵌入 `python/` 未入，依赖文档化）
  - 发票识别重命名工具 → `AI工具库/发票识别重命名工具/`（含源码：是；启动 `scripts\启动工具.bat`；已 `node --check` 验证；`runtime/`/`mac版/`/`node_modules` 未入，依赖文档化）
  - sinopec-oa-qianbao-draft → `AI工具库/sinopec-oa-qianbao-draft/`（SKILL.md + `scripts/oa_qianbao_draft.py`；已 `py_compile` 验证）
- 保持原位 + 双链：微信自动答题小工具、三角洲改枪码数据管理工具（私人向，不入库）；网络代理工具包、任务完成标记看板（个人项目，不入库）
- 跳过 / 未动：
  - wechat-cli本地查询：源码在 Mac 端（wechat-cli pip），本机 Windows 无源码，无法补 `scripts/`（待 Mac 端补）
  - WorkBuddy私有Skills、Anthropic官方Skills：属其他端/第三方，不动
  - DSH远程连接包 / _tun.ps1 / dsh-fs-bridge.mjs：DSH 端相关，不动
- git commit：<回填>
- push：gitea-pub <待执行> / github <无 PAT，未推>
- 遗留问题：
  1. 库内副本仅存源码，未捆绑嵌入式运行时（嵌入 python / 便携 node / runtime），运行需自备 Python 3.13 / Node 20 + `pip install` / `npm install`；本机原副本保留为日常运行副本（删原副本会破坏日常使用，故保留）。
  2. 现场检查/网络学院 源码与原 OneDrive/巡站724 副本并存，后续改代码需同步回源或统一改库内副本（建议单一真源落到库内）。
  3. 发票工具 `mac版/`/`runtime/` 未入（以 Windows 端为主，Mac 端如需可自行补）。

## 确认项
- [x] 源码已复制进 AI工具库/<工具名>/scripts/（非仅文档入口）：现场检查/网络学院补 scripts；加油机/发票/oa 新建完整目录
- [x] 仅 `git add` 迁入工具目录 + 本回报（未用 `git add .` / `-A`）
- [x] claim + release 锁（5 工具）
- [x] 未替其他端 commit/push（仅提交本端工具 + 回报）
