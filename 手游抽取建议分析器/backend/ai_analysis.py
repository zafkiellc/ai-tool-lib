"""AI 辅助分析：线上 API 与本地大模型双接口（OpenAI 兼容 chat/completions）。

设计要点：
- 全局「无 AI」的快速方法只有「规则基线」（content_extractor + analyzer），由 config.analysis_mode="rule" 唯一指定。
- 本模块是「第二层」增强：把角色属性 + 视频证据喂给 LLM，输出结构化建议（含可选 time_point）。
- 线上(online)：任意 OpenAI 兼容服务（OpenAI / DeepSeek / Moonshot / 通义 / 智谱等），需 base_url + api_key + model。
- 本地(local)：Ollama(http://localhost:11434/v1) 或 LM Studio(http://localhost:1234/v1) 等 OpenAI 兼容服务，base_url 指向本地，api_key 通常为空。
- 未启用或调用失败一律优雅降级返回 None，绝不影响规则基线结果。

⚠️ 角色隔离（核心防幻觉机制）：
- SYSTEM_PROMPT 使用「目标锁定 + 禁止名单 + 负面示例」三重约束
- analyze() 返回前通过 _detect_character_contamination() 后处理检测：
  若 pros/cons/reasons/summary 中出现非目标角色名 → 强制 verdict=insufficient 并标注污染警告
"""
import json
import re
import urllib.request

from common import UA


def _load_all_character_names():
    """加载全角色名列表（用于构建禁止名单）。失败时返回空集。"""
    try:
        from character_db import all_characters
        chars = all_characters()
        names = set()
        for c in chars:
            names.add(c.get("name", ""))
            for a in c.get("aliases", []):
                names.add(a)
        return names
    except Exception:
        return set()


# 全局缓存的角色名集合（模块加载时初始化）
_ALL_CHAR_NAMES = _load_all_character_names()


