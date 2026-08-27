"""手动标注：单角色「真实具体分析结果」的持久化存储。

用户可在单角色面板手动更新真实分析结论，并附「证明来源」（标题/链接/具体时间点/备注）。
存储于 data/analysis_overrides.json，结构：
{
  "<char_id>": {
    "verdict": "strong_pull|pull|wait|skip|insufficient",
    "summary": "手动结论说明",
    "sources": [ {"title","url","time_point","note"} ],
    "updated_at": "ISO 时间"
  }
}
手动标注在展示时优先级最高（覆盖规则/AI 自动结果）。
"""
import json
import os
from datetime import datetime

from common import DATA_DIR

VALID_VERDICTS = {"strong_pull", "pull", "wait", "skip", "pure_xp", "insufficient"}

# 强度梯队（仅供总览参考；非官方结论，不参与抽取主结论）
VALID_TIERS = {"T0", "T0.5", "T1", "T2", "T3", "未分级"}

_PATH = os.path.join(DATA_DIR, "analysis_overrides.json")


def _load_all():
    if not os.path.exists(_PATH):
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_all_overrides():
    """一次读取全部手动标注（供总览页合并 verdict 用）。"""
    return _load_all()


def _save_all(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_override(char_id):
    data = _load_all()
    return data.get(char_id)


def set_override(char_id, payload):
    """保存（覆盖）某角色的手动标注。返回校验后的 dict 或抛出 ValueError。"""
    verdict = payload.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise ValueError("verdict 非法：%s" % verdict)
    sources = []
    for s in payload.get("sources", []) or []:
        sources.append({
            "title": (s.get("title") or "").strip(),
            "url": (s.get("url") or "").strip(),
            "time_point": (s.get("time_point") or "").strip(),
            "note": (s.get("note") or "").strip(),
        })
    rec = {
        "verdict": verdict,
        "summary": (payload.get("summary") or "").strip(),
        "sources": sources,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    # 梯队标签：可选，仅作总览参考，不参与抽取主结论
    tier = (payload.get("tier") or "").strip()
    if tier:
        if tier not in VALID_TIERS:
            raise ValueError("tier 非法：%s（应为 T0/T0.5/T1/T2/T3/未分级）" % tier)
        rec["tier"] = tier
    data = _load_all()
    data[char_id] = rec
    _save_all(data)
    return rec
