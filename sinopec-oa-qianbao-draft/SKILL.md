---
name: sinopec-oa-qianbao-draft
description: 中石化 OA（newoa03.sinopec.com，GRC v5 新一代协同办公）签报起草自动上草稿。当用户要"上 OA 签报草稿 /
  公文管理-签报起草 / 自动填密级标题电话并上传正文附件存草稿"时使用。覆盖无验证码登录、三级手风琴菜单导航、表单字段选择器、IndiDocX(ActiveX)
  上传限制（标准 Chromium/Edge 内核无法自动化，需 IE 模式）。
agent_created: true
permalink: main/工作/项目/资产/ai-工具库/sinopec-oa-qianbao-draft/skill
---

# 中石化 OA 签报起草（自动上草稿）

## 系统与环境
- 入口：`https://newoa03.sinopec.com/grcv5/user/product/oa/workspace/workbench.jsp`
- 认证：中石化统一 SSO（SIAM `TAMUserPassAuth`），表单 `j_username` / `j_password` / `j_checkcode`。
- **浏览器**：用本机系统 **Edge（Chromium 内核）** + Playwright（`channel="msedge"`）。无需下载 Chromium。
  - venv：`C:/Users/zafki/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（已装 playwright）。
  - 启动参数必须加 `--ignore-certificate-errors --disable-features=InsecureFormWarnings`。
  - **必须 `launch_persistent_context(user_data_dir=空目录)`**（不是 `launch(user_data_dir=...)`，`user_data_dir` 是 persistent_context 的参数）。

## ⚠️ 两个致命坑（已实测）
1. **登录无验证码**：公司内网 SSO 对真实浏览器**不强制验证码**（页面 JS `Display` 标志控制，只有 curl 等非浏览器才被卡验证码）。填账号密码直接 submit 即可，**不要去识别/处理验证码**。
2. **必须用空 profile / 隐私模式，绝不能复用本人浏览器 cookie**：否则会把你已登录的个人账号带进登录流程，造成**串号**。每次启动都用全新的空 `user_data_dir`（脚本里的 `edge_fresh` 目录，用完可清）。

## 登录 + 进起草页（核心代码）
```python
ctx = await p.chromium.launch_persistent_context(
    FRESH, channel="msedge", headless=True,
    args=["--ignore-certificate-errors","--disable-features=InsecureFormWarnings"],
    ignore_https_errors=True, viewport={"width":1600,"height":900})
page = await ctx.new_page()
await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
await page.wait_for_selector('input[name="j_username"]', timeout=30000)
await page.fill('input[name="j_username"]', USER)
await page.fill('input[name="j_password"]', PWD)
await (await page.query_selector_all('button.white.loginBt'))[0].click()
for _ in range(40):                      # 等 SSO 回跳
    await page.wait_for_timeout(500)
    if "newoa03.sinopec.com" in page.url and "Authn" not in page.url: break
# 三级手风琴（菜单在主页面，非 iframe）
await page.locator('i[title="公文管理"]').first.click(force=True)   # 父级 li 遮罩拦截 -> force
await page.wait_for_timeout(1000)
await page.locator('dt[title="签报"]').first.click(force=True)
await page.wait_for_timeout(1000)
await (await page.locator('a:has-text("签报起草")').first.element_handle()).click(force=True)
await page.wait_for_timeout(4000)
# 起草页在新标签弹出（create.htm?flowId=...）
dp = page
for pg in ctx.pages:
    if "create.htm" in pg.url or "bpm" in pg.url: dp = pg; break
```
- 菜单结构：`公文管理`(<i class="nav_sub_title" title="公文管理">) → `签报`(<dt title="签报">) → `签报起草`(<a target="workflow" inner-href=".../docBusinessTypeCom.jsp?doc_type=OA-QBGL">)。**直接 GET 起草 URL 会被弹回 SSO**，必须走菜单点击在同一会话内打开。

## 表单字段（实测选择器）
| 字段 | 选择器 | 说明 |
|---|---|---|
| 密级 | `label:has(input[name="oasecurityGrade"][value="0"])` | radio 的 input 隐藏，点 label。value: 0=无,5=普通商密,4=核心商密,3=秘密,2=机密,1=绝密,6=内部 |
| 标题 | `textarea#docTitle` | 填请示标题 |
| 电话 | `input#phone` | 填固定电话 |
| 添加正文 | `a:has-text("添加正文")` | onclick=`fnProductTjzw()`，实为 `AddFile(-1)` |
| 添加附件 | `a:has-text("添加附件")` | onclick=`AddFile(0)` |
| 保存 | `button:has-text("保存")` | 右上角，存为草稿（**不要点提交**） |

