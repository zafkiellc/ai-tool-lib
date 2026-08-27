# -*- coding: utf-8 -*-
"""NGA 玩家社区（bbs.nga.cn）检索：作为游戏社区论证数据源。

能力（均需登录 Cookie，本机运行）：
- search_nga：按角色名在对应游戏版块搜索主题（thread.php?key=…&__output=11）
- hot_nga  ：拉取版块近 N 天热帖（app_api.php?__lib=subject&__act=hot）
- fetch_nga_posts：读取主题正文（read.php?tid=…&__output=11）

Cookie 仅保存在本机 config.json 的 cookie.NGA_COOKIE，接口响应一律掩码，绝不回传原文。
版块 fid 来自 forum.php 版面树（2026-08 实测）：原神650 / 星铁818 / 绝区零853 / 鸣潮854 / 终末地846。
异环暂未开设 NGA 版块，返回空并给出说明。
"""
import json
import re
import time
import urllib.parse
import urllib.request

from common import load_config, game_keywords

UA = "NGA_WP_JW Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
BASE = "https://bbs.nga.cn"

# 各游戏 NGA 主版块 fid（forum.php 版面树实测；异环未开版）
NGA_FIDS = {
    "genshin": 650,
    "hsr": 818,
    "zzz": 853,
    "wuthering_waves": 854,
    "arknights_endfield": 846,
}

OTHER_GAME_NAMES = {
    "genshin": ["星穹", "崩坏", "星铁", "绝区零", "鸣潮", "方舟", "异环", "hsr", "zzz", "wuwa", "endfield"],
    "hsr": ["原神", "提瓦特", "绝区零", "鸣潮", "方舟", "异环", "genshin", "zzz", "wuwa"],
    "zzz": ["原神", "星穹", "崩坏", "星铁", "鸣潮", "方舟", "异环", "genshin", "hsr", "wuwa"],
    "wuthering_waves": ["原神", "星穹", "崩坏", "星铁", "绝区零", "方舟", "异环", "genshin", "hsr", "zzz"],
    "arknights_endfield": ["原神", "星穹", "崩坏", "星铁", "绝区零", "鸣潮", "异环", "genshin", "hsr", "zzz", "wuwa"],
    "nte": ["原神", "星穹", "崩坏", "星铁", "绝区零", "鸣潮", "方舟", "genshin", "hsr", "zzz", "wuwa"],
}


def get_nga_cookie(cfg=None):
    cfg = cfg or load_config()
    return ((cfg.get("cookie") or {}).get("NGA_COOKIE") or "").strip()


def mask_cookie(c):
    """掩码 Cookie：仅显示前 8 位与后 4 位，防止在响应/日志中泄露原文。"""
    c = (c or "").strip()
    if not c:
        return ""
    if len(c) <= 16:
        return c[:4] + "…"
    return c[:8] + "…" + c[-4:]


def has_nga_board(game):
    return game in NGA_FIDS


def board_name(game):
    return {650: "原神", 818: "崩坏：星穹铁道", 853: "绝区零",
            854: "鸣潮", 846: "明日方舟终末地"}.get(NGA_FIDS.get(game), "")


def _request(url, cookie, timeout=20):
    headers = {"User-Agent": UA, "Referer": BASE + "/", "Cookie": cookie}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    # __output=11 为 UTF-8；个别接口可能回 GBK，做兜底
    try:
        return raw.decode("utf-8")
    except Exception:
        return raw.decode("gbk", "replace")


def _parse_json(body):
    """宽松 JSON 解析（NGA 偶发 alterinfo 含 \\t 等导致解析失败）。"""
    try:
        return json.loads(body)
    except Exception:
        # 去掉控制字符后再试（不保留 alterinfo 原文，仅取正文足够）
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", body)
        return json.loads(cleaned)


