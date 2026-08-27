#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用模块测试：登录→打开模块→设日期→查询→导出→记录（随 sinopec-system-scrape skill 分发）
用法: python test_module.py <URL关键字> <开始日期> <结束日期> [输出目录]
示例: python test_module.py ckd 2026-08-01 2026-08-18
常用 URL 关键字：jhys(进货验收) ckd(出库单) manualContrast(液位比对) stockHour(时点库存)
                  bfJhysStatus(进油验收状态同步) tostatis(进货损耗区间) salesgl(油站日平衡,按单日查)
"""
import asyncio, json, os, sys, re
from playwright.async_api import async_playwright

# ---- 账号配置（按需修改） ----
BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "lvch36"
PASSWORD = "cc336699."

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

KW = sys.argv[1]
START = sys.argv[2] if len(sys.argv) > 2 else "2026-08-01"
END = sys.argv[3] if len(sys.argv) > 3 else "2026-08-18"
OUT = sys.argv[4] if len(sys.argv) > 4 else "output"
os.makedirs(OUT, exist_ok=True)

result = {"module": KW, "start": START, "end": END}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge", headless=True,
            args=["--ignore-certificate-errors",
                  "--disable-features=InsecureFormWarnings",
                  "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"],
        )
        ctx = await browser.new_context(user_agent=UA, ignore_https_errors=True,
                                        viewport={"width": 1600, "height": 900}, locale="zh-CN",
                                        accept_downloads=True)
        page = await ctx.new_page()

        # 捕获数据查询请求
        async def on_request(req):
            if ".do" in req.url and ("select" in req.url.lower() or "list" in req.url.lower()):
                result.setdefault("api_requests", []).append(
                    {"method": req.method, "url": req.url[:200],
                     "post": (req.post_data[:400] if req.post_data else "")})
        page.on("request", on_request)

        # ---- 登录 ----
        try:
            await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector('input[name="j_username"]', timeout=60000)
            await page.fill('input[name="j_username"]', USERNAME)
            await page.fill('input[name="j_password"]', PASSWORD)
            await page.click('button[type="submit"]')
            await page.wait_for_timeout(6000)
            result["login"] = "OK"
        except Exception as e:
            result["login"] = f"FAIL:{e}"
            print(json.dumps(result, ensure_ascii=False)); return

        # ---- 打开模块 ----
        try:
            await page.click(f'a[onclick*="{KW}"]', timeout=15000)
            result["menu_click"] = "OK"
        except Exception as e:
            result["menu_click"] = f"FAIL:{e}"
            print(json.dumps(result, ensure_ascii=False)); return

        frame = None
        for i in range(20):
            await page.wait_for_timeout(1000)
            for f in page.frames:
                if KW in f.url and "index.jsp" not in f.url:
                    frame = f; break
            if frame: break
        if not frame:
            result["iframe"] = "NOT_FOUND"
            print(json.dumps(result, ensure_ascii=False)); return
        result["iframe_url"] = frame.url[:200]
        await page.wait_for_timeout(4000)

        # ---- 分析控件 ----
        try:
            ids = await frame.evaluate("""() => {
                const r = {inputs: [], buttons: []};
                document.querySelectorAll('input[id],select[id]').forEach(e => {
                    if (e.id && !e.id.startsWith('_easyui')) r.inputs.push(e.id);
                });
                document.querySelectorAll('a,button').forEach(e => {
                    const t=(e.innerText||'').trim();
                    const oc=e.getAttribute('onclick')||'';
                    if (t || oc) r.buttons.push({t:t.slice(0,14), oc:oc.slice(0,90)});
                });
                return r;
            }""")
            result["inputs"] = ids["inputs"]
            result["buttons"] = ids["buttons"]
        except Exception as e:
            result["analyze"] = f"FAIL:{e}"

        # ---- 设日期（easyui datebox/datetimebox） ----
        date_ok = False
        try:
            # 先探测控件类型
            ctype = await frame.evaluate("""() => {
                const s = document.querySelector('#startTime');
                if (!s) return null;
                const cls = s.className||'';
                if (cls.includes('datetimebox')) return 'datetimebox';
                if (cls.includes('datebox')) return 'datebox';
                return 'plain';
            }""")
            if ctype == "datetimebox":
                await frame.evaluate(f"$('#startTime').datetimebox('setValue','{START} 08:00:00')")
                if await frame.evaluate("() => !!document.querySelector('#endTime')"):
                    await frame.evaluate(f"$('#endTime').datetimebox('setValue','{END} 08:00:00')")
                result["dates"] = f"{START} ~ {END} (datetimebox)"
                date_ok = True
            elif ctype == "datebox":
                await frame.evaluate(f"$('#startTime').datebox('setValue','{START}')")
                await frame.evaluate(f"$('#endTime').datebox('setValue','{END}')")
                v1 = await frame.evaluate("$('#startTime').datebox('getValue')")
                v2 = await frame.evaluate("$('#endTime').datebox('getValue')")
                result["dates"] = f"{v1} ~ {v2}"
                date_ok = True
            elif ctype == "plain":
                await frame.fill('#startTime', START)
                await frame.fill('#endTime', END)
                result["dates"] = f"{START} ~ {END} (直接fill)"
                date_ok = True
        except Exception as e:
            result["dates"] = f"NO_DATE_FIELD:{str(e)[:80]}"
        if not date_ok:
            result["has_date_filter"] = False

        # ---- 触发查询 ----
        try:
            fn = await frame.evaluate("""() => {
                const els = [...document.querySelectorAll('a,button,input[type=button]')];
                const btn = els.find(e => ((e.innerText||e.value||'')).includes('查询') && !((e.innerText||'')).includes('更多'));
                if (btn) return {fn: btn.getAttribute('onclick')||btn.getAttribute('onClick')||'click', tag: btn.tagName, txt:(btn.innerText||'').slice(0,10)};
                return null;
            }""")
            if fn:
                onclick = fn.get("fn", "")
                m = re.search(r'([a-zA-Z_]\w*)\s*\(', onclick)
                if onclick and m:
                    await frame.evaluate(f"{m.group(1)}()")
                    result["query_trigger"] = f"fn:{m.group(1)}()"
                elif onclick == "click":
                    await frame.click('a:has-text("查询")')
                    result["query_trigger"] = "click"
            else:
                result["query_trigger"] = "NO_QUERY_BUTTON"
        except Exception as e:
            result["query_trigger"] = f"FAIL:{e}"
        await page.wait_for_timeout(8000)

        # ---- 分页信息（记录数） ----
        try:
            info = await frame.inner_text(".datagrid-pager.pagination")
            result["pagination"] = re.sub(r"\s+", " ", info).strip()[:160]
        except Exception:
            try:
                info = await frame.inner_text("body")
                result["pagination"] = "no .datagrid-pager"
            except Exception:
                result["pagination"] = "?"

        # ---- 导出 ----
        try:
            exp_sel = await frame.evaluate("""() => {
                if (document.querySelector('#expExcel')) return '#expExcel';
                const el = [...document.querySelectorAll('a,button')].find(e => (e.innerText||'').includes('导出Excel'));
                return el ? 'TEXT' : null;
            }""")
            if exp_sel == "#expExcel":
                async with page.expect_download(timeout=45000) as dl_info:
                    await frame.click('#expExcel', timeout=10000)
                dl = await dl_info.value
                fname = os.path.join(OUT, dl.suggested_filename)
                await dl.save_as(fname)
                result["export"] = f"OK:{dl.suggested_filename} ({os.path.getsize(fname)}B)"
            elif exp_sel == "TEXT":
                async with page.expect_download(timeout=45000) as dl_info:
                    await frame.evaluate("""() => {
                        const el = [...document.querySelectorAll('a,button')].find(e => (e.innerText||'').includes('导出Excel'));
                        el.click();
                    }""")
                dl = await dl_info.value
                fname = os.path.join(OUT, dl.suggested_filename)
                await dl.save_as(fname)
                result["export"] = f"OK(text):{dl.suggested_filename} ({os.path.getsize(fname)}B)"
            else:
                result["export"] = "NO_EXPORT_BUTTON"
        except Exception as e:
            result["export"] = f"FAIL:{str(e)[:120]}"

        # ---- 汇总 ----
        # 去掉超长字段便于展示
        summary = {k: v for k, v in result.items() if k != "api_requests"}
        print(json.dumps(summary, ensure_ascii=False))
        with open(f"{OUT}/result_{KW}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        await browser.close()

asyncio.run(main())
