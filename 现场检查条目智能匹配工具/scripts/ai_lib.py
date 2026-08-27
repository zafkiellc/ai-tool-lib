# -*- coding: utf-8 -*-
"""
ai_lib.py — 阶段四：免费 LLM 语义匹配（OpenAI 兼容 chat/completions）

设计目标：
- 仅依赖标准库（urllib），不引入第三方包，保持轻量。
- 支持多种免费/本地后端：DeepSeek、豆包(火山方舟)、本地 Ollama、自定义 OpenAI 兼容端点、演示(mock)。
- 前端会把每条手工记录的「候选标准条目」一起发过来，本模块让 LLM 只从这些候选里挑 code，
  既省 token 又避免编造不存在的条目。
- 多记录分块调用（每块最多 20 条），单块失败不影响其它块。
"""
import json
import os
import re
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
AI_CONFIG = os.path.join(HERE, "ai_config.json")

# 预设：base_url / model / 提示语
PRESETS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "hint": "deepseek.com 后台获取 API Key（注册送免费额度）",
        "label": "DeepSeek",
    },
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-1-6-250615",
        "hint": "火山方舟 Ark 获取 API Key 与推理接入点模型 ID",
        "label": "豆包 / 火山方舟",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "api_key": "ollama",
        "hint": "本地 Ollama，无需密钥；先执行 `ollama pull qwen2.5:7b`",
        "label": "本地 Ollama",
    },
    "custom": {
        "base_url": "",
        "model": "",
        "hint": "填你自己的 OpenAI 兼容端点（base_url + model + key）",
        "label": "自定义 / 套壳",
    },
    "mock": {
        "base_url": "",
        "model": "mock",
        "api_key": "mock",
        "hint": "演示模式：不调用真实接口，直接把候选第 1 名当作 AI 推荐",
        "label": "演示（无需密钥）",
    },
}

DEFAULT_CONFIG = {
    "provider": "deepseek",
    "enabled": False,
    "base_url": PRESETS["deepseek"]["base_url"],
    "api_key": "",
    "model": PRESETS["deepseek"]["model"],
}

# 占位符密钥（非真实密钥，切换 provider 时应被清除）
PLACEHOLDERS = {"mock", "ollama"}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(AI_CONFIG):
            with open(AI_CONFIG, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    cfg = {k: cfg.get(k, DEFAULT_CONFIG.get(k)) for k in DEFAULT_CONFIG}
    try:
        with open(AI_CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return cfg


def apply_preset(cfg, provider):
    p = PRESETS.get(provider)
    if not p:
        return cfg
    cfg["provider"] = provider
    if p.get("base_url"):
        cfg["base_url"] = p["base_url"]
    if p.get("model"):
        cfg["model"] = p["model"]
    if "api_key" in p:
        # mock -> "mock"，ollama -> "ollama"（占位符，无需真密钥）
        cfg["api_key"] = p["api_key"]
    else:
        # 需要真实密钥的 provider：若当前是占位符则清空，避免带着假 key 去联网
        if cfg.get("api_key") in PLACEHOLDERS:
            cfg["api_key"] = ""
    return cfg


def is_configured(cfg):
    """是否已具备调用条件（演示/mock 或 本地 ollama 视为已具备）。"""
    if cfg.get("provider") == "mock":
        return True
    if cfg.get("provider") == "ollama":
        return bool(cfg.get("base_url"))
    return bool(cfg.get("api_key"))


def _extract_json(text):
    if not text:
        return {}
    # 去掉 ```json ... ``` 代码围栏
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    # 先尝试整段直接解析
    try:
        return json.loads(t)
    except Exception:
        pass
    # 再退而求其次：抓最外层 {...}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


_SYSTEM = (
    "你是现场安全检查条目智能匹配助手。用户会提交若干条「手工检查记录」以及每条记录对应的"
    "「候选标准条目」（含编码 code、分类、短标题与描述，可能是一组较宽泛的标准条目）。"
    "请为每条记录判断最匹配的标准条目编码(code)；若候选都不匹配，则输出 null。"
    "注意用语义理解而非字面匹配：手工记录常是口语化描述（如「员工未问候客户」对应服务类"
    "「六步法/服务流程」标准、「未穿防静电服」对应 HSE/安全类标准），请依据条目描述的实际"
    "含义选择最贴切的一项。只输出 JSON，不要任何解释文字、不要 markdown 代码块。"
)

_USER_TMPL = (
    "请为下面每条记录选择最匹配候选的 code——只能从给定候选的 code 里选，确实都不匹配就给 null。\n"
    "严格只输出一个 JSON 对象：键为记录 id，值为 {{\"code\": \"<候选code或null>\", "
    "\"confidence\": <0到1的小数>, \"reason\": \"<15字内中文理由>\"}}。\n\n"
    "记录与候选：\n{records_json}"
)


def _build_messages(records):
    payload = []
    for r in records:
        payload.append({
            "id": r.get("id"),
            "text": r.get("text", ""),
            "candidates": [
                {
                    "code": c.get("code"),
                    "cat1": c.get("cat1"),
                    "cat2": c.get("cat2"),
                    "short": c.get("short"),
                    "desc": c.get("desc"),
                }
                for c in (r.get("candidates") or [])
            ],
        })
    user = _USER_TMPL.format(records_json=json.dumps(payload, ensure_ascii=False))
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]


def _call_llm(cfg, messages):
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = {
        "model": cfg.get("model") or "deepseek-chat",
        "messages": messages,
        "temperature": 0.0,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + (cfg.get("api_key") or ""),
    })
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            obj = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 模型不存在 / 鉴权失败 / 参数错误等：把状态码和响应体带回，方便前端定位
        snippet = ""
        try:
            body = e.read()
            if isinstance(body, bytes):
                snippet = body.decode("utf-8", "replace")
            else:
                snippet = str(body)
        except Exception:
            pass
        raise ValueError("HTTP %s：%s" % (e.code, snippet))
    except urllib.error.URLError as e:
        raise ValueError("网络错误：" + str(getattr(e, "reason", e))[:120])
    if not isinstance(obj, dict) or "choices" not in obj or not obj["choices"]:
        raise ValueError("响应格式异常：" + json.dumps(obj, ensure_ascii=False)[:200])
    return obj["choices"][0]["message"]["content"]


