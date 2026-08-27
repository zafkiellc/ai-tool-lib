# -*- coding: utf-8 -*-
"""拉取油站加油高峰期分析数据(按油品/油罐), 支持区间
用法: python fetch_jygf.py <站关键字> <开始> <结束> <type:oils|oilcan> <输出目录>
"""
import asyncio, os, sys
from playwright.async_api import async_playwright

BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "xiaoy1206"
PASSWORD = os.environ.get("YWY_PWD", "Yao1206022")
PICK_ACCOUNT = "xiaoy1206"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
LAUNCH_ARGS = ["--ignore-certificate-errors", "--disable-features=InsecureFormWarnings",
               "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"]
OUT_DIR = "C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output/jygf"
os.makedirs(OUT_DIR, exist_ok=True)


async def main():
    station_kw = sys.argv[1] if len(sys.argv) > 1 else "罗七路"
    start_time = sys.argv[2] if len(sys.argv) > 2 else "2026-08-01 00:00:00"
    end_time = sys.argv[3] if len(sys.argv) > 3 else "2026-08-21 23:59:59"
    dtype = sys.argv[4] if len(sys.argv) > 4 else "oils"

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
            print("未找到加油高峰模块")
            await browser.close()
            return
        print("模块URL:", frame.url)

        # 选汉阳部门加载站点
        dept_tree = await frame.evaluate("""() => {
            return new Promise((resolve) => {
                $.ajax({url:'/system/organization/dept/getDeptTreeWithQx.do', method:'get', dataType:'json',
                    success:function(d){resolve(d);}, error:function(){resolve([]);}});
            });
        }""")
        han_code = None
        def find(nodes):
            nonlocal han_code
            if han_code: return
            for n in nodes:
                if "汉阳" in str(n.get("text","")):
                    han_code = n.get("attributes",{}).get("deptCode")
                    return
                find(n.get("children",[]))
        find(dept_tree)
        print("汉阳部门码:", han_code)
        # 加载站点: iframe内ajax(字段 id/text)
        stations = await frame.evaluate("""() => {
            return new Promise((resolve) => {
                $.ajax({url:'/station/getEffectiveStationByDept.do?deptCode=3400HUA06101', method:'get', dataType:'json',
                    success:function(d){resolve(d.map(x=>({code:x.id, name:x.text})));},
                    error:function(){resolve([]);}});
            });
        }""")
        # 找目标站
        target = None
        for st in stations:
            if station_kw in st["name"] and st["code"] != "-1":
                target = st
                break
        if not target:
            print(f"未找到站 {station_kw}, 现有站:", [s['name'][-12:] for s in stations[:10]])
            await browser.close()
            return
        print("目标站:", target)

        # 选站(id/text)
        await frame.evaluate("(a) => { $('#station').combobox('setValue', a.code); }", {"code": target["code"]})
        # 设时间(注意: startTime/endTime 是 datebox, 格式 YYYY-MM-DD)
        await frame.evaluate("(a) => { $('#startTime').datebox('setValue', a.t); }", {"t": start_time[:10]})
        await frame.evaluate("(a) => { $('#endTime').datebox('setValue', a.t); }", {"t": end_time[:10]})
        # 选type
        await frame.evaluate("(a) => { $('#type').combobox('select', a.t); }", {"t": dtype})
        await frame.wait_for_timeout(800)

        # 导出
        result = await frame.evaluate("""() => {
            return new Promise((resolve) => {
                const startTime = $('#startTime').datebox('getValue');
                const endTime = $('#endTime').datebox('getValue');
                const stationCode = $('#station').combobox('getValue');
                const stationName = $('#station').combobox('getText');
                const type = $('#type').combobox('getValue');
                if(!startTime||!endTime||!stationCode){resolve({error:'missing', s:startTime,e:endTime,sc:stationCode});return;}
                $.ajax({type:'post', url:'/report/jygfExcel.do', dataType:'json',
                  data:{startTime:startTime, endTime:endTime, stationCode:stationCode, stationName:stationName, type:type, colors:''},
                  success:function(data){resolve(data);},
                  error:function(e){resolve({error:'ajaxerr', detail:JSON.stringify(e).slice(0,200)});}});
            });
        }""")
        print("导出返回:", result)
        if result.get("success"):
            xls_url = "http://10.213.73.75:8080/buildexcel/%s.xls" % result["success"]
            resp = await ctx.request.get(xls_url)
            if resp.status == 200:
                body = await resp.body()
                fname = "%s/%s_%s_%s.xls" % (OUT_DIR, station_kw, dtype, start_time[:10])
                with open(fname, "wb") as f:
                    f.write(body)
                print("已保存:", fname, len(body), "B")
        await browser.close()


asyncio.run(main())
