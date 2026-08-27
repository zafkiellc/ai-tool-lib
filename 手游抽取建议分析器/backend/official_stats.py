"""原神角色官方基础数据（用于 AI 雷达图评分的客观依据）。

数据来源（可引用 / 可拉取）：
- 离线基线（默认，沙箱可生成）：data/genshin_official_stats.json，由工具
  tools/gen_official_stats.js 从 genshin-db（GenshinData 官方数据镜像，npm 包）
  批量生成。覆盖全部已上线角色的真实数值：90 级满破白值(stats(90))、突破加成、
  元素爆发能量(combat3 attributes)、技能倍率(combat2/3 parameters)、功能性(技能描述探测)。
  生成方式：node tools/gen_official_stats.js（需先 npm i genshin-db）。
- 在线真值源（用户本机、家庭宽带可达时）：api.ambr.top（原神官方数据权威镜像）。
  通过 refresh_official_stats() 拉取，作为「缺口填补」——仅补齐基线缺失的角色
  （如 genshin-db 版本未收录的 6.x 新角色），不会回写已覆盖的角色，避免重复计算。
- 在线补源（数据中心/任意网络可达）：api.lunaris.moe（genshin-db 风格官方数据镜像，
  含未发布/最新版本角色）。ambr.top 被数据中心 IP 拦截时自动降级到 lunaris，
  同样只补齐基线缺口。

设计原则：
- 雷达图评分（compute_radar_scores）由本模块「确定性」计算，绝不依赖 AI 输出，
  避免 LLM 幻觉导致雷达图与官方数据不符。
- 各维度带 official 标记 + source 字段：
  source="official" = 由官方面板/技能数据确定性推算（数值基础/倍率/吃拐/辅助）。
  source="review"   = 官方不评价此维度，参考社区评测/UP主评测得出
  （反应强度、大世界便利性属玩法解读，官方无明确评分）。
  前端按 source 区分「📐 官方数据基准」与「📝 评测参考」，不把评测维度伪装成官方。
- 缺失字段自动回退到默认值，_missing=True 标记用于前端提示「数据不足」。

字段说明：
- base_hp/atk/def: 90 级满破（含武器加成前的裸面板白值）
- hp_pct/atk_pct/def_pct: 突破百分比加成（90级累计；genshin-db 基线已将突破并入白值，故置 0）
- energy_cost: 元素爆发能量需求
- skill_types: 普攻/战技/爆发 的技能类型标签
- has_shield/heal/buff: 功能性标记
- reaction_role: 反应定位（trigger挂元素 / multiplier乘区 / driver主C / self / none）
- talent_scaling: 倍率评级 low/medium/high/very_high
- mobility: 大世界机动性 none/dash/sprint_buff/glide/swim/climb/special
"""
import json
import os
import re
import urllib.request
import urllib.error
import datetime

from common import UA, DATA_DIR

# 注意：api.hakush.in 已于 2026-02-14 永久关闭（开发者公开公告），无法再作为
# HSR/ZZZ 的官方数值源。character_refresh 已改为「精编静态数据」模式，不再导出
# _hakush_get。本模块自带 _first / _norm_element 辅助（见下方定义），HSR/ZZZ 的
# 官方雷达数值目前无可靠数据源，refresh 时优雅降级（见 _refresh_hakush / fetch_hakush_character）。

_PATH = os.path.join(DATA_DIR, "genshin_official_stats.json")
_FLAG_PATH = os.path.join(DATA_DIR, "genshin_functional_flags.json")


def _path(game="genshin"):
    """官方数值缓存文件路径（按游戏区分）。"""
    return os.path.join(DATA_DIR, "%s_official_stats.json" % game)

AMBR_BASE = "https://api.ambr.top/v2"
LUNARIS_BASE = "https://api.lunaris.moe/data"


def _first(d, *keys):
    """多级取值：依次尝试 keys（大小写不敏感），返回首个非 None 值。"""
    if not isinstance(d, dict):
        return None
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
        sk = str(k)
        if sk in d and d[sk] is not None:
            return d[sk]
    return None


_ELEMENT_ALIAS = {
    "physical": "物理", "ice": "冰", "fire": "火", "wind": "风", "lightning": "雷",
    "thunder": "雷", "water": "水", "electric": "电", "ether": "以太",
    "quantum": "量子", "imaginary": "虚数", "grass": "草", "geo": "岩",
    "frost": "冰", "void": "无", "none": "无",
    "cryo": "冰", "electro": "雷", "anemo": "风", "pyro": "火",
    "hydro": "水", "dendro": "草",
}

_WEAPON_ALIAS = {
    "WEAPON_SWORD_ONE_HAND": "单手剑",
    "WEAPON_SWORD": "单手剑",
    "WEAPON_CLAYMORE": "双手剑",
    "WEAPON_POLE": "长柄武器",
    "WEAPON_BOW": "弓",
    "WEAPON_CATALYST": "法器",
    "sword": "单手剑",
    "claymore": "双手剑",
    "polearm": "长柄武器",
    "bow": "弓",
    "catalyst": "法器",
}
def _norm_element(v):
    """归一化元素名为中文（兼容英文/别名），已是中文则原样返回。"""
    if not v:
        return ""
    s = str(v).strip().lower()
    if s in _ELEMENT_ALIAS:
        return _ELEMENT_ALIAS[s]
    cn = {"物理", "冰", "火", "风", "雷", "水", "电", "以太", "量子", "虚数", "草", "岩", "无"}
    if s in cn:
        return s
    return s

