# -*- coding: utf-8 -*-
"""最终版：遍历 33 条审批拒绝单据，从详情页 iframe 抓审批历史"""
import sys, io, json, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright

REJECTED = []
with open('D:/workbuddy/报销/我的单据_全量.json', encoding='utf-8') as f:
    d = json.load(f)
for r in d['bt2']['rows']:
    if r.get('applyStatus') == '审批拒绝':
        REJECTED.append(r)
print(f"共 {len(REJECTED)} 条拒绝单据")

with sync_playwright() as p:
    b = p.chromium.launch(channel='msedge', headless=True)
    ctx = b.new_context(ignore_https_errors=True, storage_state='D:/workbuddy/报销/fss_state.json')
    pg = ctx.new_page()
    pg.set_extra_http_headers({'Referer': 'https://fss.sinopec.com/fss/index.action'})
    pg.goto('https://fss.sinopec.com/fss/index.action', timeout=60000)
    pg.wait_for_timeout(4000)

    all_details = []
    for i, r in enumerate(REJECTED):
        code = r['billCode']
        url = r.get('detailsUrl', '')
        print(f"\n[{i+1}/{len(REJECTED)}] {code}")
        rec = {
            'billCode': code, 'sceneName': r.get('sceneName'), 'applyDate': r.get('applyDate'),
            'billAmount': r.get('billAmount'), 'remark': r.get('remark'),
            'history': [], 'error': None
        }
        try:
            pg.goto(url, timeout=45000)
            pg.wait_for_timeout(3500)
            # 找 iframe
            frames = pg.frames
            target = None
            for f in frames:
                if 'scene' in f.url and 'jquery' in f.url:
                    target = f
                    break
            if target is None:
                # 兜底：任意非主 frame
                for f in frames:
                    if f != pg.main_frame:
                        target = f
                        break
            if target is None:
                rec['error'] = '无iframe'
                print("   ❌ 无iframe")
            else:
                try:
                    t = target.content()
                except Exception:
                    t = ''
                if '审批及操作记录' not in t:
                    rec['error'] = 'iframe无审批记录'
                    print("   ❌ iframe无审批记录")
                else:
                    # 提取"全流程"表格（含审批结果/意见/时间）
                    # 用正则抓审批行：执行步骤/人员/组织/操作/结果/意见/时间
                    rows = re.findall(r'<tr[^>]*data-index="(\d+)"[^>]*>([\s\S]*?)</tr>', t)
                    history = []
                    for idx, tr in rows:
                        cells = re.findall(r'<td[^>]*>([\s\S]*?)</td>', tr)
                        cells = [re.sub(r'<[^>]+>', '', c).strip().replace('\u00a0','').replace('&amp;','&') for c in cells]
                        cells = [re.sub(r'\s+', ' ', c).strip() for c in cells]
                        if cells:
                            history.append(cells)
                    # 若 data-index 抓不到，退化为按列提取
                    if not history:
                        trs = re.findall(r'<tr[^>]*>([\s\S]*?)</tr>', t)
                        for tr in trs:
                            if '审批时间' in tr or '执行步骤' in tr:
                                continue
                            cells = re.findall(r'<td[^>]*>([\s\S]*?)</td>', tr)
                            cells = [re.sub(r'<[^>]+>', '', c).strip().replace('\u00a0','').replace('&amp;','&') for c in cells]
                            cells = [re.sub(r'\s+', ' ', c).strip() for c in cells]
                            if len(cells) >= 5:
                                history.append(cells)
                    rec['history'] = history
                    # 打印拒绝行
                    for h in history:
                        hs = ' | '.join(h)
                        if any(k in hs for k in ['拒绝', '退回', '缺失', '不同意']):
                            print("   →", hs[:220])
                    print(f"   ✓ 历史行数: {len(history)}")
        except Exception as e:
            rec['error'] = str(e)[:120]
            print(f"   ❌ {str(e)[:120]}")
        all_details.append(rec)
        time.sleep(0.6)

    with open('D:/workbuddy/报销/审批拒绝_详情v2.json', 'w', encoding='utf-8') as f:
        json.dump(all_details, f, ensure_ascii=False, indent=1)
    print("\n✅ saved 审批拒绝_详情v2.json")
    b.close()
