# -*- coding: utf-8 -*-
"""全游戏 6 维雷达评分（确定性规则，不依赖 AI，绝不臆造）。

维度随游戏不同（返回 dims 供前端渲染轴），分数 0~10。
source 约定：
  official = 由官方数值/技能确定性推导（StarRailRes / biligame 百科数值）。
  review   = 官方不评价强度，由官方 Wiki 的角色定位标签/职业/稀有度等推导
             （明确标注「非官方数值」）。
数据不足的维度一律 5 分并注明「数据不足/按常规预设」，不伪装成官方数值。
"""

import json
import os
import re


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load(path):
    p = os.path.join(DATA_DIR, path)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _norm(value, lo, hi, out_lo=2.0, out_hi=10.0):
    """线性归一化到 [out_lo, out_hi] 并 clamp；无效值返回 out_lo。"""
    if value is None or value <= 0:
        return out_lo
    if value <= lo:
        return out_lo
    if value >= hi:
        return out_hi
    return round(out_lo + (value - lo) * (out_hi - out_lo) / (hi - lo), 1)


def _ranges(values, p10=0.1, p90=0.9):
    """返回列表的 10/90 分位（作为归一化 lo/hi）。"""
    vs = sorted(float(v) for v in values if v is not None)
    if not vs:
        return (1, 1)
    if len(vs) == 1:
        return (vs[0] * 0.8, vs[0] * 1.2)
    lo = vs[min(len(vs) - 1, int(len(vs) * p10))]
    hi = vs[min(len(vs) - 1, int(len(vs) * p90))]
    return (lo, hi)


def _char(game, cid):
    doc = _load("%s_characters.json" % game)
    for c in doc.get("characters", []):
        if c.get("id") == cid:
            return c
    return {}


def _dims(*labels):
    """labels: (key, label) ×6。各游戏维度不同，默认等权。"""
    n = len(labels)
    w = round(1.0 / n, 3) if n else 0.0
    return [{"key": k, "label": lab, "weight": w} for k, lab in labels]


def _finish(dims, scores, source, note_prefix=""):
    out = {}
    for d in dims:
        k = d["key"]
        d = scores.get(k) or {}
        if "score" not in d:
            d = {"score": 5.0, "note": "数据不足，按常规预设 5", "source": "review"}
        d.setdefault("source", source)
        # 仅 review 维度加「非官方数值」前缀；official 维度直接展示官方推导说明
        if d.get("source") == "review" and note_prefix:
            d["note"] = (note_prefix + d.get("note", "")).strip()
        else:
            d["note"] = (d.get("note", "") or "").strip()
        out[k] = d
    return {"dims": dims, "scores": out, "missing": False,
            "source": source, "fetched": None}


# ============================================================
# HSR 崩坏：星穹铁道 —— StarRailRes 官方数值 + 技能（official）
# ============================================================
HSR_DIMS = _dims(
    ("base_stats", "数值基础"), ("multiplier", "倍率水平"),
    ("aoe", "对群能力"), ("utility", "辅助功能"),
    ("team_dependency", "吃拐强度"), ("energy", "能量循环"),
)
_SKILL_DMG_TYPES = {"普攻", "战技", "终结技", "天赋"}
_UTIL_KW = ["治疗", "回复生命", "生命恢复", "护盾", "屏障", "减伤", "驱散",
            "解除", "复活", "加速", "拉条", "推条", "增伤", "易伤", "减防",
            "充能", "能量", "暴击", "攻击力提升", "防御力提升", "效果抵抗"]
_SCALE_KW = {"攻击力": "ATK", "生命上限": "HP", "防御力": "DEF"}