# ---- 默认值（数据不足时使用） ----
_DEFAULT_STATS = {
    "base_hp": 0,
    "base_atk": 0,
    "base_def": 0,
    "hp_pct": 0,
    "atk_pct": 0,
    "def_pct": 0,
    "energy_cost": 0,
    "skill_types": {"normal": "物理", "skill": "元素", "burst": "元素"},
    "has_shield": False,
    "has_heal": False,
    "has_buff": False,
    "reaction_role": "none",
    "talent_scaling": "medium",  # low / medium / high / very_high
    "mobility": "none",  # none / dash / sprint_buff / glide / swim / climb / special
}


def _load(game="genshin"):
    """加载本地缓存的角色官方数据。"""
    p = _path(game)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _functional_flags():
    """加载人工核对的功能性白名单（heal/shield/buff → {id: bool}）。

    语义为「能辅助队友/场上角色」：治疗是群体/场上治疗，护盾是给角色套盾，
    增伤/减抗/聚怪/队友技能等级等才算 buff；自我回血、自我增伤不算。
    白名单显式 false 用于纠正旧版本宽松正则造成的噪声。
    """
    try:
        with open(_FLAG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _flag_for(char_id, kind, default=None):
    """返回白名单中某角色的功能性标记；未收录返回 default。"""
    flags = _functional_flags()
    m = flags.get(kind)
    if isinstance(m, dict) and char_id in m:
        return bool(m[char_id])
    return default


def get_stats(char_id, game="genshin"):
    """获取指定角色的官方统计数据。

    Args:
        char_id: 角色 ID（如 furina, zhongli, hu_tao）

    Returns:
        dict: 角色统计字典，缺失字段使用默认值。若完全无数据则返回默认字典 + _missing=True 标记。
    """
    db = _load(game)
    raw = db.get(char_id) or {}
    if not raw:
        result = dict(_DEFAULT_STATS)
        result["_missing"] = True
        return result
    result = dict(_DEFAULT_STATS)
    result.update(raw)
    # 白名单优先：即使旧缓存有噪声标记，也以人工核对结果为准
    for kind in ("heal", "shield", "buff"):
        v = _flag_for(char_id, kind)
        if v is not None:
            result["has_%s" % kind] = v
    result["_missing"] = False
    return result


def format_for_prompt(char_id, char_name=None):
    """将角色官方数据格式化为 AI prompt 可读文本。

    返回一段结构化文字，描述该角色的关键数值特征，
    用于辅助 LLM 给出更准确的 radar_scores 评分。
    """
    s = get_stats(char_id)
    name = char_name or char_id
    lines = []
    lines.append("【%s 官方面板数据】" % name)

    if s.get("_missing"):
        lines.append("（暂无该角色的详细官方数据，请根据元素/武器/稀有度常规水平评估）")
        return "\n".join(lines)

    # 基础白值
    bh = s.get("base_hp", 0)
    ba = s.get("base_atk", 0)
    bd = s.get("base_def", 0)
    if bh or ba or bd:
        parts = []
        if bh: parts.append("HP %d" % bh)
        if ba: parts.append("ATK %d" % ba)
        if bd: parts.append("DEF %d" % bd)
        lines.append("90级满破白值：%s" % " / ".join(parts))

    # 突破加成
    ap = []
    hpp = s.get("hp_pct", 0)
    atkp = s.get("atk_pct", 0)
    defp = s.get("def_pct", 0)
    if hpp: ap.append("HP+%d%%" % hpp)
    if atkp: ap.append("ATK+%d%%" % atkp)
    if defp: ap.append("DEF+%d%%" % defp)
    if ap:
        lines.append("突破加成：" + " / ".join(ap))

    # 能量与技能
    ec = s.get("energy_cost", 0)
    if ec:
        lines.append("元素爆发能量需求：%d点%s" % (ec,
            "（高能量，较依赖充能队友）" if ec >= 70 else
            "（中等能量）" if ec >= 60 else "（低能量，容易循环）"))
    st = s.get("skill_types", {})
    lines.append("技能类型：普攻(%s) / 战技(%s) / 爆发(%s)" % (
        st.get("normal", "?"), st.get("skill", "?"), st.get("burst", "?")))

    # 倍率评级
    ts = s.get("talent_scaling", "")
    scaling_map = {
        "low": "倍率偏低（伤害主要靠反应/协同）",
        "medium": "倍率中等",
        "high": "倍率较高（核心输出向）",
        "very_high": "倍率极高（顶级直伤C）",
    }
    if ts and ts in scaling_map:
        lines.append("技能倍率评级：%s" % scaling_map[ts])

    # 功能性
    funcs = []
    if s.get("has_shield"): funcs.append("护盾")
    if s.get("has_heal"): funcs.append("治疗")
    if s.get("has_buff"): funcs.append("增伤/减抗/聚怪")
    if funcs:
        lines.append("功能性：%s" % " + ".join(funcs))
    else:
        lines.append("功能性：纯输出，无盾奶增伤")

    # 反应定位
    rr = s.get("reaction_role", "none")
    role_map = {
        "driver": "反应主C（自己触发反应打伤害）",
        "trigger": "反应挂元素（为队友提供元素触发）",
        "multiplier": "反应乘区（提供增伤/减抗促进队友反应）",
        "none": "纯直伤，不依赖元素反应",
    }
    if rr and rr in role_map:
        lines.append("反应定位：%s" % role_map[rr])

    # 大世界能力
    mob = s.get("mobility", "none")
    mob_map = {
        "dash": "有冲刺/位移能力",
        "sprint_buff": "加速跑图",
        "glide": "滑翔/飞行能力",
        "swim": "水上行动能力",
        "climb": "攀爬能力",
        "special": "特殊大世界能力",
        "none": "无特殊大世界能力",
    }
    if mob and mob in mob_map:
        lines.append("大世界：%s" % mob_map[mob])
        ovd = s.get("overworld_detail")
        if ovd:
            lines.append("大世界独特能力（评测参考）：%s" % ovd)

    return "\n".join(lines)


# ===================================================================
# 雷达图评分（确定性计算，不依赖 AI 输出）
# ===================================================================

def _norm(value, lo, hi, out_lo=2.0, out_hi=10.0):
    """线性归一化到 [out_lo, out_hi]，并 clamp。"""
    if value <= 0:
        return out_lo
    if value <= lo:
        return out_lo
    if value >= hi:
        return out_hi
    return out_lo + (value - lo) * (out_hi - out_lo) / (hi - lo)


def compute_radar_scores(stats, char_name=None):
    """由官方数据确定性计算 6 维度雷达评分（各 0~10）。

    维度：base_stats(数值基础) / multiplier(倍率水平) / reaction(反应强度) /
          team_dependency(吃拐强度) / utility(辅助能力) / overworld(大世界便利性)

    返回 dict: { 维度key: {"score": float, "note": str}, ... }
    """
    name = char_name or "该角色"
    missing = stats.get("_missing", False)
    if missing:
        # 数据缺失时所有维度统一用预设 5，并明确标注「官方数据缺失」，
        # 绝不把默认值伪装成官方真值。
        dims = {}
        for key, label in (
                ("base_stats", "数值基础"), ("multiplier", "倍率水平"),
                ("reaction", "反应强度"), ("team_dependency", "吃拐强度"),
                ("utility", "辅助能力"), ("overworld", "大世界便利性")):
            dims[key] = {
                "score": 5.0,
                "note": "官方数据缺失，按常规预设评分 5",
                "official": False,
                "source": "review",
            }
        return dims
    s = stats

    # ---- 1. 数值基础（白值+突破加成，加权） ----
    bh = s.get("base_hp", 0) or 0
    ba = s.get("base_atk", 0) or 0
    bd = s.get("base_def", 0) or 0
    hpp = s.get("hp_pct", 0) or 0
    atkp = s.get("atk_pct", 0) or 0
    defp = s.get("def_pct", 0) or 0
    eff_hp = bh * (1 + hpp / 100.0)
    eff_atk = ba * (1 + atkp / 100.0)
    eff_def = bd * (1 + defp / 100.0)
    hp_n = _norm(eff_hp, 7000, 18000)
    atk_n = _norm(eff_atk, 180, 360)
    def_n = _norm(eff_def, 500, 1000)
    base_stats = round(0.4 * hp_n + 0.4 * atk_n + 0.2 * def_n, 1)
    base_stats_official = (not missing) and bool(bh or ba or bd)
    if missing:
        base_stats_note = "官方数据缺失，按常规预设评分 5"
        base_stats = 5.0
    else:
        base_stats_note = ("有效HP≈%d / ATK≈%d / DEF≈%d（含突破加成）"
                           % (round(eff_hp), round(eff_atk), round(eff_def)))

    # ---- 2. 倍率水平（技能倍率评级） ----
    scaling_map = {"very_low": 2, "low": 4, "medium": 6, "high": 8, "very_high": 10}
    ts = s.get("talent_scaling", "") or ""
    multiplier_official = (not missing) and ts in scaling_map
    if ts in scaling_map:
        multiplier = float(scaling_map[ts])
        multiplier_note = "技能倍率评级：%s" % ts
    else:
        multiplier = 5.0
        multiplier_note = "倍率评级缺失，按中等预设 5"

    # ---- 3. 反应强度（反应定位 + 元素） ----
    role_react = {"driver": 7, "trigger": 6, "multiplier": 6, "self": 4, "none": 2}
    rr = s.get("reaction_role", "none") or "none"
    reaction = float(role_react.get(rr, 2))
    reaction_official = False  # 反应强度为玩法解读，非官方面板字段
    reaction_source = "review"  # 官方不评价反应强度，参考社区评测
    reaction_note = "反应强度：官方不评价，参考社区评测（反应定位：%s）" % rr
    # 元素微调：可触发强力反应的元素 +1
    reactive = {"火", "水", "雷", "冰", "风", "草"}
    if s.get("element") in reactive:
        reaction = min(10.0, reaction + 1.0)
        reaction_note += "（可触发强力元素反应 +1）"

    # ---- 4. 吃拐强度（受队伍增益收益） ----
    # has_buff 的语义是「能辅助队友/场上角色」，不能当作「吃拐」，
    # 因此这里只用主属性/反应定位/能量需求等官方字段推导。
    team = 4.0
    team_note = []
    scaling = s.get("scaling_stat", "ATK") or "ATK"
    if scaling == "ATK":
        team += 2.0; team_note.append("主属性攻击，吃攻击/增伤拐")
    elif scaling == "DEF":
        team += 1.5; team_note.append("主属性防御，吃防御/增伤拐")
    elif scaling == "HP":
        team += 1.0; team_note.append("主属性生命，吃生命/增伤拐")
    if rr in ("multiplier", "trigger"):
        team += 2.0; team_note.append("反应体系吃队友")
    elif rr == "driver":
        team += 1.0; team_note.append("站场主C吃增益")
    if (s.get("energy_cost", 0) or 0) >= 70:
        team += 1.0; team_note.append("高充能需求需电池")
    if not team_note:
        team_note.append("纯直伤，较少吃拐")
    team = round(min(10.0, team), 1)
    team_note = "；".join(team_note)
    team_official = not missing  # 吃拐由主属性/反应定位/能量需求等官方字段推导

    # ---- 5. 辅助能力（功能性） ----
    utility = 2.0
    unote = []
    if s.get("has_shield"):
        utility += 3.0; unote.append("护盾")
    if s.get("has_heal"):
        utility += 3.0; unote.append("治疗")
    if s.get("has_buff"):
        utility += 3.0; unote.append("增伤/减抗/聚怪")
    if rr in ("multiplier", "trigger"):
        utility += 1.0; unote.append("赋能队友反应")
    utility = round(min(10.0, utility), 1)
    utility_official = not missing  # 功能性由官方技能描述文本探测得出
    utility_note = ("功能性：" + " + ".join(unote)) if unote else "纯输出，无辅助能力"

    # ---- 6. 大世界便利性（机动性 + 续航 + 元素） ----
    # 评分：独特探索能力（飞行/游泳/攀爬/钩索/载具）评测参考下给高分，普通位移中等。
    mob_map = {"none": 2, "dash": 5, "sprint_buff": 6, "glide": 8,
               "swim": 8, "climb": 8, "special": 8.5}
    mob = s.get("mobility", "none") or "none"
    overworld = float(mob_map.get(mob, 2))
    overworld_official = False  # 大世界便利性为玩法解读，非官方面板字段
    overworld_source = "review"  # 官方不评价大世界能力，参考社区评测（位移/攀爬/游泳/飞行等）
    onote = ["大世界便利性：官方不评价，参考社区评测（机动性：%s）" % mob]
    # 评测参考白名单说明（如飞行/游泳/攀爬等独特探索能力，由攻略人工核对）
    ov_detail = s.get("overworld_detail")
    if ov_detail:
        onote.append("评测参考：" + ov_detail)
    if s.get("has_heal"):
        overworld = min(10.0, overworld + 1.0); onote.append("续航治疗+1")
    # 大世界实用元素：火(烧藤/木)/风(聚怪/起飞)/草(燃烧)/水(过河)
    if s.get("element") in ("火", "风", "草", "水"):
        overworld = min(10.0, overworld + 1.0); onote.append("元素利于探索+1")
    overworld = round(overworld, 1)
    overworld_note = "；".join(onote)

    return {
        "base_stats": {"score": base_stats, "note": base_stats_note, "official": base_stats_official, "source": "official"},
        "multiplier": {"score": multiplier, "note": multiplier_note, "official": multiplier_official, "source": "official"},
        "reaction": {"score": round(reaction, 1), "note": reaction_note, "official": reaction_official, "source": reaction_source},
        "team_dependency": {"score": team, "note": team_note, "official": team_official, "source": "official_derived"},
        "utility": {"score": utility, "note": utility_note, "official": utility_official, "source": "official_derived"},
        "overworld": {"score": overworld, "note": overworld_note, "official": overworld_official, "source": overworld_source},
    }


# ===================================================================
# HSR / ZZZ 官方数值拉取（原 hakush.in，站点已于 2026-02-14 永久关闭）
# —— 以下函数保留供未来接入新官方数据源（如米游社 Wiki 精编）复用，
#    当前 fetch_hakush_character / _refresh_hakush 已优雅降级为「不可用」。
# ===================================================================

def _num(v):
    """强制转为数值；失败返回 0。"""
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except Exception:
            return 0
    return 0


def _max_of(v):
    """取标量本身或列表中的最大值。"""
    if isinstance(v, list):
        nums = [_num(x) for x in v]
        return max(nums) if nums else 0
    return _num(v)


def _collect_descriptions(game, d):
    """收集技能/核心技能描述文本，用于功能性探测。多语言回退。"""
    descs = []
    # HSR: skills 字典；ZZZ: skill 字典
    skills = _first(d, "skills") or _first(d, "skill") or {}
    if isinstance(skills, dict):
        for sk in skills.values():
            if not isinstance(sk, dict):
                continue
            # 直接描述
            for key in ("desc", "description", "simple_desc"):
                val = sk.get(key)
                if isinstance(val, str):
                    descs.append(val)
                elif isinstance(val, list):
                    for it in val:
                        if isinstance(it, str):
                            descs.append(it)
                        elif isinstance(it, dict):
                            descs.append(it.get("desc", "") or it.get("description", "") or "")
            # 等级描述（HSR level_info / ZZZ level）
            lv = sk.get("level") or sk.get("level_info") or {}
            if isinstance(lv, dict):
                for li in lv.values():
                    if isinstance(li, dict):
                        d2 = li.get("description") or li.get("desc")
                        if isinstance(d2, str):
                            descs.append(d2)
                        elif isinstance(d2, list):
                            for it in d2:
                                if isinstance(it, str):
                                    descs.append(it)
    # ZZZ 核心技能 passive
    pas = _first(d, "passive")
    if isinstance(pas, dict):
        for lv in pas.values():
            if isinstance(lv, dict):
                for k in ("desc", "description"):
                    v = lv.get(k)
                    if isinstance(v, str):
                        descs.append(v)
                    elif isinstance(v, list):
                        for it in v:
                            if isinstance(it, str):
                                descs.append(it)
    return [x for x in descs if x]


def _deep_max(d, keys, lo, hi):
    """递归搜索整棵 JSON，收集匹配 keys（大小写不敏感）的数值，
    仅在合理区间 [lo,hi] 内取最大值（避免把技能倍率/数值误当面板）。"""
    best = 0.0
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(k, str) and k.lower() in keys:
                n = _num(v)
                if lo <= n <= hi:
                    best = max(best, n)
            else:
                best = max(best, _deep_max(v, keys, lo, hi))
    elif isinstance(d, list):
        for it in d:
            best = max(best, _deep_max(it, keys, lo, hi))
    return best


def _extract_base_stats(game, d):
    """从角色详情抽取 90/Lv.max 裸面板（HP/ATK/DEF）。（原 hakush 解析逻辑，站点已关闭）

    ZZZ：stats 为扁平字典（hp/atk/def）。
    HSR：stats 为按突破阶段索引的字典，每阶段含 hp/attack/defence 数组（按等级），
         取最高突破阶段的最大值。
    兜底：对整棵 JSON 递归搜索 hp/atk/def 键名（限合理数值区间），最大化兼容不同布局。
    """
    hp = atk = df = 0.0
    stats = _first(d, "stats")
    if isinstance(stats, dict):
        # ZZZ 扁平
        zh = _num(_first(stats, "hp")) or _num(_first(stats, "HP"))
        za = _num(_first(stats, "atk")) or _num(_first(stats, "ATK"))
        zd = _num(_first(stats, "def")) or _num(_first(stats, "DEF"))
        if zh or za or zd:
            hp, atk, df = zh, za, zd
            return int(round(hp)) or 0, int(round(atk)) or 0, int(round(df)) or 0
        # HSR 嵌套（按突破阶段 max）
        try:
            best_promo = max(stats.keys(), key=lambda k: _num(k))
        except Exception:
            best_promo = None
        if best_promo is not None:
            pv = stats[best_promo]
            if isinstance(pv, dict):
                hp = _max_of(_first(pv, "hp", "hp_max"))
                atk = _max_of(_first(pv, "attack", "atk"))
                df = _max_of(_first(pv, "defence", "def", "def_max"))
                if hp or atk or df:
                    return int(round(hp)) or 0, int(round(atk)) or 0, int(round(df)) or 0
    # 退化：扫描顶层
    hp = _num(_first(d, "base_hp", "hp")) or hp
    atk = _num(_first(d, "base_atk", "attack", "atk")) or atk
    df = _num(_first(d, "base_def", "defence", "def")) or df
    if hp or atk or df:
        return int(round(hp)) or 0, int(round(atk)) or 0, int(round(df)) or 0
    # 终极兜底：整棵递归搜索（限合理区间，避免误取倍率）
    hp = _deep_max(d, {"hp"}, 800, 20000)
    atk = _deep_max(d, {"attack", "atk"}, 80, 2500)
    df = _deep_max(d, {"defence", "def"}, 80, 2500)
    return int(round(hp)) or 0, int(round(atk)) or 0, int(round(df)) or 0


def _extract_energy(game, d):
    """尽力抽取爆发/终结技能量（HSR 为 ultimate 能量；ZZZ 通常无单一能量）。"""
    if game == "hsr":
        # HSR 能量可能在 skills 的 ultimate 节点或顶层 energy 字段
        skills = _first(d, "skills") or {}
        if isinstance(skills, dict):
            for sk in skills.values():
                if isinstance(sk, dict):
                    ec = _num(_first(sk, "energy") or _first(sk, "cost") or _first(sk, "energy_cost"))
                    if ec:
                        return int(round(ec))
    return 0


def _local_char(char_id, game):
    """从本地角色库读取该角色（element/rarity 等），用于补全。懒加载避免循环导入。"""
    try:
        from character_db import find_character
        return find_character(char_id, game) or {}
    except Exception:
        return {}


def fetch_hakush_character(char_id, game):
    """原从 api.hakush.in 拉取单个 HSR/ZZZ 角色的官方数据。

    ⚠️ hakush.in 已于 2026-02-14 永久关闭，该数据源不可用。
    为避免写入任何「假官方数值」，统一返回 {}（绝不抛异常、绝不造假）。
    后续可在此接入米游社 Wiki 精编数据等替代源。
    """
    return {}


def _refresh_hakush(char_ids, game):
    """批量刷新 HSR/ZZZ 官方数值缓存。

    ⚠️ 原数据源 api.hakush.in 已于 2026-02-14 永久关闭，暂无可替代的官方数据源，
    优雅降级：返回 updated=0 并说明原因，绝不写入假数据。
    """
    return {"updated": 0, "failed": [], "source": "hakush_closed",
            "total": 0, "gap_fill": False,
            "note": "hakush.in 已于 2026-02-14 永久关闭，HSR/ZZZ 官方数值刷新暂不可用。"
                    "请等待接入新的官方数据源（如米游社 Wiki 精编）。当前雷达图将显示「数据不足」。"}


def get_radar(char_id, char_name=None, game="genshin"):
    """获取角色雷达评分 + 数据来源信息。供 server / frontend 使用。

    原神：官方面板真值源（genshin-db / ambr.top），离线基线 + 在线缺口填补。
    HSR / ZZZ：官方数值源（StarRailRes / biligame 百科）确定性推导。
    鸣潮 / 异环 / 终末地：官方 Wiki 角色定位标签/职业/稀有度推导（review，明确标注）。
    未刷新时返回 missing=True（数据不足），绝不展示假的官方雷达。
    """
    if game in ("hsr", "zzz", "wuthering_waves", "arknights_endfield", "nte"):
        try:
            from radar import radar_for
            r = radar_for(game, char_id)
            r["char_id"] = char_id
            return r
        except Exception:
            return {"char_id": char_id, "missing": True, "scores": None,
                    "dims": None, "source": "error", "fetched": None}
    if game != "genshin":
        return {"char_id": char_id, "missing": True, "scores": None,
                "dims": None, "source": "unsupported", "fetched": None}
    try:
        s = get_stats(char_id, game)
        scores = compute_radar_scores(s, char_name or char_id)
        if s.get("_missing"):
            src = "not_refreshed"  # 该游戏官方数据尚未刷新
        else:
            src = s.get("_source", "local_cache")
        fetched = s.get("_fetched")
        return {
            "char_id": char_id,
            "missing": s.get("_missing", False),
            "scores": scores,
            "dims": [{"key": "base_stats", "label": "数值基础", "weight": 0.20},
                     {"key": "multiplier", "label": "倍率水平", "weight": 0.25},
                     {"key": "reaction", "label": "反应强度", "weight": 0.20},
                     {"key": "team_dependency", "label": "吃拐强度", "weight": 0.15},
                     {"key": "utility", "label": "辅助能力", "weight": 0.10},
                     {"key": "overworld", "label": "大世界便利性", "weight": 0.10}],
            "source": src,
            "fetched": fetched,
        }
    except Exception:
        return {"char_id": char_id, "missing": True, "scores": None,
                "dims": None, "source": "error", "fetched": None}


def save_stats(stats_dict, game="genshin"):
    """保存/更新角色统计数据到本地 JSON。

    注意：仅覆盖 dict 中显式提供的字段；不传入的字段保留原值。
    """
    db = _load(game)
    for cid, vals in stats_dict.items():
        existing = db.get(cid, {})
        merged = dict(existing)
        for k, v in vals.items():
            if v is not None:
                merged[k] = v
        db[cid] = merged
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_path(game), "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


# ===================================================================
# 在线官方数据拉取（api.ambr.top）—— 可引用 / 可拉取的真值源
# ===================================================================

def _ambr_get(url):
    """带 UA 的请求 ambr.top，返回解析后的 JSON 或 None。"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json",
        }, method="GET")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, Exception):
        return None


def _dig(d, *keys, default=None):
    """安全多级取值，支持数字/字符串混合 key。"""
    cur = d
    for k in keys:
        if cur is None:
            return default
        if isinstance(cur, dict):
            if k in cur:
                cur = cur[k]
            elif str(k) in cur:
                cur = cur[str(k)]
            else:
                return default
        elif isinstance(cur, list):
            try:
                cur = cur[int(k)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return cur


def _detect_functional(text):
    """从技能描述文本保守探测功能性标记。

    只认强信号；buff 必须同时出现「队友/全队上下文 + 增益词」，
    避免把自我增伤、自我回血误判成辅助能力。
    """
    t = (text or "").lower()
    has_heal = bool(re.search(r"\bheal(s|ing|ed)?\b|治疗|回血|恢复生命|incoming healing", t, re.I))
    has_shield = bool(re.search(r"\bshield(s|ed|ing)?\b|护盾|伤害抵挡|damage absorption", t, re.I))
    team = bool(re.search(r"all party|party members|nearby characters|active character|team|全队|队伍|队友|附近的角色", t, re.I))
    gain = bool(re.search(r"increase|boost|gain|bonus|buff|增伤|提高|提升|增加|加成|减抗", t, re.I))
    has_buff = team and gain
    return has_heal, has_shield, has_buff


# ===================================================================
# 在线官方数据拉取（api.lunaris.moe）—— genshin-db 风格官方数据镜像
# 包含未发布/最新版本角色，ambr.top 不可达时作为原神数值补源。
# ===================================================================

def _lunaris_get(url):
    """带 UA 的请求 lunaris，返回解析后的 JSON 或 None。"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "application/json",
        }, method="GET")
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _lunaris_version():
    """读取 lunaris 数据包的当前版本号；失败返回 None。"""
    data = _lunaris_get("%s/version.json" % LUNARIS_BASE)
    if isinstance(data, dict) and data.get("version"):
        return str(data["version"])
    return None


