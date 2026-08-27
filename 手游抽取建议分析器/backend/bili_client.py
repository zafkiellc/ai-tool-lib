"""B 站数据抓取：按 UID 拉取视频列表，支持真实抓取与离线示例降级。"""
import json
import os
import re
import time
import urllib.request

from common import (BiliClient, SAMPLE_DIR, cache_get, cache_set,
                    load_config, now_ts, BASE_DIR, UA, game_keywords)


def _is_game_relevant(text, game="genshin"):
    """判断文本是否与指定游戏相关（按游戏关键词匹配）。"""
    t = (text or "").lower()
    kw = game_keywords(game)
    # 正向匹配：包含该游戏任一关键词
    if any(k.lower() in t for k in kw):
        return True
    return False


def _is_cross_game_contamination(text, target_game="genshin"):
    """检测文本是否混入了其他游戏的内容（跨游戏污染检测）。

    若文本中出现「目标游戏以外的游戏名」且不含目标游戏自身关键词，
    则判定为跨游戏污染。
    """
    t = (text or "").lower()
    target_kw = set(k.lower() for k in game_keywords(target_game))
    # 目标游戏自身的关键词是否出现
    has_target = any(k in t for k in target_kw)
    if has_target:
        return False  # 已确认是目标游戏内容，不算污染

    # 检查是否出现其他游戏名
    other_games = {
        "genshin": ["星穹", "崩坏", "星铁", "绝区零", "鸣潮", "方舟", "异环", "NTE",
                    "honkai", "hsr", "zzz", "wuthering", "arknights"],
        "hsr": ["原神", "提瓦特", "蒙德", "璃月", "稻妻", "须弥", "枫丹", "纳塔",
               "genshin", "绝区零", "鸣潮", "方舟", "异环"],
        "zzz": ["原神", "提瓦特", "星穹", "崩坏", "星铁", "鸣潮", "方舟"],
        "wuthering_waves": ["原神", "提瓦特", "星穹", "崩坏", "星铁", "绝区零", "方舟"],
        "arknights_endfield": ["原神", "提瓦特", "星穹", "崩坏", "绝区零", "鸣潮"],
        "nte": ["原神", "提瓦特", "星穹", "崩坏", "绝区零", "鸣潮"],
    }
    other_names = other_games.get(target_game, [])
    found_other = [n for n in other_names if n in t]
    return len(found_other) > 0


def _normalize_vlist(vlist, source, game="genshin"):
    out = []
    for v in vlist:
        # B站 x/space/wbi/arc/search 返回 created（Unix 时间戳），非 pubdate
        pub = int(v.get("pubdate") or v.get("created") or 0)
        text = " ".join([
            v.get("title", ""), v.get("description", ""), v.get("tag", "")
        ])
        # 用户手动订阅的主播/官方号：其发布内容默认视为游戏相关（避免误杀）
        # 仅在关键词搜索场景才需要 strict relevance 过滤
        is_subscribed = source.get("role") in ("main", "cross_check", "official")
        # 跨游戏污染检测：如果文本出现其他游戏名但不含当前游戏关键词，标记为不相关
        relevant = is_subscribed or (_is_game_relevant(text, game) and not _is_cross_game_contamination(text, game))
        out.append({
            "bvid": v.get("bvid"),
            "aid": v.get("aid"),
            "title": v.get("title", ""),
            "description": v.get("description", ""),
            "tag": v.get("tag", ""),
            "author": v.get("author", source.get("name")),
            "mid": v.get("mid", source.get("uid")),
            "pubdate": pub,
            "pubdate_str": time.strftime("%Y-%m-%d", time.localtime(pub)) if pub else "",
            "play": v.get("play", 0),
            "pic": v.get("pic", ""),
            "url": "https://www.bilibili.com/video/" + v.get("bvid", ""),
            "relevant": relevant,
        })
    return out


