"""本地服务：静态前端 + JSON API。无第三方依赖（基于 http.server）。"""
import json
import os
import re
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 打包为 exe（PyInstaller onedir）后，数据/前端/config 位于 sys._MEIPASS（_internal）目录。
# 但为了让「设置/数据/前端」的编辑即时生效、官方数据持久化（用户本机直接改 config.json / data 即可），
# 优先使用 exe 同级目录的「项目根」（E:/）下的真实文件；仅当项目根缺失时才回退到打包内 _internal。
if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    _proj = os.path.dirname(os.path.dirname(sys.executable))
    if os.path.isdir(_proj):
        BASE_DIR = _proj
    else:
        BASE_DIR = sys._MEIPASS
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_DIR = os.path.join(BASE_DIR, "data")
AVATAR_DIR = os.path.join(DATA_DIR, "avatars")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
sys.path.insert(0, BACKEND_DIR)

from analyzer import analyze_character, analyze_all, VERDICT
from character_db import load_characters, all_characters
from common import (load_config, clear_cache, parse_uid_from_input,
                    resolve_bilibili_user, game_state, list_games)
from ai_analysis import (analyze as ai_analyze, status as ai_status, test as ai_test,
                         VERDICT_LABELS as AI_VERDICT_LABELS)
from manual_analysis import get_override, set_override
from bili_client import (fetch_videos, all_sources, search_videos, search_articles,
                         fetch_video_subtitle, fetch_article_text, _bvid_from_url,
                         _aid_from_url, subscribed_video_relevance)
from official_stats import get_radar, get_stats
from character_refresh import refresh_character_db, fetch_avatars, update_db
from gacha_import import (import_history, load_history, clear_history,
                          supported_games as gacha_supported_games)
from loadout import build_loadout
from nga_client import (get_nga_cookie, mask_cookie, has_nga_board,
                        search_nga, hot_nga, fetch_nga_posts, test_connection,
                        board_name as nga_board_name)

PORT = int(os.environ.get("PORT", "8787"))

# AI 分析结果本地缓存目录（按 游戏+角色+是否增强 保存；仅手动点击「AI 分析」才刷新）
AI_CACHE_DIR = os.path.join(DATA_DIR, ".ai_cache")


def _ai_cache_path(game_id, char_id, enhanced):
    safe = re.sub(r"[^\w.-]", "_", "%s__%s__e%d" % (game_id, char_id, 1 if enhanced else 0))
    return os.path.join(AI_CACHE_DIR, safe + ".json")


