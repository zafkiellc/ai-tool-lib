# -*- coding: utf-8 -*-
"""抽卡记录自动导入（米哈游系官方 getGachaLog 接口）。

原理：用户在游戏内打开一次「抽卡记录」页面即可获得带 authkey 的链接
（authkey 有时效，过期需重新打开一次）。本模块解析该链接，按各卡池类型
分页拉取历史抽卡记录，统计 5★/4★ 出货与垫抽数，并写入本地
data/gacha_history_<game>.json（不保存 authkey，仅存统计与角色名）。

仅支持米哈游三件套（原神 / 星穹铁道 / 绝区零）——官方公开的 getGachaLog
接口。鸣潮 / 终末地 / 异环 无官方抽卡记录接口，返回明确提示。
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 各游戏卡池类型（按优先级排序；空列表即无官方接口）
GACHA_TYPES = {
    "genshin": {"301": "角色活动", "302": "武器活动", "200": "常驻", "100": "新手"},
    "hsr": {"11": "角色活动", "12": "角色活动·复刻", "21": "光锥活动", "2": "常驻", "1": "新手"},
    "zzz": {"2": "独家频道·角色", "3": "独家频道·音擎", "1": "常驻", "5": "邦布频道"},
}

GAME_DISPLAY = {
    "genshin": "原神",
    "hsr": "崩坏：星穹铁道",
    "zzz": "绝区零",
    "wuthering_waves": "鸣潮",
    "arknights_endfield": "终末地",
    "nte": "异环",
}


def _history_path(game):
    return os.path.join(DATA_DIR, "gacha_history_%s.json" % game)


def supported_games():
    return list(GACHA_TYPES.keys())


def detect_game(url, hint=None):
    """从链接主机名/路径推断游戏；hint（当前游戏）仅作兜底。"""
    host = (urllib.parse.urlparse(url).netloc or "").lower()
    path = urllib.parse.urlparse(url).path.lower()
    if "hk4e" in host or "hk4e" in path or "ys" in host:
        return "genshin"
    if "hkrpg" in host or "hkrpg" in path or "sr" in host:
        return "hsr"
    if "nap" in host or "zzz" in host or "nap" in path:
        return "zzz"
    return hint if hint in GACHA_TYPES else ""


def _http_get_json(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://webstatic.mihoyo.com/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _build_page_url(base_url, gacha_type, page, size=20, end_id=0):
    """保留用户链接的全部参数（authkey/sign_type/lang/region…），仅替换分页参数。"""
    parsed = urllib.parse.urlsplit(base_url)
    q = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    q["gacha_type"] = [str(gacha_type)]
    q["page"] = [str(page)]
    q["size"] = [str(size)]
    q["end_id"] = [str(end_id)]
    return urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc, parsed.path,
        urllib.parse.urlencode(q, doseq=True), ""))


def _pull_key(p):
    return p.get("id") or "%s|%s|%s" % (p.get("time"), p.get("gacha_type"), p.get("name"))


def fetch_game_history(url, game, timeout=15, max_pages_per_type=30):
    """分页拉取指定游戏的抽卡记录，返回原始条目（按卡池分组）。"""
    if game not in GACHA_TYPES:
        raise ValueError("游戏 %s 暂无官方抽卡记录接口（仅支持原神/星穹铁道/绝区零）。"
                         % GAME_DISPLAY.get(game, game))
    types = list(GACHA_TYPES[game].keys())
    banners = {}
    seen = set()
    for gt in types:
        end_id = 0
        page = 1
        items = []
        while page <= max_pages_per_type:
            url_page = _build_page_url(url, gt, page, end_id=end_id)
            try:
                d = _http_get_json(url_page, timeout)
            except Exception as e:
                raise RuntimeError("拉取 %s(%s) 第 %d 页失败：%s（若提示 401/404，请重新在游戏内打开一次抽卡记录页复制新链接）"
                                   % (GAME_DISPLAY.get(game, game), GACHA_TYPES.get(game, {}).get(gt, gt), page, e))
            ret = d.get("retcode")
            if ret not in (0, None) or d.get("message") in ("authkey valid time expired", "authkey is invalid"):
                raise RuntimeError("接口拒绝访问（retcode=%s）：%s。authkey 有时效，请重新打开一次游戏内抽卡记录页复制新链接。"
                                   % (ret, d.get("message", "")))
            data = d.get("data") or {}
            lst = data.get("list") or []
            if not lst:
                break
            page += 1
            items.extend(lst)
            if len(items) >= (data.get("total") or 0) > 0:
                break
            if data.get("page") == data.get("size") or len(lst) < 20:
                break
            end_id = lst[-1].get("id") or end_id
            time.sleep(0.25)
        # 去重（跨页可能出现重复条目）
        uniq = []
        for p in items:
            k = _pull_key(p)
            if k in seen:
                continue
            seen.add(k)
            uniq.append(p)
        if uniq:
            banners[str(gt)] = {"gacha_type": str(gt),
                                "label": GACHA_TYPES[game].get(str(gt), "未知卡池"),
                                "items": uniq}
    if not banners:
        raise RuntimeError("链接有效但未拉取到任何记录。请确认链接来自该游戏，并在本机（家庭宽带）运行。")
    return banners


def _norm(s):
    return re.sub(r"[\s·・.．_\-—]+", "", str(s or "")).lower()


def _char_lookup(game):
    """游戏角色名/别名/英文名 → 本地角色 id。"""
    path = os.path.join(DATA_DIR, "%s_characters.json" % game)
    lookup = {}
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        return lookup
    for c in doc.get("characters", []) or []:
        cid = c.get("id")
        if not cid:
            continue
        for nm in [c.get("name"), c.get("en")] + list(c.get("aliases") or []):
            n = _norm(nm)
            if n:
                lookup.setdefault(n, cid)
    return lookup


def summarize_banner(items, game):
    """按卡池统计：总数 / 5★ / 4★ / 当前垫抽 / 五星清单。"""
    lookup = _char_lookup(game)
    five = []
    four = 0
    since = 0
    pity_list = []
    for p in reversed(items):  # 时间正序 → 逆序统计
        rk = int(p.get("rank_type") or 0)
        since += 1
        if rk >= 5:
            five.append({
                "name": p.get("name", ""),
                "item_type": p.get("item_type", ""),
                "time": p.get("time", ""),
                "pity": since,
                "local_id": lookup.get(_norm(p.get("name"))),
            })
            pity_list.append(since)
            since = 0
        elif rk == 4:
            four += 1
    return {
        "total": len(items),
        "five_count": len(five),
        "four_count": four,
        "current_pity": since,       # 距上次 5★ 已垫抽数
        "five_stars": list(reversed(five)),
        "recent": [{"name": p.get("name", ""), "item_type": p.get("item_type", ""),
                    "rank": int(p.get("rank_type") or 0), "time": p.get("time", "")}
                   for p in items[-20:][::-1]],
    }


def import_history(url, game=None, timeout=15):
    """入口：导入链接 → 写本地文件 → 返回统计摘要。"""
    url = (url or "").strip()
    if not url or "getGachaLog" not in url:
        raise ValueError("链接无效：请从游戏内「抽卡记录」页面复制包含 getGachaLog 的完整链接。")
    game = detect_game(url, game)
    if not game:
        raise ValueError("无法识别该链接对应的游戏。请先切换到对应游戏再导入。")
    banners = fetch_game_history(url, game, timeout=timeout)

    summary_banners = {}
    total = 0
    total5 = 0
    total4 = 0
    uid = ""
    for gt, b in banners.items():
        s = summarize_banner(b["items"], game)
        s["label"] = b["label"]
        s["gacha_type"] = gt
        summary_banners[gt] = s
        total += s["total"]
        total5 += s["five_count"]
        total4 += s["four_count"]
        for it in b["items"]:
            if it.get("uid"):
                uid = str(it["uid"])
    out = {
        "game": game,
        "game_display": GAME_DISPLAY.get(game, game),
        "imported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "uid": uid,
        "source_host": urllib.parse.urlparse(url).netloc,
        "banners": summary_banners,
        "summary": {"total_pulls": total, "total_5": total5, "total_4": total4},
        "note": "抽卡记录为本地导入，不含 authkey；仅统计与角色名。",
    }
    path = _history_path(game)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return out


def load_history(game):
    path = _history_path(game)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear_history(game):
    path = _history_path(game)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