def _fetch_live(source, cfg, client, game="genshin"):
    """真实抓取：拉取多页，最多约 100 条。"""
    videos = []
    for pn in range(1, 4):
        params = {
            "mid": str(source["uid"]),
            "ps": "30",
            "pn": str(pn),
            "order": "pubdate",
            "keyword": "",
        }
        data = client.get_json(
            "https://api.bilibili.com/x/space/wbi/arc/search", params=params)
        if data.get("code") != 0:
            raise RuntimeError("bili api code=%s msg=%s" %
                               (data.get("code"), data.get("message")))
        vlist = data.get("data", {}).get("list", {}).get("vlist", [])
        if not vlist:
            break
        videos.extend(_normalize_vlist(vlist, source, game))
        if len(vlist) < 30:
            break
    return videos


def _fetch_sample(source, game="genshin"):
    """示例数据：读取 data/samples/space_<uid>.json（明确标记为示例，非真实视频）。"""
    path = os.path.join(SAMPLE_DIR, "space_%s.json" % source["uid"])
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    vlist = data.get("data", {}).get("list", {}).get("vlist", [])
    return _normalize_vlist(vlist, source, game)


def fetch_videos(source, cfg=None, force_live=False, game="genshin"):
    """返回该来源（已归一化）的视频列表。优先缓存。

    - demo_mode=True 或 未配置 SESSDATA：返回【示例数据】（带 is_sample 标记）。
    - demo_mode=False 且 配置了 SESSDATA：真实抓取 B 站；失败则严格返回空（不伪装成真实）。
    """
    cfg = cfg or load_config()
    cache_key = "videos_%s_%s" % (game, source["uid"])
    cached = cache_get(cache_key)
    if cached is not None and not force_live:
        return cached

    demo = cfg.get("demo_mode", True)
    sess = cfg.get("cookie", {}).get("SESSDATA", "")
    use_live = force_live or (not demo and sess)
    videos = []
    source_mode = "sample"
    is_sample = True
    if use_live:
        try:
            client = BiliClient(sess)
            videos = _fetch_live(source, cfg, client, game)
            source_mode = "live"
            is_sample = False
        except Exception as e:
            videos = []
            source_mode = "live_failed:%s" % e
            is_sample = False
    if not videos:
        if is_sample:
            # demo 模式或真实抓取失败：仅 demo 模式才用示例填充
            if demo:
                videos = _fetch_sample(source, game)
                source_mode = "sample"
                is_sample = True
            else:
                videos = []
                source_mode = "empty(no_data)"
                is_sample = False

    # 给每条视频附加来源元信息
    for v in videos:
        v["source_uid"] = source["uid"]
        v["source_name"] = source["name"]
        v["source_role"] = source.get("role", "normal")
        v["trusted"] = bool(source.get("trusted", False))
        v["source_mode"] = source_mode
        v["is_sample"] = is_sample
    cache_set(cache_key, videos)
    return videos


def all_sources(cfg=None, game=None):
    """返回订阅来源（主播 + 官方），按当前游戏隔离。

    每个游戏有独立的主播订阅（主播不一定重合，不能通用）。
    """
    cfg = cfg or load_config()
    from common import game_state
    _, g = game_state(cfg, game)
    srcs = []
    for s in g.get("streamers", []):
        srcs.append(dict(s))
    for o in g.get("official", []):
        srcs.append(dict(o))
    return srcs


# ---------------------- 搜索过滤关键词 ----------------------

# 角色分析/评测相关的高价值关键词（用于搜索查询增强 + 结果相关性评分）
ANALYSIS_KEYWORDS = [
    # 评测类
    "评测", "测评", "分析", "解析", "盘点", "排行", "梯队", "强度榜",
    "角色评测", "强度分析", "价值分析", "抽取建议", "抽卡建议", "值得抽",
    # 强度/强度向
    "强度", "T0", "T1", "T2", "人权卡", "必抽", "推荐", "不推荐",
    "天花板", "下限", "上限", "输出", "DPS", "伤害",
    # 培养/使用
    "培养", "攻略", "配队", "阵容", "圣遗物", "武器推荐", "命座",
    "天赋", "突破", "材料", "毕业",
    # 实战场景
    "深渊", "竞速", "速通", "大世界", "探索", "挖矿",
    "元素反应", "蒸发", "融化", "绽放", "超载", "冻结", "扩散", "结晶", "感电",
    "激化", "绽放", "超绽放", "烈绽放",
    # 功能性
    "辅助", "增伤", "减抗", "聚怪", "盾", "治疗", "奶", "挂元素",
    "功能性", "通用性", "就业", "泛用",
    # 其他高价值信号
    "XP", "颜值", "厨力", "老婆", "老公", "萌新",
    "性价比", "保值", "未来可期", "复刻",
]

