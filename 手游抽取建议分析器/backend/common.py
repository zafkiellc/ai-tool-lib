"""公共工具：配置加载、路径、wbi 签名请求、简单文件缓存。"""
import json
import os
import time
import urllib.request
import urllib.parse
import hashlib
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 打包为 exe（PyInstaller onedir）后，数据/前端/config 位于 _internal 目录，
# 但为了让「设置/数据」的编辑即时生效且持久化到用户本机（直接改 config.json / data 即可），
# 若 exe 所在项目的父目录存在，则优先使用外部项目根目录（而非只读的 sys._MEIPASS 临时解压目录）。
if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    _proj = os.path.dirname(os.path.dirname(sys.executable))
    if os.path.isdir(_proj):
        BASE_DIR = _proj
    else:
        BASE_DIR = sys._MEIPASS
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")
SAMPLE_DIR = os.path.join(DATA_DIR, "samples")
CACHE_DIR = os.path.join(BASE_DIR, ".cache")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61,
    26, 17, 0, 1, 57, 22, 25, 54, 21, 56, 20, 11, 52, 44, 51, 59, 6, 60, 4, 34,
    36, 30, 62, 63
]


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------- 多游戏状态 ----------------------
def game_state(cfg, game_id=None):
    """返回 (game_id, game_dict)。game_dict 含 display_name / category_field /
    category_label / category_order / current_version / streamers / official。"""
    game_id = game_id or cfg.get("current_game") or "genshin"
    games = cfg.get("games", {}) or {}
    g = games.get(game_id)
    if not g:
        # 兼容旧配置：无 games 时退化为顶层字段（视为原神）
        g = {
            "display_name": cfg.get("display_name", game_id),
            "category_field": "element",
            "category_label": "元素",
            "category_order": [],
            "current_version": cfg.get("current_version", ""),
            "streamers": cfg.get("streamers", []),
            "official": cfg.get("official", []),
        }
        game_id = "genshin"
    # 补齐缺省字段
    g.setdefault("category_field", "element")
    g.setdefault("category_label", "元素")
    g.setdefault("category_order", [])
    g.setdefault("streamers", [])
    g.setdefault("official", [])
    return game_id, g


def list_games(cfg):
    """返回游戏列表（用于前端切换），每项含 id / display_name / category_* /
    character_count（调用方补）。"""
    games = cfg.get("games", {}) or {}
    cur = cfg.get("current_game") or "genshin"
    # 兼容：若没有 games，构造一个原神项
    if not games:
        games = {"genshin": {
            "display_name": cfg.get("display_name", "原神"),
            "category_field": "element", "category_label": "元素",
            "category_order": [], "current_version": cfg.get("current_version", ""),
            "streamers": cfg.get("streamers", []), "official": cfg.get("official", []),
        }}
    out = []
    for gid, g in games.items():
        out.append({
            "id": gid,
            "display_name": g.get("display_name", gid),
            "category_field": g.get("category_field", "element"),
            "category_label": g.get("category_label", "元素"),
            "category_order": g.get("category_order", []),
            "current": gid == cur,
        })
    return out


# ---------------------- 各游戏关键词（用于 B 站内容过滤/搜索） ----------------------
_GAME_KEYWORDS = {
    "genshin": [
        "原神", "genshin", "提瓦特", "蒙德", "璃月", "稻妻", "须弥",
        "枫丹", "纳塔", "至冬", "深渊", "圣遗物", "命座", "天赋",
        "元素", "反应", "绽放", "超载", "蒸发", "冻结", "扩散", "结晶", "感电",
        "抽卡", "卡池", "UP", "小保底", "大保底", "定轨", "纠缠之缘",
        "五星", "四星", "摩拉", "原石", "树脂",
    ],
    "hsr": [
        "星穹铁道", "崩坏星铁", "星铁", "hsr", "honkai star rail",
        "命途", "光锥", "行迹", "遗器", "忘却之庭", "模拟宇宙",
        "虚构叙事", "混沌回忆", "缇宝", "星琼", "专武",
        "毁灭", "巡猎", "智识", "同谐", "虚无", "存护", "丰饶", "记忆",
        "击破", "弱点击破", "追加攻击", "持续伤害",
    ],
    "zzz": [
        "绝区零", "zzz", "zenless zone zero",
        "属性", "邦布", "驱动盘", "专属影画", "压缩空间", "恶战",
        "电击", "异常", "支援", "强攻", "击破", "以太", "物理",
        "新艾利都", "空洞", "以骸", "绳匠",
    ],
    "wuthering_waves": [
        "鸣潮", "wuthering waves", "wuwa",
        "声骸", "衍射", "导电", "冷凝", "热熔", "气动", "湮灭",
        "漂移", "共鸣链", "协奏", "变奏", "声纹",
        "今州", "浩渺", "悲鸣",
    ],
    "arknights_endfield": [
        "终末地", "明日方舟终末", "arknights endfield",
        "干员", "职业", "基建", "战术", "终端",
    ],
    "nte": [
        "异环", "NTE", "Neverness To Everness",
        "异象", "扭曲", "映像",
    ],
}