## ⚠️ 上传环节（关键，实测结论 —— 已据实大幅修正）
> **重要更正**：早期误判为"ActiveX 死结 / 仅 IE 模式能传"。反编译起草页 JS 后确认：**OA 上传走 V6/HTML5 插件（与平台无关），并非 ActiveX 死结**。Linux 办公机、Mac 均能传，靠的就是 V6。

### 真实架构（反编译 `indiDocX_sl.js` / `indiDocX_custom.js`，部署版 2026.0318.1）
- `slCtl` 是 JS 抽象对象，非死绑 Silverlight。`isIdxPluginInstalled()` 与 `isIE()` **被硬编码返回 false**（custom.js 注释：禁用 V5 插件就覆盖这俩返回 false）→ **V5/ActiveX 路径在本部署已关闭**。
- 上传后端两套：**V5/Silverlight(ActiveX)** 与 **V6/HTML5**。开关 `struseV6IDX="1"`（默认开启）。
- **V6/HTML5 = 本机本地 HTTP 服务**：`slCtl.sendRequest()` 向 `http://localhost:17239`(及 17244 等) 发请求（`_initHttpServer`→`/inithttpserver`）。V6 插件握手成功时 `slCtl.isV6PluginInstall=true`（并写 `localStorage["isV6PluginInstall"]="true"` 缓存）。
- `V6IDXStatusUpdate()`：`isV6PluginInstall` 为真 → **显示 `.indidocx-fileAddBar`（HTML5 文件条）**、隐藏"需安装"提示。`oaJqueryFileUpload`(`fileupload-main2.js`) 渲染真正的 `<input type="file" name="Filedata" multiple>`。
- **实测本机（用户 Windows PC）17239/17244 端口正在监听** → V6 本地服务此刻就在跑；用户"普通 Edge 能传"正是靠它（非 IE 模式、非 ActiveX）。

### 为什么 Playwright 从「全新 profile」仍难稳定上传（根因，非死结）
- 真正的 `<input type=file>` 只在 **V6 完整握手成功后**由 `oaJqueryFileUpload` 渲染。全新 headless profile 的 `localStorage` 为空 → 每次重新握手；且 **HTTPS 页连 `http://localhost` 被混合内容策略拦截** → 握手起不来 → 文件框不渲染。
- 强制 `slCtl.isV6PluginInstall=true` + `V6IDXStatusUpdate()` 能露出 `.indidocx-fileAddBar` 容器（bars=1）但 `files=0`（文件框未渲染）。
- 用户真实 Edge 能成：V6 已初始化 + `localStorage` 已缓存 `isV6PluginInstall=true` → 每次稳定 V6。

### 可靠全自动的正路
- **在用户真实浏览器上下文里跑**（V6 已初始化、localStorage 已缓存）。⚠️ 但须**先清掉 OA 会话 cookie 再登录 qinziyi25**，杜绝"串号"（用户明确警告过：复用本人正常浏览器 cookie 会把已登录账号带进来）。
- 上传改走 **直接 `set_input_files` 到 `.indidocx-fileAddBar` 内的 `<input type=file>`**，绕开 `AddFile()` 的 `ShowOpenFileDialog`（那是 V6 控件对话框，headless 抓不到）。
- 已验证「登录→导航→填密级/标题/电话」全自动；上传卡在 V6 握手/mixed-content，需真实上下文才稳。

### 已废止的旧结论（勿再信）
- ❌ "ActiveX 死结 / 仅 IE 模式能传" —— 错，是 V6/HTML5。
- ❌ "UA/平台伪装能解锁 HTML5" —— 错，上传非 UA 嗅探分支；但 Linux UA 探查帮助定位到 V6 架构（间接有价值）。
- ❌ "有头 + 装插件能成" —— 错，ActiveX 在 Chromium 任何模式都加载不了（且本部署 ActiveX 已关）。

## 可复用脚本
- 位置：`scripts/oa_qianbao_draft.py`（已随本 skill 入册 AI工具库；原路径为 `D:\workbuddy\<日期>\oa_draft\`）
- 用法：`python oa_qianbao_draft.py <请示文件夹>`（文件夹内含一份 .docx 正文、可选 .xlsx 附件；标题默认取 docx 文件名）。
- 该脚本已固化：无验证码登录 + 空 profile + 三级菜单导航 + 填密级/标题/电话 + 尝试上传 + 保存，并对上传限制做了优雅降级。

## 流程要点（给用户的标准 SOP）
1. 空 profile 启动 Edge（避免串号）→ 打开 OA → 填 qinziyi25 / 密码 → 直接登录（无验证码）。
2. 公文管理 → 签报 → 签报起草。
3. 密级点选「无」；标题填请示标题；电话填固定电话（15971474453）。
4. 点「添加正文」上传请示正文本身（docx）；如有其他附件，点「添加附件」上传（xlsx）。
5. 点右上角「保存」存为草稿。