def _skill_multiplier(skill):
    """提取技能真实伤害倍率（官方参数）。

    只认「#n% 攻击力/防御力/生命上限 … 伤害」形态（如“等同于三月七#1[i]%攻击力的
    虚数属性伤害”），排除充能点数/秒数/速度提升/伤害增益等非伤害参数。
    """
    desc = skill.get("desc") or ""
    params = skill.get("params") or []
    best = 0.0
    for m in re.finditer(r"#(\d+)\[[if]\]\s*%", desc):
        try:
            idx = int(m.group(1)) - 1
            if idx >= len(params) or params[idx] is None:
                continue
            tail = desc[m.end():m.end() + 16]
            if not re.match(r"(?:攻击力|防御力|生命上限)", tail):
                continue  # % 后不是属性白值 → 非伤害倍率（如速度/充能%）
            if "伤害" not in desc[m.end():m.end() + 44]:
                continue  # 该句未提“伤害”→ 可能是治疗/护盾类
            best = max(best, float(params[idx]))
        except Exception:
            continue
    return best


def _hsr_scale_stat(skills):
    blob = " ".join((s.get("desc") or "") for s in skills)
    for kw, tag in _SCALE_KW.items():
        if kw in blob:
            return tag
    return "ATK"


def radar_hsr(cid, char):
    stats_doc = _load("hsr_official_stats.json").get("stats", {})
    skills_doc = _load("hsr_skills.json").get("skills", {})
    st = stats_doc.get(cid) or {}
    sk = skills_doc.get(cid) or []
    if not st and not sk:
        return {"dims": HSR_DIMS, "scores": None, "missing": True,
                "source": "not_refreshed", "fetched": None}

    # 1) 数值基础（Lv80 白值，全 roster 归一化）
    all_st = list(stats_doc.values())
    hp_lo, hp_hi = _ranges([s.get("hp80") for s in all_st])
    atk_lo, atk_hi = _ranges([s.get("atk80") for s in all_st])
    def_lo, def_hi = _ranges([s.get("def80") for s in all_st])
    base = round(0.4 * _norm(st.get("hp80"), hp_lo, hp_hi)
                 + 0.4 * _norm(st.get("atk80"), atk_lo, atk_hi)
                 + 0.2 * _norm(st.get("def80"), def_lo, def_hi), 1)
    base_note = ("Lv80 HP≈%s / ATK≈%s / DEF≈%s / 速度%s"
                 % (st.get("hp80"), st.get("atk80"), st.get("def80"), st.get("spd")))

    # 2) 倍率水平：战技/终结技 最高倍率，全 roster 归一化
    roster_mults = []
    for lid, ls in skills_doc.items():
        core = [s for s in ls if s.get("type_text") in ("战技", "终结技", "天赋")]
        if core:
            roster_mults.append(max(_skill_multiplier(s) for s in core))
    core_skills = [s for s in sk if s.get("type_text") in ("战技", "终结技", "天赋")]
    max_mult = max([_skill_multiplier(s) for s in core_skills] or [0])
    mult_lo, mult_hi = _ranges(roster_mults)
    multiplier = round(_norm(max_mult, mult_lo, mult_hi), 1)
    mult_note = ("核心技能最高倍率≈%s%%（官方参数，%d 名角色对比）"
                 % (round(max_mult * 100) if max_mult else "?", len(roster_mults)))
    if not max_mult:
        multiplier, mult_note = 5.0, "倍率参数缺失，按中等预设 5"

    # 3) 对群能力：AOE/扩散/弹射 技能占比
    aoe_n = sum(1 for s in sk if re.search(r"AoE|Blast|Bounce", s.get("effect") or ""))
    aoe_ratio = aoe_n / len(sk) if sk else 0
    aoe = round(_norm(aoe_ratio, 0.15, 0.6), 1)
    aoe_note = "%d/%d 个技能带对群（AOE/扩散/弹射）" % (aoe_n, len(sk))

    # 4) 辅助功能：关键词命中数
    blob = " ".join((s.get("desc") or "") + " " + (s.get("effect_text") or "") for s in sk)
    hits = [kw for kw in _UTIL_KW if kw in blob]
    utility = round(_norm(len(hits), 1, 5), 1)
    util_note = ("命中功能性关键词：%s" % ("、".join(hits) if hits else "无（纯输出向）"))

    # 5) 吃拐强度：伤害乘区属性 + 双暴 + 自拐
    scale_stat = _hsr_scale_stat(sk)
    team = 4.0
    tnote = ["倍率基于" + scale_stat]
    if scale_stat == "ATK":
        team += 2.0; tnote.append("受常规ATK拐")
    crit = (st.get("crit_rate") or 0) >= 0.1 or (st.get("crit_dmg") or 0) >= 0.8
    if crit:
        team += 1.0; tnote.append("高双暴受益增伤拐")
    if "自身" in blob and ("提升" in blob or "提高" in blob):
        team += 1.0; tnote.append("含自拐")
    if len(hits) > 2:
        team += 1.0; tnote.append("多功能性依赖队友补位")
    team = round(min(10.0, team), 1)

    # 6) 能量循环：max_sp 越低越容易循环（roster 归一化）
    max_sp = st.get("max_sp")
    if max_sp is None:
        energy, enote = 5.0, "能量需求数据缺失，按中等预设 5"
    else:
        sp_lo, sp_hi = _ranges([s.get("max_sp") for s in all_st])
        energy = round(11 - _norm(max_sp, sp_lo, sp_hi), 1)
        energy = round(min(10.0, max(2.0, energy)), 1)
        enote = "大招能量上限 %s（越低循环越快）" % max_sp

    return _finish(HSR_DIMS, {
        "base_stats": {"score": base, "note": base_note, "source": "official"},
        "multiplier": {"score": multiplier, "note": mult_note, "source": "official"},
        "aoe": {"score": aoe, "note": aoe_note, "source": "official"},
        "utility": {"score": utility, "note": util_note, "source": "official"},
        "team_dependency": {"score": team, "note": "；".join(tnote), "source": "official"},
        "energy": {"score": energy, "note": enote, "source": "official"},
    }, "official")


