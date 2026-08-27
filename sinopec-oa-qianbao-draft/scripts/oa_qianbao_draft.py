#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中石化 OA 签报起草 —— 自动上草稿脚本（GRC v5 / newoa03）
------------------------------------------------------------
流程：登录(无验证码, 空profile) -> 公文管理/签报/签报起草
      -> 填 密级=无 / 标题 / 电话
      -> 添加正文(docx) + 添加附件(xlsx)
      -> 点右上角「保存」存为草稿

重要前提/限制：
1. 登录不需要验证码（公司内网 SSO 对浏览器非强制），但必须用「空 profile / 隐私模式」
   启动，绝不能复用你本人正常浏览器的 cookie，否则会把你已登录的账号带进来造成「串号」。
2. 「添加正文 / 添加附件」底层是 IndiDocX 文档控件，页面以 <object classid> (ActiveX) 嵌入。
   ActiveX 只有 IE / Edge IE 兼容模式才支持，标准 Chromium/Edge 内核（无论无头/有头、手动或
   Playwright 驱动）都加载不了。故「上传 + 保存」在 Playwright 方案下根本不可自动化，必须由
   用户在支持 ActiveX 的环境（其 IE 模式 Edge）手动完成。脚本自动化边界止于「登录→导航→填表」，
   上传/保存做优雅降级提示，不报错退出。

用法：
  python oa_qianbao_draft.py <请示文件夹>
文件夹内需含：一份 .docx（正文）、可含一份 .xlsx（附件，可选）。
标题默认取 .docx 文件名（去扩展名）。
"""
import asyncio, os, sys, glob
from playwright.async_api import async_playwright

# ===================== 配置区 =====================
URL       = "https://newoa03.sinopec.com/grcv5/user/product/oa/workspace/workbench.jsp"
USER, PWD = "qinziyi25", "Qzy010101"
PHONE     = "15971474453"          # 固定电话
SECURITY  = "0"                    # 密级：0=无,5=普通商密,4=核心商密,3=秘密,2=机密,1=绝密,6=内部
HERE      = os.path.dirname(os.path.abspath(__file__))
FRESH     = os.path.join(HERE, "edge_fresh")   # 空 profile，避免串号
# 有头/无头：默认无头（便于复用）；设 OA_HEADLESS=0 则弹真实窗口（用于 IndiDocX 上传）
HEADLESS  = os.environ.get("OA_HEADLESS", "1") != "0"
# =================================================

def pick_files(folder):
    docx = sorted(glob.glob(os.path.join(folder, "*.docx")))
    xlsx = sorted(glob.glob(os.path.join(folder, "*.xlsx")))
    if not docx:
        raise SystemExit(f"[错误] 文件夹未找到 .docx 正文：{folder}")
    body = docx[0]
    att  = xlsx[0] if xlsx else None
    title = os.path.splitext(os.path.basename(body))[0]
    return body, att, title

async def open_draft(page, ctx):
    await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_selector('input[name="j_username"]', timeout=30000)
    await page.fill('input[name="j_username"]', USER)
    await page.fill('input[name="j_password"]', PWD)
    btns = await page.query_selector_all('button.white.loginBt')
    await btns[0].click()
    for _ in range(40):
        await page.wait_for_timeout(500)
        if "newoa03.sinopec.com" in page.url and "Authn" not in page.url:
            break
    await page.wait_for_timeout(2000)
    # 三级手风琴（force 跳过父级 li 遮罩拦截）
    await page.locator('i[title="公文管理"]').first.click(force=True)
    await page.wait_for_timeout(1000)
    await page.locator('dt[title="签报"]').first.click(force=True)
    await page.wait_for_timeout(1000)
    link = await page.locator('a:has-text("签报起草")').first.element_handle()
    await link.click(force=True)
    await page.wait_for_timeout(4000)
    dp = page
    for pg in ctx.pages:
        if "create.htm" in pg.url or "bpm" in pg.url:
            dp = pg; break
    await dp.wait_for_timeout(3000)
    return dp

async def upload_file(dp, link_text, filepath, label):
    print(f"[上传] {label}: 点击「{link_text}」")
    link = await dp.locator(f'a:has-text("{link_text}")').first.element_handle()
    try:
        async with dp.expect_file_chooser(timeout=12000) as fc:
            await link.click()
        chooser = await fc.value
        await chooser.set_files(filepath)
        print(f"        -> 已选择文件: {os.path.basename(filepath)}")
        await dp.wait_for_timeout(4000)
        return True
    except Exception as e:
        print(f"        !! 上传弹窗未打开（很可能 IndiDocX/Silverlight 插件缺失）：{str(e)[:80]}")
        return False

async def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法: python oa_qianbao_draft.py <请示文件夹>")
    folder = sys.argv[1]
    body, att, title = pick_files(folder)
    print(f"[准备] 正文={os.path.basename(body)}  附件={os.path.basename(att) if att else '无'}  标题={title}")

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            FRESH, channel="msedge", headless=HEADLESS,
            args=["--ignore-certificate-errors", "--disable-features=InsecureFormWarnings"],
            ignore_https_errors=True, viewport={"width":1600,"height":900},
        )
        page = await ctx.new_page()
        dp = await open_draft(page, ctx)
        print(f"[起草页] {dp.url}")

        # 密级 = 无（radio 的 input 隐藏，点对应 label）
        await dp.locator(f'label:has(input[name="oasecurityGrade"][value="{SECURITY}"])').click()
        print("[填表] 密级=无")
        # 标题
        await dp.fill('textarea#docTitle', title)
        print(f"[填表] 标题={title}")
        # 电话
        await dp.fill('input#phone', PHONE)
        print(f"[填表] 电话={PHONE}")

        # 添加正文
        ok1 = await upload_file(dp, "添加正文", body, "正文")
        # 添加附件（可选）
        ok2 = True
        if att:
            ok2 = await upload_file(dp, "添加附件", att, "附件")

        if not (ok1 and ok2):
            print("\n[警告] 上传未完成（Silverlight 插件缺失，无头环境限制）。")
            print("        请在装有 IndiDocX 插件的真实(有头)Edge 中运行本脚本以完成上传。")
            print("        当前已填好的 密级/标题/电话 已就位，待上传后可手动点保存，或重跑本脚本。")
            await ctx.close()
            return

        # 保存（右上角）
        print("[保存] 点击右上角「保存」")
        save_btn = await dp.locator('button:has-text("保存")').first.element_handle()
        await save_btn.click()
        await dp.wait_for_timeout(4000)
        print(f"[完成] 草稿已保存。最终URL: {dp.url}")
        await ctx.close()

if __name__ == "__main__":
    asyncio.run(main())