SYSTEM_PROMPT_TEMPLATE = """你是一名手游抽卡（角色抽取）建议分析助手。
你的任务：【仅】对【{game_display_name}】游戏中的【{target_name}】这一个角色给出抽取建议分析报告。

═══ 绝对规则（违反任何一条 = 回答错误）═══

0. 【游戏锁定】你正在分析的是【{game_display_name}】的角色。如果证据中出现其他游戏（如原神/星穹铁道/绝区零/鸣潮/方舟/异环等）的内容，
   那是搜索噪音或跨游戏污染，你必须【完全忽略】这些内容，不能当作{target_name}的证据。
   特别是：不要把「星铁的水神」「绝区零的火系」等跨游戏引用当成{target_name}的评价依据。
1. 【唯一对象】你只能分析、评价、判断【{target_name}】。全文不允许出现其他任何角色的名字。
2. 【禁止名单】以下角色名在你的回答中【绝对禁止出现】：{forbidden_list}
   如果证据中提到这些名字，那是视频标题的背景噪音，你必须完全忽略。
3. 【禁止比较】不要写"比XX强""不如XX""和XX差不多""XX的下位替代"这类句子。
4. 【禁止跨角色】如果 pros/cons/reasons/evidence_chain 中出现了除{target_name}以外的角色名，
   说明你违反了规则，请立即删除该条内容或重写。
5. 【数据不足即 insufficient】如果你在证据中找不到关于{target_name}的实质内容，
   verdict 必须填 insufficient，summary 必须说明"因证据中几乎找不到关于{target_name}的内容"。

❌ 错误示例（绝对不要这样输出）：
- pros: ["造型很棒"]  <- 这可能是在评价别的角色
- cons: ["相比那维莱特倍率偏低"]  <- 出现了别的角色名，违规！
- reasons: ["兹白作为岩系单手剑..."]  <- 完全在说别的角色！
- evidence_chain: ["星铁的水神伤害很高..."]  <- 跨游戏污染！这是在说星穹铁道的角色，不是{target_name}
- summary: "作为水神，她在队伍中..."  <- "水神"可能是其他游戏的角色，必须用全名{target_name}

✅ 正确示例（只针对目标角色）：
- 分析芙宁娜时：pros: ["高频挂水辅助"、"元素爆发伤害可观"]
- 分析钟离时：cons: ["纯护盾定位、输出依赖岩反应"]

═══ JSON 输出格式 ═══

只输出一个 JSON 对象，不要有任何多余文字。JSON 结构：
{{
  "verdict": "strong_pull|pull|wait|skip|pure_xp|insufficient",
  "confidence": 0.0到1.0之间的数字,
  "summary": "一句话中文结论（只关于{target_name}）",
  "tier": "强度定位（无则空字符串）",
  "pros": ["仅关于{target_name}的优点"],
  "cons": ["仅关于{target_name}的短板"],
  "reasons": ["仅关于{target_name}的判断理由"],
  "evidence_chain": [
    {{"point": "要点", "source": "来源", "time_point": "时间点或空", "quote": "原话", "support": "positive|negative|neutral"}}
  ],
  "verdict_rationale": "证据如何汇总成该结论",
  "who_should_pull": "推荐人群",
  "risk_note": "风险提示（无则空）",
  "team_advice": "配队定位与抽取价值：{target_name}在哪些队伍体系中发挥核心作用，是否值得为凑齐配队而抽（可提及通用定位/元素反应，但不要出现其他具体角色名）",
  "weapon_advice": "武器/光锥抽取建议：是否值得抽专武/限定武器，或对平民武器/下位替代的建议（只针对{target_name}的装备选择）",
  "constellation_advice": "命座/星魂提升建议：列出对该角色强度影响最大的关键命座/星魂（如1命/2命/6命或对应星魂），说明每阶带来的核心机制/数值跃迁，并给出『是否值得为补命座而投入』的结论（只谈{target_name}自身，不要出现其他角色名）",
  "rerun_advice": "复刻/卡池时间预测：基于该游戏的版本节奏与该角色的上线/上次UP版本，推测其下次复刻大致所处版本号或时间窗口；若信息不足请明确写『无法可靠预测』，不要把臆测当确定结论",
  "roi": "性价比(ROI)评估：结合该角色获取成本（所需原石/星琼或抽数）与强度/泛用性提升，给出投入产出比判断（如高/中/低），并说明『对哪类玩家更划算』",
  "radar_scores": {{
    "base_stats": {{"score": 0-10, "note": "数值基础评价", "weight": 0.20, "source": "official|official_derived|review"}},
    "multiplier": {{"score": 0-10, "note": "倍率水平", "weight": 0.25, "source": "official|official_derived|review"}},
    "reaction": {{"score": 0-10, "note": "反应强度", "weight": 0.20, "source": "official|official_derived|review"}},
    "team_dependency": {{"score": 0-10, "note": "吃拐强度", "weight": 0.15, "source": "official|official_derived|review"}},
    "utility": {{"score": 0-10, "note": "辅助能力", "weight": 0.10, "source": "official|official_derived|review"}},
    "overworld": {{"score": 0-10, "note": "大世界便利性", "weight": 0.10, "source": "official|official_derived|review"}}
  }}
}}
verdict: strong_pull=必抽, pull=推荐, wait=观望, skip=不推荐, pure_xp=纯XP, insufficient=数据不足。
radar_scores 每项 0~10 分；数据不足给 5 分并 note 说明。
权重固定为 base_stats 20% / multiplier 25% / reaction 20% / team_dependency 15% / utility 10% / overworld 10%，不要自行修改。
source 取值：official=官方数值/技能文本直接推导；official_derived=由官方文本间接推导（如吃拐/辅助）；review=社区评测（如大世界便利性）。"""


def _build_system_prompt(target_name, game="genshin", game_display_name=None):
    """动态构建 SYSTEM_PROMPT，注入目标角色名 + 禁止名单 + 游戏上下文。"""
    if not game_display_name:
        game_display_name = {"genshin": "原神", "hsr": "崩坏：星穹铁道",
                            "zzz": "绝区零", "wuthering_waves": "鸣潮",
                            "arknights_endfield": "明日方舟：终末地",
                            "nte": "异环 (Neverness To Everness)"}.get(game, game)
    # 构建禁止名单：所有角色名减去目标角色及其别名
    forbidden = sorted(_ALL_CHAR_NAMES - {target_name})
    # 如果角色名太多，截取前 80 个（避免 prompt 过长）
    if len(forbidden) > 80:
        forbidden = forbidden[:80] + ["...等共%d个其他角色" % (len(forbidden) - 80)]
    forbidden_str = "、".join(forbidden) if forbidden else "（无）"
    return SYSTEM_PROMPT_TEMPLATE.format(
        target_name=target_name,
        forbidden_list=forbidden_str,
        game_display_name=game_display_name,
    )


# 向后兼容：保留 SYSTEM_PROMPT 变量名供外部引用（实际使用 _build_system_prompt 动态生成）
SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(
    target_name="{目标角色}", forbidden_list="（动态生成）",
    game_display_name="当前游戏",
)