# 高权重关键词（标题包含这些 → 直接高相关）
HIGH_WEIGHT_KEYWORDS = [
    "评测", "测评", "强度", "分析", "解析", "抽取建议", "值得抽",
    "角色评测", "强度分析", "价值分析", "T0", "人权卡", "必抽",
    "培养攻略", "配队", "深渊", "DPS",
]

# 无关/低质量关键词（标题包含这些 → 降低相关性）
NOISE_KEYWORDS = [
    "整活", "鬼畜", "MMD", "手书", "AMV", "混剪", "二创",
    "过场动画", "CG", "PV", "预告片", "宣传片",
    "表情包", "梗图", "玩梗", "搞笑",
    "<em", "</em>", "keyword",  # HTML 标签残留
]


import re as _re

_HTML_TAG_RE = _re.compile(r'<[^>]+>')


def _strip_html(text):
    """去除文本中的 HTML 标签。"""
    return _HTML_TAG_RE.sub('', text or "").strip()


def _score_relevance(title, description="", character_name="", aliases=None, game="genshin"):
    """对单条搜索结果进行相关性评分（0.0 ~ 1.0）。

    用于在原始搜索结果中筛选出真正与「角色分析/评测」相关的内容。
    游戏感知：跨游戏内容（提到其他游戏名但不含当前游戏关键词）大幅降权。

    改进：把「角色名/别名是否真的出现在结果里」纳入评分——
    命中的才是该角色的评测，未命中的（标题里完全没有该角色名或别名）
    即便带分析关键词也可能是别的角色的评测/泛泛而谈，给予轻微惩罚，
    避免把无关内容当成该角色的证据。
    """
    clean_title = _strip_html(title or "").lower()
    desc_lower = _strip_html(description or "").lower()

    # 角色名 + 别名的归一化集合（用于判断是否真的是该角色）
    names = set()
    if character_name:
        names.add(character_name.lower())
    for a in (aliases or []):
        if a:
            names.add(a.lower())

    score = 0.2  # 基础分（至少搜到了这个角色名）
    
    # ===== 跨游戏污染检测（关键修复）=====
    # 如果结果中出现「其他游戏名」但没有目标游戏关键词 → 严重降权
    if _is_cross_game_contamination(title + " " + (description or ""), game):
        score -= 0.4  # 跨游戏污染：大概率是其他游戏的同名角色或无关内容
        # 但如果明确提到了目标角色名，稍微回退一点惩罚
        if names and any(n in clean_title for n in names):
            score += 0.15  # 确实是目标角色，只是被其他游戏名带偏了

    if names:
        name_in_title = any(n in clean_title for n in names)
        name_in_desc = any(n in desc_lower for n in names)
        if name_in_title:
            score += 0.25   # 明确是该角色的评测/分析
        elif name_in_desc:
            score += 0.10   # 标题没写全名，但简介提及（如梯队盘点类视频）
        else:
            score -= 0.05   # 完全没提到该角色，可能是别的角色的评测，略降权

    # 1. 高权重关键词匹配（每个 +0.15）
    for kw in HIGH_WEIGHT_KEYWORDS:
        if kw.lower() in clean_title:
            score += 0.15

    # 2. 一般分析关键词匹配（每个 +0.05）
    for kw in ANALYSIS_KEYWORDS:
        if kw.lower() in clean_title:
            score += 0.05

    # 3. 噪音词扣分
    for kw in NOISE_KEYWORDS:
        if kw.lower() in clean_title:
            score -= 0.2

    # 4. 标题长度合理性（太短或太长都可能是垃圾）
    title_len = len(clean_title)
    if 8 <= title_len <= 50:
        score += 0.1   # 合理长度加分
    elif title_len < 5:
        score -= 0.15  # 太短可能是无意义内容

    return min(1.0, max(0.0, score))