def _ai_cache_load(game_id, char_id, enhanced):
    try:
        p = _ai_cache_path(game_id, char_id, enhanced)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _ai_cache_save(game_id, char_id, enhanced, ai):
    try:
        os.makedirs(AI_CACHE_DIR, exist_ok=True)
        d = dict(ai)
        d["cached_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(_ai_cache_path(game_id, char_id, enhanced), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _ai_cache_latest(game_id, char_id):
    """取该角色最新一条 AI 缓存（e0/e1 取 cached_at 最新），无则 None。"""
    best = None
    try:
        if not os.path.isdir(AI_CACHE_DIR):
            return None
        prefix = re.sub(r"[^\w.-]", "_", "%s__%s__e" % (game_id, char_id))
        for fn in os.listdir(AI_CACHE_DIR):
            if not fn.endswith(".json") or not fn.startswith(prefix):
                continue
            try:
                with open(os.path.join(AI_CACHE_DIR, fn), encoding="utf-8") as f:
                    d = json.load(f)
                if best is None or (d.get("cached_at") or "") > (best.get("cached_at") or ""):
                    best = d
            except Exception:
                continue
    except Exception:
        return None
    return best


def _ai_cache_stats():
    """统计 AI 缓存：条目列表 + 总大小。"""
    items = []
    total = 0
    if os.path.isdir(AI_CACHE_DIR):
        for fn in os.listdir(AI_CACHE_DIR):
            if not fn.endswith(".json"):
                continue
            p = os.path.join(AI_CACHE_DIR, fn)
            try:
                sz = os.path.getsize(p)
                total += sz
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
                base = fn[:-5]
                parts = base.split("__")
                game = parts[0] if parts else ""
                char = parts[1] if len(parts) > 1 else base
                items.append({
                    "game": game,
                    "character": char,
                    "enhanced": base.endswith("_e1"),
                    "cached_at": d.get("cached_at", ""),
                    "verdict": d.get("verdict", ""),
                    "size": sz,
                })
            except Exception:
                continue
    return items, total

# AI 分析进度（内存态，前端轮询；带 10 分钟 TTL 自动清理）
_AI_PROGRESS = {}


def _set_progress(key, stage, message, pct):
    if not key:
        return
    _AI_PROGRESS[key] = {"stage": stage, "message": message, "pct": pct,
                         "ts": time.time()}
    if len(_AI_PROGRESS) > 200:
        now = time.time()
        for k in [k for k, v in list(_AI_PROGRESS.items())
                  if now - v.get("ts", 0) > 600]:
            _AI_PROGRESS.pop(k, None)

# 中文控制台输出鲁棒性：直接以 python 运行时（start.bat 的 Python 回退路径），
# 若系统区域非 UTF-8，print 中文可能抛 UnicodeEncodeError 进而中断线程。
# 这里强制 stdout/stderr 为 UTF-8（detached 场景下跳过）。
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except PermissionError:
        raise RuntimeError("无法写入配置文件（权限不足或只读文件系统）。"
                           "若使用 exe 版本，请确保项目目录可写：\n  %s" % CONFIG_PATH)
    except OSError as e:
        raise RuntimeError("写入配置文件失败：%s\n  路径：%s" % (e, CONFIG_PATH))


def _json(body, status=200):
    return status, {"Content-Type": "application/json; charset=utf-8"}, \
        json.dumps(body, ensure_ascii=False).encode("utf-8")


def _config_block(cfg, game_id=None):
    gid, g = game_state(cfg, game_id)
    return {
        "game": gid,
        "display_name": g.get("display_name", gid),
        "current_version": g.get("current_version", ""),
        "category_field": g.get("category_field", "element"),
        "category_label": g.get("category_label", "元素"),
        "category_order": g.get("category_order", []),
        "recency_days": cfg.get("recency_days"),
        "demo_mode": cfg.get("demo_mode", True),
        "analysis_mode": cfg.get("analysis_mode", "rule"),
        "ai": ai_status(cfg),
        "content": cfg.get("content", {}),
        "streamers": [{"uid": s.get("uid"), "name": s.get("name"),
                       "trusted": s.get("trusted"), "role": s.get("role"),
                       "resolved": s.get("resolved", True)}
                      for s in g.get("streamers", [])],
        "official": [{"uid": o.get("uid"), "name": o.get("name"),
                      "trusted": o.get("trusted"), "role": "official",
                      "resolved": o.get("resolved", True)}
                     for o in g.get("official", [])],
    }


def _settings_block(cfg):
    """供设置面板预填的可编辑配置（含敏感字段，仅本地工具内部使用）。"""
    ai = cfg.get("ai", {})
    gid, g = game_state(cfg)
    return {
        "display_name": g.get("display_name", ""),
        "current_version": g.get("current_version", ""),
        "recency_days": cfg.get("recency_days", 365),
        "demo_mode": bool(cfg.get("demo_mode", True)),
        "analysis_mode": cfg.get("analysis_mode", "rule"),
        "sessdata": cfg.get("cookie", {}).get("SESSDATA", ""),
        "nga_cookie_masked": mask_cookie(get_nga_cookie(cfg)),
        "nga_cookie_set": bool(get_nga_cookie(cfg)),
        "nga_boards": {g: {"fid": f, "name": nga_board_name(g)}
                       for g, f in [("genshin", 650), ("hsr", 818), ("zzz", 853),
                                    ("wuthering_waves", 854), ("arknights_endfield", 846)]},
        "ai": {
            "enabled": bool(ai.get("enabled")),
            "provider": ai.get("provider", "online"),
            "prompt_lang": ai.get("prompt_lang", "zh"),
            "online": ai.get("online", {}),
            "local": ai.get("local", {}),
        },
        "content": cfg.get("content", {}),
        "weights": cfg.get("weights", {}),
    }


def _apply_settings(s, cfg):
    """把设置面板的字段安全合并进 config（保留 game 与 streamers/official）。"""
    if not isinstance(s, dict):
        return cfg
    def get(k, d):
        return s[k] if k in s and s[k] is not None else d
    gid, g = game_state(cfg)
    g["display_name"] = str(get("display_name", g.get("display_name", "")))
    g["current_version"] = str(get("current_version", g.get("current_version", "")))
    try:
        cfg["recency_days"] = int(get("recency_days", cfg.get("recency_days", 365)))
    except Exception:
        pass
    cfg["demo_mode"] = bool(get("demo_mode", cfg.get("demo_mode", True)))
    cfg["analysis_mode"] = get("analysis_mode", cfg.get("analysis_mode", "rule"))
    if cfg["analysis_mode"] not in ("rule", "ai", "hybrid"):
        cfg["analysis_mode"] = "rule"
    cookie = cfg.setdefault("cookie", {})
    cookie["SESSDATA"] = str(get("sessdata", cookie.get("SESSDATA", "")))
    if "nga_cookie" in s:
        nga = str(s.get("nga_cookie") or "").strip()
        if nga:
            cookie["NGA_COOKIE"] = nga
        else:
            cookie.pop("NGA_COOKIE", None)  # 输入框清空保存 = 清除 Cookie
    ai_in = get("ai", {}) or {}
    ai = cfg.setdefault("ai", {})
    ai["enabled"] = bool(ai_in.get("enabled", ai.get("enabled", False)))
    ai["provider"] = ai_in.get("provider", ai.get("provider", "online"))
    if ai["provider"] not in ("online", "local"):
        ai["provider"] = "online"
    ai["prompt_lang"] = ai_in.get("prompt_lang", ai.get("prompt_lang", "zh"))
    for k in ("online", "local"):
        pc = ai.setdefault(k, {})
        pci = ai_in.get(k, {}) or {}
        pc["base_url"] = str(pci.get("base_url", pc.get("base_url", "")))
        pc["api_key"] = str(pci.get("api_key", pc.get("api_key", "")))
        pc["model"] = str(pci.get("model", pc.get("model", "")))
    content_in = get("content", {}) or {}
    content = cfg.setdefault("content", {})
    content["source"] = content_in.get("source", content.get("source", "metadata"))
    content["prefer_audio_only"] = bool(content_in.get("prefer_audio_only",
                                                         content.get("prefer_audio_only", True)))
    content["asr_provider"] = str(content_in.get("asr_provider", content.get("asr_provider", "")))
    w_in = get("weights", {}) or {}
    w = cfg.setdefault("weights", {})
    for k in ("trusted", "official", "normal"):
        try:
            w[k] = float(w_in.get(k, w.get(k, {"trusted": 3.0, "official": 2.0, "normal": 1.0}[k])))
        except Exception:
            pass
    try:
        w["recency_half_life_days"] = int(w_in.get("recency_half_life_days",
                                                     w.get("recency_half_life_days", 120)))
    except Exception:
        pass
    return cfg


def _enhanced_sources_block(enhanced_evidence):
    """增强参考来源展示块：按角色相关度排序，订阅主播/官方带标签，上限 50 条。"""
    ordered = sorted(enhanced_evidence,
                     key=lambda e: (-float(e.get("relevance") or 0),
                                    0 if e.get("subscribed") else 1,
                                    -(e.get("play") or 0)))
    return [
        {"title": e.get("title", ""), "url": e.get("url", ""),
         "play": e.get("play", 0), "like": e.get("like", 0),
         "favorite": e.get("favorite", 0),
         "relevance": e.get("relevance"),
         "result_type": e.get("result_type", "video"),
         "subscribed": bool(e.get("subscribed")),
         "source_role": e.get("source_role", ""),
         "author": e.get("author", ""),
         "mid": e.get("mid", ""),
         "is_sample": bool(e.get("is_sample", False)),
         "pubdate_str": e.get("pubdate_str", "")}
        for e in ordered[:50]
    ]


def _merged_analysis(character_query, cfg, mode="rule", enhanced=False,
                     game_id=None, progress_key=None, force_refresh=False):
    """合并三层结果：规则基线(rule) + AI(ai, 可选) + 手动标注(manual)。
    effective 表示最终展示采用哪一层（优先级：manual > ai > rule）。
    enhanced=True 时，额外拉取 B 站搜索结果（视频+专栏）作为 AI 交叉验证证据。"""
    if not game_id:
        game_id = cfg.get("current_game", "genshin")
    sess = (cfg.get("cookie", {}) or {}).get("SESSDATA", "")
    demo = cfg.get("demo_mode", True)
    rule = analyze_character(character_query, game_id)
    if not rule.get("ok"):
        return rule
    ch = rule["character"]
    ch_id = ch["id"]
    manual = get_override(ch_id)
    if manual:
        manual = dict(manual)
        manual["verdict_label"] = VERDICT.get(manual.get("verdict"), manual.get("verdict"))

    # 增强证据：拉取 B 站搜索结果（带关键词过滤 + 相关性评分）+ NGA 社区检索
    # 所有模式都执行（rule/ai/hybrid），保证用户勾选后任何模式都能看到引用来源。
    enhanced_evidence = []
    enhanced_note = ""
    nga_cookie = get_nga_cookie(cfg)
    if enhanced:
        # 订阅主播/官方来源：即使播放量不高也必须进入增强证据，但仍需角色级相关度过滤。
        seen_bvids = set()
        seen_aids = set()
        sub_count = 0
        cutoff = int(time.time()) - int(cfg.get("recency_days", 365)) * 86400
        _set_progress(progress_key, "search", "正在合并订阅主播/官方视频…", 10)
        try:
            for src in all_sources(cfg, game_id):
                for v in (fetch_videos(src, cfg, game=game_id) or []):
                    if not v.get("relevant"):
                        continue
                    rel = subscribed_video_relevance(
                        v, ch.get("name"), ch.get("aliases"), game_id)
                    if rel <= 0:
                        continue
                    if v.get("pubdate", 0) and int(v.get("pubdate", 0)) < cutoff:
                        continue
                    bvid = v.get("bvid") or ""
                    if bvid and bvid in seen_bvids:
                        continue
                    if bvid:
                        seen_bvids.add(bvid)
                    v["subscribed"] = True
                    v["relevance"] = round(rel, 2)
                    enhanced_evidence.append(v)
                    sub_count += 1
        except Exception:
            sub_count = 0
        if not sess or demo:
            enhanced_note = ("未拉取真实 B站 数据：" + ("当前为示例模式" if demo else "未配置 SESSDATA")
                             + "。请在「设置」中关闭示例模式并填入 SESSDATA 后重试。")
            if sub_count:
                enhanced_note += "（已并入 %d 条订阅来源示例视频）" % sub_count
        else:
            _set_progress(progress_key, "search", "正在搜索 B站 增强参考来源…", 15)
            try:
                char_name = ch.get("name", "")
                char_aliases = ch.get("aliases", []) or []
                meta_combined = {"queries": 0, "raw": 0, "after_dedupe": 0,
                                "passed_filter": 0, "aliases_used": []}
                # 用角色名+别名搜索，自动附加分析关键词（别名按搜索优先级加权）
                res_v, meta_v = search_videos(char_name, cfg, limit=20, order="click",
                                              character_name=char_name, aliases=char_aliases,
                                              debug=True, game=game_id)
                for sv in res_v:
                    bvid = sv.get("bvid") or ""
                    if bvid and bvid not in seen_bvids:
                        seen_bvids.add(bvid)
                        enhanced_evidence.append(sv)
                res_a, meta_a = search_articles(char_name, cfg, limit=10, order="click",
                                                character_name=char_name, aliases=char_aliases,
                                                debug=True, game=game_id)
                for sa in res_a:
                    aid = sa.get("aid")
                    if aid and aid not in seen_aids:
                        seen_aids.add(aid)
                        enhanced_evidence.append(sa)
                # 合并诊断 meta
                for mk in ("queries", "raw", "after_dedupe", "passed_filter"):
                    meta_combined[mk] = meta_v.get(mk, 0) + meta_a.get(mk, 0)
                used = []
                for m in (meta_v.get("aliases_used", []), meta_a.get("aliases_used", [])):
                    for a in (m or []):
                        if a and a not in used:
                            used.append(a)
                meta_combined["aliases_used"] = used
                _enh_meta = meta_combined
            except Exception:
                _enh_meta = None
            if enhanced_evidence:
                sub_part = "（含订阅主播/官方 %d 条）" % sub_count if sub_count else ""
                enhanced_note = "已收集 %d 条筛选后的引用来源%s" % (len(enhanced_evidence), sub_part)
                _set_progress(progress_key, "search", "已收集 %d 条增强参考来源，准备拉取内容…" % len(enhanced_evidence), 25)
            else:
                alias_str = ""
                if _enh_meta and _enh_meta.get("aliases_used"):
                    alias_str = "（已用角色名+别名 %s 发起 %d 个查询，原始命中 %d 条、去重后 %d 条、通过相关性过滤 %d 条）" % (
                        " / ".join(_enh_meta.get("aliases_used", [])),
                        _enh_meta.get("queries", 0),
                        _enh_meta.get("raw", 0),
                        _enh_meta.get("after_dedupe", 0),
                        _enh_meta.get("passed_filter", 0))
                enhanced_note = ("已搜索 B站，但未找到与「%s」高相关的视频/专栏%s"
                                 % (ch.get("name", ""), alias_str)
                                 + " —— 若一直为空：可能是数据中心/沙箱网络无法访问 B站，"
                                 + "或 SESSDATA 失效；请在本机家庭宽带环境运行，并确保设置中已填有效 SESSDATA。")
                _set_progress(progress_key, "search", "未找到高相关来源，直接进行 AI 分析…", 30)
        # ---- NGA 社区检索（独立于 B站；需 NGA Cookie，真实模式才启用） ----
        nga_hits = 0
        if not demo and nga_cookie:
            _set_progress(progress_key, "search", "正在检索 NGA 社区…", 18)
            try:
                char_name = ch.get("name", "")
                char_aliases = ch.get("aliases", []) or []
                nga_items = search_nga(char_name, game_id, nga_cookie,
                                       char_name=char_name, aliases=char_aliases, limit=10)
                nga_hot = hot_nga(game_id, nga_cookie,
                                  char_name=char_name, aliases=char_aliases, days=30, limit=6)
                seen_tids = set()
                for it in list(nga_items) + list(nga_hot):
                    tid = it.get("tid")
                    if tid and tid not in seen_tids:
                        seen_tids.add(tid)
                        enhanced_evidence.append(it)
                nga_hits = sum(1 for e in enhanced_evidence
                               if e.get("result_type") == "forum")
            except Exception:
                nga_hits = 0
            if nga_hits:
                enhanced_note = ("已收集 %d 条引用来源（B站 %d + NGA %d）"
                                 % (len(enhanced_evidence),
                                    len(enhanced_evidence) - nga_hits, nga_hits))
                _set_progress(progress_key, "search",
                              "已收集 %d 条增强参考来源（含 NGA %d 条），准备拉取内容…"
                              % (len(enhanced_evidence), nga_hits), 25)
            elif has_nga_board(game_id):
                enhanced_note = (enhanced_note + " " if enhanced_note else "") \
                    + ("NGA %s 版块已检索但未命中「%s」（或 Cookie 已过期）。"
                       % (nga_board_name(game_id), ch.get("name", "")))
        elif not nga_cookie and has_nga_board(game_id):
            enhanced_note = enhanced_note + " " if enhanced_note else ""
            enhanced_note += "未检索 NGA：设置中未保存 NGA Cookie。"
        elif not has_nga_board(game_id):
            enhanced_note = enhanced_note + " " if enhanced_note else ""
            enhanced_note += "NGA 暂无该游戏版块（异环未开版），未检索。"

    ai = None
    ai_from_cache = False
    if mode in ("ai", "hybrid"):
        cached = _ai_cache_load(game_id, ch_id, enhanced)
        if cached and not force_refresh:
            # 命中缓存：直接复用，不消耗 token
            ai = dict(cached)
            ai_from_cache = True
            _set_progress(progress_key, "ai", "已保存的 AI 分析结果（本次未消耗 token）…", 95)
        else:
            base_evidence = list(rule.get("evidence", []) or [])
            if enhanced_evidence:
                from content_extractor import extract_signals
                existing_by_bvid = {e.get("bvid"): e for e in base_evidence if e.get("bvid")}
                existing_by_aid = {e.get("aid"): e for e in base_evidence if e.get("aid")}
                for v in enhanced_evidence:
                    sigs = extract_signals(v, [ch])
                    for s in sigs:
                        if s.character_id == ch_id:
                            item = s.to_dict()
                            item["age_days"] = 0
                            item["recency_factor"] = 1.0
                            item["subscribed"] = bool(v.get("subscribed"))
                            item["author"] = v.get("author") or ""
                            item["mid"] = v.get("mid") or ""
                            item["is_sample"] = bool(v.get("is_sample", False))
                            item["enhanced"] = True
                            item["bvid"] = v.get("bvid") or ""
                            item["aid"] = v.get("aid") or ""
                            if item["subscribed"]:
                                role_w = {"main": 1.2, "official": 1.0,
                                          "cross_check": 0.9}.get(v.get("source_role"), 0.8)
                            else:
                                role_w = 0.8
                            item["source_weight"] = role_w
                            item["contribution"] = round(s.polarity * s.weight * role_w, 3)
                            dup = existing_by_bvid.get(item["bvid"]) or existing_by_aid.get(item["aid"])
                            if dup is not None:
                                if item["subscribed"]:
                                    dup["subscribed"] = True
                                    dup["author"] = item["author"] or dup.get("author")
                                    dup["mid"] = item["mid"] or dup.get("mid")
                                    dup["source_name"] = item.get("source_name") or dup.get("source_name")
                                    dup["source_role"] = item.get("source_role") or dup.get("source_role")
                                continue
                            base_evidence.append(item)
                            if item["bvid"]:
                                existing_by_bvid[item["bvid"]] = item
                            if item["aid"]:
                                existing_by_aid[item["aid"]] = item
            # 抓取关键证据的实际内容（视频字幕 / 专栏正文），让 AI 做内容级分析
            if sess and not demo and base_evidence:
                vids = [e for e in base_evidence
                        if e.get("bvid") or _bvid_from_url(e.get("url", ""))]
                arts = [e for e in base_evidence
                        if e.get("aid") or _aid_from_url(e.get("url", ""))]
                sub_vids = [e for e in vids if e.get("subscribed")]
                targets = sub_vids[:6] + [e for e in vids if not e.get("subscribed")][:4] + arts[:2]
                total = len(targets)
                done = 0
                for e in targets:
                    txt = ""
                    try:
                        bvid = e.get("bvid") or _bvid_from_url(e.get("url", ""))
                        if bvid:
                            txt = fetch_video_subtitle(bvid, sess)
                        else:
                            aid = e.get("aid") or _aid_from_url(e.get("url", ""))
                            if aid:
                                txt = fetch_article_text(aid, sess)
                    except Exception:
                        txt = ""
                    if txt:
                        e["content"] = txt
                        done += 1
                    _set_progress(progress_key, "content",
                                  "正在拉取视频字幕/专栏正文（%d/%d，成功 %d）…" % (targets.index(e) + 1, total, done),
                                  30 + int(40 * (targets.index(e) + 1) / max(1, total)))
                # NGA 主题正文（文字内容多、对 AI 更友好）
                if nga_cookie:
                    nga_targets = [e for e in enhanced_evidence
                                   if e.get("result_type") == "forum"][:2]
                    for e in nga_targets:
                        try:
                            posts = fetch_nga_posts(e.get("tid"), nga_cookie, max_posts=6)
                            if posts:
                                text = "；".join(posts)[:5000]
                                e["content"] = text
                                # 同步到 base_evidence 中的信号条目（按 url 匹配），供 AI 提示词使用
                                for be in base_evidence:
                                    if be.get("url") == e.get("url"):
                                        be["content"] = text
                        except Exception:
                            pass
                _set_progress(progress_key, "content", "内容抓取完成（%d 条含正文），开始 AI 分析…" % done, 75)
            else:
                _set_progress(progress_key, "content", "未抓取视频内容（示例模式或无 SESSDATA），按标题/简介分析…", 40)
            _set_progress(progress_key, "ai", "AI 分析中…", 80)
            ai = ai_analyze(ch, base_evidence, cfg, game=game_id)
            if ai and isinstance(ai, dict) and ai.get("ok"):
                _ai_cache_save(game_id, ch_id, enhanced, ai)
            _set_progress(progress_key, "ai", "AI 分析完成，正在整理结果…", 90)
        if ai and isinstance(ai, dict):
            ai["from_cache"] = ai_from_cache
            ai["enhanced_evidence_count"] = len(enhanced_evidence)
            ai["enhanced_sources"] = _enhanced_sources_block(enhanced_evidence)
    elif mode == "rule":
        # 规则模式：附带已保存的 AI 结果（保留分析成果，不重复消耗 token）
        cached = _ai_cache_load(game_id, ch_id, enhanced)
        if cached:
            ai = dict(cached)
            ai["from_cache"] = True
            ai["enhanced_evidence_count"] = len(enhanced_evidence)

    # 增强证据来源（顶层，所有模式可用）：供前端展示「收集到的引用资料」
    rule["enhanced_requested"] = enhanced
    rule["enhanced_evidence_count"] = len(enhanced_evidence)
    rule["enhanced_sources"] = _enhanced_sources_block(enhanced_evidence)
    rule["enhanced_note"] = enhanced_note
    effective = "manual" if manual else ("ai" if (ai and ai.get("ok")) else "rule")
    rule["manual"] = manual
    rule["ai"] = ai
    rule["ai_from_cache"] = bool(ai and ai.get("from_cache"))
    rule["analysis_mode"] = mode
    rule["effective"] = effective

    # ===== 官方数据雷达（确定性计算，不依赖 AI，避免幻觉） =====
    try:
        orb = get_radar(ch_id, ch.get("name"), game_id)
        rule["official_radar_scores"] = orb["scores"]
        rule["radar_dims"] = orb.get("dims")
        if game_id == "genshin":
            raw_stats = get_stats(ch_id, game_id)
            rule["official_stats"] = {k: v for k, v in raw_stats.items()
                                      if not k.startswith("_")}
        else:
            rule["official_stats"] = {}
        rule["official_source"] = orb["source"]
        rule["official_fetched"] = orb["fetched"]
        rule["official_missing"] = orb["missing"]
    except Exception:
        pass
    return rule


def _handle_api(path, query, body=None):
    # ---------- 角色列表 ----------
    if path == "/api/characters":
        cfg = load_config()
        # 优先使用前端传入的 ?game= 参数（游戏切换），缺省回退 current_game
        req_game = (query.get("game", [""])[0] or "").strip()
        if req_game and req_game in (cfg.get("games") or {}):
            gid, g = game_state(cfg, req_game)
        else:
            gid, g = game_state(cfg)
        cats = g.get("category_field", "element")
        chars = all_characters(gid)
        overview = analyze_all(gid)
        ov_map = {o["id"]: o for o in overview}
        # 读取手动标注的梯队标签（供卡片徽标与梯队榜使用）
        from manual_analysis import get_all_overrides
        tier_map = {cid: (ov.get("tier") or "") for cid, ov in get_all_overrides().items()}
        out = []
        for c in chars:
            o = ov_map.get(c["id"], {})
            item = {
                "id": c["id"], "name": c["name"],
                "aliases": c.get("aliases", []),
                "element": c.get("element"), "weapon": c.get("weapon"),
                "rarity": c.get("rarity"),
                "version": c.get("version"),
                "status": c.get("status", "released"),
                "note": c.get("note", ""),
                "icon": c.get("icon", ""),
                "icon_fallback": c.get("icon_fallback", ""),
                "verdict": o.get("verdict", "insufficient"),
                "verdict_label": o.get("verdict_label", "数据不足"),
                "net_score": o.get("net_score", 0),
                "evidence_count": o.get("evidence_count", 0),
                "tier": tier_map.get(c["id"], "") or "",
                "category": c.get(cats),
            }
            # 合并已缓存的 AI 结论：角色卡片的推荐度状态在重开后保持（不重新消耗 token）
            cached = _ai_cache_latest(gid, c["id"])
            if cached and cached.get("verdict") in AI_VERDICT_LABELS \
                    and cached.get("verdict") != "insufficient":
                item["verdict"] = cached["verdict"]
                item["verdict_label"] = (cached.get("verdict_label")
                                         or AI_VERDICT_LABELS[cached["verdict"]])
                item["ai_cached"] = True
            if cached:
                item["ai_tier"] = cached.get("tier", "")
            out.append(item)
        return _json({"ok": True, "game": gid,
                      "game_meta": {
                          "display_name": g.get("display_name", gid),
                          "category_field": cats,
                          "category_label": g.get("category_label", "元素"),
                          "category_order": g.get("category_order", []),
                          "current_version": g.get("current_version", ""),
                      },
                      "games": list_games(cfg),
                      "characters": out, "config": _config_block(cfg, gid)})

    # ---------- 切换当前游戏 ----------
    if path == "/api/switch" and body is not None:
        cfg = load_config()
        gid = (body.get("game") or "").strip()
        games = cfg.get("games", {}) or {}
        if gid not in games:
            return _json({"ok": False, "error": "未知游戏：%s" % gid}, 400)
        cfg["current_game"] = gid
        try:
            save_config(cfg)
        except RuntimeError as e:
            return _json({"ok": False, "error": str(e)}, 500)
        except Exception as e:
            return _json({"ok": False, "error": "保存配置失败：%s" % e}, 500)
        return _json({"ok": True, "current_game": gid})

    # ---------- 主播订阅：列表（仅 GET，按当前游戏隔离） ----------
    if path == "/api/streamers" and body is None:
        cfg = load_config()
        gid, g = game_state(cfg)
        return _json({"ok": True, "game": gid,
                      "streamers": g.get("streamers", []),
                      "official": g.get("official", [])})

    # ---------- 主播订阅：新增 ----------
    if path == "/api/streamers" and body is not None:
        cfg = load_config()
        gid, g = game_state(cfg)
        inp = (body.get("input") or "").strip()
        role = body.get("role", "cross_check")
        trusted = bool(body.get("trusted", role == "main"))
        uid = parse_uid_from_input(inp)
        if not uid:
            return _json({"ok": False, "error": "无法解析 UID，请输入数字 UID 或 B 站空间链接"}, 400)
        # 去重（当前游戏内）
        existing = [s for s in g.get("streamers", []) + g.get("official", [])
                    if str(s.get("uid")) == str(uid)]
        if existing:
            return _json({"ok": False, "error": "该 UID 已在本游戏订阅"}, 409)
        # 解析真实频道名（本机可访问 B 站时生效；沙箱会失败但依旧加入）
        try:
            info = resolve_bilibili_user(uid, cfg.get("cookie", {}).get("SESSDATA", ""))
            name = info["name"]
            resolved = True
        except Exception as e:
            name = "UID:%s（未能解析，请在可访问 B 站的本机运行）" % uid
            resolved = False
        item = {"uid": uid, "name": name, "trusted": trusted,
                "role": role, "resolved": resolved}
        if role == "official":
            g.setdefault("official", []).append(item)
        else:
            g.setdefault("streamers", []).append(item)
        try:
            save_config(cfg)
        except RuntimeError as e:
            return _json({"ok": False, "error": str(e)}, 500)
        except Exception as e:
            return _json({"ok": False, "error": "保存配置失败：%s" % e}, 500)
        return _json({"ok": True, "item": item, "resolved": resolved})

    # ---------- 主播订阅：删除 ----------
    if path.startswith("/api/streamers/") and body is not None and body.get("_method") == "DELETE":
        uid = path.split("/")[-1]
        cfg = load_config()
        gid, g = game_state(cfg)
        removed = False
        for key in ("streamers", "official"):
            before = len(g.get(key, []))
            g[key] = [s for s in g.get(key, []) if str(s.get("uid")) != str(uid)]
            if len(g[key]) != before:
                removed = True
        if removed:
            try:
                save_config(cfg)
            except RuntimeError as e:
                return _json({"ok": False, "error": str(e)}, 500)
            except Exception as e:
                return _json({"ok": False, "error": "保存配置失败：%s" % e}, 500)
            return _json({"ok": True, "removed": uid})
        return _json({"ok": False, "error": "未找到该订阅"}, 404)

    # ---------- 主播订阅：修改（信任/角色/名称） ----------
    if path.startswith("/api/streamers/") and body is not None:
        uid = path.split("/")[-1]
        cfg = load_config()
        gid, g = game_state(cfg)
        found = None
        for key in ("streamers", "official"):
            for s in g.get(key, []):
                if str(s.get("uid")) == str(uid):
                    found = s
        if not found:
            return _json({"ok": False, "error": "未找到该订阅"}, 404)
        if "trusted" in body:
            found["trusted"] = bool(body["trusted"])
        if "role" in body and body["role"] in ("main", "cross_check", "official"):
            found["role"] = body["role"]
        if "name" in body:
            found["name"] = body["name"]
        try:
            save_config(cfg)
        except RuntimeError as e:
            return _json({"ok": False, "error": str(e)}, 500)
        except Exception as e:
            return _json({"ok": False, "error": "保存配置失败：%s" % e}, 500)
        return _json({"ok": True, "item": found})

    # ---------- 更新分析（清缓存 + 可选真实重抓） ----------
    if path == "/api/refresh":
        removed = clear_cache()
        cfg = load_config()
        return _json({"ok": True, "cache_cleared": removed,
                      "demo_mode": cfg.get("demo_mode", True),
                      "note": "缓存已清空，下次分析将重新计算。"
                              + ("（当前为示例模式，数据为演示用，非真实视频）"
                                 if cfg.get("demo_mode") else "")})

    # ---------- 单角色分析（合并 rule/ai/manual） ----------
    if path == "/api/analyze":
        char = query.get("character", [""])[0]
        if not char:
            return _json({"ok": False, "error": "缺少 character 参数"}, 400)
        cfg = load_config()
        mode = query.get("mode", [""])[0] or cfg.get("analysis_mode", "rule")
        enhanced = query.get("enhanced", ["0"])[0] in ("1", "true")
        refresh = query.get("refresh", ["0"])[0] in ("1", "true")
        game = query.get("game", [""])[0] or cfg.get("current_game", "genshin")
        pkey = query.get("progress_key", [""])[0]
        _set_progress(pkey, "start", "分析开始…", 5)
        try:
            r = _merged_analysis(char, cfg, mode, enhanced=enhanced,
                                 game_id=game, progress_key=pkey, force_refresh=refresh)
        finally:
            _set_progress(pkey, "done", "分析完成", 100)
        return _json(r)

    # ---------- AI 分析进度（前端轮询） ----------
    if path == "/api/ai-progress" and body is None:
        key = query.get("key", [""])[0]
        p = _AI_PROGRESS.get(key)
        if not p:
            return _json({"ok": False, "error": "无此进度（可能已完成或已过期）"}, 404)
        return _json({"ok": True, "stage": p.get("stage"), "message": p.get("message"),
                      "pct": p.get("pct", 0)})

    # ---------- AI 结果缓存：统计 / 清空 ----------
    if path == "/api/ai-cache":
        if body and body.get("_method") == "DELETE":
            removed = 0
            if os.path.isdir(AI_CACHE_DIR):
                for fn in os.listdir(AI_CACHE_DIR):
                    if fn.endswith(".json"):
                        try:
                            os.remove(os.path.join(AI_CACHE_DIR, fn))
                            removed += 1
                        except Exception:
                            pass
            return _json({"ok": True, "removed": removed,
                          "message": "已清空 %d 个 AI 缓存条目。" % removed})
        items, total = _ai_cache_stats()
        return _json({"ok": True, "count": len(items), "total_size": total,
                      "items": sorted(items, key=lambda x: x.get("cached_at") or "", reverse=True)[:200]})

    # ---------- 官方基础数值 / 技能（hsr=StarRailRes、zzz=biligame，本地 JSON 数据文件） ----------
    if path == "/api/official-data" and body is None:
        cfg = load_config()
        game = query.get("game", [""])[0] or cfg.get("current_game", "genshin")
        cid = query.get("character", [""])[0]
        if not cid:
            return _json({"ok": False, "error": "缺少 character 参数"}, 400)

        def _load(fn):
            p = os.path.join(DATA_DIR, fn)
            if not os.path.exists(p):
                return None
            with open(p, encoding="utf-8") as f:
                return json.load(f)

        if game == "hsr":
            st = _load("hsr_official_stats.json") or {}
            sk = _load("hsr_skills.json") or {}
            stats = (st.get("stats") or {}).get(cid)
            skills = (sk.get("skills") or {}).get(cid, [])
            if stats is None and not skills:
                return _json({"ok": False, "error":
                    "该角色暂无官方数值。请先在「设置 → 数据来源」关闭示例模式并点「在线拉取最新角色名单」（hsr → StarRailRes）。"}, 404)
            return _json({"ok": True, "game": game, "stats": stats, "skills": skills,
                          "date": st.get("date"), "source": st.get("source")})
        if game == "zzz":
            st = _load("zzz_official_stats.json") or {}
            stats = (st.get("stats") or {}).get(cid)
            if stats is None:
                return _json({"ok": False, "error":
                    "该角色暂无官方数值。请先在「设置 → 数据来源」点「在线拉取最新角色名单」（zzz → biligame 百科）。"}, 404)
            return _json({"ok": True, "game": game, "stats": stats,
                          "date": st.get("date"), "source": st.get("source")})
        return _json({"ok": False, "error": "该游戏暂无官方数值数据（原神走雷达图；hsr / zzz 已接入）。"}, 404)

    # ---------- 角色库：精编静态数据重建（hsr/zzz/鸣潮/终末地/异环，离线精编） ----------
    if path == "/api/refresh-characters" and body is not None:
        cfg = load_config()
        gid = (body.get("game") or cfg.get("current_game", "genshin")).strip()
        if gid not in ("hsr", "zzz", "wuthering_waves", "arknights_endfield", "nte"):
            return _json({"ok": False, "error":
                "该游戏不支持重建角色库（支持 hsr/zzz/鸣潮/终末地/异环 精编数据）；原神名单由 build_chars.py 维护，请用在线拉取补齐新版本角色。"}, 400)
        try:
            res = refresh_character_db(gid)
        except Exception as e:
            return _json({"ok": False, "error": "重建角色库失败：%s" % e}, 500)
        if res.get("ok"):
            return _json({"ok": True, **res,
                          "message": "已用精编数据重建 %s 角色库（%d 名，国服官方名），旧文件已备份。"
                                     % (res.get("game"), res.get("count", 0))})
        return _json({"ok": False, "error": res.get("error", "未知错误"),
                      "debug_written": res.get("debug_written")}, 502)

    # ---------- 角色库：联网拉取升级（六游戏官方镜像/百科源） ----------
    if path == "/api/update-db" and body is not None:
        cfg = load_config()
        gid = (body.get("game") or cfg.get("current_game", "genshin")).strip()
        if gid not in ("hsr", "genshin", "arknights_endfield", "zzz", "wuthering_waves", "nte"):
            return _json({"ok": False, "error":
                "未知游戏：%s。" % gid}, 400)
        try:
            res = update_db(gid)
        except Exception as e:
            return _json({"ok": False, "error": "拉取升级失败：%s" % e}, 500)
        if not res.get("ok"):
            code = 200 if res.get("error") in ("network_unavailable",) else 400
            return _json({"ok": False, **res}, code)
        config_updated = False
        if gid == "genshin" and res.get("version_text"):
            g = cfg.get("games", {}).get("genshin")
            if g:
                try:
                    g["current_version"] = res["version_text"]
                    save_config(cfg)
                    config_updated = True
                except Exception:
                    config_updated = False
        return _json({"ok": True, **res, "config_updated": config_updated})

    # ---------- 角色头像：联网拉取真实图标（hsr 支持，写回 data/<game>_characters.json） ----------
    if path == "/api/fetch-avatars" and body is not None:
        cfg = load_config()
        gid = (body.get("game") or cfg.get("current_game", "genshin")).strip()
        try:
            updated, status = fetch_avatars(gid)
        except Exception as e:
            return _json({"ok": False, "error": "拉取头像失败：%s" % e}, 500)
        if status == "unsupported":
            return _json({"ok": False, "error":
                "该游戏暂无可确定性映射的头像源（目前仅 原神 / hsr / 终末地 / 异环 已接入；鸣潮等维持官方属性色卡）。"}, 400)
        if status == "network_unavailable":
            return _json({"ok": False, "error":
                "网络不可用，无法拉取头像。已保留现有数据（官方属性色卡兜底），联网后重试即可。"}, 200)
        return _json({"ok": True, "game": gid, "updated": updated, "status": status,
                      "message": "已为 %s 拉取并写入 %d 个真实头像（仅验证通过的 URL 被写入）。" % (gid, updated)})

    # ---------- 单角色手动标注：读取 ----------
    if path.startswith("/api/characters/") and path.endswith("/analysis") and body is None:
        cid = path.split("/")[3]
        return _json({"ok": True, "character_id": cid, "override": get_override(cid)})

    # ---------- 单角色手动标注：保存（PUT） ----------
    if path.startswith("/api/characters/") and path.endswith("/analysis") and body is not None:
        cid = path.split("/")[3]
        try:
            rec = set_override(cid, body)
            return _json({"ok": True, "override": rec})
        except ValueError as e:
            return _json({"ok": False, "error": str(e)}, 400)

    # ---------- AI 连通性测试 ----------
    if path == "/api/ai/test":
        cfg = load_config()
        return _json({"ok": True, **ai_test(cfg)})

    # ---------- B 站真实连接测试（本机家庭宽带 + SESSDATA 时有效） ----------
    if path == "/api/test-connection":
        cfg = load_config()
        demo = cfg.get("demo_mode", True)
        sess = cfg.get("cookie", {}).get("SESSDATA", "")
        if demo:
            return _json({"ok": True, "mode": "demo", "reachable": None,
                          "message": "当前为示例模式，未连接 B 站。关闭示例模式并填入 SESSDATA 后可测试真实连接。"})
        if not sess:
            return _json({"ok": False, "mode": "live", "reachable": False,
                          "message": "真实模式但未填写 SESSDATA，无法连接 B 站。请在设置中填入登录后的 SESSDATA。"})
        srcs = all_sources(cfg)
        if not srcs:
            return _json({"ok": False, "mode": "live", "reachable": False,
                          "message": "未订阅任何主播/官方来源，无法测试。"})
        tried = []
        sample_titles = []
        for src in srcs[:3]:
            try:
                vs = fetch_videos(src, cfg, force_live=True)
                tried.append(src.get("name"))
                sample_titles.extend([v["title"] for v in vs[:3]])
            except Exception as e:
                return _json({"ok": False, "mode": "live", "reachable": False,
                              "message": "连接 B 站失败：%s。若提示 -352/-412，说明当前网络（数据中心 IP）被风控，"
                                         "需在本机家庭宽带环境运行。" % e,
                              "tried": src.get("name")})
        return _json({"ok": True, "mode": "live", "reachable": True,
                      "message": "连接成功，已抓取到真实视频（共 %d 个来源测试）。" % len(tried),
                      "sample_titles": sample_titles[:5]})

    # ---------- NGA 社区连接测试（本机 + NGA Cookie 时有效） ----------
    if path == "/api/nga/test":
        cfg = load_config()
        gid, g = game_state(cfg)
        cookie = get_nga_cookie(cfg)
        ok, msg = test_connection(gid, cookie)
        return _json({"ok": ok, "game": gid,
                      "board": nga_board_name(gid) if has_nga_board(gid) else "",
                      "cookie_set": bool(cookie),
                      "cookie_masked": mask_cookie(cookie),
                      "message": msg})

    # ---------- 配置：读取（含可编辑设置） ----------
    if path == "/api/config" and body is None:
        cfg = load_config()
        return _json({"ok": True, "config": _config_block(cfg), "settings": _settings_block(cfg)})

    # ---------- 配置：保存（设置面板） ----------
    if path == "/api/config" and body is not None:
        cfg = load_config()
        cfg = _apply_settings(body.get("settings", body), cfg)
        try:
            save_config(cfg)
        except RuntimeError as e:
            return _json({"ok": False, "error": str(e)}, 500)
        except Exception as e:
            return _json({"ok": False, "error": "保存配置失败：%s" % e}, 500)
        return _json({"ok": True, "config": _config_block(cfg), "settings": _settings_block(cfg)})

    # ---------- 抽卡记录：导入（粘贴游戏内 getGachaLog 链接，一键分页拉取） ----------
    if path == "/api/gacha-import" and body is not None:
        cfg = load_config()
        url = (body.get("url") or "").strip()
        game = (body.get("game") or cfg.get("current_game", "genshin")).strip()
        if not url:
            return _json({"ok": False, "error": "请粘贴游戏内「抽卡记录」页面复制出的完整链接。"}, 400)
        try:
            out = import_history(url, game=game)
        except ValueError as e:
            return _json({"ok": False, "error": str(e)}, 400)
        except RuntimeError as e:
            return _json({"ok": False, "error": str(e)}, 502)
        except Exception as e:
            return _json({"ok": False, "error": "导入失败：%s" % e}, 500)
        return _json({"ok": True, "data": out,
                      "message": "已导入 %s 的抽卡记录（%s 抽，5★ %d，4★ %d）。"
                                 % (out.get("game_display"), out.get("summary", {}).get("total_pulls", 0),
                                    out.get("summary", {}).get("total_5", 0),
                                    out.get("summary", {}).get("total_4", 0))})

    # ---------- 抽卡记录：读取 / 清空（本地统计，不含 authkey） ----------
    if path == "/api/gacha-history":
        cfg = load_config()
        game = (query.get("game", [""])[0] or cfg.get("current_game", "genshin")).strip()
        if body and body.get("_method") == "DELETE":
            cleared = clear_history(game)
            return _json({"ok": True, "cleared": cleared,
                          "message": "已清空 %s 的本地抽卡记录。" % game if cleared
                                     else "%s 暂无本地抽卡记录。" % game})
        hist = load_history(game)
        if not hist:
            return _json({"ok": False, "error": "尚无 %s 的本地抽卡记录。请在游戏内打开一次抽卡记录页，复制链接后在「抽卡规划 → 抽卡记录」粘贴导入。"
                         % (game,), "game": game}, 404)
        return _json({"ok": True, "game": game, "data": hist,
                      "supported_games": gacha_supported_games()})

    # ---------- 配装推荐（武器/套装/词条/技能/配队） ----------
    if path == "/api/loadout" and body is None:
        cfg = load_config()
        game = (query.get("game", [""])[0] or cfg.get("current_game", "genshin")).strip()
        cid = query.get("character", [""])[0]
        if not cid:
            return _json({"ok": False, "error": "缺少 character 参数"}, 400)
        ai = _ai_cache_latest(game, cid)
        try:
            r = build_loadout(game, cid, ai=ai)
        except Exception as e:
            return _json({"ok": False, "error": "配装推荐生成失败：%s" % e}, 500)
        return _json(r)

    return _json({"ok": False, "error": "unknown api: " + path}, 404)


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, headers, body):
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        if path.startswith("/api/"):
            status, headers, body = _handle_api(path, query)
            self._send(status, headers, body)
            return
        # 头像静态资源（本地自包含：enka.network 的 .png + jmp.blue 的 .webp）
        if path.startswith("/avatars/"):
            fname = os.path.basename(path)
            fpath = os.path.join(AVATAR_DIR, fname)
            ext = os.path.splitext(fname)[1].lower()
            if os.path.exists(fpath) and ext in (".webp", ".png"):
                ctype = "image/webp" if ext == ".webp" else "image/png"
                with open(fpath, "rb") as f:
                    self._send(200, {"Content-Type": ctype}, f.read())
            else:
                self._send(404, {}, b"not found")
            return
        # 前端
        if path in ("/", "/index.html"):
            fpath = os.path.join(FRONTEND_DIR, "index.html")
        else:
            fpath = os.path.normpath(os.path.join(FRONTEND_DIR, path.lstrip("/")))
            if not fpath.startswith(FRONTEND_DIR):
                self._send(403, {}, b"forbidden")
                return
        if not os.path.exists(fpath):
            self._send(404, {}, b"not found")
            return
        ctype = "text/html; charset=utf-8"
        if fpath.endswith(".js"):
            ctype = "application/javascript; charset=utf-8"
        elif fpath.endswith(".css"):
            ctype = "text/css; charset=utf-8"
        elif fpath.endswith(".json"):
            ctype = "application/json; charset=utf-8"
        with open(fpath, "rb") as f:
            self._send(200, {"Content-Type": ctype}, f.read())

    def do_POST(self):
        self._method("POST")

    def do_PUT(self):
        self._method("PUT")

    def do_PATCH(self):
        self._method("PATCH")

    def do_DELETE(self):
        self._method("DELETE")

    def _method(self, m):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            body = {}
        body = body or {}
        # DELETE 通过 body._method 标记（前端可能用 POST 模拟）
        if m == "DELETE":
            body = {"_method": "DELETE"}
        status, headers, out = _handle_api(path, {}, body)
        self._send(status, headers, out)

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("gacha-advisor running at http://localhost:%d" % PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