VERDICT_LABELS = {
    "strong_pull": "必抽", "pull": "推荐", "wait": "观望",
    "skip": "不推荐", "pure_xp": "纯XP", "insufficient": "数据不足",
}

# 雷达图维度定义（用于前端渲染 + 后端校验）
# weight 为综合加权：数据类指标（数值/倍率/反应）权重更高，
# 非数据类指标（吃拐/辅助/大世界）作为修正项降低权重。
RADAR_DIMENSIONS = [
    ("base_stats", "数值基础", 0.20),
    ("multiplier", "倍率水平", 0.25),
    ("reaction", "反应强度", 0.20),
    ("team_dependency", "吃拐强度", 0.15),
    ("utility", "辅助能力", 0.10),
    ("overworld", "大世界便利性", 0.10),
]

# radar_scores 默认值（数据不足时使用）
_RADAR_DEFAULT = {
    dim: {"score": 5, "note": "数据不足，暂评中等", "weight": w, "source": "review"}
    for dim, _label, w in RADAR_DIMENSIONS
}


def _validate_radar_scores(raw):
    """校验并规范化 radar_scores。确保每项 score 为 0~10 整数，note 为字符串。"""
    if not raw or not isinstance(raw, dict):
        return dict(_RADAR_DEFAULT)
    result = {}
    for dim, label, w in RADAR_DIMENSIONS:
        val = raw.get(dim)
        if isinstance(val, dict):
            try:
                s = int(val.get("score", 5))
                s = max(0, min(10, s))
            except (ValueError, TypeError):
                s = 5
            n = str(val.get("note", "") or "")
            src = val.get("source")
            if src not in ("official", "official_derived", "review"):
                src = "review"
            mw = val.get("weight")
            try:
                fw = float(mw) if mw is not None else w
                fw = max(0.0, min(1.0, fw))
            except (ValueError, TypeError):
                fw = w
            result[dim] = {"score": s, "note": n, "weight": fw, "source": src}
        else:
            # 兼容旧格式：直接是数字
            try:
                s = int(val) if val is not None else 5
                s = max(0, min(10, s))
            except (ValueError, TypeError):
                s = 5
            result[dim] = {"score": s, "note": "", "weight": w, "source": "review"}
    # 确保所有6个维度都存在
    for dim, label, w in RADAR_DIMENSIONS:
        if dim not in result:
            result[dim] = {"score": 5, "note": "", "weight": w, "source": "review"}
    return result


VALID_VERDICTS = set(VERDICT_LABELS.keys())


def _provider_cfg(cfg):
    ai = cfg.get("ai", {})
    provider = ai.get("provider", "online")
    pc = ai.get(provider, {}) or {}
    return provider, pc


def _endpoint(base_url):
    base = (base_url or "").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _extract_json(text):
    """从模型输出中稳健提取 JSON（兼容 ```json 包裹与前后多余文字）。"""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        idx = t.rfind("```")
        if idx > 0:
            t = t[:idx]
        t = t.strip()
    try:
        return json.loads(t)
    except Exception:
        s = t.find("{")
        e = t.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(t[s:e + 1])
            except Exception:
                return None
        return None


def _detect_character_contamination(parsed, target_name, target_aliases=None):
    """后处理检测：检查 AI 返回内容是否包含非目标角色名。

    返回 (contaminated: bool, leaked_names: list[str], warning: str)。
    若 pros/cons/reasons/summary 中出现非目标角色名 → 标记为污染。
    """
    if not parsed or not isinstance(parsed, dict):
        return False, [], ""

    # 构建允许的名字集合（目标角色 + 别名）
    allowed = {target_name}
    if target_aliases:
        allowed.update(target_aliases)

    # 要检查的字段（这些字段不应该出现其他角色名）
    check_fields = ["pros", "cons", "reasons", "summary"]
    leaked = set()

    for field in check_fields:
        val = parsed.get(field)
        if isinstance(val, list):
            text = " ".join(str(x) for x in val)
        elif isinstance(val, str):
            text = val
        else:
            continue
        # 在文本中查找是否有非目标角色名
        for char_name in _ALL_CHAR_NAMES:
            if char_name in allowed:
                continue
            # 用词边界匹配，避免子串误判（如"林"匹配到"琴"不会但"夜兰"要精确）
            if len(char_name) >= 2 and char_name in text:
                leaked.add(char_name)

    if leaked:
        warning = ("⚠️ AI 返回内容检测到非目标角色名泄漏：%s。"
                   "LLM 忽略了角色隔离约束，结果已被标记为不可信。" % "、".join(sorted(leaked)))
        return True, sorted(leaked), warning

    return False, [], ""


