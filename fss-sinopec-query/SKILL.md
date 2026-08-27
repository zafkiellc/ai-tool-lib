---
name: fss-sinopec-query
description: 查询中国石化 FSS 费用报销系统（https://fss.sinopec.com）数据。当用户要求查询报销单据、审批状态、审批拒绝原因、待办汇总、借款还款、事前申请等
  FSS 系统数据，或需要抓取 FSS 审批历史/审批意见时使用。支持 SSO 自动登录、单据列表抓取、审批历史解析、拒绝原因归类与汇总报告生成。账号凭据由用户现场提供，不硬编码。
agent_created: true
permalink: main/工作/项目/资产/work-buddy-私有-skills/fss-sinopec-query/skill
---

# FSS 中石化报销系统数据查询

## Overview

自动化访问中国石化 FSS 财务共享自助服务门户（https://fss.sinopec.com），完成：
1. SSO 登录（域账号 + 密码，密码明文填入由页面 JS 加密）
2. 抓取"我的单据"列表（按 billType 区分事前申请/报销单/借款/还款等）
3. 抓取单张单据的审批历史（审批及操作记录，含审批意见）
4. 提取"审批拒绝"单据的最新拒绝意见，按词库归类，生成汇总报告

**重要**：账号密码由用户现场提供，**绝不写入任何文件、脚本或本 SKILL**。本机沙盒可直接访问公司内网（无网络隔离）。

## 工作流决策树

```
用户要求查 FSS 数据
   │
   ├─ 只需列表数据（单据编号/状态/金额/事由）
   │     └─ 用 scripts/fetch_bills.py（基于已存会话）
   │
   ├─ 需要审批历史/拒绝原因
   │     ├─ 会话有效 → scripts/fetch_rejected_details.py
   │     └─ 会话过期 → scripts/login_fss.py 先登录
   │
   └─ 需要汇总报告
         └─ clean_rejections.py 清洗 + 生成 MD/HTML 报告
```

## Step 1: 登录（scripts/login_fss.py）

**前置**：确保 Python venv 存在：`C:\Users\zafki\.workbuddy\binaries\python\envs\default\Scripts\python.exe`

**关键经验（踩坑记录）**：
- ❌ 不要用 `form.submit()` 直接提交 —— 会绕过页面 JS 的 Base64 密码加密，服务器收到明文 → "认证失败"
- ❌ 不要先手动 Base64 加密再填入 —— `validateLoginFields()` 会二次加密 → 双重 Base64 → 认证失败
- ✅ 正确姿势：**填明文密码** → 点击 `button.loginBt`（触发页面自身 `validateLoginFields` 加密 + 提交）
- ✅ 密码正确时验证码区 `display:none`，无需验证码；密码错才会出现验证码（用户已确认）
- ✅ 登录后会话保存到 `fss_state.json`，后续脚本复用 `storage_state` 无需重复登录

```bash
PY="C:/Users/zafki/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" scripts/login_fss.py
```

脚本内 USERNAME/PASSWORD 需用户提供（脚本从环境变量或命令行读取更安全，当前版本直接在脚本内定义）。

登录成功标志：URL 变为 `https://fss.sinopec.com/fssue/?param=...#/home`，页面标题"财务共享平台"。

## Step 2: 抓取单据列表（scripts/fetch_bills.py）

调用 API：
```
POST https://fss.sinopec.com/fssueservice/ers/bill/list
Content-Type: application/json
body: {"loginname":"lvch36.husy","empCode":"01219164","sceneCode":"","compCode":"",
       "billType":"2","startTime":"20260101#20261231","billCode":"","reiEmpName":"",
       "remark":"","billStatus":"","pageSize":500,"currentPage":1,"quotaType":"",
       "billTypeCode":"","fromBillAmount":"","toBillAmount":"","billState":"",
       "contractNum":"","suppCode":"","suppName":"","selArchive":"","isReplace":""}
```

**billType 枚举**：
| billType | 含义 | 备注 |
|----------|------|------|
| 1 | 事前申请 | SQ- 单号 |
| 2 | 报销单 | BX- 单号（463 条量级） |
| 3-10 | 借款/还款/暂估/支付等 | 多数为空 |

**applyStatus 枚举**：审批中 / 审批通过 / 已关闭 / 前审中 / 后审中 / 核定中 / 已过账 / 审批拒绝 / 已保存 / 已结算 / 已作废

