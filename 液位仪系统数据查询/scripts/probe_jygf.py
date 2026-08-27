# -*- coding: utf-8 -*-
"""探索油站加油高峰期分析模块(report/jygfCharts.do)结构"""
import asyncio, os
from playwright.async_api import async_playwright

BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "xiaoy1206"
PASSWORD = os.environ.get("YWY_PWD", "Yao1206022")
PICK_ACCOUNT = "xiaoy1206"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
LAUNCH_ARGS = ["--ignore-certificate-errors", "--disable-features=InsecureFormWarnings",
               "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"]
OUT = "C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output/"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True, args=LAUNCH_ARGS)
        ctx = await browser.new_context(user_agent=UA, ignore_https_errors=True,
                                        viewport={"width": 1600, "height": 900}, accept_downloads=True)
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

        # 打开加油高峰模块
        await page.evaluate("addTab('油站加油高峰期分析','report/jygfCharts.do','7164','7254',true)")
        await page.wait_for_timeout(2500)
        frame = None
        for _ in range(20):
            await page.wait_for_timeout(800)
            for f in page.frames:
                if "jygfCharts" in f.url:
                    frame = f
                    break
            if frame:
                break
        if not frame:
            print("未找到加油高峰模块iframe")
            print([f.url for f in page.frames])
            await browser.close()
            return
        print("模块URL:", frame.url)
        html = await frame.content()
        with open(OUT + "jygf_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("页面长度:", len(html))

        info = await frame.evaluate("""() => {
            const out = {inputs:[], selects:[], buttons:[]};
            for (const el of document.querySelectorAll('input')) {
                out.inputs.push({id:el.id, name:el.name, ph:el.placeholder, type:el.type, cls:el.className.slice(0,30)});
            }
            for (const el of document.querySelectorAll('select')) {
                out.selects.push({id:el.id, name:el.name, opts:[...el.options].map(o=>({v:o.value,t:o.text})).slice(0,30)});
            }
            for (const el of document.querySelectorAll('button, a')) {
                const t=(el.textContent||'').trim();
                const oc=el.getAttribute('onclick')||'';
                if (t && /导出|查询|搜索|Excel|exp/i.test(t+oc)) {
                    out.buttons.push({id:el.id, text:t.slice(0,20), onclick:oc.slice(0,100)});
                }
            }
            return out;
        }""")
        print("=== inputs ===")
        for i in info["inputs"]:
            print("  ", i)
        print("=== selects ===")
        for s in info["selects"]:
            print("  ", s)
        print("=== buttons ===")
        for b in info["buttons"]:
            print("  ", b)
        await page.screenshot(path=OUT + "jygf.png", full_page=False)
        await browser.close()


asyncio.run(main())
