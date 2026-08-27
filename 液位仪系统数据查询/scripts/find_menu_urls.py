"""登录并抓取所有菜单的onclick URL, 定位历史液位曲线分析等模块"""
import asyncio, json, os
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "xiaoy1206"
PASSWORD = os.environ.get("YWY_PWD", "Yao1206022")  # 优先环境变量
PICK_ACCOUNT = "xiaoy1206"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
LAUNCH_ARGS = ["--ignore-certificate-errors","--disable-features=InsecureFormWarnings","--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"]
OUT = "C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output/menu_urls.json"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True, args=LAUNCH_ARGS)
        ctx = await browser.new_context(user_agent=UA, ignore_https_errors=True, viewport={"width":1600,"height":900})
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
                    await b.click(); break
            await page.wait_for_timeout(6000)
        print("登录后:", await page.title())

        # 抓取所有 onclick 含 addTab 的菜单
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        items = {}
        for a in soup.find_all("a", onclick=True):
            oc = a["onclick"]
            if "addTab" in oc:
                label = a.get_text(strip=True)
                items[label] = oc
        # 也抓所有带 href/onclick 的元素
        for el in soup.find_all(True):
            oc = el.get("onclick","")
            if "addTab" in oc:
                label = el.get_text(strip=True)
                if label: items[label] = oc

        with open(OUT,"w",encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"抓到 {len(items)} 个菜单项, 存 {OUT}")
        # 打印含"历史液位"或"曲线"的
        for k,v in items.items():
            if "历史液位" in k or "曲线" in k or "时点库存" in k:
                print(f"  [{k}] -> {v}")
        await browser.close()

asyncio.run(main())
