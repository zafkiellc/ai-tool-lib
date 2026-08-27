# -*- coding: utf-8 -*-
"""登录液位仪系统，验证账号权限范围"""
import asyncio, sys, json
from playwright.async_api import async_playwright

BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "xiaoy1206"
PASSWORD = "Yao1206022"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge", headless=True,
            args=["--ignore-certificate-errors",
                  "--disable-features=InsecureFormWarnings",
                  "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"])
        ctx = await browser.new_context(user_agent=UA, ignore_https_errors=True,
                                        viewport={"width":1600,"height":900})
        page = await ctx.new_page()
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_selector('input[name="j_username"]', timeout=60000)
        except Exception as e:
            print("未找到登录框，当前URL:", page.url)
            print("页面内容片段:", (await page.content())[:500])
            await browser.close(); return
        await page.fill('input[name="j_username"]', USERNAME)
        await page.fill('input[name="j_password"]', PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(8000)
        print("登录后URL:", page.url)
        print("标题:", await page.title())
        # 抓取页面里可见的片区/公司信息
        content = await page.content()
        # 找菜单里的片区/模块信息
        import re
        # 尝试提取页面文本中的片区名
        for kw in ["汉阳","新洲","黄陂","蔡甸","江夏","武昌","汉口","东西湖","东湖高新"]:
            if kw in content:
                print("页面含片区关键字:", kw)
        # 保存截图
        await page.screenshot(path="C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output/login_test.png", full_page=False)
        print("已保存截图 output/login_test.png")
        await browser.close()

asyncio.run(main())
