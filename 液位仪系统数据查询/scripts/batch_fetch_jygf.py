# -*- coding: utf-8 -*-
"""批量拉取汉阳所有站点加油高峰数据(oils+oilcan), 一次登录循环
用法: python batch_fetch_jygf.py <开始> <结束> <输出目录>
"""
import asyncio, os, sys, datetime, json
from playwright.async_api import async_playwright

BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "xiaoy1206"
PASSWORD = os.environ.get("YWY_PWD", "Yao1206022")
PICK_ACCOUNT = "xiaoy1206"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
LAUNCH_ARGS = ["--ignore-certificate-errors", "--disable-features=InsecureFormWarnings",
               "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"]
HAN_DEPT_ID = "108"
HAN_DEPT_CODE = "3400HUA06101"


async def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-08-01"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-08-21"
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output/jygf_all"
    os.makedirs(out_dir, exist_ok=True)

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
            print("未找到模块")
            await browser.close()
            return

        # 加载汉阳站点(id/text)
        stations = await frame.evaluate("""() => {
            return new Promise((resolve) => {
                $.ajax({url:'/station/getEffectiveStationByDept.do?deptCode=3400HUA06101', method:'get', dataType:'json',
                    success:function(d){resolve(d.map(x=>({code:x.id, name:x.text})));},
                    error:function(){resolve([]);}});
            });
        }""")
        stations = [s for s in stations if s["code"] != "-1"]
        print("汉阳站点:", len(stations))

        results = []
        for st in stations:
            for dtype in ["oils", "oilcan"]:
                fname = "%s/%s_%s_%s.xls" % (out_dir, st["code"], dtype, start)
                if os.path.exists(fname):
                    print("跳过(已存在):", os.path.basename(fname))
                    continue
                try:
                    # 选站
                    await frame.evaluate("(a) => { $('#station').combobox('setValue', a.code); }", {"code": st["code"]})
                    await frame.evaluate("(a) => { $('#startTime').datebox('setValue', a.t); }", {"t": start})
                    await frame.evaluate("(a) => { $('#endTime').datebox('setValue', a.t); }", {"t": end})
                    await frame.evaluate("(a) => { $('#type').combobox('select', a.t); }", {"t": dtype})
                    await frame.wait_for_timeout(600)
                    result = await frame.evaluate("""() => {
                        return new Promise((resolve) => {
                            const s = $('#startTime').datebox('getValue');
                            const e = $('#endTime').datebox('getValue');
                            const sc = $('#station').combobox('getValue');
                            const sn = $('#station').combobox('getText');
                            const ty = $('#type').combobox('getValue');
                            if(!s||!e||!sc){resolve({error:'missing'});return;}
                            $.ajax({type:'post', url:'/report/jygfExcel.do', dataType:'json',
                              data:{startTime:s, endTime:e, stationCode:sc, stationName:sn, type:ty, colors:''},
                              success:function(d){resolve(d);}, error:function(e2){resolve({error:'ajaxerr'});}});
                        });
                    }""")
                    if result.get("success"):
                        # 下载前等待服务器就绪
                        await page.wait_for_timeout(1200)
                        import xlrd
                        ok = False
                        for attempt in range(3):
                            try:
                                resp = await ctx.request.get("http://10.213.73.75:8080/buildexcel/%s.xls" % result["success"])
                                if resp.status == 200:
                                    body = await resp.body()
                                    with open(fname, "wb") as f:
                                        f.write(body)
                                    # 验证文件有效
                                    xlrd.open_workbook(fname)
                                    ok = True
                                    break
                                else:
                                    print("X %s %s 下载失败%s" % (st["name"][-10:], dtype, resp.status))
                            except Exception as e:
                                print("X %s %s 下载中断,重试%d: %s" % (st["name"][-10:], dtype, attempt+1, e))
                            await page.wait_for_timeout(1000)
                        if ok:
                            results.append((st["name"], dtype, len(body)))
                            print("OK %s %s (%dB)" % (st["name"][-10:], dtype, len(body)))
                        else:
                            if os.path.exists(fname):
                                os.remove(fname)
                            print("X %s %s 下载最终失败" % (st["name"][-10:], dtype))
                    else:
                        print("X %s %s 导出失败:%s" % (st["name"][-10:], dtype, result))
                except Exception as e:
                    print("X %s %s 异常:%s" % (st["name"][-10:], dtype, e))
                await page.wait_for_timeout(300)
        print("\n完成, 成功:", len(results))
        await browser.close()


asyncio.run(main())
