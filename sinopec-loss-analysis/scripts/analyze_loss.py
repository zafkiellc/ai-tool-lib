#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中石化加油站进油验收与损耗综合分析脚本
=========================================
输入：
  --files  用 "标签:路径" 逗号分隔传入文件，标签取值：
             check_7m | check_8m | check_* : 进油验收报表 .xls（可传多个月）
             rank_7m  | rank_8m  | rank_*  : 损耗排名 .xlsx（可传多个月）
  --weather （可选）Open-Meteo 天气 JSON 文件路径；不传则自动联网获取
  --lat --lon （可选）站点经纬度，默认武汉(30.59,114.30)
  --out     （可选）输出统计 JSON 路径

输出：
  控制台打印关键统计 + 可选 JSON：
   - 按站点：汽油/柴油损耗率、验收温度、温差、损溢率Vt
   - 按油品：温度与损溢
   - 卸油时段×天气交叉
   - 罐位相关性
   - 排名后五站点

依赖：xlrd>=2.0（读.xls）、openpyxl（读.xlsx）、urllib（天气）
安装：pip install -i https://pypi.tuna.tsinghua.edu.cn/simple xlrd openpyxl
      （用户网络直连 pypi 会超时，须用清华镜像；本地网络受限 WinError 10054 时
       用 WebFetch 抓 Open-Meteo JSON 落盘后 --weather 传入）

重要口径陷阱：
  1) 验收报表表头行不固定：7月文件表头在「第2行(0索引=1)」，8月文件表头在「第1行(0索引=0)」。
     本脚本自动扫描前 4 行定位表头，无需手工指定。
  2) 油品列名不一致：7月=「油品」，8月=「油品名称」。统一用子串「油品」匹配。
  3) 未满月报表严禁直接比损耗量绝对值，须用损耗率(‰)/日均。