# ============================================================
# ZZZ 绝区零 —— biligame 百科官方数值（official）
# ============================================================
ZZZ_DIMS = _dims(
    ("base_stats", "数值基础"), ("dps", "输出定位"),
    ("break", "失衡控制"), ("utility", "辅助生存"),
    ("anomaly", "异常能力"), ("energy", "能量循环"),
)
ZZZ_SPEC_DPS = {"强攻": 8, "异常": 7, "命破": 6, "击破": 5, "支援": 3, "防护": 2}
ZZZ_SPEC_UTIL = {"支援": 8, "防护": 6, "异常": 5, "击破": 4, "命破": 3, "强攻": 2}


def radar_zzz(cid, char):
    stats_doc = _load("zzz_official_stats.json").get("stats", {})
    st = stats_doc.get(cid) or {}
    if not st:
        return {"dims": ZZZ_DIMS, "scores": None, "missing": True,
                "source": "not_refreshed", "fetched": None}
    spec = char.get("specialty") or st.get("specialty") or ""
    all_st = list(stats_doc.values())
    hp_lo, hp_hi = _ranges([s.get("hp60") for s in all_st])
    atk_lo, atk_hi = _ranges([s.get("atk60") for s in all_st])
    def_lo, def_hi = _ranges([s.get("def60") for s in all_st])
    imp_lo, imp_hi = _ranges([s.get("impact") for s in all_st])
    ap_lo, ap_hi = _ranges([s.get("anomaly_proficiency") for s in all_st])
    am_lo, am_hi = _ranges([s.get("anomaly_mastery") for s in all_st])
    er_lo, er_hi = _ranges([s.get("energy_regen") for s in all_st])

    base = round(0.4 * _norm(st.get("hp60"), hp_lo, hp_hi)
                 + 0.4 * _norm(st.get("atk60"), atk_lo, atk_hi)
                 + 0.2 * _norm(st.get("def60"), def_lo, def_hi), 1)
    base_note = ("Lv60 HP≈%s / ATK≈%s / DEF≈%s" % (st.get("hp60"), st.get("atk60"), st.get("def60")))
    dps = ZZZ_SPEC_DPS.get(spec, 5)
    dps_note = "特性：%s（%s）" % (spec or "未知", "官方数值定位" if spec else "数据不足")
    brk = round(min(10.0, _norm(st.get("impact"), imp_lo, imp_hi)
                    + (2 if spec in ("击破", "命破") else 0)), 1)
    brk_note = "冲击力 %s（%s）" % (st.get("impact"), "击破/命破特性 +2" if spec in ("击破", "命破") else "常规")
    util = ZZZ_SPEC_UTIL.get(spec, 4)
    util_note = "特性：%s（%s）" % (spec or "未知", "支援/防护偏辅助生存" if spec in ("支援", "防护") else "输出向")
    ap_score = round(_norm(st.get("anomaly_proficiency"), ap_lo, ap_hi), 1)
    am_score = round(_norm(st.get("anomaly_mastery"), am_lo, am_hi), 1)
    anomaly = round(min(10.0, 0.6 * ap_score + 0.4 * am_score + (2 if spec == "异常" else 0)), 1)
    anomaly_note = ("异常精通 %s / 掌控 %s" % (st.get("anomaly_proficiency"), st.get("anomaly_mastery")))
    energy = round(_norm(st.get("energy_regen"), er_lo, er_hi), 1)
    energy_note = "能量自动回复 %s/s" % st.get("energy_regen")
    return _finish(ZZZ_DIMS, {
        "base_stats": {"score": base, "note": base_note, "source": "official"},
        "dps": {"score": dps, "note": dps_note, "source": "official"},
        "break": {"score": brk, "note": brk_note, "source": "official"},
        "utility": {"score": util, "note": util_note, "source": "official"},
        "anomaly": {"score": anomaly, "note": anomaly_note, "source": "official"},
        "energy": {"score": energy, "note": energy_note, "source": "official"},
    }, "official")


