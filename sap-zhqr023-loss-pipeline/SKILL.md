---
name: sap-zhqr023-loss-pipeline
description: SAP ZHQR023 油品进销付存自动拉数 + 损耗排名/看板/通报 全管线。当用户要求"拉取 SAP 油品进销付存数据、刷新月度损耗排名、生成汉阳损耗看板/每日损耗通报"，或排查"SAP
  日期字段无法自动填写、导出中文站名丢失、Excel/WPS 文件锁定、查询字段怎么改"等问题时使用。Windows 桌面自动化（pywin32 + sapshcut），关键技法是"点击聚焦
  + 剪贴板 Ctrl+V 绕开中文 IME"。
when_to_use: 用户要求拉 SAP ZHQR023 数据、刷损耗排名/看板/通报，或卡在 SAP 日期字段、导出乱码/站名丢失、文件锁时。
agent_created: true
permalink: main/工作/项目/资产/work-buddy-私有-skills/sap-zhqr023-loss-pipeline/skill-1
---

# SAP ZHQR023 油品进销付存自动拉数管线

## ⚠️ 两类数据口径（2026-08-23 用户指正，防止混淆）
| 数据 | 来源 | 口径 | 用途 |
|---|---|---|---|
| **进销存** | **SAP ZHQR023** (run_zhqr023_auto.py) | **销项** | **公司损耗排名/通报模板**（@损耗统计表同源）、汉阳看板 |
| 进货验收 | 液位仪系统 (fetch_jhys.py) | 进项/卸油 | 卸油损溢分析、全公司进油验收通报 |
- **公司通报模板口径**（@损耗统计表 8.21 sheet）：销量=col10小计、损耗=col24当期损耗、损耗率=损耗/销量×1000；
  片区归属用 col2 零售片区代码；排名=合计损耗率从低到高（1=最优）；站点sheet按损耗率降序。
- **必须剔除公司模板不含的站**（特许加盟/他有他营/移库专用等 19 站），否则特许加盟站巨额负损耗污染片区合计
  （例：黄陂幸福加油站 92# −24229L → 黄陂从正常 1.20‰ 算成 −29‰）。剔除 = 只保留 @损耗统计表 8.21 sheet 存在的站。
- 全公司模板 xlsx 生成：`损耗通报_自动生成/gen_company_rank.py`（每日自动化通用版：自动找最新 SAP 全公司 xlsx、自动当天日期命名输出）。

## 目标
Windows 桌面 SAP GUI 自动化：查"油品进销付存"（事务码 ZHQR023）本月1日~今日数据 → 导出 MHTML → 转 xlsx → 刷新月度损耗排名表 + 汉阳损耗看板 + 每日损耗通报。**全程一键脚本化**（`run_zhqr023_auto.py`）。

## 运行环境（必须）
- 用隔离 venv python 跑（系统 python 缺 pywin32）：
  `C:\Users\zafki\.workbuddy\binaries\python\envs\default\Scripts\python.exe`
- 依赖：`pywin32`(win32com/win32clipboard/win32con) + `openpyxl`。
- SAP 启动器：`C:\Program Files (x86)\SAP\FrontEnd\SAPgui\sapshcut.exe`

## 账号与范围（关键）
| 账号 | 范围 | 用途 |
|---|---|---|
| `lijj2257`（B10/Client800） | **仅汉阳** 1 片区，**有 ZHQR023 权限** ✅ | 日常汉阳损耗 |
| `lvch36`（液位仪账号，密码通用） | **能登录 SAP 但无 ZHQR023 权限** ❌ | 不能跑 ZHQR023 |
| `xiaoy1206`（省级/全公司权限，密码存 `~/.workbuddy/sap_credentials.env`） | **能进 ZHQR023** ✅（全公司范围待确认） | **全公司通报**首选 |
| `qinziyi25`（全省权限） | 全武汉/全省所有片区（待验证 ZHQR023 权限） | 备选 |

> **账号权限实测（2026-08-22）**：`lvch36` 密码与液位仪通用（能登 B10），但 `/nZHQR023` 进不去（卡"轻松访问"）→ 液位仪"市公司权限"≠ SAP ZHQR023 权限，两系统授权分离。
> `xiaoy1206`（密码存 `~/.workbuddy/sap_credentials.env`，base64）**能进 ZHQR023** ✅（但选屏 `=ONLI` 未出结果屏，疑需填公司代码，全公司范围未确认）。还原密码：`PWD=$(sed -n 's/^SAP_PWD_B64_XIAOY="\(.*\)"$/\1/p' ~/.workbuddy/sap_credentials.env | base64 -d)`（**勿用 cut -d=，base64 含 `==` 会被切断**）。
> 测账号：`SAP_USER=X SAP_PWD=Y python probe_lvch36_6.py`。

