# -*- coding: utf-8 -*-
"""抓取我的单据全量 + 待提交列表（精确字段）
用法：
  python fetch_bills.py                          # 用环境变量 FSS_LOGIN/FSS_EMP 或默认值
  FSS_LOGIN=lvch36.husy FSS_EMP=01219164 python fetch_bills.py
  FSS_STATE=D:/path/fss_state.json python fetch_bills.py   # 自定义会话文件
输出：D:/workbuddy/报销/我的单据_全量.json
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

LOGINNAME = os.environ.get('FSS_LOGIN', 'lvch36.husy')
EMPCODE = os.environ.get('FSS_EMP', '01219164')
STATE = os.environ.get('FSS_STATE', 'D:/workbuddy/报销/fss_state.json')
OUT = os.environ.get('FSS_OUT', 'D:/workbuddy/报销/我的单据_全量.json')

def mkbody(bt, bs='', ps=500, pg=1):
    return {
        "loginname": LOGINNAME, "empCode": EMPCODE, "sceneCode": "",
        "compCode": "", "billType": str(bt), "startTime": "20260101#20261231",
        "billCode": "", "reiEmpName": "", "remark": "", "billStatus": bs,
        "pageSize": ps, "currentPage": pg, "quotaType": "", "billTypeCode": "",
        "fromBillAmount": "", "toBillAmount": "", "billState": "", "contractNum": "",
        "suppCode": "", "suppName": "", "selArchive": "", "isReplace": ""
    }

def call(pg, url, body):
    resp = pg.evaluate("""async ({url, body}) => {
        const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
        return {status: r.status, text: await r.text()};
    }""", {"url": url, "body": body})
    try:
        outer = json.loads(resp['text'])
        inner = json.loads(outer['data']) if isinstance(outer.get('data'), str) else outer.get('data')
        return inner
    except Exception as e:
        return {"__err": resp['text'][:200]}

with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=True)
    ctx = b.new_context(ignore_https_errors=True, storage_state=STATE)
    pg = ctx.new_page()
    pg.goto('https://fss.sinopec.com/fssue/#/home', timeout=60000)
    pg.wait_for_timeout(6000)

    # 1. 探测 billType 1-10 × billStatus '' 的状态分布
    results = {}
    for bt in ['1','2','3','4','5','6','7','8','9','10']:
        inner = call(pg, 'https://fss.sinopec.com/fssueservice/ers/bill/list', mkbody(bt))
        if inner and isinstance(inner, dict) and inner.get('data') and isinstance(inner['data'], dict):
            rl = inner['data'].get('resultList') or []
            total = inner['data'].get('listTotal', len(rl))
            st = {}
            for r in rl:
                s = r.get('applyStatus', '?')
                st[s] = st.get(s, 0) + 1
            print(f"billType={bt} total={total} 状态={st}")
            results[f'bt{bt}'] = {'total': total, 'rows': rl}
        else:
            print(f"billType={bt} → {str(inner)[:100]}")

    # 2. 探测 billStatus 各值（用 bt=1）
    print("\n== billStatus 枚举探测 ==")
    for bs in ['', '1','2','3','4','5','6','7','8','9']:
        inner = call(pg, 'https://fss.sinopec.com/fssueservice/ers/bill/list', mkbody('1', bs))
        if inner and isinstance(inner, dict) and inner.get('data') and isinstance(inner['data'], dict):
            rl = inner['data'].get('resultList') or []
            print(f"billStatus={bs or '(空)'} → {len(rl)} 条, 样例状态: {[r.get('applyStatus') for r in rl[:3]]}")

    with open('D:/workbuddy/报销/我的单据_全量.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("\nsaved 我的单据_全量.json")
    b.close()