"""
import argparse, json, os, re, sys
from collections import defaultdict

# ---------- 通用工具 ----------
def f(v):
    try:
        x = float(v)
        return x if x == x else None  # NaN 过滤
    except (TypeError, ValueError):
        return None

def find_col(hdr, *cands):
    """在表头列表中按子串匹配返回第一个命中的列索引；多个候选取最优先。"""
    for cand in cands:
        for i, h in enumerate(hdr):
            if cand in str(h):
                return i
    return None

def detect_header_row(sh):
    """扫描前 min(5,nrows) 行，返回含关键字段最多的行号（表头行）。"""
    keys = ['油品', '实发温度', '验收时间', '损溢率Vt']
    best, best_row = -1, 0
    for r in range(min(5, sh.nrows)):
        score = 0
        for c in range(sh.ncols):
            cell = str(sh.cell_value(r, c))
            if any(k in cell for k in keys):
                score += 1
        if score > best:
            best, best_row = score, r
    return best_row

def load_xls(path):
    """读取进油验收报表 .xls，返回归一化字典列表。
    归一化键：oil, shicol(实发温度), qiantemp(卸前油温), houtemp(卸后油温),
              pr(损溢率‰ 非Vt), vt(损溢率Vt‰), qiansheng(卸前升数L),
              housheng(卸后升数L), qiangao(卸前油高mm), time(验收时间)"""
    import xlrd
    wb = xlrd.open_workbook(path)
    sh = wb.sheet_by_index(0)
    hrow = detect_header_row(sh)
    hdr = [str(sh.cell_value(hrow, c)).strip() for c in range(sh.ncols)]
    col = {
        'oil':     find_col(hdr, '油品名称', '油品'),
        'shicol':  find_col(hdr, '实发温度'),
        'qiantemp':find_col(hdr, '卸前油温'),
        'houtemp': find_col(hdr, '卸后油温'),
        'vt':      find_col(hdr, '损溢率Vt'),
        'pr':      find_col(hdr, '损溢率'),
        'qiansheng':find_col(hdr, '卸前升数'),
        'housheng':find_col(hdr, '卸后升数'),
        'qiangao': find_col(hdr, '卸前油高'),
        'time':    find_col(hdr, '验收时间'),
    }
    # pr 须排除 Vt 列（两者都含「损溢率」），取不含 Vt 的那个
    if col['pr'] is not None and col['vt'] is not None and col['pr'] == col['vt']:
        col['pr'] = None
    if col['pr'] is None:  # 回退：含「损溢率」且含「‰」不含「Vt」
        for i, h in enumerate(hdr):
            if '损溢率' in h and 'Vt' not in h:
                col['pr'] = i; break
    rows = []
    for r in range(hrow + 1, sh.nrows):
        rec = {}
        for k, ci in col.items():
            rec[k] = sh.cell_value(r, ci) if ci is not None else None
        rows.append(rec)
    return rows, hrow

def load_rank_dq(path):
    """读取损耗排名 xlsx 的『当期数据』sheet，返回 [(站,油品,销售,损耗)]"""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["当期数据"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    hdr = [str(h).strip() if h else "" for h in rows[0]]
    i_st   = find_col(hdr, '油站')
    i_oil  = find_col(hdr, '油品名称', '油品')
    i_sale = find_col(hdr, '总计')
    i_loss = find_col(hdr, '当期损耗')
    out = []
    for r in rows[1:]:
        if i_oil is None or i_st is None or r[i_oil] is None or r[i_st] is None:
            continue
        out.append((str(r[i_st]), str(r[i_oil]), f(r[i_sale]) or 0, f(r[i_loss]) or 0))
    return out

def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float('nan')
    mx, my = sum(xs)/n, sum(ys)/n
    cov = sum((x-mx)*(y-my) for x, y in zip(xs, ys))/n
    sx = (sum((x-mx)**2 for x in xs)/n) ** 0.5
    sy = (sum((y-my)**2 for y in ys)/n) ** 0.5
    return cov/(sx*sy) if sx*sy else 0

def get_weather(lat, lon, start, end, out_path=None):
    """Open-Meteo 历史天气；优先读本地 JSON，否则联网获取"""
    if out_path and os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as fp:
            return json.load(fp)["daily"]
    url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
           f"&start_date={start}&end_date={end}"
           f"&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
           f"precipitation_sum,relative_humidity_2m_mean,weather_code&timezone=Asia%2FShanghai")
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False)
    return data["daily"]

def stname(s):
    m = re.search(r'武汉汉阳\S*?加油站', str(s))
    return m.group(0) if m else str(s)

def analyze(check_months, rank_months, weather=None, lat=30.59, lon=114.30, out=None):
    result = {}
    # ---- 排名表：汽油/柴油拆分 ----
    for label, path in rank_months.items():
        rows = load_rank_dq(path)
        gas_l = die_l = gas_s = die_s = 0
        by_st = defaultdict(lambda: [0, 0])
        for st, oil, sale, loss in rows:
            if '汽油' in oil:
                gas_l += loss; gas_s += sale; by_st[st][0] += loss; by_st[st][1] += sale
            elif '柴油' in oil:
                die_l += loss; die_s += sale
        g_rate = gas_l/gas_s*1000 if gas_s else 0
        d_rate = die_l/die_s*1000 if die_s else 0
        full_rate = (gas_l+die_l)/(gas_s+die_s)*1000 if gas_s+die_s else 0
        ranked = sorted(by_st.items(), key=lambda kv: (kv[1][0]/kv[1][1]*1000 if kv[1][1] else 0), reverse=True)
        print(f"\n===== {label} 排名表(当期数据) =====")
        print(f"  汽油: 销售{gas_s:,.0f}L 损耗{gas_l:,.1f}L 率{g_rate:.3f}‰")
        print(f"  柴油(单列): 销售{die_s:,.0f}L 损耗{die_l:,.1f}L 率{d_rate:.3f}‰")
        print(f"  全品: 率{full_rate:.3f}‰  (注: 柴油盘盈稀释汽油真实损耗)")
        print(f"  汽油口径站点排名(损耗率降序, 取前10):")
        for i, (st, (l, s)) in enumerate(ranked[:10], 1):
            print(f"    {i:>2}. {st[:26]:<28} 率{l/s*1000 if s else 0:>7.2f}‰ 损耗{l:>9,.1f}L 销售{s:>10,.0f}L")
        result[label] = dict(gas_rate=g_rate, die_rate=d_rate, full_rate=full_rate,
                             gas_sale=gas_s, gas_loss=gas_l, die_sale=die_s, die_loss=die_l,
                             top_stations=[{"st": st[:30], "rate": l/s*1000 if s else 0, "loss": l}
                                           for st, (l, s) in ranked[:10]])

    # ---- 验收报表：温度/温差/损溢 ----
    for label, path in check_months.items():
        rows, hrow = load_xls(path)
        gas = [d for d in rows if d['oil'] and '汽油' in str(d['oil'])]
        print(f"\n===== {label} 进油验收(表头行={hrow}, 汽油{len(gas)}车/总{len(rows)}车) =====")
        def m(k):
            v = [f(d.get(k)) for d in gas if f(d.get(k)) is not None]
            return sum(v)/len(v) if v else float('nan')
        dt = [f(d['qiantemp'])-f(d['shicol']) for d in gas
              if f(d['qiantemp']) is not None and f(d['shicol']) is not None]
        print(f"  实发温={m('shicol'):.2f}°C 卸前温={m('qiantemp'):.2f}°C 卸后温={m('houtemp'):.2f}°C")
        print(f"  温差(卸前-实发)={sum(dt)/len(dt) if dt else float('nan'):.2f}°C")
        print(f"  损溢率(非Vt)={m('pr'):.2f}‰ 损溢率Vt={m('vt'):.2f}‰")
        # 温差 vs Vt 相关性
        pairs = [(f(d['qiantemp'])-f(d['shicol']), f(d['vt'])) for d in gas
                 if f(d['qiantemp']) is not None and f(d['shicol']) is not None and f(d['vt']) is not None]
        if len(pairs) > 3:
            print(f"  温差 vs 损溢率Vt 相关系数 r={pearson([p[0] for p in pairs], [p[1] for p in pairs]):.3f}")
        # 卸油时段
        by_slot = defaultdict(list)
        for d in gas:
            hh = re.search(r'(\d{1,2}):', str(d['time']))
            if not hh: continue
            hr = int(hh.group(1)); vt = f(d['vt'])
            if vt is None: continue
            slot = '凌晨(0-6)' if hr < 6 else ('上午(6-12)' if hr < 12 else ('午后(12-18)' if hr < 18 else '夜间(18-24)'))
            by_slot[slot].append(vt)
        print("  卸油时段 vs 损溢率Vt:")
        for k in ['凌晨(0-6)', '上午(6-12)', '午后(12-18)', '夜间(18-24)']:
            vs = by_slot.get(k, [])
            if vs:
                print(f"    {k}: n={len(vs)} Vt={sum(vs)/len(vs):.2f}‰")
        # 罐位相关性
        for col, name in [('qiansheng', '卸前存量'), ('housheng', '卸后存量'), ('qiangao', '卸前油高')]:
            pp = [(f(d[col]), f(d['vt'])) for d in gas
                  if f(d[col]) is not None and f(d['vt']) is not None]
            if len(pp) > 3:
                print(f"  {name} vs 损溢率Vt: r={pearson([p[0] for p in pp], [p[1] for p in pp]):.3f}")

    # ---- 天气 × 卸油时段（最近一个验收月） ----
    if check_months:
        last_label, last_path = list(check_months.items())[-1]
        rows, _ = load_xls(last_path)
        rows = [d for d in rows if d['oil'] and '汽油' in str(d['oil'])]
        dates = sorted(set(str(d['time'])[:10] for d in rows if d['time']))
        if dates:
            try:
                wx = get_weather(lat, lon, dates[0], dates[-1], weather)
            except Exception as e:  # 联网受限时优雅降级：提示用 --weather 本地JSON
                print(f"\n[跳过] {last_label} 天气×卸油时段：联网获取 Open-Meteo 失败（{type(e).__name__}）。"
                      f"\n        请用 WebFetch 抓取天气 JSON 后加 --weather 路径重跑，其余分析不受影响。")
            else:
                wxmap = {d: dict(tmax=wx["temperature_2m_max"][i], prec=wx["precipitation_sum"][i])
                         for i, d in enumerate(wx["time"])}
                hot_days = sum(1 for d in dates if wxmap.get(d, {}).get('tmax', 0) >= 35)
                print(f"\n===== {last_label} 天气×卸油时段（{len(dates)}个作业日，高温≥35°C共{hot_days}天） =====")
                cross = defaultdict(list)
                for d in rows:
                    dt = str(d['time'])[:10]; vt = f(d['vt'])
                    hh = re.search(r'(\d{1,2}):', str(d['time']))
                    if vt is None or not hh or dt not in wxmap: continue
                    hr = int(hh.group(1))
                    slot = '凌晨' if hr < 6 else ('上午' if hr < 12 else ('午后' if hr < 18 else '夜间'))
                    hot = wxmap[dt]['tmax'] >= 35
                    cross[(hot, slot)].append(vt)
                for hot in (True, False):
                    for sl in ['凌晨', '上午', '午后', '夜间']:
                        vs = cross.get((hot, sl), [])
                        if vs:
                            print(f"    {'高温≥35°C' if hot else '非高温'} × {sl}: n={len(vs)} Vt={sum(vs)/len(vs):.2f}‰")
    if out:
        with open(out, "w", encoding="utf-8") as fp:
            json.dump(result, fp, ensure_ascii=False, indent=1)
        print(f"\n统计JSON已写入: {out}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", required=True,
                    help="标签:路径 逗号分隔。标签: check_*(验收xls) / rank_*(排名xlsx)")
    ap.add_argument("--weather", default=None, help="天气JSON路径(可选)")
    ap.add_argument("--lat", type=float, default=30.59)
    ap.add_argument("--lon", type=float, default=114.30)
    ap.add_argument("--out", default=None, help="输出统计JSON路径(可选)")
    args = ap.parse_args()
    check_months, rank_months = {}, {}
    for item in args.files.split(","):
        label, path = item.split(":", 1)
        path = path.strip()
        if not os.path.exists(path):
            print(f"警告: 文件不存在 {path}")
            continue
        if label.startswith("check"): check_months[label] = path
        elif label.startswith("rank"): rank_months[label] = path
    analyze(check_months, rank_months, weather=args.weather, lat=args.lat, lon=args.lon, out=args.out)

if __name__ == "__main__":
    main()
