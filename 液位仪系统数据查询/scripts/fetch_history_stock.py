# -*- coding: utf-8 -*-
"""拉取历史液位曲线: 在 iframe 内操作, 全部用 jQuery ajax(带session)
流程: 打开模块 -> iframe内调getDeptTree拿部门码 -> selectYZ加载站点 -> 选站->getBfTank加载油罐 -> 逐日导出
用法: python fetch_history_stock.py <开始日期> <结束日期> <输出目录> <站点关键字1,2,...>
"""
import asyncio, os, sys, datetime
from playwright.async_api import async_playwright

BASE_URL = "http://10.213.73.75:8080/index.jsp"
USERNAME = "xiaoy1206"
PASSWORD = os.environ.get("YWY_PWD", "Yao1206022")
PICK_ACCOUNT = "xiaoy1206"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
LAUNCH_ARGS = ["--ignore-certificate-errors", "--disable-features=InsecureFormWarnings",
               "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"]


async def main():
    start_date = sys.argv[1] if len(sys.argv) > 1 else "2026-08-01"
    end_date = sys.argv[2] if len(sys.argv) > 2 else "2026-08-21"
    out_dir = sys.argv[3] if len(sys.argv) > 3 else "C:/Users/zafki/.workbuddy/skills/液位仪系统数据查询/output/history_stock"
    kw_arg = sys.argv[4] if len(sys.argv) > 4 else "罗七路,江城东,曙光"
    TARGET = [k.strip() for k in kw_arg.split(",") if k.strip()]
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

        # 打开历史液位模块
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
            print("未找到模块iframe")
            await browser.close()
            return
        print("模块URL:", frame.url)

        # 1. iframe 内调 getDeptTreeWithQx 拿部门树, 找汉阳部门码
        dept_tree = await frame.evaluate("""() => {
            return new Promise((resolve) => {
                $.ajax({url:'/system/organization/dept/getDeptTreeWithQx.do', method:'get', dataType:'json',
                    success:function(d){resolve(d);},
                    error:function(e){resolve({__err:'ajaxerr'});}});
            });
        }""")
        if isinstance(dept_tree, dict) and dept_tree.get("__err"):
            print("deptTree ajax 失败:", dept_tree)
            await browser.close()
            return

        # 递归找汉阳/湖北武汉分公司 部门码
        han_dept_code = None
        def find_dept(nodes, depth=0):
            nonlocal han_dept_code
            if depth > 10 or han_dept_code:
                return
            for n in nodes:
                txt = str(n.get("text", ""))
                if "汉阳" in txt:
                    han_dept_code = n.get("attributes", {}).get("deptCode")
                    print("找到汉阳部门:", txt, "code=", han_dept_code)
                    return
                find_dept(n.get("children", []), depth + 1)
        find_dept(dept_tree)
        if not han_dept_code:
            # 回退: 用第一个有子部门的顶层(湖北武汉分公司)
            print("未直接找到汉阳, 列出顶层部门:")
            for n in dept_tree[:20]:
                print("  ", n.get("text"), n.get("attributes", {}).get("deptCode"))
            # 尝试递归找含"武汉"或"湖北"的叶子部门
            def find_any(nodes):
                for n in nodes:
                    t = str(n.get("text", ""))
                    if "湖北" in t or "武汉" in t:
                        return n.get("attributes", {}).get("deptCode"), t
                    r = find_any(n.get("children", []))
                    if r:
                        return r
                return None, None
            han_dept_code, han_name = find_any(dept_tree)
            print("回退部门:", han_name, han_dept_code)

        if not han_dept_code:
            print("无法定位部门码, 退出")
            await browser.close()
            return

        # 2. iframe 内 selectYZ(deptCode) 加载该部门站点
        await frame.evaluate("(a) => { selectYZ(a.code); }", {"code": han_dept_code})
        await frame.wait_for_timeout(2000)
        stations = await frame.evaluate("""() => {
            try { return $('#station').combobox('getData').map(x=>({code:x.stationCode, name:x.stationName})); } catch(e) { return []; }
        }""")
        print("加载部门站点:", len(stations), "个")
        if not stations:
            print("站点加载失败")
            await browser.close()
            return

        # 3. 找目标站
        target_codes = {}
        for st in stations:
            for kw in TARGET:
                if kw in st["name"] and st["code"] != "-1" and kw not in target_codes:
                    target_codes[kw] = st["code"]
        print("目标站:", target_codes)

        # 4. 逐站-罐-日 导出
        for kw, code in target_codes.items():
            await frame.evaluate("(a) => { $('#station').combobox('select', a.code); }", {"code": code})
            await frame.wait_for_timeout(1800)
            tanks = await frame.evaluate("""() => {
                try { return $('#gh').combobox('getData').map(x=>({id:x.id, text:x.text})); } catch(e) { return []; }
            }""")
            print("★ %s(%s) 油罐: %s" % (kw, code, tanks))
            for tank in tanks:
                await frame.evaluate("(a) => { $('#gh').combobox('select', a.id); }", {"id": tank["id"]})
                await frame.wait_for_timeout(500)
                d = datetime.date.fromisoformat(start_date)
                end = datetime.date.fromisoformat(end_date)
                while d <= end:
                    ds = d.isoformat()
                    await frame.evaluate("(a) => { $('#dateTime').datebox('setValue', a.d); }", {"d": ds})
                    await frame.wait_for_timeout(400)
                    try:
                        # 先 searchData() 查询(加载数据), 再导出
                        await frame.evaluate("searchData()")
                        await frame.wait_for_timeout(3000)
                        result = await frame.evaluate("""() => {
                            return new Promise((resolve) => {
                                const stationCode = $('#station').combobox('getValue');
                                const gh = $('#gh').combobox('getValue');
                                const sdate = $('#dateTime').datebox('getValue');
                                if(!stationCode||!gh||!sdate){resolve({error:'missing'});return;}
                                $.ajax({type:'post', url:'/sh/stock/dayrealstockToExcel.do', dataType:'json',
                                  data:{stationCode:stationCode, gh:gh, sdate:sdate},
                                  success:function(data){resolve(data);},
                                  error:function(e){resolve({error:'ajaxerr'});}});
                            });
                        }""")
                        if result.get("success"):
                            xls_url = "http://10.213.73.75:8080/buildexcel/%s.xls" % result["success"]
                            resp = await ctx.request.get(xls_url)
                            if resp.status == 200:
                                body = await resp.body()
                                safe_tank = tank["text"].replace("/", "_").replace(" ", "")
                                fname = "%s/%s_%s_%s.xls" % (out_dir, kw, safe_tank, ds)
                                with open(fname, "wb") as f:
                                    f.write(body)
                                print("  OK %s 罐%s %s (%dB)" % (kw, tank["text"], ds, len(body)))
                            else:
                                print("  X %s 罐%s %s 下载失败%s" % (kw, tank["text"], ds, resp.status))
                        else:
                            print("  X %s 罐%s %s 导出失败:%s" % (kw, tank["text"], ds, result))
                    except Exception as e:
                        print("  X %s 罐%s %s 异常:%s" % (kw, tank["text"], ds, e))
                    d += datetime.timedelta(days=1)
        await browser.close()
        print("完成")


if __name__ == "__main__":
    asyncio.run(main())
