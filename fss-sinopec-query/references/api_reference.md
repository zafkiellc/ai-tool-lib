---
title: api_reference
type: note
permalink: main/工作/项目/资产/work-buddy-私有-skills/fss-sinopec-query/references/api-reference
---

# FSS 系统 API 参考

> 整理自 2026-08-19 实测抓包。Base：`https://fss.sinopec.com`

## 认证链路

| 步骤 | URL | 说明 |
|------|-----|------|
| 1 | `GET https://fss.sinopec.com/sso/fsso.jsp?sys=ers` | SSO 入口（sys=ers 费用报销 / sys=ssp 共享自助）|
| 2 | `GET https://auth.siam.sinopec.com/idp/profile/SAML2/Redirect/SSO?...` | SAML 重定向到 IAM |
| 3 | `POST https://auth.siam.sinopec.com/idp/Authn/TAMUserPassAuth?authenTypes=...` | 表单提交（j_username / j_password / j_checkcode）|
| 4 | 回跳 `https://fss.sinopec.com/fssue/?param=...#/home` | 登录成功 |

- 密码加密：`CryptoJS.enc.Base64.stringify(CryptoJS.enc.Utf8.parse(pw))`（页面 JS 自动处理）
- 验证码：`Kaptcha.jpg?dt=<ts>`，仅密码错误时显示（displayVerificationCode.do 判断）
- 登录成功标志：URL 含 `fssue` 且标题"财务共享平台"

## 核心业务 API（登录后）

### 1. 单据列表
```
POST /fssueservice/ers/bill/list
Content-Type: application/json
```
请求体（必填字段）：
```json
{
  "loginname": "lvch36.husy",       // 域账号（登录名.后缀）
  "empCode": "01219164",            // 员工编码
  "billType": "2",                  // 1=事前申请 2=报销单
  "startTime": "20260101#20261231", // 年份范围 # 分隔
  "billStatus": "",                 // 状态过滤
  "pageSize": 500, "currentPage": 1
}
```
响应：`data` 字段为**字符串**，需二次 JSON.parse；`data.resultList` 为单据数组。

单据字段：billCode, billTypeCode, sceneName, applyStatus, applyDate, claimant, submitTime, billAmount, remark, detailsUrl, backUrl。

> ⚠ 2026-08-19 实测：请求体**多加了未知字段会返回空**（曾加 orderBy/isPaperBill 导致全空）。字段必须与页面实际发出的一致。

### 2. 待办计数
```
POST /fssueservice/ers/bill/backlogCount        body: {"loginname":"lvch36.husy"}
POST /fssueservice/union/bill/todoSubmitCount   body: {"empCode":"01219164","loginname":"lvch36.husy",...}
POST /fssueservice/ers/bill/getErrorBacklogCount body: {"applyEmpId":"01219164"}
```

### 3. 待办列表（待审核）
```
POST /fssueservice/ers/bill/backlogs
body: {"loginname":"...","empCode":"...","pageSize":100000,"currentPage":1}
```

### 4. 单据详情（审批历史）
```
GET /fss-scene/scene_viewRmaSceneBill.action?billCode=BX-XXX
```
- 需先访问 `/fss/index.action` 建立内部会话
- 需带 `Referer: https://fss.sinopec.com/fss/index.action`
- 审批及操作记录在页面 **iframe** 内：`/fss-scene/fss/jquery/scene/<id>.html?t=...&billCode=...`

### 5. 流程/审批相关（辅助）
```
GET  /fss/from_ViewFlowShow.action?businessId=BX-XXX    → 流程图页
GET  /bpm/viewFlowShowHtml.action?businessId=BX-XXX     → 流程 HTML
GET  /bpm/getBusinessInstanceId.action?businessId=XXX   → 实例 ID
GET  /bpm/getIntanceExecutes.action?instanceId=XXX      → 节点执行状态
POST /fss-scene/scene_getAuditBaseUrl.action            → 智能审核 URL + JWT
```

## 单据类型编码（billTypeCode）

| 编码 | 类型 | 编码 | 类型 |
|------|------|------|------|
| 001 | 境内差旅报销 | 013 | 境外差旅报销 |
| 002 | 主办会议报销 | 014 | 基于合同报销 |
| 003 | 业务招待报销 | 033 | 业务情景报销单（水费/办公费/福利费等）|
| 004 | 其他费用报销 | 040 | 付款报销单 |
| 007 | 业务招待申请 | 041 | 收款报销单 |

## 审批状态枚举

已保存 / 已提交 / 审批中 / 前审中 / 后审中 / 核定中 / 审批通过 / 审批拒绝 / 已过账 / 已结算 / 已关闭 / 已作废

## 审批节点链路（标准报销单）

1. 单据填报（提交人）
2. 财务代表初审（综合办）
3. 部门领导（综合办）
4. 初审协同发起（费用报销业务二部 → 派给企业初审角色）
5. 初审协同处理（财务核算部）
6. 共享初审（费用报销业务二部，最终拒绝决定）
7. 单据提报（回到提交人 = 待提交）

> 经验：节点 4 的"核算信息缺失/错误"是真正根因；节点 5/6 的"退回不退单"是系统话术。

## 拒绝原因高频词库

| 类别 | 触发词 |
|------|--------|
| 成本中心/分摊 | 成本中心与申请事由不一致、洗车成本中心分摊错误、水费未做分摊、分摊比例不对、四新成本中心错误 |
| 超预算/情况说明 | 吨油水费/电费超标、超预算、情况说明无片区领导签字、超额原因过于简单 |
| 发票/金额 | 发票缺少数量/单位/单价、总金额与不含税金额不符、税金与分摊税金不一致 |
| 附件/明细 | 请附签收单和发放领用单、影像缺少蔬菜采购明细、私车公用需附用车协议 |
| 事由/科目 | 成本中心与申请事由不一致、请修改费用项目、已停业站点报销需补充情况说明 |