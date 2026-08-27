# -*- coding: utf-8 -*-
"""配装推荐：武器 / 套装 / 词条 / 技能升级 / 配队建议。

数据来源（按优先级）：
1. biligame 百科结构化「角色/配装推荐」模板族：
   - 绝区零：角色主页（驱动盘/音擎/词条/技能）
   - 星穹铁道 / 原神：「角色名/攻略」子页（遗器/光锥/圣遗物/武器/词条）
   revisions 接口被防爬拦截时自动退回 parse 接口取 wikitext。
2. 规则推导：基于官方数值（白值/定位/属性）生成「主词条/面板」建议，
   不臆造具体装备名，明确标注为通用建议。
3. AI 缓存：若已运行过「AI 分析」，合并 weapon_advice / team_advice 文本。

产物返回统一结构，前端按来源徽标区分「百科配装 / 规则推导 / AI 建议」。
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOADOUT_CACHE_DIR = os.path.join(DATA_DIR, ".loadout_cache")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# biligame 各游戏 wiki slug 与参考页
WIKI = {
    "zzz": {"api": "https://wiki.biligame.com/zzz/api.php", "ref": "https://wiki.biligame.com/zzz/",
            "display": "biligame 绝区零百科"},
    "hsr": {"api": "https://wiki.biligame.com/sr/api.php", "ref": "https://wiki.biligame.com/sr/",
            "display": "biligame 星穹铁道百科"},
    "genshin": {"api": "https://wiki.biligame.com/ys/api.php", "ref": "https://wiki.biligame.com/ys/",
                "display": "biligame 原神百科"},
}

GAME_DISPLAY = {
    "genshin": "原神", "hsr": "崩坏：星穹铁道", "zzz": "绝区零",
    "wuthering_waves": "鸣潮", "arknights_endfield": "终末地", "nte": "异环",
}

# 元素 → 元素伤害加成主词条（杯/五号位等）
ELEMENT_DMG = {
    "genshin": {"火": "火元素伤害加成", "水": "水元素伤害加成", "雷": "雷元素伤害加成",
                "冰": "冰元素伤害加成", "风": "风元素伤害加成", "草": "草元素伤害加成",
                "岩": "岩元素伤害加成", "物理": "物理伤害加成"},
    "hsr": {"物理": "物理伤害提高", "火": "火属性伤害提高", "冰": "冰属性伤害提高",
            "雷": "雷属性伤害提高", "风": "风属性伤害提高", "量子": "量子属性伤害提高",
            "虚数": "虚数属性伤害提高"},
    "zzz": {"电": "电属性伤害加成", "火": "火属性伤害加成", "冰": "冰属性伤害加成",
            "以太": "以太属性伤害加成", "物理": "物理伤害加成", "烈霜": "烈霜属性伤害加成",
            "玄墨": "玄墨属性伤害加成", "凛刃": "凛刃属性伤害加成",
            "风": "风属性伤害加成", "流明": "流明属性伤害加成"},
    "wuthering_waves": {"衍射": "衍射伤害加成", "导电": "导电伤害加成", "冷凝": "冷凝伤害加成",
                        "热熔": "热熔伤害加成", "气动": "气动伤害加成", "湮灭": "湮灭伤害加成"},
    "arknights_endfield": {"物理": "物理伤害加成", "灼热": "灼热伤害加成", "电磁": "电磁伤害加成",
                           "寒冷": "寒冷伤害加成", "自然": "自然伤害加成"},
    "nte": {"光": "光属性伤害加成", "灵": "灵属性伤害加成", "咒": "咒属性伤害加成",
            "暗": "暗属性伤害加成", "魂": "魂属性伤害加成", "相": "相属性伤害加成"},
}


def _load(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _norm_equip(s):
    """装备名归一化：去掉 ★/件套/标点/空格，供图标映射模糊匹配。"""
    s = str(s or "").replace("★", "").replace("☆", "")
    s = re.sub(r"\d+\s*件套", "", s)
    s = re.sub(r"\d+\s*星", "", s)
    s = re.sub(r"[（(）):：]", "", s)
    s = re.sub(r"\s+", "", s)
    return re.sub(r"^[0-9]+", "", s.lower())


def _equip_icon(name, kind="weapon"):
    """查装备官方图标；未收录返回空字符串，绝不伪造。"""
    d = _load(os.path.join(DATA_DIR, "genshin_equip_icons.json")) or {}
    key = str(name or "").strip()
    if kind == "weapon":
        if key in (d.get("weapons") or {}):
            return d["weapons"][key]
        return (d.get("weapons_norm") or {}).get("__" + _norm_equip(key), "")
    if key in (d.get("artifacts") or {}):
        parts = d["artifacts"][key]
        return parts.get("flower") or next(iter(parts.values()), "")
    return (d.get("artifacts_norm") or {}).get("__" + _norm_equip(key), {}).get(
        "flower", "")


def _find_char(game, char_id):
    doc = _load(os.path.join(DATA_DIR, "%s_characters.json" % game))
    for c in (doc or {}).get("characters", []) or []:
        if c.get("id") == char_id:
            return c
    return None


def _stats_for(game, char):
    """取该角色官方数值（不同游戏结构不同），返回 dict。"""
    if game == "genshin":
        d = _load(os.path.join(DATA_DIR, "genshin_official_stats.json")) or {}
        return d.get(char.get("id")) or d.get(char.get("name")) or {}
    if game == "hsr":
        d = _load(os.path.join(DATA_DIR, "hsr_official_stats.json")) or {}
        return (d.get("stats") or {}).get(char.get("id")) or {}
    if game == "zzz":
        d = _load(os.path.join(DATA_DIR, "zzz_official_stats.json")) or {}
        return (d.get("stats") or {}).get(char.get("id")) or {}
    if game == "wuthering_waves":
        d = _load(os.path.join(DATA_DIR, "wuthering_waves_official_stats.json")) or {}
        return (d.get("stats") or {}).get(char.get("name")) or {}
    if game == "arknights_endfield":
        d = _load(os.path.join(DATA_DIR, "arknights_endfield_official_stats.json")) or {}
        stats = d.get("stats") or {}
        hit = stats.get(char.get("id")) or stats.get(char.get("name")) or stats.get(char.get("en"))
        if not hit:
            for s in stats.values():
                if (s.get("name") == char.get("name")) or (s.get("en") == char.get("en")):
                    hit = s
                    break
        return hit or {}
    if game == "nte":
        d = _load(os.path.join(DATA_DIR, "nte_official_stats.json")) or {}
        return (d.get("stats") or {}).get(char.get("en") or char.get("name")) or {}
    return {}


# ==================== biligame 百科模板解析 ====================
def _bili_rev(api, title, ref, timeout=25):
    """取页面 wikitext：revisions 优先，被防爬拦截时退回 parse 接口。"""
    headers = {"User-Agent": UA, "Referer": ref,
               "Accept": "application/json,text/plain,*/*",
               "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
               "Connection": "keep-alive"}

    def _get(params):
        url = api + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")

    try:
        d = json.loads(_get({
            "action": "query", "titles": title, "prop": "revisions",
            "rvprop": "content", "rvslots": "main", "format": "json"}))
        for pg in d.get("query", {}).get("pages", {}).values():
            revs = pg.get("revisions") or []
            if revs:
                return revs[0].get("slots", {}).get("main", {}).get("*", "")
    except Exception:
        pass
    try:
        d = json.loads(_get({
            "action": "parse", "page": title,
            "prop": "wikitext", "format": "json"}))
        return d.get("parse", {}).get("wikitext", {}).get("*", "")
    except Exception:
        return ""


def _extract_templates(wikitext):
    """提取全部 {{...}} 模板原始内容（正确处理嵌套）。"""
    out = []
    i, n = 0, len(wikitext)
    while i < n:
        if wikitext.startswith("{{", i):
            depth = 0
            j = i
            while j < n:
                if wikitext.startswith("{{", j):
                    depth += 1
                    j += 2
                elif wikitext.startswith("}}", j):
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                else:
                    j += 1
            out.append(wikitext[i + 2:j - 2])
            i = j
        else:
            i += 1
    return out


def _parse_body(raw):
    """模板体 → (name, positional[], fields{})。"""
    name, _, rest = raw.partition("|")
    name = name.strip()
    pos, fields = [], {}
    for seg in _split_top_level(rest):
        seg = seg.strip()
        if not seg:
            continue
        if "=" in seg:
            k, v = seg.split("=", 1)
            fields[k.strip()] = v.strip()
        else:
            pos.append(seg)
    return name, pos, fields


def _split_top_level(s, sep="|"):
    """按顶层 | 切分模板体（忽略 {{...}} 内部的 |，支持嵌套）。"""
    parts, cur = [], []
    depth, i, n = 0, 0, len(s)
    while i < n:
        if s.startswith("{{", i):
            depth += 1
            cur.append("{{")
            i += 2
        elif s.startswith("}}", i):
            depth = max(0, depth - 1)
            cur.append("}}")
            i += 2
        elif s[i] == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(s[i])
            i += 1
    parts.append("".join(cur))
    return parts


def _icon_names(text, icon_kind):
    """从 {{图标/驱动盘|名|||4件套}} 等提取名称与套数；icon_kind 可空=任意图标模板。"""
    out = []
    for raw in _extract_templates(text):
        nm, pos, _ = _parse_body(raw)
        if icon_kind and nm != icon_kind:
            continue
        if icon_kind is None and not nm.startswith("图标"):
            continue
        if pos:
            if nm in ("图标/小", "图标/攻略") and len(pos) >= 2 and pos[0] in (
                    "圣遗物", "武器", "遗器", "光锥", "音擎", "驱动盘",
                    "位面饰品", "隧洞遗器", "声骸", "装备", "回响"):
                item = {"name": pos[1]}
            else:
                item = {"name": pos[0]}
            pieces = next((p for p in pos[1:] if re.match(r"^\d+件套$", p)), None)
            if pieces:
                item["pieces"] = pieces
            out.append(item)
    return out


def _icon_kind(text):
    """图标模板的装备类别：{{图标/驱动盘|...}} → 驱动盘；{{图标/小|武器|...}} → 武器。"""
    raws = _extract_templates(text)
    if not raws:
        return ""
    nm, pos, _ = _parse_body(raws[0])
    if nm in ("图标/小", "图标/攻略"):
        return pos[0] if pos else ""
    return nm.split("/", 1)[1] if "/" in nm else nm


def _pieces_label(pieces, digit=None):
    """把模板里的 4 / 2 或 4件套 统一成展示文案，缺失时用 ?件套。"""
    if pieces:
        s = str(pieces).strip()
        if s.endswith("件套"):
            return s
        return "%s件套" % s
    if digit:
        return "%s件套" % digit
    return "?件套"


def _button_names(text):
    """从 {{图标|按钮|核心技}}>... 提取技能升级顺序。"""
    out = []
    for raw in _extract_templates(text):
        nm, pos, _ = _parse_body(raw)
        if nm in ("图标", "图标/按钮") and pos:
            out.append(pos[-1])
    return out


def _parse_main_stats(res, fields):
    """解析主词条 / 副词条 / 词条理由（兼容「主词条x」与直接槽位两种写法）。"""
    for k, v in fields.items():
        kk = re.sub(r"^主词条", "", (k or "")).strip()
        vv = (v or "").strip()
        if not kk or not vv:
            continue
        if "副词条" in kk:
            res["sub_stats"] = (res["sub_stats"] + " " + vv).strip()
            continue
        if kk in ("link", "链接"):
            continue
        if "理由" in kk or "推荐" in kk:
            res["skill_note"] = (res["skill_note"] + " " + vv).strip()
            continue
        if not any(x["slot"] == kk and x["value"] == vv for x in res["main_stats"]):
            res["main_stats"].append({"slot": kk, "value": vv})


def _parse_quick_table(res, fields):
    """hsr/原神「角色/配装推荐/简表」：遗器/位面饰品/光锥/词条一览。"""
    groups, descs = {}, {}
    for k, v in fields.items():
        if not v:
            continue
        kk = k.strip()
        m = re.match(r"^(隧洞遗器|位面饰品|驱动盘|遗器|声骸|装备|回响)\s*(\d*)$", kk)
        if m:
            for it in _icon_names(v, None):
                pcs = _pieces_label(it.get("pieces"), m.group(2))
                groups.setdefault(m.group(1), []).append("%s：%s" % (pcs, it["name"]))
            continue
        dm = re.match(r"^(隧洞遗器|位面饰品|驱动盘|遗器|声骸|装备|回响)描述\s*(\d*)$", kk)
        if dm:
            descs.setdefault(dm.group(1), []).append(v)
            continue
        if "副词条" in kk:
            res["sub_stats"] = (res["sub_stats"] + " " + v).strip()
            continue
        if "理由" in kk:
            res["skill_note"] = (res["skill_note"] + " " + v).strip()
            continue
        if re.search(r"(光锥|武器|音擎)", kk):
            if "描述" in kk:
                res["weapon_note"] = (res["weapon_note"] + " " + v).strip()
            else:
                tag = "毕业推荐" if ("毕业" in kk or "首选" in kk or "推荐" in kk) else "可选"
                if kk.startswith("可选"):
                    tag = "可选"
                for it in _icon_names(v, None):
                    it["tag"] = tag
                    if not any(x.get("name") == it["name"] for x in res["weapons"]):
                        res["weapons"].append(it)
            continue
        if kk in ("躯干", "脚部", "位面球", "连结绳", "沙", "杯", "头"):
            if not any(x["slot"] == kk and x["value"] == v for x in res["main_stats"]):
                res["main_stats"].append({"slot": kk, "value": v})
    for cat, items in groups.items():
        res["plans"].append({"title": cat + "（百科简表）", "items": items,
                             "note": "；".join(descs.get(cat, []))})


def _parse_detail_table(res, pos, fields):
    """hsr/原神「角色/配装推荐/详表」：图标行 + 推荐理由 → 套装/武器。"""
    kind = (fields.get("类型") or "").strip()
    if not kind:
        for seg in pos:
            seg = (seg or "").strip()
            if seg.startswith("{{"):
                k = _icon_kind(seg)
                if k:
                    kind = k
                    break
    rows, cur = [], None
    for seg in pos:
        seg = (seg or "").strip()
        if not seg:
            continue
        icons = _icon_names(seg, None)
        row_kind = _icon_kind(seg)
        if icons and seg.startswith("{{") and (not kind or row_kind == kind):
            if cur is not None:
                rows.append(cur)
            cur = {"items": icons, "kind": row_kind, "reason": ""}
        elif cur is not None:
            cur["reason"] = (cur["reason"] + " " + seg).strip()
    if cur is not None:
        rows.append(cur)
    for row in rows:
        if kind and row["kind"] != kind:
            continue
        items, reason = row["items"], row["reason"]
        if kind in ("武器", "光锥", "音擎"):
            for item in items:
                item["tag"] = "百科推荐"
                if not any(x.get("name") == item["name"] for x in res["weapons"]):
                    res["weapons"].append(item)
                if reason:
                    res["weapon_note"] = (res["weapon_note"] + " " + item["name"] + "：" + reason).strip()
        else:
            labels = [_pieces_label(it.get("pieces")) + "：" + it["name"] for it in items]
            plan = {"title": (kind or "百科详表") + "方案",
                    "items": labels, "note": reason}
            if not any(x["title"] == plan["title"] and x["items"] == plan["items"] for x in res["plans"]):
                res["plans"].append(plan)


def parse_wiki_loadout(wikitext):
    """解析 biligame「角色/配装推荐」模板族 → 结构化配装。"""
    wikitext = re.sub(r"<!--.*?-->", "", wikitext, flags=re.S)
    res = {"plans": [], "weapons": [], "main_stats": [], "sub_stats": "",
           "skill_order": [], "skill_note": "", "weapon_note": "", "note": ""}
    pending_titles = []   # 已声明但尚未展示的标题队列
    cur_title = "默认方案"
    for raw in _extract_templates(wikitext):
        nm, pos, fields = _parse_body(raw)
        nm = re.sub(r"<!--.*?-->", "", nm).strip()
        if nm == "角色/配装推荐":
            if pos and pos[0] in ("默认显示", "默认折叠") and len(pos) > 1:
                pending_titles.append(pos[1])
            elif pos and pos[0] in ("显示内容", "折叠内容"):
                # 展示下一段内容：弹出一个标题作为当前方案名
                if pending_titles:
                    cur_title = pending_titles.pop(0)
            continue
        if nm == "角色/配装推荐/词条":
            _parse_main_stats(res, fields)
            continue
        if nm == "角色/配装推荐/简表":
            _parse_quick_table(res, fields)
            continue
        if nm == "角色/配装推荐/详表":
            _parse_detail_table(res, pos, fields)
            continue
        if nm != "角色/配装推荐/分表":
            continue
        # 词条 / 音擎 / 光锥 / 武器 / 技能 分表
        if pos and pos[0] in ("词条", "音擎", "光锥", "武器", "技能"):
            kind = pos[0]
            if kind == "词条":
                _parse_main_stats(res, fields)
            elif kind in ("音擎", "光锥", "武器"):
                for k, v in fields.items():
                    if not v:
                        continue
                    if "理由" in k:
                        res["weapon_note"] = (res["weapon_note"] + " " + v).strip()
                        continue
                    tag = "毕业推荐" if ("毕业" in k or "首选" in k or "推荐" in k) else "可选"
                    if k.startswith("可选"):
                        tag = "可选"
                    for it in _icon_names(v, None):
                        it["tag"] = tag
                        if not any(x.get("name") == it["name"] for x in res["weapons"]):
                            res["weapons"].append(it)
            elif kind == "技能":
                res["skill_order"] = _button_names(fields.get("技能升级推荐", ""))
                if fields.get("技能升级推荐理由"):
                    res["skill_note"] = fields["技能升级推荐理由"]
            continue
        # 驱动盘套装方案（含 h4 等其它字段）
        plan = {"title": cur_title, "items": [], "note": fields.get("套装推荐理由", "")}
        for k, v in fields.items():
            m = re.match(r"^(驱动盘|遗器|声骸|装备|光锥|回响)\s*(\d*)", k)
            if m and v:
                pieces = m.group(2)  # 4 / 2
                names = [it["name"] for it in _icon_names(v, None)]
                if names:
                    plan["items"].append(_pieces_label(None, pieces) + "：" + "、".join(names))
        if plan["items"]:
            res["plans"].append(plan)
    return res


def fetch_wiki_loadout(game, char):
    """尝试从 biligame 拉取并解析配装；失败返回 None（网络/防爬/无模板）。"""
    w = WIKI.get(game)
    if not w:
        return None
    cache_path = os.path.join(LOADOUT_CACHE_DIR, "%s__%s.json" % (game, char.get("id")))
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 页面标题候选：全名 → 别名/简称 → 英文名，并附「/攻略」子页
    # （星铁 / 原神把配装模板放在 角色名/攻略，绝区零在角色主页）。
    cands = [char.get("name") or ""]
    cands += list(char.get("aliases") or [])
    cands += [char.get("en") or ""]
    # 「·」连接的全名在百科常拆成短名（如 安比·德玛拉 → 安比）
    if "·" in (char.get("name") or ""):
        cands.append((char.get("name") or "").split("·")[0])
    for base in list(cands):
        if base and base.strip():
            cands.append(base.strip() + "/攻略")
    seen = set()
    for title in cands:
        title = (title or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        try:
            wt = _bili_rev(w["api"], title, w["ref"])
        except Exception:
            return None
        if "配装推荐" not in wt and "配装" not in wt:
            continue
        parsed = parse_wiki_loadout(wt)
        parsed["source"] = "%s（%s）" % (w["display"], title)
        parsed["source_date"] = time.strftime("%Y-%m-%d")
        try:
            os.makedirs(LOADOUT_CACHE_DIR, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=1)
        except Exception:
            pass
        return parsed
    return None


# ==================== 规则推导（兜底，非官方） ====================
def _main_stat_rules(game, char, stats):
    """基于官方数值推导主词条建议（输出/辅助按定位区分）。"""
    name = char.get("name") or ""
    element = char.get("element") or ""
    role = ""
    for key in ("specialty", "weapon", "role", "profession"):
        v = char.get(key)
        if v and str(v).strip() and str(v) not in ("None", "null"):
            role = str(v).strip()
            break
    scaling = "ATK"
    if stats:
        hp = stats.get("base_hp") or stats.get("hp1") or 0
        atk = stats.get("base_atk") or stats.get("atk1") or 0
        deff = stats.get("base_def") or stats.get("def1") or 0
        if isinstance(hp, (int, float)) and isinstance(atk, (int, float)) and hp and atk:
            if hp / max(atk, 1) >= 12:
                scaling = "HP"
        if isinstance(deff, (int, float)) and isinstance(atk, (int, float)) and deff and atk:
            if deff / max(atk, 1) >= 6:
                scaling = "DEF"
    if stats and stats.get("scaling_stat"):
        scaling = str(stats.get("scaling_stat") or "ATK")
    is_support = bool(stats and stats.get("has_heal")) or any(
        kw in (name + role) for kw in ("辅助", "支援", "丰饶", "存护", "治疗", "击破", "同谐", "增益"))
    is_burst = not is_support

    main = []
    if game == "genshin":
        main.append({"slot": "时之沙", "value": "%s%%" % scaling if scaling != "ATK" else "攻击力%"})
        dmg = ELEMENT_DMG.get("genshin", {}).get(element)
        main.append({"slot": "空之杯", "value": dmg or "对应元素伤害加成"})
        crown = "治疗加成" if (stats and stats.get("has_heal")) else ("暴击率/暴击伤害" if is_burst else "元素充能效率")
        main.append({"slot": "理之冠", "value": crown})
        sub = "暴击率、暴击伤害、%s%%、元素充能效率" % scaling if is_burst else "元素充能效率、%s%%、暴击率、暴击伤害" % scaling
    elif game == "hsr":
        main.append({"slot": "躯干", "value": "暴击率/暴击伤害" if is_burst else "治疗量加成/效果命中"})
        dmg = ELEMENT_DMG.get("hsr", {}).get(element)
        main.append({"slot": "位面球", "value": dmg or "对应属性伤害提高"})
        main.append({"slot": "连结绳", "value": "能量恢复效率" if is_burst else "速度"})
        sub = "速度、暴击率、暴击伤害、%s%%" % scaling if is_burst else "速度、%s%%、效果抵抗、生命" % scaling
    elif game == "zzz":
        if "击破" in role or "异常" in role:
            main.append({"slot": "四号位", "value": "冲击力" if "击破" in role else "异常精通"})
        else:
            main.append({"slot": "四号位", "value": "暴击率/暴击伤害"})
        dmg = ELEMENT_DMG.get("zzz", {}).get(element)
        main.append({"slot": "五号位", "value": dmg or "对应属性伤害加成"})
        main.append({"slot": "六号位", "value": "冲击力" if "击破" in role else ("能量自动回复" if "支援" in role else "攻击力%")})
        sub = "暴击率、暴击伤害、攻击力%、穿透值" if "强攻" in role or "异常" in role else "攻击力%、冲击力、能量回复"
    else:
        main.append({"slot": "主属性①", "value": "双暴/攻击" if is_burst else "生命%/速度/充能"})
        dmg = ELEMENT_DMG.get(game, {}).get(element)
        main.append({"slot": "主属性②", "value": dmg or "对应属性伤害加成"})
        main.append({"slot": "主属性③", "value": "双暴" if is_burst else "充能/生命"})
        sub = "双暴、%s%%、充能" % scaling if is_burst else "充能、%s%%、生命/防御" % scaling
    return main, sub, scaling


def _role_tags(game, c):
    """从角色库字段粗提取定位标签（输出/辅助/治疗/护盾/生存/控制）。"""
    text = " ".join(str(x) for x in (
        c.get("role_cn"), c.get("role"), c.get("class"),
        c.get("specialty"), c.get("job"), c.get("path")
    ) if x)
    low = text.lower()
    tags = []
    mapping = [
        ("main dps", "输出"), ("sub dps", "副C"), ("dps", "输出"),
        ("输出", "输出"), ("主c", "输出"), ("主C", "输出"),
        ("强攻", "输出"), ("异常", "输出"), ("近卫", "输出"),
        ("突击", "输出"), ("术师", "输出"),
        ("support", "辅助"), ("辅助", "辅助"), ("支援", "辅助"),
        ("先锋", "辅助"), ("healer", "治疗"), ("heal", "治疗"),
        ("治疗", "治疗"), ("奶", "治疗"), ("shielder", "护盾"),
        ("shield", "护盾"), ("护盾", "护盾"), ("重装", "生存"),
        ("防护", "生存"), ("sustain", "生存"), ("击破", "控制"),
        ("控制", "控制"), ("tank", "生存"),
    ]
    for kw, tag in mapping:
        if kw in text or kw in low:
            tags.append(tag)
    stats = _stats_for(game, c) or {}
    if stats.get("has_heal"):
        tags.append("治疗")
    if stats.get("has_shield"):
        tags.append("护盾")
    if stats.get("has_buff"):
        tags.append("辅助")
    return sorted(set(tags))


def _teammate_role(game, c):
    """队友职责展示：优先 role_cn/role/class/specialty，去重拼接。"""
    seen, parts = set(), []
    for k in ("role_cn", "role", "class", "specialty", "job"):
        v = str(c.get(k) or "").strip()
        if v and v not in seen:
            seen.add(v)
            parts.append(v)
    stats = _stats_for(game, c) or {}
    if stats.get("has_heal"):
        parts.append("治疗")
    if stats.get("has_shield"):
        parts.append("护盾")
    if stats.get("has_buff"):
        parts.append("增伤/减抗")
    return " / ".join(parts)[:40]


def _rule_teammates(game, char):
    """按相性推荐队友：优先补当前角色缺口（治疗/护盾/增伤），其次同属性与稀有度。"""
    doc = _load(os.path.join(DATA_DIR, "%s_characters.json" % game))
    el = char.get("element") or ""
    my_tags = _role_tags(game, char)
    my_stats = _stats_for(game, char) or {}
    need_heal = not my_stats.get("has_heal")
    need_shield = not my_stats.get("has_shield")
    need_buff = not my_stats.get("has_buff")
    out = []
    for c in (doc or {}).get("characters", []) or []:
        if c.get("id") == char.get("id"):
            continue
        c_el = c.get("element") or ""
        if el and c_el and c_el != el:
            continue
        if not el or not c_el:
            # 无元素字段（如终末地）时按定位粗配，避免整队无关联
            if not (set(my_tags) & set(_role_tags(game, c))):
                continue
        tags = _role_tags(game, c)
        score = 0
        if need_heal and "治疗" in tags:
            score += 3
        if need_shield and "护盾" in tags:
            score += 3
        if need_buff and "辅助" in tags:
            score += 2
        if el and c_el and c_el == el:
            score += 2
        score += (int(c.get("rarity") or 0) or 0) / 10.0
        out.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "element": c_el,
            "icon": c.get("icon") or "",
            "icon_fallback": c.get("icon_fallback") or "",
            "role": _teammate_role(game, c),
            "score": round(score, 2),
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:4]


def _panel_from_stats(game, stats):
    """毕业面板：Lv1→满级白值 + 双暴（有则显示）。"""
    if not stats:
        return []
    panel = []

    def _fmt(v):
        if v is None:
            return "—"
        try:
            v = float(v)
            return str(int(v)) if v == int(v) else ("%.1f" % v)
        except Exception:
            return str(v)

    if game == "genshin":
        base = [("生命值", "base_hp"), ("攻击力", "base_atk"), ("防御力", "base_def")]
        for label, k in base:
            if stats.get(k) is not None:
                panel.append({"k": label, "v": _fmt(stats[k])})
    elif game == "hsr":
        pairs = [("生命值", "base_hp", "hp80"), ("攻击力", "base_atk", "atk80"),
                 ("防御力", "base_def", "def80"), ("速度", "spd", None),
                 ("暴击率", "crit_rate", None), ("暴击伤害", "crit_dmg", None)]
        for label, k1, k2 in pairs:
            if stats.get(k1) is not None:
                v = _fmt(stats[k1]) if k2 is None else (_fmt(stats[k1]) + " → " + _fmt(stats[k2]))
                if k1 in ("crit_rate", "crit_dmg") and isinstance(stats.get(k1), float):
                    v = "%.0f%%" % (float(stats[k1]) * 100)
                panel.append({"k": label, "v": v})
    elif game == "zzz":
        pairs = [("生命值", "hp1", "hp60"), ("攻击力", "atk1", "atk60"),
                 ("防御力", "def1", "def60"), ("冲击力", "impact", None),
                 ("异常掌控", "anomaly_mastery", None), ("异常精通", "anomaly_proficiency", None),
                 ("能量回复", "energy_regen", None)]
        for label, k1, k2 in pairs:
            if stats.get(k1) is not None:
                v = _fmt(stats[k1]) if k2 is None else (_fmt(stats[k1]) + " → " + _fmt(stats[k2]))
                panel.append({"k": label, "v": v})
    elif game == "wuthering_waves":
        pairs = [("生命值", "base_hp", "hp90"), ("攻击力", "base_atk", "atk90"),
                 ("防御力", "base_def", "def90")]
        for label, k1, k2 in pairs:
            if stats.get(k1) is not None:
                v = _fmt(stats[k1]) if k2 is None else (_fmt(stats[k1]) + " → " + _fmt(stats[k2]))
                panel.append({"k": label, "v": v})
    elif game == "arknights_endfield":
        pairs = [("生命值", "base_hp", "hp_max"), ("攻击力", "base_atk", "atk_max"),
                 ("防御力", "base_def", "def_max"), ("破甲", "pen", None),
                 ("暴击率", "crit_rate", None), ("暴击伤害", "crit_dmg", None)]
        for label, k1, k2 in pairs:
            if stats.get(k1) is not None:
                v = _fmt(stats[k1]) if k2 is None else (_fmt(stats[k1]) + " → " + _fmt(stats[k2]))
                if k1 in ("crit_rate", "crit_dmg") and isinstance(stats.get(k1), float):
                    v = "%.0f%%" % (float(stats[k1]) * 100)
                panel.append({"k": label, "v": v})
    elif game == "nte":
        pairs = [("生命值", "base_hp", "hp80"), ("攻击力", "base_atk", "atk80"),
                 ("防御力", "base_def", "def80")]
        for label, k1, k2 in pairs:
            if stats.get(k1) is not None:
                v = _fmt(stats[k1]) if k2 is None else (_fmt(stats[k1]) + " → " + _fmt(stats[k2]))
                panel.append({"k": label, "v": v})
    return panel


def _is_pure_output(st):
    """角色是否偏纯输出（无治疗/护盾/增益标记）。"""
    return not (st.get("has_heal") or st.get("has_shield") or st.get("has_buff"))


def build_rules_loadout(game, char, stats, ai):
    """规则推导配装（明确标注非官方/通用建议）。"""
    main, sub, _scaling = _main_stat_rules(game, char, stats)
    teammates = _rule_teammates(game, char)
    out = {
        "plans": [],
        "weapons": [],
        "main_stats": main,
        "sub_stats": sub,
        "skill_order": [],
        "skill_note": "",
        "weapon_note": "",
        "teams": [],
        "team_note": "",
    }
    if ai:
        if ai.get("weapon_advice"):
            out["weapons"] = [{"name": "AI 建议（见说明）", "tag": "AI"}]
            out["weapon_note"] = ai.get("weapon_advice")
        if ai.get("team_advice"):
            out["team_note"] = ai.get("team_advice")
    if not out["weapons"]:
        out["weapons"] = [{"name": "运行「🤖 AI 分析」获取角色专属建议", "tag": "通用"}]
        out["weapon_note"] = "当前无该角色的专属装备建议。运行 AI 分析后会自动填充角色专属武器/装备推荐（非官方，仅供参考）。"
    if teammates:
        out["teams"] = [{"name": "同属性 / 同定位队友候选（非官方）", "members": teammates}]
    if not out["team_note"]:
        needs = []
        st = stats or {}
        if not st.get("has_heal") and not st.get("has_shield"):
            needs.append("优先补充治疗/护盾生存位")
        elif not st.get("has_heal"):
            needs.append("优先补充治疗队友")
        elif not st.get("has_shield"):
            needs.append("优先补充护盾队友")
        if not st.get("has_buff") and _is_pure_output(st):
            needs.append("搭配增伤/减抗辅助")
        if not needs:
            needs.append("自身生存/增益齐全，可优先补输出或反应挂元素位")
        out["team_note"] = "队友候选按「功能缺口优先 → 同属性 → 稀有度」排序：%s；装备相性以主词条/倍率推导为参考（非完整阵容）。" \
                           "运行「🤖 AI 分析」后可获得角色专属配队与抽取价值建议。" % "；".join(needs)
    return out


def _skill_order_from_hsr(stats_skills):
    """HSR 技能优先级推导（有技能数据时）：天赋/战技 > 终结技 > 普攻。"""
    order = []
    for s in stats_skills or []:
        nm = (s.get("name") or "").strip()
        tp = (s.get("type_text") or s.get("type") or "").strip()
        if not nm:
            continue
        if "天赋" in tp:
            order.append((nm, 1))
        elif "战技" in tp:
            order.append((nm, 2))
        elif "终结技" in tp:
            order.append((nm, 3))
        elif "普攻" in tp or "攻击" in tp:
            order.append((nm, 4))
    order.sort(key=lambda x: x[1])
    return [x[0] for x in order]


# ==================== 对外入口 ====================
def build_loadout(game, char_id, ai=None):
    """组装配装推荐：wiki 优先，规则兜底，AI 补充。"""
    char = _find_char(game, char_id)
    if not char:
        return {"ok": False, "error": "未找到角色：%s" % char_id}
    stats = _stats_for(game, char)
    wiki = None
    if game in WIKI:
        try:
            wiki = fetch_wiki_loadout(game, char)
        except Exception:
            wiki = None

    panel = _panel_from_stats(game, stats)
    result = {
        "ok": True,
        "game": game,
        "game_display": GAME_DISPLAY.get(game, game),
        "character": {"id": char.get("id"), "name": char.get("name"),
                      "element": char.get("element") or "",
                      "rarity": char.get("rarity") or "",
                      "icon": char.get("icon") or "",
                      "icon_fallback": char.get("icon_fallback") or ""},
        "source_type": "rules",
        "source": "规则推导（非官方，仅供参考）",
        "source_date": "",
        "weapons": [],
        "weapon_note": "",
        "plans": [],
        "main_stats": [],
        "sub_stats": "",
        "skill_order": [],
        "skill_note": "",
        "teams": [],
        "team_note": "",
        "panel": panel,
        "panel_title": "面板属性（官方白值）",
        "note": "",
    }

    rules = build_rules_loadout(game, char, stats, ai)
    result.update(rules)

    if wiki and (wiki.get("plans") or wiki.get("weapons") or wiki.get("main_stats")):
        result["source_type"] = "wiki"
        result["source"] = wiki.get("source", "biligame 百科配装")
        result["source_date"] = wiki.get("source_date", "")
        if wiki.get("plans"):
            result["plans"] = wiki["plans"]
        if wiki.get("weapons"):
            result["weapons"] = wiki["weapons"]
        if wiki.get("weapon_note"):
            result["weapon_note"] = wiki["weapon_note"]
        elif result.get("weapons"):
            result["weapon_note"] = ""  # 已有百科具体武器，不再显示规则兜底文本
        if wiki.get("main_stats"):
            result["main_stats"] = wiki["main_stats"]
        if wiki.get("sub_stats"):
            result["sub_stats"] = wiki["sub_stats"]
        if wiki.get("skill_order"):
            result["skill_order"] = wiki["skill_order"]
        if wiki.get("skill_note"):
            result["skill_note"] = wiki["skill_note"]
        result["note"] = "配装方案来自百科结构化模板，实时性以百科为准；配队为 AI/同属性候选，仅参考。"
    else:
        # HSR：用本地技能数据推导升级顺序
        if game == "hsr":
            sk = _load(os.path.join(DATA_DIR, "hsr_skills.json")) or {}
            skills = (sk.get("skills") or {}).get(char.get("id")) or []
            order = _skill_order_from_hsr(skills)
            if order:
                result["skill_order"] = order
        # 鸣潮：按技能满级总倍率从高到低推导升级顺序（真实数值，非臆造）
        if game == "wuthering_waves":
            mult = (stats or {}).get("skill_mult") or {}
            labels = [("normal_max", "普通攻击"), ("skill_max", "共鸣技能"),
                      ("circuit_max", "共鸣回路"), ("lib_max", "共鸣解放"),
                      ("vari_max", "变奏技能")]
            ranked = sorted([(float(mult.get(k) or 0), label) for k, label in labels],
                            reverse=True)
            if ranked and ranked[0][0] > 0:
                result["skill_order"] = [label for _, label in ranked]
        result["note"] = ("当前无百科结构化配装数据。主词条/面板由官方数值推导，武器/套装/配队为通用建议"
                          "（非官方、非角色专属），运行「🤖 AI 分析」可获得更贴合角色的建议。")
        if not wiki and game in WIKI:
            result["note"] = ("biligame %s 百科暂不可达（数据中心 IP 常被 567 防盗链拦截），"
                              "已使用本地规则推导兜底；在本机家庭宽带运行即可自动拉取百科配装。%s"
                              % (GAME_DISPLAY.get(game, game), result["note"]))

    # 装备图标补齐：武器/圣遗物套装命中官方图标库才附加图标，未命中保持纯文本
    for w in result.get("weapons") or []:
        if isinstance(w, dict) and w.get("name"):
            w["icon"] = _equip_icon(w["name"], "weapon")
    for p in result.get("plans") or []:
        items = p.get("items") or []
        enriched = []
        for it in items:
            if isinstance(it, str):
                icon = _equip_icon(it, "artifact")
                enriched.append({"text": it, "icon": icon} if icon else it)
            else:
                enriched.append(it)
        if enriched:
            p["items"] = enriched
    return result
