# -*- coding: utf-8 -*-
"""清洗数据：提取每条单据的最新/核心拒绝意见，按场景分类"""
import json, io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

d = json.load(open('D:/workbuddy/报销/审批拒绝_详情v2.json', encoding='utf-8'))

# 补差旅单数据（第一轮抓到的）
travel = None
try:
    d1 = json.load(open('D:/workbuddy/报销/审批拒绝_详情.json', encoding='utf-8'))
    for r in d1:
        if r['billCode'] == 'BX-X420202605003832':
            travel = r
            break
except: pass

def extract_rejections(history):
    """从历史行中提取所有'拒绝'节点 + 意见"""
    rejects = []
    for h in history:
        if len(h) < 5: continue
        # 找审批结果列（倒数第3）
        result = h[-3] if len(h) >= 3 else ''
        opinion = h[-2] if len(h) >= 2 else ''
        step = h[1] if len(h) > 1 else ''
        person = h[2] if len(h) > 2 else ''
        time = h[-1] if len(h) >= 1 else ''
        # 只保留真正的拒绝（审批结果含拒绝，或意见含退回/拒绝且步骤含'共享初审'或'审核'）
        is_reject = ('拒绝' in result) or ('拒绝' in opinion and ('初审' in step or '审核' in step))
        if is_reject and opinion and '请输入' not in opinion and len(opinion) > 2:
            rejects.append({
                'step': step.strip(),
                'person': person.strip(),
                'result': result.strip(),
                'opinion': opinion.strip(),
                'time': time.strip()
            })
    return rejects

results = []
for r in d:
    code = r['billCode']
    rejects = extract_rejections(r.get('history') or [])
    results.append({
        'billCode': code,
        'sceneName': r.get('sceneName'),
        'applyDate': r.get('applyDate'),
        'billAmount': r.get('billAmount'),
        'remark': r.get('remark'),
        'rejects': rejects,
        'error': r.get('error')
    })

# 差旅单合并
if travel:
    for res in results:
        if res['billCode'] == 'BX-X420202605003832':
            res['rejects'] = extract_rejections(travel.get('approveHistory') or [])
            res['error'] = None

# 统计
print(f"共 {len(results)} 条单据")
n_with = sum(1 for r in results if r['rejects'])
print(f"有拒绝意见的: {n_with} 条")

with open('D:/workbuddy/报销/拒绝意见_清洗.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=1)

# 打印摘要
for r in results:
    print(f"\n=== {r['billCode']} | {r['sceneName']} | {r['billAmount']}元 | {r['applyDate']}")
    if r['rejects']:
        last = r['rejects'][-1]
        print(f"  最新拒绝: [{last['step']}] {last['person']}: {last['opinion'][:120]}")
    elif r['error']:
        print(f"  ⚠ {r['error']}")
    else:
        print("  (无拒绝意见)")
print("\nsaved 拒绝意见_清洗.json")
