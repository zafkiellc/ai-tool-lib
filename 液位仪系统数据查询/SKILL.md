---
name: 液位仪系统数据查询
description: 液位仪系统数据查询（原 sinopec-system-scrape）——抓取"中国石化液位仪深化应用系统"(http://10.213.73.75:8080)
  各业务模块数据并导出 Excel。当需要登录该系统抓取 进货验收/出库单查询/时点库存实时清单/液位手工测量比对/加油站盘点/配送单查询 等任一常用功能的数据、或导出"进油验收报表(*.xls)"时使用。覆盖
  SSO 登录、菜单导航、easyui 筛选设置、导出/查询接口调用全流程。
agent_created: true
permalink: main/工作/项目/资产/work-buddy-私有-skills/液位仪系统数据查询/skill-1
---

# 中石化液位仪系统数据抓取

## 系统与认证（必须理解）
- 应用：http://10.213.73.75:8080/index.jsp（标题"液位仪深化应用系统"），内网地址，Bash/curl/Playwright 均可直连（WebFetch 会被私有 IP 策略拦截，别用）。
- **认证是中石化企业 SSO（SIAM/IAM）**：index.jsp → /login.jsp → SAML2 Redirect 到 `auth.siam.sinopec.com` → `TAMUserPassAuth` 登录页。
- 登录默认方式 `TAMUsernamePassword`：j_username + j_password + j_checkcode（验证码）。
  - **验证码对真实浏览器非强制**（页面 JS `Display` 标志控制）；curl 等非浏览器客户端会被要求验证码 → 必须用 Playwright/浏览器。
  - **HTTPS→HTTP 回传会被 Chromium 拦截（"表单不安全"）**：登录成功后 SAMLResponse 自动 POST 回 `http://10.213.73.75:8080`，必须加启动参数放行（见下）。
- 账号密码：用户提供（如 lvch36 / cc336699.）。

## 环境准备（一次性）
```bash
# 隔离 venv（Windows）
C:/Users/zafki/.workbuddy/binaries/python/versions/3.13.12/python.exe -m venv C:/Users/zafki/.workbuddy/binaries/python/envs/default
C:/Users/zafki/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple playwright xlrd openpyxl
```
- 浏览器用系统 Edge（`channel="msedge"`），路径 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`（无需下载 Chromium）。

## 登录（Playwright + Edge，关键参数）
```python
browser = await p.chromium.launch(
    channel="msedge", headless=True,
    args=["--ignore-certificate-errors",
          "--disable-features=InsecureFormWarnings",          # 放行 HTTPS→HTTP SAML 回传，关键！
          "--unsafely-treat-insecure-origin-as-secure=http://10.213.73.75:8080"])
ctx = await browser.new_context(user_agent=UA, ignore_https_errors=True, viewport={"width":1600,"height":900})
page = await ctx.new_page()
await page.goto("http://10.213.73.75:8080/index.jsp", wait_until="domcontentloaded", timeout=60000)
await page.wait_for_selector('input[name="j_username"]', timeout=60000)
await page.fill('input[name="j_username"]', USERNAME)
await page.fill('input[name="j_password"]', PASSWORD)
await page.click('button[type="submit"]')
await page.wait_for_timeout(6000)   # 等 SSO 回跳
# 成功后 URL=http://10.213.73.75:8080/index.jsp，标题=液位仪深化应用系统
```

## 打开功能模块（菜单 → iframe）
- 首页菜单是 easyui 渲染，功能项形如：
  `<a onclick="addTab('进货验收','sh/jhys/tojhys.do','7111','7250',true)">`
- **直接 GET 模块 URL 会被弹回 index.jsp**，必须点菜单在 iframe 里打开：
```python
await page.click('a[onclick*="tojhys"]', timeout=15000)   # 按 URL 关键字点对应菜单
frame = None
for _ in range(20):
    await page.wait_for_timeout(1000)
    for f in page.frames:
        if "tojhys" in f.url:      # 用模块 URL 关键字匹配
            frame = f; break
    if frame: break
```
- 常用功能模块 URL 表（从 addTab 提取，2026-08 已全部实测通过）：
  - 进货验收：`sh/jhys/tojhys.do`（导出 `selectJhysListToExcel.do`，产出"进油验收报表*.xls"35列）
  - 出库单查询：`ckd/toCkd.do`（查询 `selectAll.do`、计数 `selectCkdCount.do`、导出 `selectCkdToExcel.do`）
  - 时点库存实时清单：`sh/stockHour/toStockHour.do`（查询/导出 `selectStockHour.do`/`selectStockHourToExcel.do`，**startTime 是 datetimebox 单时间点**）
  - 液位手工测量比对：`manualContrast/toView.do`（查询 `selectManualContrast.do`、导出 `manualContrastExcel.do`）
  - 进油验收状态同步：`sh/bfJhysStatus/toBfJhysStatus.do`（参数名 **beginOilTime/endOilTime**，导出 `selectBfJhysStatusToExcel.do`）
  - 进货损耗率区间段统计：`sh/jhys/tostatis.do`（查询 `selectBfSyl.do`，含 ssshlV20/ssshlV10 损耗率区间参数，默认 -5~5）
  - 油站日平衡表：`sh/salesgl/tolist.do`（查询 `selectAll.do`、导出 `selectAllSalesglToExcel.do`；**按单日查询**，区间查询返回 0）
  - 加油站盘点：`sh/sync/tosync.do`；盘点历史：`sh/syncHistory/tosyncHistory.do`
  - 班结数据查询：`yzbb/yzbbView.do`；配送单查询：`psd/toPsd.do`
  - 回罐数据查询：`hgxskc/hgView.do`；销售数据查询：`hgxskcHistory/yqxsView.do`
  - 移入/移出单：`transferInOutBill/toTransferInBillView.do` / `toTransferOutBillView.do`
  - 进货验收损溢分析：`sh/jhystj/toJhystj.do`；油站日平衡表：`sh/salesgl/tolist.do`（按天）
  - 进油验收状态同步：`sh/bfJhysStatus/toBfJhysStatus.do`
- **日期口径**：现在是 2026 年，测业务数据用当前月份（如 2026-08-01 ~ 2026-08-18），别用 2020 之类历史年份（手工测量比对等新功能无历史数据；进货验收有历史数据）。
- **通用模式**：每个业务页都有"导出Excel"按钮（部分带 id="expExcel"，部分只有文字+onclick="expExcel()"），导出接口命名规律 `<select模块名>ToExcel.do` 或 `<模块>Excel.do`；查询接口 `<select模块名>.do`。

## 快速测试脚本（随 skill 分发，开箱即用）
- `scripts/test_module.py`：通用单模块测试——登录→点菜单→设日期→查询→导出→写 `output/result_<关键字>.json`。账号配置在文件顶部（BASE_URL/USERNAME/PASSWORD）。
```bash
# venv 里需已装 playwright（见"环境准备"）
C:/Users/zafki/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
  scripts/test_module.py ckd 2026-08-01 2026-08-18 output
```
- 输出：导出文件（如"出库单报表[20260801-20260818].xls"）+ result JSON（含控件清单/分页/接口请求参数）。

## 设置筛选（easyui 控件）
- easyui 组件要用其 API 设值（直接 fill 无效）：
```python
await frame.evaluate("$('#startTime').datebox('setValue','2020-08-01')")
await frame.evaluate("$('#endTime').datebox('setValue','2020-08-18')")
await frame.evaluate("$('#oilsId').combobox('setValue','')")  # 油品等 combobox 同理
# 回读校验：await frame.evaluate("$('#startTime').datebox('getValue')")
```
- 查询按钮可能不可直接点击（`a:has-text("查询")` 不可见），**改用 evaluate 调函数**：
```python
await frame.evaluate("searchSh()")   # 进货验收页的查询函数；其他页找对应函数或 $(...).datagrid('load',{})
```

## 导出 Excel（首选，一次拿全量）
- 大多数业务页都有"导出Excel"按钮（`id="expExcel"`, `onclick="expExcel()"`），对应后端 `.do` 导出接口：
  - 进货验收：`POST /sh/bfJhys/selectJhysListToExcel.do`（参数同查询接口）
  - 液位手工测量比对：`POST /manualContrast/manualContrastExcel.do`（参数 `deptId=&nodeno=&startTime=&endTime=`）
- Playwright 捕获下载：
```python
async with page.expect_download(timeout=60000) as dl:
    await frame.click('#expExcel', timeout=10000)
dl = await dl.value; await dl.save_as("output/" + dl.suggested_filename)
```
- 产物命名形如 `进油验收报表（20200801-20200818）<id>.xls`，即"中石化损耗分析"skill 的输入格式（35 列，表头在 R1，Sheet1）。手工测量对比导出为 `手工测量对比.xls`（10 列）。

## 查询接口（不进页面直接抓，备用/批量）
- `POST http://10.213.73.75:8080/sh/bfJhys/selectBfAll.do`
  参数：`startTime=2020-08-01&endTime=2020-08-18&ckId=&ssshlV20=&ssshlV10=&oilsId=&deptId=&stationCode=&useTemp=&isEnter=&gh=&bxbf=0&depotName=&cpNo=&page=1&rows=20`
  （rows 可加大到 100；需要登录态 Cookie——可从 Playwright 上下文 `ctx.cookies()` 导出后给 requests 用）
- 计数接口：`selectJyysCount.do`（同参数，返回记录数）

## 验证与后续
- .xls 用 xlrd 读（`xlrd.open_workbook`）；进油验收报表 35 列、表头在 R1、数据从 R2 起。
- 抓到的进油验收报表可直接交给 `sinopec-loss-analysis` skill 做损耗分析。

## 常见坑
1. 忘加 `--disable-features=InsecureFormWarnings` → 登录后停在"表单不安全"页（chrome-error://）。
2. 用 curl 直接登录 → 被验证码卡住（认证失败）。验证码只对浏览器免强制。
3. 直接 GET 模块 URL → 被弹回 index.jsp，必须点菜单在 iframe 打开。
4. easyui datebox/combobox 用原生 fill 不生效，要用 `.datebox('setValue')` / `.combobox('setValue')`。
5. 登录后要等 5~6 秒让 SSO 回跳完成，再操作。

## 多账号选择页（重要！2026-08 实测）
- 部分员工（如 xiaoy1206）SSO 登录后会被引导到"您在本系统有多个账号，请选择目标账号登录"页，列出 3 个同名变体（`xiaoy1206_3` / `xiaoy1206` / `xiaoy1206_2`），后缀 `_3` 通常权限最大、原始名次之、`_2` 最小。
- **必须用 evaluate 匹配按钮文字**点击对应账号，不要直接 GET：
```python
for b in await page.query_selector_all("button, input[type='button'], input[type='submit'], a"):
    t = (await b.text_content() or "").strip() or (await b.get_attribute("value") or "")
    if t.strip() == "xiaoy1206":
        await b.click()
        break
```
- 用户指定哪个就用哪个（如"汉阳片区吕晨"给的是 xiaoy1206，该账号实际拿到的是省级/全公司权限，菜单含"进货验收"+"湖北武汉分公司"全部数据）。

## Playwright evaluate 关键坑（2026-08 实测）
- `frame.evaluate(expression, arg)` 只支持**单参数**位置，要传多值就打包成 dict/list：
  ```python
  # 错：frame.evaluate("$('#a').datebox('setValue', arguments[0])", "2026-08-01")
  # → ReferenceError: arguments is not defined
  # 对：frame.evaluate("(args) => $('#' + args.id).datebox('setValue', args.val)", {"id": "startTime", "val": "2026-08-01"})
  ```
- `frame.evaluate("searchSh()")` 直接调用页面 JS 函数可用，无需参数。
- 取 datagrid 记录数：`frame.evaluate("$('#dg').datagrid('getData').total")`。

## 一键拉全公司进货验收（xiaoy1206 适配）
- 2026-08 实测：`scripts/fetch_jhys.py` 用 xiaoy1206 登录后 → 进「进货验收」→ 设本月日期范围 → searchSh() → 导出 xls → 一键产出 3500+ 条全公司记录。
- 关键参数：USERNAME=登录员工号、PICK_ACCOUNT=多账号页按钮文字（如 xiaoy1206）。
- 输出：35 列 xls（表头在 R2），覆盖 4 油库 / 177 站 / 4 油品，足够支撑"全公司损耗通报"级别分析。


## 历史液位曲线分析模块（2026-08-21 实测跑通）
- **模块URL**：`sh/stock/dayrealStock.jsp`（菜单"统计分析→业务分析→历史液位曲线分析"，addTab('历史液位曲线分析','sh/stock/dayrealStock.jsp','7166','7254',true)）。
- **参数**：station(站点)、gh(油罐,下拉随站点联动 `loadYg`→`/sh/stock/getBfTank.do?stationCode=`)、dateTime(单日)。
- **关键**：必须选站→选罐(选罐才知道品种)→选日期；导出接口 `POST /sh/stock/dayrealstockToExcel.do`，参数 stationCode+gh+sdate；**必须先 searchData() 查询(createChat加载)才能导出**，否则报 `error:'1'`(请查询后导出)。
- **导出流程**：searchData() → 等3秒 → ajax 调 dayrealstockToExcel.do → 返回 `data["success"]`(文件名) → GET `/buildexcel/<文件名>.xls` 下载。
- **站点加载**：需先选部门 `selectYZ(deptCode)` 触发，部门码从 `/system/organization/dept/getDeptTreeWithQx.do` 拿(汉阳=3400HUA06101)。station 用 combobox('select',code)，gh 用 combobox('select',id)。
- **数据格式**：每5秒1条，列=油站代码/罐号/油高(mm)/温度(°C)/油体积(L)/记录时间，每天约17280行。可直接用于卸油事件/温差/进油节奏分析。
- **脚本**：`scripts/fetch_history_stock.py`（按站-罐-日循环导出）。

- **批量拉取核对**：拉多站液位曲线/加油高峰后，务必用 `ls 站名* | awk -F'_' '{print $1}' | sort | uniq -c` 核对**每个目标站都有文件**，避免某站因后台任务中断/未开始而静默缺失。生成报告前重新汇总数据 JSON。
- **耗时评估**：单站单罐单日约6-7秒(查询3s+导出)。全公司177站×4罐×21天≈15000次≈25+小时，超1小时门槛，全站拉取不可行；只拉落后站/重点站。


## 油站加油高峰期分析模块（2026-08-21 实测，高效！）
- **模块URL**：`report/jygfCharts.do`（菜单"统计分析→业务分析→油站加油高峰期分析"）。
- **参数**：station(站点)、startTime/endTime(datebox,区间≤3月)、type(oils按油品|oilcan按罐)、colors。
- **导出接口**：`POST /report/jygfExcel.do`，参数 startTime/endTime/stationCode/stationName/type/colors。
- **数据**：一次拉一个站整月，行=油品(或罐号)，列=24时段销售升数。可直接看主力品种+销售高峰。
- **站点加载**：`/station/getEffectiveStationByDept.do?deptCode=3400HUA06101`，字段 id/text(注意非stationCode/stationName)。选站用 combobox('setValue', id)。
- **下载坑**：导出后下载可能中断致文件损坏，需"等待1-2秒+重试3次+xlrd验证"，损坏则删重拉。
- **脚本**：`scripts/fetch_jygf.py`(单站)、`scripts/batch_fetch_jygf.py`(批量39站)。
- **价值**：比历史液位曲线(单站单罐单日)高效太多，推荐用于批量销售画像/主力品种/高峰时段分析。