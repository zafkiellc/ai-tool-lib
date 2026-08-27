"""内容抽取：从视频标题/简介/标签中抽取「角色提及 + 情感信号」。
demo 阶段轻量实现：别名匹配 + 否定抵消的情感打分。
后续可替换为 ASR/OCR/转写 + LLM 的真实内容理解，接口保持一致即可。"""
import re

POSITIVE = [
    "必抽", "人权", "强度天花板", "T0", "强烈推荐", "推荐抽", "值得抽",
    "真神", "必练", "毕业", "顶级", "保值", "神卡", "抽到不亏", "建议抽",
    "必入", "万金油", "万能", "必养", "抽到赚", "强度在线", "优先抽",
]
NEGATIVE = [
    "跳过", "不推荐", "别抽", "别练", "仓管", "拉胯", "不值得", "避雷",
    "划水", "玩具", "退环境", "不保值", "翻车", "别碰", "坑", "不如预期",
    "谨慎抽", "不值得抽", "可有可无", "一般", "不值得练",
]

# 否定标记：出现在正向词前 1 个字符时，抵消该正向（整段视为中性）
NEG_MARKERS = set("不没别勿未莫无甭")

# 官方前瞻/角色演示：出现角色即视为「被官方点名/主推」，给正向相关权重
OFFICIAL_POSITIVE = ["角色演示", "前瞻", "上线", "复刻", "新角色", "特别节目"]


class Signal:
    def __init__(self, character_id, character_name, polarity, weight,
                 context, video):
        self.character_id = character_id
        self.character_name = character_name
        self.polarity = polarity          # +1 正 / -1 负 / 0 中性(官方点名)
        self.weight = weight
        self.context = context
        self.video = video

    def to_dict(self):
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "polarity": self.polarity,
            "weight": round(self.weight, 3),
            "context": self.context,
            "source_name": self.video.get("source_name"),
            "source_role": self.video.get("source_role"),
            "trusted": self.video.get("trusted"),
            "subscribed": bool(self.video.get("subscribed")),
            "author": self.video.get("author"),
            "mid": self.video.get("mid"),
            "title": self.video.get("title"),
            "url": self.video.get("url"),
            "pubdate_str": self.video.get("pubdate_str"),
            "source_mode": self.video.get("source_mode"),
            "is_sample": bool(self.video.get("is_sample", False)),
        }


def _find_spans(text, keywords):
    """返回 [(start, end, keyword), ...]。"""
    spans = []
    for kw in keywords:
        start = 0
        while True:
            i = text.find(kw, start)
            if i < 0:
                break
            spans.append((i, i + len(kw), kw))
            start = i + 1
    return spans


def _sentiment_over_windows(text, mention_positions, window=28):
    """在每次提及附近的窗口内做情感判定，聚合整段视频对该角色的态度。
    处理否定抵消：正向词前紧邻否定标记 -> 该正向作废，且其区间内的负向词一并作废。"""
    pos_spans = _find_spans(text, POSITIVE)
    neg_spans = _find_spans(text, NEGATIVE)

    cancelled = set()  # 被作废的 span 索引

    # 处理否定抵消
    for pi, (ps, pe, pkw) in enumerate(pos_spans):
        before = text[max(0, ps - 1):ps]
        before2 = text[max(0, ps - 2):ps]
        negated = (before in NEG_MARKERS) or (before2 in NEG_MARKERS)
        if negated:
            cancelled.add(("pos", pi))
            # 作废与该正向区间重叠的负向词
            for ni, (ns, ne, nkw) in enumerate(neg_spans):
                if not (ne <= ps - 2 or ns >= pe + 1):
                    cancelled.add(("neg", ni))

    pos_hits, neg_hits = [], []
    for pi, (ps, pe, pkw) in enumerate(pos_spans):
        if ("pos", pi) in cancelled:
            continue
        # 仅统计落在某个提及窗口内的正向词
        if any(abs(ps - mp) <= window for mp in mention_positions):
            pos_hits.append(pkw)
    for ni, (ns, ne, nkw) in enumerate(neg_spans):
        if ("neg", ni) in cancelled:
            continue
        if any(abs(ns - mp) <= window for mp in mention_positions):
            neg_hits.append(nkw)

    return pos_hits, neg_hits


def extract_signals(video, characters):
    title = video.get("title", "") or ""
    desc = video.get("description", "") or ""
    tag = video.get("tag", "") or ""
    # 用原文做匹配，单独 lowercase 做命中（中文 lowercase 无影响，保留以兼容英文）
    raw_full = title + "\n" + desc + "\n" + tag
    role = video.get("source_role")
    is_official = role == "official"

    signals = []
    for ch in characters:
        mention_positions = []
        for alias in ch["aliases"]:
            start = 0
            while True:
                i = raw_full.find(alias, start)
                if i < 0:
                    break
                mention_positions.append(i)
                start = i + 1
        if not mention_positions:
            continue

        if is_official:
            if any(k in raw_full for k in OFFICIAL_POSITIVE):
                signals.append(Signal(ch["id"], ch["name"], 0, 1.0,
                                       "官方点名/展示", video))
            continue

        pos_hits, neg_hits = _sentiment_over_windows(raw_full, mention_positions)
        if pos_hits and not neg_hits:
            signals.append(Signal(ch["id"], ch["name"], 1,
                                  min(1.0 + 0.15 * len(pos_hits), 2.0),
                                  "正向：" + "、".join(pos_hits), video))
        elif neg_hits and not pos_hits:
            signals.append(Signal(ch["id"], ch["name"], -1,
                                  min(1.0 + 0.15 * len(neg_hits), 2.0),
                                  "负向：" + "、".join(neg_hits), video))
        elif pos_hits and neg_hits:
            net = len(pos_hits) - len(neg_hits)
            pol = 1 if net > 0 else (-1 if net < 0 else 0)
            signals.append(Signal(ch["id"], ch["name"], pol,
                                  min(1.0 + 0.15 * max(len(pos_hits), len(neg_hits)), 2.0),
                                  "混合：正(%s)/负(%s)" % (
                                      "、".join(pos_hits), "、".join(neg_hits)),
                                  video))
        else:
            signals.append(Signal(ch["id"], ch["name"], 0, 0.4,
                                  "提及（无明确情感）", video))
    return signals