def subscribed_video_relevance(video, character_name=None, aliases=None, game="genshin"):
    """订阅主播/官方投稿的角色级相关性过滤（低播放量不限制）。

    订阅来源直接拉取整页投稿，不能像搜索那样依赖“命中了角色名查询”，
    必须硬性校验标题/简介是否真正提到当前角色，并把 PV/动画/其他游戏内容剔除。
    返回 0.0 表示不采用；返回 >0 为实际相关性评分。
    """
    title = _strip_html(video.get("title") or "")
    desc = _strip_html(video.get("description") or "")
    rel = _score_relevance(title, desc, character_name, aliases, game)
    names = set()
    if character_name:
        names.add(character_name.lower())
    for a in (aliases or []):
        a = (a or "").strip()
        if len(a) >= 2:
            names.add(a.lower())
    hit = any(n in title.lower() or n in desc.lower() for n in names) if names else False
    if not hit:
        return 0.0
    title_l = title.lower()
    if any(k.lower() in title_l for k in NOISE_KEYWORDS):
        return 0.0
    role = video.get("source_role") or ""
    if role == "official":
        analysis_text = title_l + " " + desc.lower()
        if not any(k.lower() in analysis_text
                   for k in HIGH_WEIGHT_KEYWORDS + ANALYSIS_KEYWORDS):
            return 0.0
        if rel < 0.35:
            return 0.0
    elif rel < 0.3:
        return 0.0
    return rel


def _alias_priority(alias):
    """估算某个别名作为 B站 搜索词的「优先级加成」。

    经验规律（不臆测具体角色，仅按通用命名特征加权）：
    - 以「神」结尾且长度<=3：绝大多数是「七神」称号（水神/雷神/火神…），
      在 UP主 标题里出现频率远高于全名，搜索召回的评测最集中 → 最高加成。
    - 长度<=2 的短昵称（芙芙/钟钟…）：精准且常用 → 小幅加成。
    - 其余：0。
    """
    a = (alias or "").strip()
    if not a:
        return 0.0
    if a.endswith("神") and len(a) <= 3:
        return 0.4
    if len(a) <= 2:
        return 0.15
    return 0.0


def _build_search_queries(character_name, aliases=None, game="genshin"):
    """为角色生成多个搜索查询（角色名+别名 + 高价值关键词组合）。

    改进：
    - 去重名字（避免主名与别名首位重复浪费槽位）；
    - 别名覆盖上限从 3 提到 5，避免「枫丹女神」这类高相关昵称被丢弃；
    - 每个名字的查询权重 = 基础权重 + 该名字的搜索优先级加成
      （神名/短昵称权重更高，符合「有的昵称搜索优先级更高」的实际情况）；
    - **游戏名注入（跨游戏隔离核心）**：每个查询都拼接当前游戏的官方简称
      （如「原神」「星穹铁道」「绝区零」），从源头让 B站 返回本游戏内容，
      避免「普通名字命中其他游戏同名角色」或「AI/搜索混用其他不相关游戏内容」。

    Returns:
        list of (query_string, weight) 元组。
    """
    names = []
    seen = set()
    if character_name:
        names.append(character_name)
        seen.add(character_name.lower())
    for a in (aliases or []):
        al = (a or "").strip()
        if al and al.lower() not in seen:
            names.append(al)
            seen.add(al.lower())
    names = names[:5]  # 主名 + 最多 4 个别名，避免查询爆炸

    # 游戏官方简称（用于注入查询，隔离跨游戏结果）
    gk = game_keywords(game)
    game_tag = gk[0] if gk else ""
    if not game_tag or len(game_tag) > 6:
        # 过长或不稳定的标签（如英文全称）不注入，退化为原策略
        game_tag = ""

    def _tag(n):
        """拼接游戏名（若名字本身已含游戏名则不加，避免冗余）。"""
        if game_tag and game_tag not in n:
            return n + game_tag
        return n

    queries = []
    # 主查询：名字 + 核心分析词（权重最高）
    core_terms = ["评测", "强度", "攻略", "值得抽吗", "培养"]
    for n in names:
        w = 1.0 + _alias_priority(n)
        for t in core_terms:
            queries.append((_tag(n) + t, round(w, 2)))

    # 扩展查询：名字 + 场景词（权重略低）
    scene_terms = ["深渊", "配队", "大世界", "DPS", "推荐"]
    for n in names[:3]:
        w = 0.8 + _alias_priority(n)
        for t in scene_terms:
            queries.append((_tag(n) + t, round(w, 2)))

    # 纯名查询（兜底）
    for n in names[:3]:
        w = 0.6 + _alias_priority(n)
        queries.append((_tag(n), round(w, 2)))

    return queries