> **⚠️ 全公司通报的正确路径 = 液位仪系统，不是 SAP ZHQR023！**（2026-08-22 复盘）
> SAP ZHQR023(lijj2257/xiaoy1206) 只能拉**汉阳**或未确认范围。**全公司(9片区)数据用 `xiaoy1206` 从液位仪系统拉"进货验收"**：
> - 拉数：`python ~/.workbuddy/skills/液位仪系统数据查询/scripts/fetch_jhys.py`（内网直连，Playwright，产"进油验收报表*.xls"）
> - 生成通报：`python .../损耗通报_自动生成/gen_company_jhys_report.py`（9片区汽油损溢率Vt排名+汉阳后3站）→ `考核指标/全公司进油验收通报_*.html`
> - 密码同 `~/.workbuddy/sap_credentials.env`（xiaoy1206）。详见 `液位仪系统数据查询` skill。

> **⚠️⚠️ SAP 登录账号被 .SAP 快捷方式锁死（2026-08-22 最致命教训）**：
> 桌面快捷方式 `零管系统...油品进销付存查询.SAP` 里 `[User] Name=LIJJ2257` **硬编码了 lijj2257**。
> 脚本命令行 `sapshcut -system=B10 -client=800 -user=xiaoy1206 -pw=...` **看似传了 xiaoy1206，但 SAP Logon 实际仍加载/登录 .SAP 绑定的 lijj2257** → "用 xiaoy1206 登录"是假象，真实一直是 lijj2257（只有汉阳权限）→ 所以怎么试都出不了全公司结果，且 lijj2257/xiaoy1206 表现一样（同一账号）。
> **要真正用别的账号登录，必须从主程序 SAP Logon 740 手动选系统/输账号，或用不绑定账号的启动方式，登录后先确认真实账号**（勿假设 -user 参数生效）。

## 执行 OK code 的关键（SendInput 回车）
- 写文本用 `WM_SETTEXT`（cid=1001 Edit），**回车必须用全局 `SendInput` 真实键盘** `tap(0x0D)`。
- SendMessage/PostMessage 的 `WM_KEYDOWN VK_RETURN` 会被 SAP 自绘控件忽略（probe5 对比 probe6 实锤）。

## ⚠️ 等待必须用轮询（2026-08-23 全公司数据教训，最高优先级）
- **SAP 大查询（尤其全公司/多片区）`=ONLI` 后加载要很久**（683 行 vs 汉阳 97 行，MHTML 1.1MB vs 170KB）。
- **绝对不要固定 sleep 几秒后单次检查就判失败**——loading 没结束会被误判。
- **必须轮询**：每 10 秒检测一次标题/对话框/文件，最长 5 分钟（`timeout=300, poll=10`）。
- 已封装在 `sap_zhqr_helpers.py`：`wait_title_contains` / `wait_file_exists` / `wait_top_dialog`。
- 步骤4 =ONLI 等"商品"标题、步骤5 &XXL 等"另存为"对话框、步骤6 等 MHTML 文件，全部用轮询。
- 教训：曾因固定 wait=10 秒误判全公司 =ONLI 失败（用户亲眼确认"其实已出结果，只是 loading"）。

## 一键管线（`C:\Users\zafki\WorkBuddy\Claw\sap\run_zhqr023_auto.py`）
1. `kill_sap()` + 删旧 `C:\Users\zafki\Desktop\export.MHTML`（先清残留）
2. `sapshcut -system=B10 -client=800 -user=... -pw=... -language=ZH` → `/nZHQR023`
3. **填"查阅期限-从"**（IME-proof，见下）
4. OK code Edit(cid=1001) `WM_SETTEXT` 发 `=ONLI` 执行
5. 再发 `&XXL` 导出 → 弹标准 `#32770 另存为`
6. 另存为：`cid=1148` 文件名框改 `C:\Users\zafki\Desktop\export.MHTML` + `cid=1` 保存按钮 `BM_CLICK`
7. 解析 MHTML(`Mappe1.htm` 单表) → 注入 26 列表头 → 写 `油品进销付存_YYYYMMDD-YYYYMMDD.xlsx`
8. `update_ranking(sap_path=...)` 刷 7 透视表（Excel COM）
9. `gen_dashboard_daily.main()` 刷 `汉阳损耗看板.html`
10. `gen_notify_only` 生成 `每日损耗通报_YYYYMMDD.html`

## 核心技术：怎么改"查阅期限-从"字段（死磕点，IME-proof）
**根因**：中文输入法(IME)拦截 SendInput 的 `KEYEVENTF_UNICODE` 字符事件 → "输入法报错卡住"。**不是**沙箱/服务端/Afx 自绘的锅。
**杀招**：**剪贴板 Ctrl+V 粘贴走剪贴板，不经过 IME 组词**，中文输入法下也拦不住。

> **⚠️⚠️ 最高优先级：公司代码默认 3400，禁止点击/填写（2026-08-23 用户亲眼确认）⚠️⚠️**
> 选屏第一行"公司代码"默认已填好 3400，**进选屏后直接跳过，绝不要点击它、绝不要 Ctrl+A/Backspace/粘贴**。
> 教训：点击公司代码 → Ctrl+A+Backspace 清掉默认 3400 → 焦点跳下一行 → 公司代码被填进起始日期，后续全错位。
> **正确流程：只点一次"查阅期限-从"(340,180) → 粘贴起始日期 → =ONLI，"到"留默认。**