def match_records(cfg, records):
    """records: [{id, text, candidates:[{code,cat1,cat2,short,desc}]}]
    返回 {id(str): {code, confidence, reason}}
    """
    provider = cfg.get("provider")

    # 演示模式：直接取候选第 1 名，不联网
    if provider == "mock":
        out = {}
        for r in records:
            cands = r.get("candidates") or []
            if cands:
                out[str(r["id"])] = {
                    "code": cands[0].get("code"),
                    "confidence": 0.6,
                    "reason": "（演示）模拟推荐",
                }
            else:
                out[str(r["id"])] = {"code": None, "confidence": 0.0, "reason": "无候选"}
        return out

    # 准备真实调用
    work = dict(cfg)
    if provider == "ollama":
        if not work.get("api_key"):
            work["api_key"] = "ollama"
    else:
        if not work.get("api_key"):
            raise ValueError("未配置 API Key，请先在 ⚙️ AI 设置 中填写")

    out = {}
    CHUNK = 20
    for i in range(0, len(records), CHUNK):
        chunk = records[i:i + CHUNK]
        msgs = _build_messages(chunk)
        try:
            raw = _call_llm(work, msgs)
            parsed = _extract_json(raw)
        except urllib.error.HTTPError:
            raise   # 直接抛给上层，返回明确错误
        except urllib.error.URLError as e:
            msg = "网络错误：" + str(getattr(e, "reason", e))[:60]
            for r in chunk:
                out[str(r["id"])] = {"code": None, "confidence": 0.0, "reason": msg}
            continue
        except Exception as e:
            msg = "调用失败：" + str(e)[:120]
            for r in chunk:
                out[str(r["id"])] = {"code": None, "confidence": 0.0, "reason": msg}
            continue
        if not parsed:
            # 模型连通了但没返回可解析的 JSON（如空响应、纯文本、"null" 字符串）：
            # 把模型原文带出来，方便判断是模型名不对还是该模型不遵循 JSON 输出
            snippet = (raw or "").strip().replace("\n", " ")[:140]
            for r in chunk:
                out[str(r["id"])] = {"code": None, "confidence": 0.0, "reason": "模型未返回可解析JSON：" + snippet}
            continue
        for r in chunk:
            rid = str(r["id"])
            item = parsed.get(rid) or {}
            if not isinstance(item, dict):
                item = {}
            out[rid] = {
                "code": item.get("code"),
                "confidence": item.get("confidence", 0.5),
                "reason": item.get("reason", ""),
            }
    return out


if __name__ == "__main__":
    # 简单自检
    cfg = apply_preset(load_config(), "mock")
    demo = [{
        "id": "rec1",
        "text": "卸油区静电释放器接地线断裂",
        "candidates": [
            {"code": "A01", "cat1": "设备", "cat2": "防静电", "short": "静电释放器完好", "desc": "静电接地线应完好连接"},
            {"code": "B02", "cat1": "消防", "cat2": "灭火器", "short": "灭火器压力正常", "desc": "压力表在绿区"},
        ],
    }]
    print(json.dumps(match_records(cfg, demo), ensure_ascii=False, indent=2))