def _clean_ubb(text):
    """去除 NGA UBB/HTML 标签，压平空白。"""
    t = re.sub(r"\[[^\]]*\]", " ", text or "")
    t = re.sub(r"<br\s*/?>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _thread_url(tid):
    return "%s/read.php?tid=%s" % (BASE, tid)


def _relevance(title, content, char_name, aliases, game):
    """标题/正文是否命中角色名或别名，且无跨游戏污染。"""
    t = (title or "") + " " + (content or "")
    names = [n for n in ([char_name] + list(aliases or [])) if n and len(str(n).strip()) >= 2]
    if not names:
        return 0.0
    hit = 0.0
    for n in names:
        n = str(n)
        if n in t:
            hit = max(hit, 1.0 if len(n) >= 3 else 0.7)
    if hit <= 0:
        return 0.0
    # 跨游戏污染
    tl = t.lower()
    kws = [k.lower() for k in game_keywords(game)]
    if not any(k in tl for k in kws):
        for other in OTHER_GAME_NAMES.get(game, []):
            if other.lower() in tl:
                hit *= 0.3
    return round(hit, 2)


def _normalize_thread(v, char_name, aliases, game, src_label):
    tid = v.get("tid")
    subject = _clean_ubb(v.get("subject", ""))
    postdate = int(v.get("postdate") or 0)
    rel = _relevance(subject, "", char_name, aliases, game)
    if rel <= 0:
        return None
    return {
        "title": subject,
        "url": _thread_url(tid),
        "tid": str(tid),
        "author": v.get("author", ""),
        "postdate": postdate,
        "pubdate_str": time.strftime("%Y-%m-%d", time.localtime(postdate)) if postdate else "",
        "replies": int(v.get("replies") or 0),
        "recommend": int(v.get("recommend") or 0),
        "play": int(v.get("replies") or 0),     # 兼容前端播放量展示 → 用回复数
        "like": int(v.get("recommend") or 0),   # 用推荐/赞数
        "favorite": 0,
        "relevance": rel,
        "source_name": src_label,
        "source_role": "search",
        "trusted": False,
        "is_sample": False,
        "result_type": "forum",
    }


def search_nga(keyword, game, cookie, char_name=None, aliases=None, limit=15, page=1):
    """按角色名在游戏版块内搜索主题（thread.php?key=…）。失败/无 cookie 返回 []。"""
    fid = NGA_FIDS.get(game)
    if not fid or not cookie:
        return []
    try:
        params = {
            "fid": str(fid), "key": keyword, "page": str(page),
            "order_by": "lastpostdesc", "__output": "11",
        }
        url = BASE + "/thread.php?" + urllib.parse.urlencode(params)
        d = _parse_json(_request(url, cookie))
    except Exception:
        return []
    data = d.get("data") or {}
    rows = data.get("__T") or []
    if isinstance(rows, dict):
        rows = list(rows.values())
    out = []
    for v in rows:
        if not isinstance(v, dict) or not v.get("tid"):
            continue
        item = _normalize_thread(v, char_name or keyword, aliases, game,
                                 "NGA论坛·%s" % board_name(game))
        if item:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def hot_nga(game, cookie, char_name=None, aliases=None, days=7, limit=15):
    """拉取版块近 N 天热帖并按角色相关性过滤。失败返回 []。"""
    fid = NGA_FIDS.get(game)
    if not fid or not cookie:
        return []
    try:
        url = BASE + "/app_api.php?" + urllib.parse.urlencode({
            "__lib": "subject", "__act": "hot", "fid": str(fid),
            "days": str(days), "__output": "11"})
        d = _parse_json(_request(url, cookie))
    except Exception:
        return []
    rows = d.get("data") if isinstance(d, dict) else d
    if isinstance(rows, dict):
        rows = rows.get("__T") or list(rows.values())
    if not isinstance(rows, list):
        return []
    out = []
    for v in rows:
        if not isinstance(v, dict) or not v.get("tid"):
            continue
        item = _normalize_thread(v, char_name or "", aliases or [], game,
                                 "NGA热帖·%s" % board_name(game))
        if item:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def fetch_nga_posts(tid, cookie, max_posts=8):
    """读取主题首页正文（主楼 + 前若干回复），返回纯文本列表。失败返回 []。"""
    if not cookie or not tid:
        return []
    try:
        url = BASE + "/read.php?" + urllib.parse.urlencode({
            "tid": str(tid), "page": "1", "__output": "11"})
        d = _parse_json(_request(url, cookie))
    except Exception:
        return []
    data = d.get("data") or {}
    posts = data.get("__R") or []
    if not isinstance(posts, list):
        return []
    out = []
    for p in posts:
        if not isinstance(p, dict):
            continue
        c = _clean_ubb(p.get("content", ""))
        if len(c) >= 8:
            out.append(c)
        if len(out) >= max_posts:
            break
    return out


def test_connection(game, cookie):
    """测试 NGA 连通性：搜索一次当前游戏版块。返回 (ok, message)。"""
    if not cookie:
        return False, "未配置 NGA Cookie，无法连接。请在设置中粘贴登录后的 NGA Cookie。"
    if not has_nga_board(game):
        return False, "该游戏在 NGA 暂无对应版块（异环未开版），无需 Cookie。"
    try:
        rows = search_nga("角色", game, cookie, char_name="角色", limit=3)
        if rows:
            return True, "连接成功：已检索到 %s 版块 %d 条相关主题（掩码 %s）。" % (
                board_name(game), len(rows), mask_cookie(cookie))
        return True, "连接成功（版块 %s 可访问），但关键词「角色」暂无命中。" % board_name(game)
    except Exception as e:
        return False, "连接失败：%s。请确认 Cookie 未过期（重新登录 NGA 复制 Cookie），并在家庭宽带网络运行。" % e
