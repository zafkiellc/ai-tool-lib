---
title: README
type: note
permalink: main/工作/项目/资产/ai-工具库/readme
---

# AI 工具统一库（AI工具库）

> 各 AI（Hermes / WorkBuddy / DeepSeek Harness / Codex / 其它）产出的**可复用工具成品**统一收纳处。
> 多 AI 可在此持续认领、改造、优化同一批工具，并通过云同步 + 本地 git 实现工程化协作。

## 同步与版本机制
- **日常工作区 = 本文件夹**，由微力同步（verysync）+ Fast Note Sync 在多端实时云同步 → 所有 AI 都能直接读写。
- **唯一真相 + 历史 = 本地 git**（仓库在 `AI工具库/.git`，已被 `.verysync/ignoreList` 忽略，不会在多端间复制，避免冲突）。
- 远程镜像（GitHub / Gitea）**已接入并实测可用**：双远程 push 规则见 [[统一工具库接入指南]] 第6节「push 边界」（只 push 自己改造的工具，不替别端 commit/push）。

## 接入与跨端统一
- **各端 AI 自动接入**：本库已在 `00-规范/多端AI同步执行指令.md` 第 9 条 + `00-总览/首页.md`「统一工具库接入」节 固化接入要求。任何端 AI 开工即读 [[统一工具库接入指南]] 并执行。
- **统一入口**：`统一工具库接入指南.md` 是各端 AI 发现/加载/协同改造工具的唯一入口（含各端路径映射、认领锁执行、会话统一设计）。
- **verysync 共享只读/读写连接**：本库位于 vault 同步树内，微力同步已把整个 vault 作为「共享同步文件夹」推送到各端。各端只需确保本机已加入该 verysync 密钥/链接（即同一 vault 同步文件夹），无需为工具库单独建同步目录——工具随 vault 自动一致。详见 [[统一工具库接入指南]] 第二节「各端本地路径映射」。

## 目录约定
```
AI工具库/
├── README.md            # 本说明
├── 协作协议.md          # 多 AI 认领锁 / 改造流程
├── _template/           # 新建工具时的模板（复制改名即可）
│   ├── SKILL.md
│   └── scripts/.gitkeep
├── <工具名>/            # 每个工具一个文件夹
│   ├── SKILL.md        # 工具说明（含用法、依赖、注意事项）
│   ├── MANIFEST.json   # 元数据：创建者/版本/状态/认领锁
│   ├── scripts/        # 代码
│   └── references/     # 文档、API 参考（可选）
└── ...
```

## 每个工具的必含文件
1. **SKILL.md** — 工具干什么、怎么用、依赖什么、坑在哪。
2. **MANIFEST.json** — 机器可读的元数据（见 `_template/MANIFEST.json`），其中 `lock` 字段实现认领锁（见协议）。
3. **scripts/** — 实际代码。

## 入库流程（新工具）
1. 复制 `_template` 为 `AI工具库/<新工具名>/`。
2. 填好 `SKILL.md` 与 `MANIFEST.json`（`created_by` 写清是哪个 AI / 哪个会话）。
3. 在 `MANIFEST.json` 设 `"status": "beta"`。
4. `git add . && git commit -m "add <工具名>: ..."`（见协议里的 git 约定）。

## 改造流程（已有工具）
见 [[协作协议]]。