标准做法：
1. `MoveWindow(hwnd,0,0,1100,800,True)` 钉窗口到左上角（坐标可预测）
2. **直接** `SetCursorPos(340,180)+mouse_event` 点击，聚焦"查阅期限-从"（**不要点公司代码行**）→ `caret_pos()` 返回 `focus=Afx:792B0000:1008`（确认命中；rcCaret 是**控件内坐标**，不是屏幕坐标）
3. 切英文输入法双保险：`ActivateKeyboardLayout(0x04090409,0)` + `PostMessageW(hwnd,0x0050,1,0x04090409)`
4. `win32clipboard.SetClipboardData(CF_UNICODETEXT,'2026.08.01')` → `Ctrl+A` + `Ctrl+V`
5. "到"留 SAP 默认（=今日）；执行用 OK code `=ONLI`（比 F8 稳，F8 焦点不在字段会失效）
6. `run_zhqr023_auto.py` 步骤3 已按此规则：只 `fill_field(hwnd, 340, 180, FROM_STR)`，**无任何公司代码操作**

## 两个必踩的坑（已修复）
1. **中文站名丢失**：解析 MHTML 时**不要** `quopri.decodestring(块.encode('latin-1',errors='ignore'))`——
   latin-1 装不下中文，`errors='ignore'` 会把"油站名"全丢只剩代码 31000033。
   该 MHTML 块是 `Content-Transfer-Encoding:text/html + charset=utf-8` 明文，**直接当 UTF-8 用**即可保留全名 `31000033 武汉汉阳邹家湾加油站`。
2. **站级销量 join 为 0**：SAP 导出 col3=`代码 全名`，排名表"图表"sheet col1=短名(邹家湾)，格式不同 join 不上。
   → 用 `Claw/sap/station_map.py`（代码/全名/短名三向映射，SAP 29 站↔图表 25 站）。
   **排名表"当期数据"col3 必须保持 SAP 原始"编码+站名"，绝不额外加工成短名**（用户明确要求，否则他表匹配不上）。
   短名映射只在**读取端**做：`gen_dashboard_daily` 从 col3 取编码 → `CODE_SHORT[code]` → join `图表` 站名算销量（25/25 非零）。

## 纯 ctypes 剪贴板写/读的坑（2026-08-23 新增，崩溃修复）
- 若不想依赖 pywin32 的 win32clipboard，可用 `sap_zhqr_helpers.set_clipboard`（ctypes 写 CF_UNICODETEXT）。
- **必须同时设 `restype=c_void_p` 和 `argtypes=[c_void_p]`**，对
  `GlobalAlloc/GlobalLock/GlobalFree/GlobalSize/GetClipboardData/SetClipboardData` 逐个设置，
  否则 ctypes 把 64 位句柄符号扩展为负数 → `GlobalLock`/`SetClipboardData` 报
  `OverflowError: int too long to convert`（经典崩溃）。
- 剪贴板回读验证日期字段：SAP 分段控件 Ctrl+A 全选可能只选中"年"段 → 回读只剩 `2026`，**不代表值不完整**；
  以 `=ONLI` 是否进结果屏为准。

## 通报综合损耗率/总销量为 0 的修复（2026-08-23）
- 原因：通报从 `ws_chart`(图表sheet短名) 读站名，去 join `当期数据`(编码+全名) 的销量 → key 不匹配 → 全 0。
- 修复：综合损耗率/总销量**直接从 `当期数据` sheet 汇总**：`total_sale=Σcol9`, `sum_loss=Σcol24`,
  `loss_rate=sum_loss/total_sale*1000`（与看板加权口径一致）。

## 文件锁定（非 Excel）
`update_ranking` 报"文件正被其他程序使用"，`taskkill EXCEL.EXE` 无效 → 真凶是 **WPS**。
跑前 `taskkill /F /IM EXCEL.EXE 2>nul` + `taskkill /F /IM WPS.exe 2>nul` 都杀。

## 口径
- 综合损耗率 = Σ(当期数据 col24 当期损耗) / Σ(col9 总计) ×1000（**加权口径**，非简单平均）。
- 当期数据 col3 = **原始"编码+站名"**（不改）；站级销量在读取端取编码 → `CODE_SHORT` → 图表短名 → join。
- 鑫龙2(33155649) 不参与排名，`read_sap_hanyang` 删除。

## 脚本位置
- `C:\Users\zafki\WorkBuddy\Claw\sap\`（run_zhqr023_auto.py / sap_ui.py / station_map.py / gen_notify_only.py）
- `C:\Users\zafki\Downloads\LxResource\LxResource\Docs\2026-08\`（update_loss_ranking.py / gen_dashboard_daily.py / 油品进销付存_*.xlsx）
- 输出：`C:\Users\zafki\OneDrive\工作\安数\考核指标\`（8月损耗排名.xlsx / 汉阳损耗看板.html / 每日损耗通报_*.html）