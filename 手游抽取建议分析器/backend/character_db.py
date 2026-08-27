"""角色库：加载 data/<game>_characters.json，提供查询/匹配。"""
import json
import os

from common import DATA_DIR


def _path(game):
    return os.path.join(DATA_DIR, "%s_characters.json" % game)


def load_characters(game="genshin"):
    p = _path(game)
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("characters", [])


def find_character(name_or_id, game="genshin"):
    chars = load_characters(game)
    q = (name_or_id or "").strip().lower()
    for c in chars:
        if c["id"].lower() == q:
            return c
        if c["name"].lower() == q:
            return c
        for a in c.get("aliases", []):
            if a.lower() == q:
                return c
    return None


def all_characters(game="genshin"):
    return load_characters(game)