def game_keywords(game="genshin"):
    """返回指定游戏的关键词列表（用于 B 站视频/文章相关性过滤）。"""
    return _GAME_KEYWORDS.get(game, _GAME_KEYWORDS["genshin"])


def now_ts():
    return int(time.time())


# ---------------------- 缓存 ----------------------
def cache_get(key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, key.replace("/", "_") + ".json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def cache_set(key, value):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, key.replace("/", "_") + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def clear_cache():
    """清空所有抓取缓存（用于「手动更新分析」）。"""
    removed = 0
    if os.path.isdir(CACHE_DIR):
        for fn in os.listdir(CACHE_DIR):
            if fn.endswith(".json"):
                try:
                    os.remove(os.path.join(CACHE_DIR, fn))
                    removed += 1
                except Exception:
                    pass
    return removed


ICON_BASE = "https://genshin.jmp.blue/characters"


def icon_url(char_id):
    return "%s/%s/icon" % (ICON_BASE, char_id)


# ---------------------- wbi 签名 HTTP ----------------------
class BiliClient:
    def __init__(self, sessdata=""):
        self.sessdata = sessdata
        self._mixin = None

    def _headers(self):
        h = {"User-Agent": UA, "Referer": "https://space.bilibili.com/"}
        if self.sessdata:
            h["Cookie"] = "SESSDATA=" + self.sessdata
        return h

    def _get_mixin(self):
        if self._mixin:
            return self._mixin
        url = "https://api.bilibili.com/x/web-interface/nav"
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        img = data["data"]["wbi_img"]["img_url"].split("/")[-1].split(".")[0]
        sub = data["data"]["wbi_img"]["sub_url"].split("/")[-1].split(".")[0]
        orig = img + sub
        self._mixin = "".join(orig[i] for i in MIXIN_KEY_ENC_TAB)[:32]
        return self._mixin

    def _sign(self, params):
        mixin = self._get_mixin()
        params = dict(params)
        params["wts"] = now_ts()
        params = dict(sorted(params.items()))
        query = urllib.parse.urlencode(params)
        params["w_rid"] = hashlib.md5((query + mixin).encode()).hexdigest()
        return params

    def get_json(self, url, params=None):
        if params is not None:
            params = self._sign(params)
            url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    def space_acc_info(self, mid):
        """解析 UID 对应的真实频道信息（需 wbi 签名）。"""
        params = {"mid": str(mid)}
        data = self.get_json(
            "https://api.bilibili.com/x/space/wbi/acc/info", params)
        if data.get("code") != 0:
            raise RuntimeError("bili code=%s msg=%s" %
                               (data.get("code"), data.get("message")))
        return data["data"]


def parse_uid_from_input(text):
    """从用户输入（纯 UID 或 B 站空间链接）解析出 UID。"""
    text = (text or "").strip()
    if not text:
        return None
    # 直接是数字
    if text.isdigit():
        return text
    # 链接形式：space.bilibili.com/13552255 或 /space/13552255
    import re
    m = re.search(r"(?:space\.bilibili\.com/|mid=)(\d+)", text)
    if m:
        return m.group(1)
    return None


def resolve_bilibili_user(uid, sessdata=""):
    """解析 UID -> 真实频道名/头像。失败抛出 RuntimeError。"""
    client = BiliClient(sessdata)
    info = client.space_acc_info(uid)
    return {
        "uid": str(uid),
        "name": info.get("name", "UID:%s" % uid),
        "face": info.get("face", ""),
        "ok": True,
    }