# ============================================================
# 鸣潮 —— biligame 百科官方白值（official）+ Wiki 定位标签（review）
# ============================================================
WUWA_DIMS = _dims(
    ("base_stats", "数值基础"), ("dps", "输出定位"), ("support", "辅助功能"),
    ("sustain", "生存治疗"), ("control", "控制能力"),
    ("utility", "功能收益"),
)


def _role_tags(role):
    import re as _re
    return [t.strip() for t in _re.split(r"[;,，、]", role or "") if t.strip()]


def radar_wuwa(cid, char):
    stats_doc = _load("wuthering_waves_official_stats.json").get("stats", {})
    def _snorm(s):
        return (s or "").replace(" ", "").replace(":", "").strip().lower()
    st = None
    for name, e in stats_doc.items():
        if _snorm(name) == _snorm(char.get("name")) or (
                _snorm(e.get("en")) and _snorm(e.get("en")) == _snorm(char.get("en"))):
            st = e
            break
    role_cn = char.get("role_cn") or (st or {}).get("role") or ""
    tags = _role_tags(role_cn) + _role_tags(char.get("role") or "")
    if not tags and not char.get("rarity") and not st:
        return {"dims": WUWA_DIMS, "scores": None, "missing": True,
                "source": "not_refreshed", "fetched": None}
    r5 = char.get("rarity") == 5
    def score_for(kws, base, bonus_r5=0):
        hit = any(any(k.lower() in t.lower() for k in kws) for t in tags)
        return (base + (1 if r5 else 0) + bonus_r5) if hit else 4.0
    def note(kws, label):
        hit = [t for t in tags if any(k.lower() in t.lower() for k in kws)]
        return ("官方 Wiki 定位标签：%s" % ("、".join(hit) if hit else "无明确%s标签" % label))
    # 1) 数值基础（官方 Lv90 白值，全 roster 归一化）
    if st and st.get("hp90"):
        all_st = list(stats_doc.values())
        hp_lo, hp_hi = _ranges([e.get("hp90") for e in all_st if e.get("hp90")])
        atk_lo, atk_hi = _ranges([e.get("atk90") for e in all_st if e.get("atk90")])
        def_lo, def_hi = _ranges([e.get("def90") for e in all_st if e.get("def90")])
        base = round(0.4 * _norm(st.get("hp90"), hp_lo, hp_hi)
                     + 0.4 * _norm(st.get("atk90"), atk_lo, atk_hi)
                     + 0.2 * _norm(st.get("def90"), def_lo, def_hi), 1)
        base_note = "Lv90 HP≈%s / ATK≈%s / DEF≈%s（biligame 百科官方数值）" % (
            st.get("hp90"), st.get("atk90"), st.get("def90"))
        base_src = "official"
    else:
        base, base_note, base_src = 5.0, "暂无官方白值（请先在线拉取），按稀有度常规预设", "review"
    # 2) 输出定位：官方技能倍率（共鸣解放/共鸣技能/回路 满级总倍率，全 roster 归一化）
    all_st = list(stats_doc.values())
    def _burst(e):
        sm = e.get("skill_mult") or {}
        return max([sm.get(k) or 0 for k in ("lib_max", "skill_max", "circuit_max")] or [0])
    roster_bursts = [_burst(e) for e in all_st if _burst(e)]
    if st and _burst(st) and roster_bursts:
        b_lo, b_hi = _ranges(roster_bursts)
        dps = round(_norm(_burst(st), b_lo, b_hi), 1)
        dps_note = "核心技能满级总倍率≈%s%%（biligame 官方参数）" % round(_burst(st))
        dps_src = "official"
    else:
        dps = score_for(["Main Damage", "Sub DPS", "Damage Dealer", "主力输出", "主C", "输出"], 7, 1)
        dps_note = note(["Main Damage", "Sub DPS", "Damage Dealer", "主力输出", "主C", "输出"], "输出")
        dps_src = "review"
    support = score_for(["Support", "Healer", "Shield", "Buff", "辅助", "治疗", "奶", "增伤"], 6, 1)
    sustain = score_for(["Healer", "Shield", "Tank", "Surviv", "生存", "护盾", "承伤"], 6, 1)
    control = score_for(["Control", "Stagger", "Crowd", "Stun", "控制", "聚怪", "牵引", "击退"], 6, 1)
    utility = score_for(["Concerto Efficiency", "Energy", "Frazzle", "Erosion", "充能", "协奏", "共鸣效率"], 6, 1)
    return _finish(WUWA_DIMS, {
        "base_stats": {"score": base, "note": base_note, "source": base_src},
        "dps": {"score": dps, "note": dps_note, "source": dps_src},
        "support": {"score": support, "note": note(["Support", "Healer", "Shield", "Buff", "辅助", "治疗", "奶", "增伤"], "辅助")},
        "sustain": {"score": sustain, "note": note(["Healer", "Shield", "Tank", "Surviv", "生存", "护盾", "承伤"], "生存")},
        "control": {"score": control, "note": note(["Control", "Stagger", "Crowd", "Stun", "控制", "聚怪", "牵引", "击退"], "控制")},
        "utility": {"score": utility, "note": note(["Concerto Efficiency", "Energy", "Frazzle", "Erosion", "充能", "协奏", "共鸣效率"], "功能")},
    }, "review", note_prefix="非官方数值，由官方 Wiki 定位标签推导；")


