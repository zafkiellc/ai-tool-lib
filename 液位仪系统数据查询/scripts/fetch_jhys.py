"""登录 + 进货验收模块导出全公司本月数据
注意: 密码从 ~/.workbuddy/sap_credentials.env 读取(SAP_PWD_B64_XIAOY base64), 不落盘明文。
"""
import asyncio
import os
import base64
from datetime import date
from playwright.async_api import async_playwright

BASE_URL = "http://10.213.73.75:8080/index.jsp"
LOGIN_USERNAME = "xiaoy1206"
PICK_ACCOUNT = "xiaoy1206"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"

def _load_pwd():
    """从 ~/.workbuddy/sap_credentials.env 还原 xiaoy1206 密码(base64 混淆, 不落盘明文)。"""
    p = os.path.expanduser(r"~/.workbuddy/sap_credentials.env")
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line.startswith("SAP_PWD_B64_XIAOY="):
            b64 = line.split("=", 1)[1].strip().strip('"')
            return base64.b64decode(b64).decode("utf-8")
    raise RuntimeError("未找到 SAP_PWD_B64_XIAOY")

LOGIN_PASSWORD = _load_pwd()

LAUNCH_ARGS = [
    "--ignore-certificate-errors",
    "--disable-features=InsecureFormWarnings",
    "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080",
]

OUT_DIR = "C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output"
DOWNLOAD_DIR = f"{OUT_DIR}/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


async def main():
    today = date.today().strftime("%Y-%m-%d")
    month_start = "2026-08-01"

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=True, args=LAUNCH_ARGS)
        ctx = await browser.new_context(
            user_agent=UA,
            ignore_https_errors=True,
            viewport={"width": 1600, "height": 900},
            accept_downloads=True,
        )
        page = await ctx.new_page()
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector('input[name="j_username"]', timeout=30000)
        await page.fill('input[name="j_username"]', LOGIN_USERNAME)
        await page.fill('input[name="j_password"]', LOGIN_PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(5000)
        if "login.jsp" in page.url:
            for b in await page.query_selector_all("button, input[type='button'], input[type='submit'], a"):
                t = (await b.text_content() or "").strip() or (await b.get_attribute("value") or "")
                if t.strip() == PICK_ACCOUNT:
                    await b.click()
                    break
            await page.wait_for_timeout(6000)
        print("登录后URL:", page.url)
        print("标题:", await page.title())

        await page.click('a[onclick*="tojhys"]', timeout=15000)
        frame = None
        for _ in range(20):
            await page.wait_for_timeout(800)
            for f in page.frames:
                if "tojhys" in f.url:
                    frame = f
                    break
            if frame:
                break
        if not frame:
            print("未找到进货验收iframe")
            print("iframe URL列表:", [f.url for f in page.frames])
            await browser.close()
            return
        print("进入进货验收iframe:", frame.url)

        # 设日期
        await frame.evaluate("(args) => { $('#' + args.id).datebox('setValue', args.val); return $('#' + args.id).datebox('getValue'); }",
                              {"id": "startTime", "val": month_start})
        await frame.evaluate("(args) => { $('#' + args.id).datebox('setValue', args.val); return $('#' + args.id).datebox('getValue'); }",
                              {"id": "endTime", "val": today})
        print("日期已设置:", month_start, "~", today)

        ctrls = await frame.evaluate("""() => {
            const out = {};
            for (const c of document.querySelectorAll('input.easyui-combobox, input.easyui-datebox, input.easyui-combogrid')) {
                out[c.id || c.name] = c.placeholder || c.title || '';
            }
            return out;
        }""")
        print("页面控件:", ctrls)

        try:
            await frame.evaluate("searchSh()")
        except Exception as e:
            print("searchSh失败:", e)
        await frame.wait_for_timeout(8000)
        try:
            row_count = await frame.evaluate("$('#dg').datagrid('getData').total")
            print("datagrid 总记录数:", row_count)
        except Exception as e:
            print("取记录数失败:", e)

        try:
            async with page.expect_download(timeout=120000) as dl:
                await frame.click('#expExcel', timeout=10000)
            dl_val = await dl.value
            save_path = f"{DOWNLOAD_DIR}/{dl_val.suggested_filename}"
            await dl_val.save_as(save_path)
            print("导出成功:", save_path)
        except Exception as e:
            print("导出Excel失败:", e)
            await page.screenshot(path=f"{OUT_DIR}/jhys_page.png", full_page=False)

        try:
            rows = await frame.evaluate("() => { const data = $('#dg').datagrid('getData').rows || []; return data.slice(0, 5); }")
            print("datagrid 前5行示例:", rows)
        except Exception:
            pass

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