def build_user_prompt(character, evidence, lang="zh"):
    lines = []
    target = character.get("name", "")
    aliases = character.get("aliases", []) or []
    char_id = character.get("id", "")

    # ===== 目标角色（突出显示） =====
    lines.append("【目标角色（仅分析此角色，绝对不要提及其他角色）】")
    lines.append("名称：%s（别名：%s）" % (target, "、".join(aliases)))
    lines.append("元素：%s ｜ 武器：%s ｜ 稀有度：%s★ ｜ 版本：%s" % (
        character.get("element", ""), character.get("weapon", ""),
        character.get("rarity", ""), character.get("version", "")))
    if character.get("note"):
        lines.append("备注：%s" % character["note"])

    # ===== 官方数据（雷达图评分的客观依据）=====
    try:
        from official_stats import format_for_prompt
        stats_text = format_for_prompt(char_id, target)
        lines.append("")
        lines.append(stats_text)
    except Exception:
        pass  # 官方数据模块不可用时静默跳过

    lines.append("")
    lines.append("=" * 60)
    lines.append("证据（以下所有证据均与【%s】相关）" % target)
    lines.append("⚠️ 再次提醒：即使证据标题中出现其他角色名，也与你无关，忽略它们！")
    lines.append("=" * 60)
    if not evidence:
        lines.append("（无可用证据 → verdict 必须为 insufficient）")
    for i, e in enumerate(evidence, 1):
        pol = "正向" if e.get("polarity", 0) > 0 else ("负向" if e.get("polarity", 0) < 0 else "中性")
        lines.append("")
        lines.append("--- 证据 #%d ---" % i)
        lines.append("情感倾向：%s" % pol)
        lines.append("关键信号：%s" % (e.get("context") or "无"))
        lines.append("来源视频：%s" % (e.get("title") or "未知"))
        if e.get("source_name") or e.get("author"):
            if e.get("subscribed"):
                role_label = {"main": "订阅主播·主意见", "cross_check": "订阅主播·交叉验证",
                              "official": "官方"}.get(e.get("source_role"), "订阅主播")
                lines.append("来源：%s（%s）" % (e.get("author") or e.get("source_name"), role_label))
            else:
                lines.append("来源：%s" % (e.get("source_name") or e.get("author")))
        if e.get("url"):
            lines.append("链接：%s" % e["url"])
        if e.get("pubdate_str"):
            lines.append("发布时间：%s" % e["pubdate_str"])
        if e.get("time_point"):
            lines.append("视频内时间点：%s" % e["time_point"])
        if e.get("content"):
            lines.append("内容摘录（字幕/正文，AI 生成字幕或作者正文）：%s" % e["content"])
    lines.append("")
    lines.append("=" * 60)
    lines.append("输出要求：")
    lines.append("1) 所有字段只允许出现【%s】，禁止出现其他任何角色名！" % target)
    lines.append("2) evidence_chain 每一条都要能支撑 verdict 或某个 pros/cons；")
    lines.append("3) verdict_rationale 说明证据如何汇总成该结论；")
    lines.append("4) 若证据不足或大部分与该角色无关 → verdict=insufficient；")
    lines.append("5) radar_scores 给出 6 维度各 0~10 分评分（基于该角色的元素/武器/定位）；")
    lines.append("   每项附带固定 weight（base_stats 0.20 / multiplier 0.25 / reaction 0.20 / "
                 "team_dependency 0.15 / utility 0.10 / overworld 0.10，不要改）与 "
                 "source（official=官方数值/技能文本直接推导、official_derived=官方文本间接推导、"
                 "review=社区评测）及 note 依据。")
    return "\n".join(lines)