def _lunaris_char_id(char_id, charlist):
    """把本地角色 id（slug 或数字 id）映射到 lunaris charlist 的 id。"""
    if not isinstance(charlist, dict):
        return None
    char_id = str(char_id)
    if char_id in charlist:
        return char_id

    def _norm(s):
        return re.sub(r"[\s'._·\-]", "", str(s or "")).lower()

    want = {_norm(char_id)}
    p = os.path.join(DATA_DIR, "genshin_characters.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            doc = json.load(f)
        for c in doc.get("characters", []):
            if str(c.get("id")) == char_id:
                want.add(_norm(c.get("en")))
                for a in (c.get("aliases") or []):
                    want.add(_norm(a))
    except Exception:
        pass

    for cid, rec in charlist.items():
        if isinstance(rec, dict) and (_norm(rec.get("enName")) in want
                                      or _norm(rec.get("chsName")) in want):
            return cid
    return None


def _lunaris_scaling_stat(detail):
    """从技能/天赋文本推断主属性；无文本时保守返回 ATK。"""
    texts = []
    info = detail.get("info") or {}
    if isinstance(info.get("description"), str):
        texts.append(info["description"])
    skills = detail.get("skills") or {}
    for key in ("normalattack", "elementalskill", "elementalburst"):
        sec = skills.get(key) or {}
        if isinstance(sec, dict) and isinstance(sec.get("description"), str):
            texts.append(sec["description"])
    for p in (detail.get("passives") or {}).values():
        if isinstance(p, dict) and isinstance(p.get("description"), str):
            texts.append(p["description"])
    t = " ".join(texts)
    atk = t.count("攻击力") + t.count("攻击")
    dfn = t.count("防御力") + t.count("防御")
    hp = t.count("生命值") + t.count("生命")
    if dfn >= atk and dfn >= hp and dfn:
        return "DEF"
    if hp >= atk and hp >= dfn and hp:
        return "HP"
    return "ATK"


def fetch_lunaris_character(char_id, version=None):
    """从 api.lunaris.moe 拉取单个角色的官方数据（90 级满破白值）。

    返回与本地 schema 兼容的 dict；拉取失败返回 {}。绝不抛异常。
    """
    if not version:
        version = _lunaris_version()
    if not version:
        return {}
    base = "%s/%s" % (LUNARIS_BASE, version)
    charlist = _lunaris_get("%s/charlist.json" % base)
    cid = _lunaris_char_id(char_id, charlist)
    if not cid:
        return {}
    detail = _lunaris_get("%s/chs/char/%s.json" % (base, cid))
    if not isinstance(detail, dict):
        return {}
    info = detail.get("info") or {}
    stats90 = None
    for a in (info.get("attributes") or []):
        if isinstance(a, dict) and str(a.get("level")) == "90":
            stats90 = a
            break
    if not isinstance(stats90, dict):
        return {}

    rec = charlist.get(cid) or {}
    out = {}
    element = _norm_element(info.get("element") or rec.get("element"))
    weapon = _WEAPON_ALIAS.get(str(info.get("weapon") or rec.get("weaponType") or "").strip()) or ""
    if element:
        out["element"] = element
    if weapon:
        out["weapon"] = weapon

    hp = _num(stats90.get("hp"))
    atk = _num(stats90.get("atk"))
    defense = _num(stats90.get("def"))
    if hp:
        out["base_hp"] = int(round(hp))
    if atk:
        out["base_atk"] = int(round(atk))
    if defense:
        out["base_def"] = int(round(defense))

    asc = rec.get("ascensionStats") or {}
    asc_key = None
    for k in asc:
        if str(k).lower() in ("hp", "atk", "def", "attack", "defense") or "%" in str(k):
            asc_key = k
            break
    scaling = "ATK"
    if asc_key:
        low = str(asc_key).lower()
        if "hp" in low and "recharge" not in low and "healing" not in low:
            scaling = "HP"
        elif "def" in low:
            scaling = "DEF"
        elif "atk" in low:
            scaling = "ATK"
    if scaling == "ATK":
        scaling = _lunaris_scaling_stat(detail)
    out["scaling_stat"] = scaling

    blob = []
    skills = detail.get("skills") or {}
    for key in ("normalattack", "elementalskill", "elementalburst"):
        sec = skills.get(key) or {}
        if isinstance(sec, dict) and sec.get("description"):
            blob.append(sec["description"])
    for p in (detail.get("passives") or {}).values():
        if isinstance(p, dict) and p.get("description"):
            blob.append(p["description"])
    heal, shield, buff = _detect_functional(" ".join(blob))
    out["has_heal"] = heal
    out["has_shield"] = shield
    out["has_buff"] = buff

    if element == "风":
        rr = "driver"
    elif element in ("水", "雷", "火", "冰"):
        rr = "multiplier"
    elif buff:
        rr = "trigger"
    else:
        rr = "none"
    out["reaction_role"] = rr

    out["_source"] = "api.lunaris.moe (genshin-db 风格官方数据镜像 / %s)" % version
    out["_fetched"] = datetime.date.today().isoformat()
    return out


def fetch_ambr_character(char_id):
    """从 api.ambr.top 拉取单个角色的官方数据。

    返回与本地 schema 兼容的 dict（仅含 ambr 能稳定提供的字段）；
    拉取失败或无需覆盖的字段返回 {}。绝不抛异常。
    """
    url = "%s/CHS/character/%s" % (AMBR_BASE, char_id)
    data = _ambr_get(url)
    if not data:
        return {}
    d = _dig(data, "data") or data
    if not isinstance(d, dict):
        return {}

    out = {}
    # 元素 / 武器
    element = _dig(d, "element")
    weapon = _dig(d, "weapon")
    if element:
        out["element"] = element
    if weapon:
        out["weapon"] = weapon

    # 基础白值（90 级）
    stats90 = _dig(d, "statistics", "90") or _dig(d, "statistics", 90)
    if isinstance(stats90, dict):
        hp = _dig(stats90, "hp") or _dig(stats90, "hp_base")
        atk = _dig(stats90, "attack") or _dig(stats90, "atk")
        defense = _dig(stats90, "defend") or _dig(stats90, "def")
        if hp: out["base_hp"] = int(round(float(hp)))
        if atk: out["base_atk"] = int(round(float(atk)))
        if defense: out["base_def"] = int(round(float(defense)))

    # 突破百分比加成：genshin-db 基线已将突破并入 base_hp/atk/def（pct 置 0），
    # 为避免重复计算，ambr 拉取同样只写入最终白值，pct 保持默认 0。
    # （如确需独立 pct，应在 get_stats 合并时做去重，当前基线约定统一不重复计入。）

    # 功能性：扫描所有技能描述
    talent = _dig(d, "talent") or {}
    blob = []
    for sec in ("attack", "skill", "burst"):
        secd = _dig(talent, sec) or {}
        # 描述可能在 description 或多个 promote 段
        desc = _dig(secd, "description")
        if desc:
            blob.append(desc)
        for pr in (_dig(secd, "promote") or []):
            if isinstance(pr, dict) and pr.get("description"):
                blob.append(pr["description"])
    heal, shield, buff = _detect_functional(" ".join(blob))
    # 白名单显式覆盖（含 false）；未收录时采用保守文本探测并显式写入，
    # 避免旧 JSON 残留的宽松正则 true 一直保留。
    out["has_heal"] = _flag_for(char_id, "heal", heal)
    out["has_shield"] = _flag_for(char_id, "shield", shield)
    out["has_buff"] = _flag_for(char_id, "buff", buff)

    # 爆发能量
    ec = _dig(d, "energySkill", "cost") or _dig(d, "burst", "cost") or _dig(d, "skill", "cost")
    if ec:
        out["energy_cost"] = int(round(float(ec)))

    if out:
        out["_source"] = "ambr.top"
        out["_fetched"] = datetime.date.today().isoformat()
    return out


def _released_ids(game="genshin"):
    """从角色库读取已上线角色 id 列表（用于缺口填补枚举）。失败返回 []。"""
    p = os.path.join(DATA_DIR, "%s_characters.json" % game)
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        out = []
        for c in d.get("characters", []):
            if not c.get("status") or c.get("status") == "released":
                cid = c.get("id")
                if cid:
                    out.append(str(cid))
        return out
    except Exception:
        return []


def refresh_official_stats(char_ids=None, game="genshin"):
    """批量刷新官方数据缓存。

    - genshin：ambr.top 优先，不可达时自动用 api.lunaris.moe 补源。
    - hsr / zzz：原 hakush.in 官方镜像（站点已关闭，当前优雅降级为不可用）。

    默认（char_ids=None）为「缺口填补」模式：仅拉取基线中缺失（_missing 或
    base_hp 为 0）的已上线角色。

    Args:
        char_ids: 角色 id 列表；为 None 时仅填补基线缺口。
        game: 游戏 id。

    Returns:
        dict: {"updated": int, "failed": list, "source": ..., "gap_fill": bool}
    """
    if game == "genshin":
        gap_fill = False
        if char_ids is None:
            gap_fill = True
            char_ids = [cid for cid in _released_ids("genshin") if _is_gap(cid, "genshin")]
        version = _lunaris_version()
        updated = 0
        failed = []
        patch = {}
        for cid in (char_ids or []):
            rec = fetch_ambr_character(cid)
            if rec and len(rec) > 1:  # 至少拿到一个有效字段
                patch[cid] = rec
                updated += 1
                continue
            rec = fetch_lunaris_character(cid, version=version)
            if rec and (rec.get("base_hp") or rec.get("base_atk") or rec.get("base_def")):
                patch[cid] = rec
                updated += 1
            else:
                failed.append(cid)
        if patch:
            save_stats(patch)
        sources = set()
        for rec in patch.values():
            src = rec.get("_source", "")
            if "ambr.top" in src:
                sources.add("ambr.top")
            elif "lunaris" in src:
                sources.add("api.lunaris.moe")
        return {"updated": updated, "failed": failed[:50],
                "source": " + ".join(sorted(sources)) or "unavailable",
                "version": version or "",
                "total": len(char_ids or []), "gap_fill": gap_fill}
    elif game in ("hsr", "zzz"):
        return _refresh_hakush(char_ids, game)
    else:
        return {"updated": 0, "failed": [], "source": "unsupported",
                "total": 0, "gap_fill": False,
                "note": "该游戏官方数值刷新尚未接入（仅 genshin / hsr / zzz 支持）。"}


def update_genshin_lunaris_stats(char_ids=None, version=None):
    """批量用 api.lunaris.moe 刷新原神官方数值（默认只补基线缺口）。"""
    if version is None:
        version = _lunaris_version()
    gap_fill = char_ids is None
    if char_ids is None:
        char_ids = [cid for cid in _released_ids("genshin") if _is_gap(cid, "genshin")]
    updated = 0
    failed = []
    patch = {}
    for cid in (char_ids or []):
        rec = fetch_lunaris_character(cid, version=version)
        if rec and (rec.get("base_hp") or rec.get("base_atk") or rec.get("base_def")):
            patch[cid] = rec
            updated += 1
        else:
            failed.append(cid)
    if patch:
        save_stats(patch)
    return {"ok": True, "game": "genshin", "kind": "official_stats",
            "updated": updated, "failed": failed[:50],
            "source": "api.lunaris.moe", "version": version or "",
            "total": len(char_ids or []), "gap_fill": gap_fill}


def _is_gap(char_id, game="genshin"):
    """判断该角色是否为基线缺口（无数据或白值为 0）。"""
    s = get_stats(char_id, game)
    if s.get("_missing"):
        return True
    if not (s.get("base_hp") or s.get("base_atk") or s.get("base_def")):
        return True
    return False


def fetch_ambr_all_ids():
    """获取 ambr.top 全角色 id 列表（用于批量刷新）。失败返回 []。"""
    data = _ambr_get("%s/CHS/character" % AMBR_BASE)
    if not data:
        return []
    d = _dig(data, "data") or data
    ids = []
    if isinstance(d, list):
        for it in d:
            cid = _dig(it, "id") or _dig(it, "name_en")
            if cid:
                ids.append(str(cid))
    elif isinstance(d, dict):
        for cid in d.keys():
            ids.append(str(cid))
    return ids