# ============================================================
# 终末地 —— EndfieldGameData 官方白值（official）+ 官方职业/稀有度（review）
# ============================================================
ENDFIELD_DIMS = _dims(
    ("base_stats", "数值基础"), ("dps", "输出定位"), ("support", "辅助功能"),
    ("sustain", "生存防护"), ("utility", "功能收益"),
    ("control", "控制能力"),
)
ENDFIELD_CLASS = {
    "近卫": {"dps": 8, "sustain": 5}, "突击": {"dps": 7, "sustain": 5},
    "术师": {"dps": 7, "utility": 5}, "重装": {"dps": 4, "sustain": 8},
    "辅助": {"support": 8, "utility": 6}, "先锋": {"utility": 7, "dps": 5},
}


def radar_endfield(cid, char):
    cls = char.get("class") or ""
    rarity = char.get("rarity") or 0
    stats_doc = _load("arknights_endfield_official_stats.json").get("stats", {})
    def _snorm(s):
        return (s or "").replace(" ", "").strip().lower()
    st = None
    for e in stats_doc.values():
        if _snorm(e.get("name")) == _snorm(char.get("name")) or (
                _snorm(e.get("en")) and _snorm(e.get("en")) == _snorm(char.get("en"))):
            st = e
            break
    if not cls and not st:
        return {"dims": ENDFIELD_DIMS, "scores": None, "missing": True,
                "source": "not_refreshed", "fetched": None}
    m = ENDFIELD_CLASS.get(cls, {})
    r6, r5 = rarity == 6, rarity == 5
    def sc(key, base):
        v = m.get(key, base)
        return round(min(10.0, v + (1 if r6 else 0) + (0.5 if r5 else 0)), 1)
    if st and st.get("hp_max"):
        all_st = list(stats_doc.values())
        hp_lo, hp_hi = _ranges([e.get("hp_max") for e in all_st if e.get("hp_max")])
        atk_lo, atk_hi = _ranges([e.get("atk_max") for e in all_st if e.get("atk_max")])
        def_lo, def_hi = _ranges([e.get("def_max") for e in all_st if e.get("def_max")])
        base = round(0.4 * _norm(st.get("hp_max"), hp_lo, hp_hi)
                     + 0.4 * _norm(st.get("atk_max"), atk_lo, atk_hi)
                     + 0.2 * _norm(st.get("def_max"), def_lo, def_hi), 1)
        base_note = "满级 HP≈%s / ATK≈%s / DEF≈%s（EndfieldGameData 官方数值）" % (
            st.get("hp_max"), st.get("atk_max"), st.get("def_max"))
        base_src = "official"
    else:
        base = (8.0 if r6 else (6.0 if r5 else 4.0))
        base_note = "暂无官方白值（数据仓库建设中），按稀有度常规预设"
        base_src = "review"
    return _finish(ENDFIELD_DIMS, {
        "base_stats": {"score": base, "note": base_note, "source": base_src},
        "dps": {"score": sc("dps", 5), "note": "官方职业：%s" % (cls or "未知")},
        "support": {"score": sc("support", 4), "note": "官方职业：%s" % (cls or "未知")},
        "sustain": {"score": sc("sustain", 4), "note": "官方职业：%s" % (cls or "未知")},
        "utility": {"score": sc("utility", 4), "note": "官方职业：%s" % (cls or "未知")},
        "control": {"score": 5.0, "note": "官方未提供控制定位数据"},
    }, "review", note_prefix="非官方数值，由官方职业/稀有度推导；")


