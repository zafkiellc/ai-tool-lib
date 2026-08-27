# -*- coding: utf-8 -*-
"""爬取汉阳所有站点罐号->品种对应表(getBfTank.do)
用法: python fetch_hanyang_tanks.py <输出csv>
"""
import asyncio, os, sys, csv
from playwright.async_api import async_playwright

BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "xiaoy1206"
PASSWORD = os.environ.get("YWY_PWD", "Yao1206022")
PICK_ACCOUNT = "xiaoy1206"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
LAUNCH_ARGS = ["--ignore-certificate-errors", "--disable-features=InsecureFormWarnings",
               "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"]
OUT = "C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output/hanyang_tanks.csv"


async def main():
    out = sys.argv[1] if len(sys.argv) > 1 else OUT
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True, args=LAUNCH_ARGS)
        ctx = await browser.new_context(user_agent=UA, ignore_https_errors=True,
                                        viewport={"width": 1600, "height": 900})
        page = await ctx.new_page()
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector('input[name="j_username"]', timeout=30000)
        await page.fill('input[name="j_username"]', USERNAME)
        await page.fill('input[name="j_password"]', PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(5000)
        if "login.jsp" in page.url:
            for b in await page.query_selector_all("button, input[type='button'], input[type='submit'], a"):
                t = (await b.text_content() or "").strip() or (await b.get_attribute("value") or "")
                if t.strip() == PICK_ACCOUNT:
                    await b.click()
                    break
            await page.wait_for_timeout(6000)
        print("登录:", await page.title())

        await page.evaluate("addTab('历史液位曲线分析','sh/stock/dayrealStock.jsp','7166','7254',true)")
        await page.wait_for_timeout(2500)
        frame = None
        for _ in range(20):
            await page.wait_for_timeout(800)
            for f in page.frames:
                if "dayrealStock" in f.url:
                    frame = f
                    break
            if frame:
                break
        if not frame:
            print("未找到模块")
            await browser.close()
            return

        # 加载汉阳站点
        stations = await frame.evaluate("""() => {
            return new Promise((resolve) => {
                $.ajax({url:'/station/selectYZ.do', method:'post', data:{deptCode:'3400HUA06101'}, dataType:'json',
                    success:function(d){resolve(d.map(x=>({code:x.stationCode, name:x.stationName})));},
                    error:function(){resolve([]);}});
            });
        }""")
        print("汉阳站点数:", len(stations))

        rows = []
        for st in stations:
            code = st["code"]
            if code == "-1":
                continue
            # 调 getBfTank.do 拿油罐
            tanks = await frame.evaluate("(a) => { return new Promise((r) => { $.ajax({url:'/sh/stock/getBfTank.do?stationCode='+a.code, method:'get', dataType:'json', success:function(d){r(d.map(x=>({id:x.id, text:x.text})));}, error:function(){r([]);}}); }); }", {"code": code})
            for tk in tanks:
                rows.append({"station_code": code, "station_name": st["name"], "tank_id": tk["id"], "tank_no": tk["text"]})
            print("  %s %s: %d罐" % (code, st["name"][-10:], len(tanks)))

        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["station_code", "station_name", "tank_id", "tank_no"])
            w.writeheader()
            w.writerows(rows)
        print("已保存:", out, len(rows), "条")
        await browser.close()


asyncio.run(main())
