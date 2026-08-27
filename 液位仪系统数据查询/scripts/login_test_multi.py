"""登录液位仪系统，验证多账号权限范围"""
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "xiaoy1206"
PASSWORD = "Yao1206022"
ACCOUNTS_TO_TRY = ["xiaoy1206", "xiaoy1206_3", "xiaoy1206_2"]
OUT_DIR = "C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output"
AREA_KEYS = ["汉阳", "新洲", "黄陂", "蔡甸", "江夏", "武昌", "汉口", "东西湖", "东湖高新", "湖北", "全公司", "全省"]
LAUNCH_ARGS = ["--ignore-certificate-errors", "--disable-features=InsecureFormWarnings", "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"


async def try_login(account_name):
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True, args=LAUNCH_ARGS)
        ctx = await browser.new_context(user_agent=UA, ignore_https_errors=True, viewport={"width": 1600, "height": 900})
        page = await ctx.new_page()
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_selector('input[name="j_username"]', timeout=30000)
        except Exception:
            print(f"[{account_name}] 未找到登录框 URL={page.url}")
            await browser.close()
            return None

        await page.fill('input[name="j_username"]', USERNAME)
        await page.fill('input[name="j_password"]', PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(5000)

        if "login.jsp" in page.url:
            btn_texts = []
            for b in await page.query_selector_all("button, input[type='button'], input[type='submit'], a"):
                t = (await b.text_content() or "").strip() or (await b.get_attribute("value") or "")
                if t:
                    btn_texts.append((t, b))
            print(f"[{account_name}] 多账号页 按钮: {[t for t, _ in btn_texts]}")
            target = None
            for t, b in btn_texts:
                if t.strip() == account_name:
                    target = b
                    break
            if not target:
                print(f"[{account_name}] 未找到该账号按钮")
                await browser.close()
                return None
            await target.click()
            await page.wait_for_timeout(6000)

        url2 = page.url
        title = await page.title()
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(" ", strip=True)
        found = [k for k in AREA_KEYS if k in text]
        jhys_found = ("进货验收" in text) or ("tojhys" in content)
        await page.screenshot(path=f"{OUT_DIR}/login_{account_name}.png", full_page=False)
        with open(f"{OUT_DIR}/menu_{account_name}.txt", "w", encoding="utf-8") as f:
            f.write(text[:8000])
        print(f"[{account_name}] URL={url2} 标题={title!r} 可见片区={found} 进货验收模块={jhys_found}")
        await browser.close()
        return {"account": account_name, "url": url2, "title": title, "areas": found, "has_jhys": jhys_found}


async def main():
    results = []
    for acc in ACCOUNTS_TO_TRY:
        try:
            r = await try_login(acc)
            if r:
                results.append(r)
        except Exception as e:
            print(f"[{acc}] 异常: {e}")
        await asyncio.sleep(1)
    print("\n=== 登录结果汇总 ===")
    for r in results:
        print(r)


if __name__ == "__main__":
    asyncio.run(main())