# ============================================================
# 异环 NTE —— Fandom 数值数据模块（official）+ 武器/定位（review）
# ============================================================
NTE_DIMS = _dims(
    ("base_stats", "数值基础"), ("dps", "输出定位"), ("support", "辅助功能"),
    ("survival", "生存能力"), ("control", "控制能力"),
    ("utility", "功能收益"),
)
NTE_DPS_WEAPON = {"双刀", "太刀", "巨锤", "双枪", "手甲", "龙爪", "格斗", "体术摩托", "拟态"}
NTE_SUP_WEAPON = {"言灵书", "指挥棒", "音响", "法器", "时停伞", "梦境"}
# 本地英文名 ↔ Fandom 页名/数据模块名不一致映射（与 character_refresh 保持一致）
NTE_EN_ALIAS = {
    "baizang": "Baicang", "kaos": "Chaos", "xiaozhi": "Chiz",
    "daffodil": "Daffodill", "zero": "Esper Zero", "requiem": "Lacrimosa",
    "zhenhong": "Shinku", "jiuyuan": "Jiuyuan", "hotori": "Hotori", "sakiri": "Sakiri",
}


def radar_nte(cid, char):
    weapon = char.get("weapon") or ""
    rarity = char.get("rarity") or 0
    esper = char.get("espertype") or ""
    stats_doc = _load("nte_official_stats.json").get("stats", {})
    def _snorm(s):
        return (s or "").replace(" ", "").replace(":", "").strip().lower()
    st = None
    target = NTE_EN_ALIAS.get(_snorm(char.get("en")), char.get("en"))
    for en_name, e in stats_doc.items():
        if _snorm(en_name) in (_snorm(target), _snorm(char.get("en"))):
            st = e
            break
    if not weapon and not esper and not rarity and not st:
        return {"dims": NTE_DIMS, "scores": None, "missing": True,
                "source": "not_refreshed", "fetched": None}
    r5 = rarity == 5
    if st and st.get("base_hp") and st.get("full"):
        all_st = [e for e in stats_doc.values() if e.get("hp80")]
        hp_lo, hp_hi = _ranges([e.get("hp80") for e in all_st])
        atk_lo, atk_hi = _ranges([e.get("atk80") for e in all_st])
        def_lo, def_hi = _ranges([e.get("def80") for e in all_st])
        base = round(0.4 * _norm(st.get("hp80"), hp_lo, hp_hi)
                     + 0.4 * _norm(st.get("atk80"), atk_lo, atk_hi)
                     + 0.2 * _norm(st.get("def80"), def_lo, def_hi), 1)
        base_note = "Lv80 HP≈%s / ATK≈%s / DEF≈%s（Fandom 数值数据模块）" % (
            st.get("hp80"), st.get("atk80"), st.get("def80"))
        base_src = "official"
    else:
        base, base_note, base_src = (6.0 if r5 else 4.5), \
            "暂无官方白值（Fandom 数值模块建设中），按稀有度常规预设", "review"
    def sc(base, hit):
        return round(min(10.0, base + (1 if r5 else 0) + (1 if hit else 0)), 1)
    dps = sc(5, weapon in NTE_DPS_WEAPON)
    support = sc(4, weapon in NTE_SUP_WEAPON or "Incantation" in esper)
    survival = sc(4, "双刃十字盾" in weapon or "巨锤" in weapon or "Guard" in esper)
    control = sc(4, "时停伞" in weapon or "Control" in esper)
    utility = sc(4, weapon in ("能量", "梦境", "伞太刀") or "Support" in esper)
    return _finish(NTE_DIMS, {
        "base_stats": {"score": base, "note": base_note, "source": base_src},
        "dps": {"score": dps, "note": "武器：%s%s" % (weapon or "未知", "（输出型武器）" if weapon in NTE_DPS_WEAPON else "")},
        "support": {"score": support, "note": "武器：%s / 异能系：%s" % (weapon or "未知", esper or "未知")},
        "survival": {"score": survival, "note": "武器：%s%s" % (weapon or "未知", "（防御/重装型）" if "双刃十字盾" in weapon or "巨锤" in weapon else "")},
        "control": {"score": control, "note": "武器：%s%s" % (weapon or "未知", "（控制型）" if "时停伞" in weapon else "")},
        "utility": {"score": utility, "note": "武器：%s%s" % (weapon or "未知", "（功能型）" if weapon in ("能量", "梦境", "伞太刀") else "")},
    }, "review", note_prefix="非官方数值，由官方 Wiki 武器/定位粗略推导；")


def radar_for(game, cid):
    """入口：返回 {dims, scores, missing, source, fetched}。"""
    char = _char(game, cid)
    if game == "hsr":
        return radar_hsr(cid, char)
    if game == "zzz":
        return radar_zzz(cid, char)
    if game == "wuthering_waves":
        return radar_wuwa(cid, char)
    if game == "arknights_endfield":
        return radar_endfield(cid, char)
    if game == "nte":
        return radar_nte(cid, char)
    return {"dims": _dims(("base_stats", "数值基础")), "scores": None,
            "missing": True, "source": "unsupported", "fetched": None}