def _dedupe_by_aid(results):
    """按 aid/bvid 去重，保留 relevance 最高的那条。"""
    seen = {}
    for r in results:
        key = r.get("aid") or r.get("bvid") or r.get("title")
        if key not in seen or r.get("_relevance", 0) > seen[key].get("_relevance", 0):
            seen[key] = r
    return list(seen.values())


# ---------------------- B 站搜索（增强证据用） ----------------------

def _normalize_search_result(item, result_type="video"):
    """归一化搜索 API 返回的单条结果。"""
    if result_type == "article":
        return {
            "bvid": None,
            "aid": item.get("id"),
            "title": item.get("title", ""),
            "description": item.get("summary", "") or item.get("description", ""),
            "author": item.get("author", "") or item.get("name", ""),
            "mid": str(item.get("mid", 0)),
            "pubdate": int(item.get("pubdate") or item.get("publish_time") or 0),
            "pubdate_str": time.strftime("%Y-%m-%d", time.localtime(
                int(item.get("pubdate") or item.get("publish_time") or 0))) if (item.get("pubdate") or item.get("publish_time")) else "",
            "play": item.get("view", 0) or item.get("play", 0),
            "like": item.get("like", 0) or item.get("likes", 0),
            "favorite": item.get("favorite", 0),
            "url": "https://www.bilibili.com/read/cv" + str(item.get("id", "")) if item.get("id") else "",
            "relevant": True,
            "source_name": "B站搜索(专栏)",
            "source_role": "search",
            "trusted": False,
            "is_sample": False,
            "result_type": "article",
        }
    # video (default)
    return {
        "bvid": item.get("bvid", ""),
        "aid": item.get("aid", ""),
        "title": item.get("title", ""),
        "description": item.get("description", "") or "",
        "author": item.get("author", ""),
        "mid": str(item.get("mid", 0)),
        "pubdate": int(item.get("pubdate") or item.get("pubdate_ts") or 0),
        "pubdate_str": time.strftime("%Y-%m-%d", time.localtime(
            int(item.get("pubdate") or item.get("pubdate_ts") or 0))) if (item.get("pubdate") or item.get("pubdate_ts")) else "",
        "play": item.get("play", 0) or item.get("play_count", 0),
        "like": item.get("like", 0) or item.get("like_count", 0),
        "favorite": item.get("favorites", 0) or item.get("favorite", 0),
        "pic": item.get("pic", ""),
        "url": "https://www.bilibili.com/video/" + (item.get("bvid", "")),
        "relevant": True,
        "source_name": "B站搜索(视频)",
        "source_role": "search",
        "trusted": False,
        "is_sample": False,
        "result_type": "video",
    }


