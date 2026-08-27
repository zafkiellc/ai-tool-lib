#!/usr/bin/env python3
"""
sessionctl.py — 共享会话索引协调器（多 AI 会话统一机制）

作用：让每个端/AI 的 agent 用同一套逻辑维护 .sessions/ 下的会话文件，
从而实现「多 AI 会话统一」：开工先扫描所有在线会话，改工具前检查跨端锁，
避免两个 AI 同时改造同一工具互相覆盖。

设计要点：
- 每端 AI 一个文件 `<endpoint>__<ai>.json`，只写自己的、只读别人的 → 不冲突。
- 易变协调文件不入 git（见 .gitignore），仅由 verysync 在各端同步。
- 提供 CLI：beat（心跳）/ view（看在线会话+锁）/ claim（申请工具锁）/ release（释放）/ who-has（查某工具被谁锁）。

用法（agent 在改造工具前）：
  python3 .sessions/sessionctl.py beat --endpoint router --ai hermes --session a6db --task "改造 fss 工具"
  python3 .sessions/sessionctl.py who-has --tool fss-sinopec-query
  python3 .sessions/sessionctl.py claim --tool fss-sinopec-query --intent "新增批量导出"
  # 若 who-has 返回他人 active 锁 → 停下，先问用户/等释放，不要 claim
  # 改完：
  python3 .sessions/sessionctl.py release --tool fss-sinopec-query
"""
import argparse, json, os, sys, datetime
from pathlib import Path

SESS_DIR = Path(__file__).resolve().parent
TTL_DEFAULT = 30  # 分钟；超过则视为掉线，其锁可被接管（先告知用户）

def now_iso():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def ttl_ok(data, ttl):
    try:
        hb = datetime.datetime.fromisoformat(data["last_heartbeat"])
        return (datetime.datetime.now(datetime.timezone.utc) - hb.astimezone(datetime.timezone.utc)).total_seconds() < ttl * 60
    except Exception:
        return False

def self_file(endpoint, ai):
    return SESS_DIR / f"{endpoint}__{ai}.json"

def all_sessions():
    out = []
    for p in sorted(SESS_DIR.glob("*.json")):
        if p.name == "sessionctl.py":
            continue
        d = load(p)
        if d:
            out.append((p, d))
    return out

def cmd_beat(args):
    f = self_file(args.endpoint, args.ai)
    d = load(f) or {}
    d.update({
        "endpoint": args.endpoint,
        "ai": args.ai,
        "session_id": args.session or d.get("session_id", "unknown"),
        "status": "active",
        "last_heartbeat": now_iso(),
        "current_task": args.task or d.get("current_task", ""),
        "ttl_minutes": args.ttl or d.get("ttl_minutes", TTL_DEFAULT),
    })
    if "tool_locks" not in d:
        d["tool_locks"] = []
    save(f, d)
    print(f"beat ok: {f.name} @ {d['last_heartbeat']}")

def active_locks(ttl):
    """返回 [(tool, owner)] 对所有 active 会话持有的工具锁"""
    res = []
    for p, d in all_sessions():
        if not ttl_ok(d, d.get("ttl_minutes", ttl)):
            continue
        for tl in d.get("tool_locks", []):
            res.append((tl.get("tool"), f"{d['endpoint']}/{d['ai']}:{d.get('session_id','?')}"))
    return res

def cmd_view(args):
    print("=== 在线会话 + 工具锁 ===")
    for p, d in all_sessions():
        ok = ttl_ok(d, d.get("ttl_minutes", args.ttl))
        flag = "ACTIVE" if ok else "STALE "
        print(f"[{flag}] {d.get('endpoint')}/{d.get('ai')} session={d.get('session_id')}")
        print(f"         task: {d.get('current_task','')}  hb: {d.get('last_heartbeat')}")
        for tl in d.get("tool_locks", []):
            print(f"         lock: {tl.get('tool')}  intent={tl.get('intent')} since={tl.get('since')}")
    print("\n=== 当前跨端锁摘要 ===")
    locks = active_locks(args.ttl)
    if not locks:
        print("(无 active 工具锁)")
    for tool, owner in locks:
        print(f"  {tool}  ->  {owner}")

def cmd_who_has(args):
    for tool, owner in active_locks(args.ttl):
        if tool == args.tool:
            print(f"LOCKED by {owner}")
            return
    print("FREE")

def cmd_claim(args):
    f = self_file(args.endpoint, args.ai)
    d = load(f)
    if not d:
        print("ERROR: 先 beat 初始化本端会话文件"); sys.exit(1)
    # 检查他人锁
    for tool, owner in active_locks(d.get("ttl_minutes", args.ttl)):
        if tool == args.tool and owner != f"{args.endpoint}/{args.ai}":
            print(f"REFUSED: {args.tool} 已被 {owner} 锁定(active)。先问用户或等释放，不要强占。")
            sys.exit(2)
    tl = {"tool": args.tool, "intent": args.intent, "since": now_iso()}
    locks = [x for x in d.get("tool_locks", []) if x["tool"] != args.tool]
    locks.append(tl)
    d["tool_locks"] = locks
    d["last_heartbeat"] = now_iso()
    save(f, d)
    print(f"claimed {args.tool} by {args.endpoint}/{args.ai}")

def cmd_release(args):
    f = self_file(args.endpoint, args.ai)
    d = load(f)
    if not d:
        print("ERROR: 会话文件不存在"); sys.exit(1)
    d["tool_locks"] = [x for x in d.get("tool_locks", []) if x["tool"] != args.tool]
    d["last_heartbeat"] = now_iso()
    save(f, d)
    print(f"released {args.tool} by {args.endpoint}/{args.ai}")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in (cmd_beat, cmd_view, cmd_who_has, cmd_claim, cmd_release):
        pass
    b = sub.add_parser("beat"); b.add_argument("--endpoint", required=True); b.add_argument("--ai", required=True)
    b.add_argument("--session", default=""); b.add_argument("--task", default=""); b.add_argument("--ttl", type=int, default=TTL_DEFAULT)
    b.set_defaults(func=cmd_beat)
    v = sub.add_parser("view"); v.add_argument("--ttl", type=int, default=TTL_DEFAULT); v.set_defaults(func=cmd_view)
    w = sub.add_parser("who-has"); w.add_argument("--tool", required=True); w.add_argument("--ttl", type=int, default=TTL_DEFAULT); w.set_defaults(func=cmd_who_has)
    c = sub.add_parser("claim"); c.add_argument("--endpoint", required=True); c.add_argument("--ai", required=True); c.add_argument("--tool", required=True); c.add_argument("--intent", required=True); c.add_argument("--ttl", type=int, default=TTL_DEFAULT); c.set_defaults(func=cmd_claim)
    r = sub.add_parser("release"); r.add_argument("--endpoint", required=True); r.add_argument("--ai", required=True); r.add_argument("--tool", required=True); r.set_defaults(func=cmd_release)
    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