**返回结构**：`data` 是 JSON 字符串，解析后 `data.resultList` 为单据数组，字段含：billCode, sceneName, applyStatus, applyDate, billAmount, remark, detailsUrl, claimant, submitTime。

**关键发现**：`billType=2` 中 `审批拒绝 33 条 + 已保存 12 条 = 45`，正好等于主页"待提交 45"计数。拒绝单都在报销单 Tab 下。

## Step 3: 抓取审批历史（scripts/fetch_rejected_details.py）

**关键经验（踩坑记录）**：
- ❌ 直连 `detailsUrl`（`scene_viewRmaSceneBill.action?billCode=xxx`）→ 报"非法访问!"
- ✅ 必须先访问 `https://fss.sinopec.com/fss/index.action` 建立内部会话
- ✅ 必须设置 `Referer: https://fss.sinopec.com/fss/index.action` 请求头
- ✅ 审批及操作记录在页面 **iframe** 内（URL 含 `fss/jquery/scene/`），需遍历 `pg.frames` 找到 iframe 取 `content()`
- 审批历史表格列：序号 | 执行步骤 | 审批人员 | 组织机构 | 操作说明 | 审批结果 | 审批意见 | 审批时间

**审批节点链路**：单据填报 → 财务代表初审 → 部门领导 → 初审协同发起 → 初审协同处理 → 共享初审 → 单据提报

**系统话术识别**：节点 5/6 的"退回不退单"、"企业要求退回不通知"是系统自动话术，**真正根因在上一步"初审协同发起/处理"的审批意见**。提取意见时要向上找最早的非"同意"行。

## Step 4: 清洗与归类（scripts/clean_rejections.py）

- 从审批历史中提取所有"拒绝"行（审批结果含"拒绝"）
- 取**最新一条有实质内容的拒绝意见**（跳过纯系统话术如"退回不退单"、"请修改"）
- 按关键词粗分类：成本中心/分摊 / 超预算/情况说明 / 发票金额 / 附件明细 / 事由科目 / 其他

**拒绝原因词库（高频）**：
| 类别 | 关键词 |
|------|--------|
| 成本中心/分摊 | 成本中心、分摊、四新、洗车 |
| 超预算/情况说明 | 超标、预算、超额、情况说明、领导签字 |
| 发票/金额 | 发票、数量、单位、单价、税金、不含税 |
| 附件/明细 | 附件、影像、签收、领用、明细、清单 |
| 事由/科目 | 事由、不符、费用项目、停业 |

## Step 5: 生成汇总报告

输出两个文件（模板参考 2026-08-19 交付）：
- `汇总报告_审批拒绝.md` — 分类统计 + 单据明细表 + 修复建议
- `汇总报告_审批拒绝.html` — 深色主题可发布版（直接可打开预览）

报告结构：① 拒绝原因分类统计表 ② 单据明细表（单号/情景/金额/日期/最新拒绝意见/节点人）③ 核心问题归纳与修复建议。

## 环境与依赖

- Python venv: `C:\Users\zafki\.workbuddy\binaries\python\envs\default\Scripts\python.exe`
- Playwright（已装），浏览器用 `channel='msedge'`（本机 Edge 路径 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`），`headless=True`
- 工作目录：`D:\workbuddy\报销\`（会话文件 `fss_state.json`、抓取产物 json、报告）
- 网络：本机可直连 fss.sinopec.com（DNS → 10.249.41.151），沙盒无隔离

## 安全红线

1. **账号密码绝不写入任何文件**（脚本、json、md、html 均不可含密码）
2. 抓取频率 ≤ 1 次/30s，不并发登录，避免风控
3. 出现验证码立即暂停，请用户浏览器手动处理，**不接第三方打码**
4. 会话文件 `fss_state.json` 属敏感凭据，注意保管

## Resources

### scripts/
- `login_fss.py` — SSO 登录 + 保存会话（用户名/密码在脚本内按用户提供值填写）
- `fetch_bills.py` — 抓取"我的单据"列表全量（各 billType）
- `fetch_rejected_details.py` — 遍历审批拒绝单据，抓审批历史
- `clean_rejections.py` — 提取最新拒绝意见 + 归类

### references/
- `api_reference.md` — FSS API 接口清单与请求/响应结构