def analyze(character, evidence, cfg, game=None):
    """调用 LLM 做结构化分析。失败或未启用返回 None（优雅降级，不影响规则基线）。"""
    ai = cfg.get("ai", {})
    if not ai.get("enabled"):
        return None
    provider, pc = _provider_cfg(cfg)
    base_url = pc.get("base_url", "")
    api_key = pc.get("api_key", "")
    model = pc.get("model", "")
    if not base_url or not model:
        return None

    if not game:
        game = cfg.get("current_game", "genshin")
    target_name = character.get("name", "")
    target_aliases = character.get("aliases", []) or []

    # 使用动态生成的 SYSTEM_PROMPT（含目标角色名 + 禁止名单 + 游戏锁定）
    system_prompt = _build_system_prompt(target_name, game=game)
    user_prompt = build_user_prompt(character, evidence, ai.get("prompt_lang", "zh"))

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.15,  # 降低温度减少幻觉
    }
    try:
        req = urllib.request.Request(
            _endpoint(base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": UA,
                "Authorization": "Bearer " + (api_key or ""),
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        return {"ok": False, "error": "AI 调用失败：%s" % e, "provider": provider}
    parsed = _extract_json(content)
    if not parsed:
        return {"ok": False, "error": "AI 输出无法解析为 JSON", "provider": provider, "raw": content[:500]}

    # ===== 后处理：角色污染检测 =====
    contaminated, leaked_names, contamination_warning = _detect_character_contamination(
        parsed, target_name, target_aliases
    )

    verdict = parsed.get("verdict")
    if verdict not in VALID_VERDICTS:
        verdict = "insufficient"

    # 若检测到污染，强制降级为 insufficient 并附加警告
    if contaminated and verdict != "insufficient":
        verdict = "insufficient"
        contamination_warning += " 已强制将 verdict 降级为 insufficient。"

    result = {
        "ok": True,
        "provider": provider,
        "verdict": verdict,
        "verdict_label": VERDICT_LABELS.get(verdict, verdict),
        "confidence": float(parsed.get("confidence", 0.0) or 0.0),
        "summary": parsed.get("summary", ""),
        "tier": parsed.get("tier", "") or "",
        "pros": parsed.get("pros", []) or [],
        "cons": parsed.get("cons", []) or [],
        "reasons": parsed.get("reasons", []) or [],
        "evidence": parsed.get("evidence", []) or [],
        "evidence_chain": parsed.get("evidence_chain", []) or [],
        "verdict_rationale": parsed.get("verdict_rationale", "") or "",
        "who_should_pull": parsed.get("who_should_pull", "") or "",
        "risk_note": parsed.get("risk_note", "") or "",
        "team_advice": parsed.get("team_advice", "") or "",
        "weapon_advice": parsed.get("weapon_advice", "") or "",
        "constellation_advice": parsed.get("constellation_advice", "") or "",
        "rerun_advice": parsed.get("rerun_advice", "") or "",
        "roi": parsed.get("roi", "") or "",
        "radar_scores": _validate_radar_scores(parsed.get("radar_scores")),
        "raw": content,
        "character_contaminated": contaminated,
        "contamination_warning": contamination_warning or None,
        "leaked_character_names": leaked_names if contaminated else [],
    }
    return result


def status(cfg):
    """返回 AI 配置摘要（不含密钥）。"""
    ai = cfg.get("ai", {})
    provider, pc = _provider_cfg(cfg)
    return {
        "enabled": bool(ai.get("enabled")),
        "provider": provider,
        "model": pc.get("model", ""),
        "base_url": pc.get("base_url", ""),
        "configured": bool(pc.get("base_url") and pc.get("model")),
    }


def test(cfg):
    """探测 AI 接口连通性：发一个最小探测请求，验证 base_url/model/api_key 是否可用。"""
    ai = cfg.get("ai", {})
    if not ai.get("enabled"):
        return {"ok": False, "error": "AI 未启用（请先在设置中开启）"}
    provider, pc = _provider_cfg(cfg)
    base_url = pc.get("base_url", "")
    api_key = pc.get("api_key", "")
    model = pc.get("model", "")
    if not base_url or not model:
        return {"ok": False, "error": "AI 未配置 base_url 或 model"}
    payload = {"model": model, "messages": [{"role": "user", "content": "ping"}],
               "temperature": 0, "max_tokens": 8}
    try:
        req = urllib.request.Request(
            _endpoint(base_url), data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": UA,
                     "Authorization": "Bearer " + (api_key or "")},
            method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return {"ok": True, "provider": provider, "reachable": True,
                "message": "连接成功，模型返回：%s" % content[:60]}
    except Exception as e:
        hint = ("线上服务请检查 base_url/api_key/model 是否正确、额度是否充足；"
                "本地服务(Ollama/LM Studio)请确认已启动且 base_url 正确（如 http://localhost:11434/v1）。")
        return {"ok": False, "error": "连接失败：%s。%s" % (e, hint)}
