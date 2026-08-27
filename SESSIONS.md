---
tags:
- 规范
- 工具库
- 会话统一
- 多AI
created: 2026-08-27
status: ✅
permalink: main/工作/项目/资产/ai-工具库/sessions
---

# 共享会话索引（.sessions/）协议

> 本文件定义 `AI工具库/.sessions/` 的运作规则。它是「多 AI 会话统一」的可运行机制：
> 各端 AI 开工先扫描所有在线会话与跨端工具锁，改造工具前先确认没有别的 active 会话正锁着同一工具。

## 一、为什么需要它
- 各端 AI 会话逻辑不同（Hermes/WorkBuddy vs Codex/DSH），但共享同一份工具文件。
- 仅靠 `MANIFEST.json` 的 `lock` 字段是「软约定」，两个 AI 若都跳过检查就会互相覆盖。
- `.sessions/` 把「谁在线、在做什么、锁了哪个工具」显性化、可扫描，让跨端协调有据可查。

## 二、文件结构
```
AI工具库/.sessions/
├── SESSIONS.md          # 本规范（入 git）
├── sessionctl.py        # 协调器 CLI（入 git，各端 AI 调用）
├── router__hermes.json  # 软路由 Hermes 的会话文件（verysync 同步，不入 git）
├── desktop__codex.json  # 台式机 Codex 的会话文件（示例，由各端自行创建）
├── mac__workbuddy.json  # MacBook WorkBuddy（示例）
└── ...（每端 AI 一个文件，命名 <endpoint>__<ai>.json）
```
- **每个端/AI 只写自己的文件**，只读别人的 → 彻底规避 verysync 多端并发写同一文件的冲突。
- `.sessions/*.json`（协调状态）已由 `.gitignore` 排除，**不进 git 历史**，仅 verysync 同步。
- `SESSIONS.md` 与 `sessionctl.py` 入 git（规范与工具，需版本追溯）。

## 三、会话文件字段
```json
{
  "endpoint": "router",          // 设备/端标识
  "ai": "hermes",                // AI 标识
  "session_id": "a6dbafdf7285",  // 当次会话 ID
  "status": "active",            // active / idle / offline
  "last_heartbeat": "ISO时间",    // 最近心跳；超 TTL 视为掉线
  "current_task": "正在做什么",
  "tool_locks": [                // 本会话持有的工具锁
    {"tool": "fss-sinopec-query", "intent": "加导出", "since": "ISO时间"}
  ],
  "ttl_minutes": 30              // 心跳 TTL，默认 30 分钟
}
```

## 四、各端 AI 的标准动作（开工 + 改造工具前）
1. **开工**：调用 `sessionctl.py beat` 注册/刷新本端会话（写自己的 `<endpoint>__<ai>.json`）。
2. **改造某工具前**：
   - `sessionctl.py who-has --tool <工具名>` 查跨端锁。
   - 若返回 `LOCKED by <其他端/AI>` → **停下，不要 claim**，先告知用户或等对方释放（对方掉线超 TTL 时，可接管但需先知会用户）。
   - 若 `FREE` → `sessionctl.py claim --tool <名> --intent "<目的>"` 申请锁（同时写入 `MANIFEST.json` 的 `lock` 双保险）。
3. **改完**：`sessionctl.py release --tool <名>` 释放，并清空 `MANIFEST.json.lock`。

## 五、与 MANIFEST 锁的关系
- `.sessions` 是「跨端在线视图 + 协调」（轻量、易变、verysync 同步）；
- `MANIFEST.json.lock` 是「工具内持久锁」（入 git、可追溯）。
- 两者同时维护：claim 时两个都写，release 时两个都清。见 [[协作协议]] 第 1 节。

## 六、关联
- [[协作协议]]（认领锁联动）
- [[统一工具库接入指南]]（会话统一设计）
- [[AI工具库/README]]