"""分析引擎：跨来源交叉验证 + 信任加权 + 时效加权 -> 抽取建议。"""
import time

from common import load_config, now_ts, game_state
from bili_client import fetch_videos, all_sources
from character_db import load_characters, find_character
from content_extractor import extract_signals

# 建议等级
VERDICT = {
    "strong_pull": "必抽",
    "pull": "推荐",
    "wait": "观望",
    "skip": "不推荐",
    "pure_xp": "纯XP",
    "insufficient": "数据不足",
}


def _recency_factor(age_days, half_life):
    if age_days < 0:
        age_days = 0
    return 0.5 ** (age_days / half_life)


def _source_weight(video, weights):
    if video.get("trusted"):
        return weights.get("trusted", 3.0)
    if video.get("source_role") == "official":
        return weights.get("official", 2.0)
    return weights.get("normal", 1.0)


def analyze_character(character_query, game="genshin"):
    cfg = load_config()
    _, _gs = game_state(cfg, game)
    recency_days = int(cfg.get("recency_days", 365))
    weights = cfg.get("weights", {})
    half_life = float(weights.get("recency_half_life_days", 120))
    now = now_ts()
    cutoff = now - recency_days * 86400

    ch = find_character(character_query, game)
    if not ch:
        return {"ok": False, "error": "未找到角色：%s" % character_query}

    characters = load_characters(game)
    sources = all_sources(cfg, game)

    # 收集该角色在所有来源（时效内 + 相关）的信号
    evidence = []
    source_stats = {}
    for src in sources:
        videos = fetch_videos(src, cfg, game=game)
        for v in videos:
            # 时效过滤：只保留最近 recency_days
            if v.get("pubdate", 0) < cutoff:
                continue
            # 相关性过滤：仅保留与原神相关视频
            if not v.get("relevant"):
                continue
            sigs = extract_signals(v, [ch])
            for s in sigs:
                if s.character_id != ch["id"]:
                    continue
                age = (now - v["pubdate"]) / 86400 if v.get("pubdate") else 9999
                rf = _recency_factor(age, half_life)
                sw = _source_weight(v, weights)
                contrib = s.polarity * s.weight * sw * rf
                item = s.to_dict()
                item["age_days"] = round(age, 1)
                item["recency_factor"] = round(rf, 3)
                item["source_weight"] = sw
                item["is_sample"] = bool(v.get("is_sample", False))
                if item["is_sample"]:
                    # 示例数据仅作演示：大幅降权，避免与真实抓取混算后误导结论
                    contrib *= 0.15
                item["contribution"] = round(contrib, 3)
                evidence.append(item)
                key = v.get("source_name", src.get("name"))
                st = source_stats.setdefault(key, {
                    "name": key, "trusted": v.get("trusted"),
                    "role": v.get("source_role"), "pos": 0, "neg": 0,
                    "neutral": 0, "videos": set()})
                if s.polarity > 0:
                    st["pos"] += 1
                elif s.polarity < 0:
                    st["neg"] += 1
                else:
                    st["neutral"] += 1
                st["videos"].add(v.get("bvid"))

    # 同一视频在多来源重复命中时，只保留贡献绝对值最大的证据，避免重复计数
    by_bvid = {}
    for e in evidence:
        bvid = e.get("bvid")
        cur = by_bvid.get(bvid)
        if cur is None or abs(e["contribution"]) > abs(cur["contribution"]):
            by_bvid[bvid] = e
    evidence = list(by_bvid.values())

    # 汇总
    total_pos = sum(e["contribution"] for e in evidence if e["contribution"] > 0)
    total_neg = sum(-e["contribution"] for e in evidence if e["contribution"] < 0)
    net = total_pos - total_neg

    # 信任主播意见（主意见）
    trusted_ev = [e for e in evidence if e.get("trusted")]
    trusted_pos = sum(e["contribution"] for e in trusted_ev if e["contribution"] > 0)
    trusted_neg = sum(-e["contribution"] for e in trusted_ev if e["contribution"] < 0)

    # 官方点名
    official_ev = [e for e in evidence if e.get("source_role") == "official"]

    # 决策
    if not evidence:
        verdict = "insufficient"
        confidence = 0.0
    else:
        confidence = min(1.0, abs(net) / (abs(net) + 2.0))
        if trusted_ev:
            # 主意见主导
            if trusted_pos > trusted_neg and net > 0:
                verdict = "strong_pull" if (net >= 3 or trusted_pos >= 2) else "pull"
            elif trusted_neg > trusted_pos and net < 0:
                verdict = "skip"
            else:
                verdict = "wait"
        else:
            if net >= 3:
                verdict = "strong_pull"
            elif net > 0:
                verdict = "pull"
            elif net < 0:
                verdict = "skip"
            else:
                verdict = "wait"

    # 证据排序：贡献绝对值大的在前
    evidence_sorted = sorted(evidence, key=lambda e: abs(e["contribution"]), reverse=True)

    sources_breakdown = []
    for k, st in source_stats.items():
        stance = "正向" if st["pos"] > st["neg"] else ("负向" if st["neg"] > st["pos"] else "中性/提及")
        sources_breakdown.append({
            "name": st["name"], "trusted": st["trusted"], "role": st["role"],
            "stance": stance, "pos": st["pos"], "neg": st["neg"],
            "neutral": st["neutral"], "video_count": len(st["videos"]),
        })

    # 时效说明
    newest = min((e["age_days"] for e in evidence), default=None)
    oldest = max((e["age_days"] for e in evidence), default=None)

    # 数据来源模式：全部为示例 / 真实 / 无数据
    if not evidence:
        data_mode = "none"
    elif any(e.get("is_sample") for e in evidence):
        data_mode = "sample"
    else:
        data_mode = "live"

    return {
        "ok": True,
        "character": ch,
        "icon": ch.get("icon", ""),
        "icon_fallback": ch.get("icon_fallback", ""),
        "data_mode": data_mode,
        "game": game,
        "verdict": verdict,
        "verdict_label": VERDICT.get(verdict, verdict),
        "confidence": round(confidence, 2),
        "net_score": round(net, 2),
        "total_pos": round(total_pos, 2),
        "total_neg": round(total_neg, 2),
        "recency_window_days": recency_days,
        "newest_age_days": round(newest, 1) if newest is not None else None,
        "oldest_age_days": round(oldest, 1) if oldest is not None else None,
        "official_mentioned": len(official_ev) > 0,
        "trusted_dominant": len(trusted_ev) > 0,
        "sources_breakdown": sources_breakdown,
        "evidence_count": len(evidence),
        "evidence": evidence_sorted,
        "config": {
            "current_version": _gs.get("current_version"),
            "streamers": [{"name": s.get("name"), "trusted": s.get("trusted"),
                           "role": s.get("role")} for s in _gs.get("streamers", [])],
            "official": [{"name": o.get("name")} for o in _gs.get("official", [])],
        },
    }


def analyze_all(game="genshin"):
    """对所有角色跑一遍，用于总览页（可选）。已合并手动标注（优先级最高）。"""
    from manual_analysis import get_all_overrides
    overrides = get_all_overrides()
    chars = load_characters(game)
    out = []
    for c in chars:
        r = analyze_character(c["id"], game)
        if r.get("ok"):
            verdict = r["verdict"]
            label = r["verdict_label"]
            ov = overrides.get(c["id"])
            if ov and ov.get("verdict") in VERDICT:
                verdict = ov["verdict"]
                label = VERDICT[ov["verdict"]]
            out.append({
                "id": c["id"], "name": c["name"], "element": c.get("element"),
                "rarity": c.get("rarity"),
                "verdict": verdict, "verdict_label": label,
                "net_score": r["net_score"], "evidence_count": r["evidence_count"],
            })
    return out