def search_bilibili(keyword, cfg=None, result_type="video", limit=20, order="click",
                    character_name=None, aliases=None, debug=False, game="genshin"):
    """通过 B 站搜索 API 拉取指定关键词的视频或专栏（用于 AI 增强证据）。

    改进：支持多查询组合搜索（角色名+别名+分析关键词），结果经过相关性过滤和评分，
    去除 HTML 标签，按相关性加权排序后返回。评分会校验「结果是否真的涉及该角色」
    （角色名/别名命中），避免把别的角色的评测误当成本角色证据。

    Args:
        keyword: 搜索关键词（通常为角色名）
        cfg: 配置对象（用于获取 SESSDATA）
        result_type: "video" 或 "article"
        limit: 最大返回条数
        order: 排序方式 — video: click(播放)/pubdate(最新)/stow(收藏)
        character_name: 角色名（用于相关性评分）
        aliases: 角色别名列表（参与相关性评分 + 搜索查询构建，优先级加权）
        debug: 为 True 时返回 (results, meta) 元组，meta 含搜索诊断信息

    Returns:
        debug=False: 归一化后的结果列表（每条含 title/description/play/like/favorite/url/relevance 等）。
        debug=True:  (结果列表, meta字典)
        失败或未配置 SESSDATA 时返回空（不抛异常，优雅降级）。
    """
    meta = {"queries": 0, "raw": 0, "after_dedupe": 0,
            "passed_filter": 0, "aliases_used": []}
    cfg = cfg or load_config()
    sess = cfg.get("cookie", {}).get("SESSDATA", "")
    demo = cfg.get("demo_mode", True)
    if not sess or demo:
        return ([], meta) if debug else []

    # 构建多个搜索查询（角色名 + 别名，按搜索优先级加权，注入游戏名隔离跨游戏结果）
    char_name = character_name or keyword
    queries = _build_search_queries(char_name, aliases, game)
    meta["queries"] = len(queries)
    try:
        meta["aliases_used"] = list(dict.fromkeys(
            [char_name] + [a for a in (aliases or []) if a]))
    except Exception:
        pass

    all_results = []
    query_weights = {}

    # 搜索 API 不需要 wbi 签名（签了反而返回 HTTP 412），
    # 用普通 urllib 直接请求即可。
    import urllib.request as _urllib_req
    import urllib.parse as _urllib_parse

    try:
        headers = {
            "User-Agent": UA,
            "Referer": "https://www.bilibili.com/",
        }
        if sess:
            headers["Cookie"] = sess

        for query, weight in queries:
            params = _urllib_parse.urlencode({
                "keyword": query,
                "search_type": result_type,
                "page": "1",
                "order": order,
                "page_size": str(min(limit * 2, 50)),
            })
            url = "https://api.bilibili.com/x/web-interface/search/type?" + params
            req = _urllib_req.Request(url, headers=headers)
            try:
                with _urllib_req.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except Exception:
                continue
            if data.get("code") != 0:
                continue
            raw_list = data.get("data", {}).get("result") or []
            meta["raw"] += len(raw_list)
            for item in raw_list[:limit * 2]:
                r = _normalize_search_result(item, result_type)
                r["_query"] = query
                r["_query_weight"] = weight
                # 去除标题中的 HTML 标签
                clean_title = _strip_html(r["title"])
                r["title"] = clean_title
                r["description"] = _strip_html(r.get("description", ""))
                # 相关性评分（传入别名+游戏，校验是否真的涉及该角色且非跨游戏污染）
                rel = _score_relevance(clean_title, r.get("description", ""), char_name, aliases, game)
                r["_relevance"] = rel
                all_results.append(r)
            # 请求间隔，避免触发 B站 限流
            time.sleep(0.3)

        if not all_results:
            return ([], meta) if debug else []

        # 去重（保留相关性最高的）
        all_results = _dedupe_by_aid(all_results)
        meta["after_dedupe"] = len(all_results)

        # 综合排序：相关性 * 查询权重 * (1 + log10(播放量))
        import math as _math
        for r in all_results:
            play_factor = 1.0 + _math.log10(max(r.get("play", 1), 1)) / 10.0
            r["_sort_score"] = r["_relevance"] * r.get("_query_weight", 1.0) * play_factor

        # 过滤低相关性结果（阈值 0.3，即至少包含一个分析类关键词且为该角色）
        filtered = [r for r in all_results if r["_relevance"] >= 0.3]

        # 如果过滤后太少，放宽到 0.2
        if len(filtered) < min(limit // 2, 5):
            filtered = [r for r in all_results if r["_relevance"] >= 0.2]

        meta["passed_filter"] = len(filtered)

        # 如果还是太少，返回原始 top N（至少给 AI 一些东西）
        if len(filtered) < 3:
            filtered = sorted(all_results, key=lambda x: x["_sort_score"], reverse=True)[:limit]

        # 按 sort_score 排序并截断
        filtered.sort(key=lambda x: x["_sort_score"], reverse=True)
        results = filtered[:limit]

        # 清理内部字段，只保留对外有用的
        src_label = "B站搜索(%s)" % ("专栏" if result_type == "article" else "视频")
        for r in results:
            r["source_name"] = src_label
            r["source_role"] = "search"
            r["trusted"] = False
            r["is_sample"] = False
            r["relevance"] = round(r.pop("_relevance", 0), 2)
            # 移除内部字段
            r.pop("_query", None)
            r.pop("_query_weight", None)
            r.pop("_sort_score", None)

        return (results, meta) if debug else results
    except Exception:
        return ([], meta) if debug else []


def search_videos(keyword, cfg=None, limit=20, order="click",
                  character_name=None, aliases=None, debug=False, game="genshin"):
    """快捷搜索视频（按播放量排序），带关键词过滤和相关性评分。"""
    return search_bilibili(keyword, cfg, "video", limit, order,
                            character_name, aliases, debug, game)


def search_articles(keyword, cfg=None, limit=10, order="click",
                    character_name=None, aliases=None, debug=False, game="genshin"):
    """快捷搜索专栏文章，带关键词过滤和相关性评分。"""
    return search_bilibili(keyword, cfg, "article", limit, order,
                            character_name, aliases, debug, game)


def _bvid_from_url(url):
    m = re.search(r"/(?:video/|BV)(BV[0-9A-Za-z]+)", url or "")
    return m.group(1) if m else ""


def _aid_from_url(url):
    """从专栏链接解析文章 id（https://www.bilibili.com/read/cv123456 → 123456）。"""
    m = re.search(r"/read/cv(\d+)", url or "")
    return m.group(1) if m else ""


def fetch_video_subtitle(bvid, sessdata="", max_len=1800):
    """抓取 B 站视频 CC 字幕文本（供 AI 做内容级分析）。

    需 SESSDATA（AI 字幕/部分字幕需登录才能拉取）；失败或无水印返回空串。
    """
    if not bvid:
        return ""
    try:
        client = BiliClient(sessdata)
        # 1) 视频信息 → 第一分P的 cid
        info = client.get_json("https://api.bilibili.com/x/web-interface/view",
                               {"bvid": bvid})
        if info.get("code") != 0:
            return ""
        pages = (info.get("data") or {}).get("pages") or []
        cid = pages[0].get("cid") if pages else 0
        if not cid:
            return ""
        # 2) 播放器接口 → 字幕列表
        pl = client.get_json("https://api.bilibili.com/x/player/wbi/v2",
                             {"bvid": bvid, "cid": cid})
        subs = (((pl.get("data") or {}).get("subtitle") or {}).get("subtitles")) or []
        if not subs:
            return ""
        sub = subs[0]
        url = sub.get("subtitle_url", "")
        if not url:
            return ""
        if url.startswith("//"):
            url = "https:" + url
        # 3) 拉取字幕 JSON（带 Cookie，AI 字幕需要）
        headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
        if sessdata:
            headers["Cookie"] = "SESSDATA=" + sessdata
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            sdata = json.loads(r.read().decode("utf-8"))
        body = sdata.get("body") or []
        text = " ".join((b.get("content") or "") for b in body)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_len]
    except Exception:
        return ""


def fetch_article_text(aid, sessdata="", max_len=1800):
    """抓取 B 站专栏文章正文（供 AI 做内容级分析）。失败返回空串。"""
    if not aid:
        return ""
    try:
        client = BiliClient(sessdata)
        d = client.get_json("https://api.bilibili.com/x/article/view", {"id": str(aid)})
        if d.get("code") != 0:
            return ""
        data = d.get("data") or {}
        content = _strip_html(data.get("content") or "")
        content = re.sub(r"\s+", " ", content).strip()
        return content[:max_len]
    except Exception:
        return ""
