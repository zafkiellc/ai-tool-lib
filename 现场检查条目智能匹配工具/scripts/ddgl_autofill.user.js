// ==UserScript==
// @name         督导系统一键录入助手
// @namespace    http://tampermonkey.net/
// @version      1.4.7
// @description  从 inspector_matcher 工具推送的待录入条目，在 ddgl.sinopec.com 上自动：搜条目 → 定位行 → 开表单 → 填字段（含整改类型=限时整改）→ 自动点确定；并提供「全自动录入模式」开关，一键把队列全部条目依次录入
// @author       WorkBuddy
// @match        https://ddgl.sinopec.com/pc/*
// @icon         https://ddgl.sinopec.com/favicon.ico
// @grant        GM_xmlhttpRequest
// @grant        GM_addStyle
// @connect      127.0.0.1
// @run-at       document-end
// ==/UserScript==

(function () {
  'use strict';

  const API_BASE = 'http://127.0.0.1:8721';
  const FAB_ID = 'ddgl-autofill-fab';
  const POPOVER_ID = 'ddgl-autofill-pop';

  // 全自动录入队列模式开关（持久化到 localStorage）
  let autoMode = false;
  // 整改类型（默认 限时整改，可由 popover 下拉菜单切换）
  let rectifyType = '限时整改';

  // ===================== 样式 =====================
  GM_addStyle(`
    #${FAB_ID} {
      position: fixed; left: 22px; bottom: 22px; z-index: 99999;
      background: linear-gradient(135deg,#ff5e5e,#ff8a3d); color: #fff;
      border: 0; border-radius: 28px; padding: 12px 18px;
      font-size: 14px; font-weight: 600; cursor: pointer;
      box-shadow: 0 6px 20px rgba(255,94,94,.45);
      font-family: -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
      transition: transform .15s;
    }
    #${FAB_ID}:hover { transform: translateY(-2px); }
    #${FAB_ID}.active { background: linear-gradient(135deg,#7c3aed,#6d28d9); }
    #${FAB_ID}.offline { background: #999; box-shadow: none; }

    /* 简洁 popover：贴着 FAB 上方弹出，不挡整屏 */
    #${POPOVER_ID} {
      position: fixed; left: 22px; bottom: 78px; z-index: 99998;
      width: 360px; max-width: calc(100vw - 30px);
      max-height: 70vh; background: #fff; border-radius: 12px;
      box-shadow: 0 12px 40px rgba(0,0,0,.22);
      display: none; flex-direction: column;
      font-family: -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
      overflow: hidden; border: 1px solid rgba(0,0,0,.05);
    }
    #${POPOVER_ID}.show { display: flex; }
    #${POPOVER_ID} .head {
      display: flex; align-items: center; gap: 6px;
      padding: 10px 12px; background: linear-gradient(135deg,#ff5e5e,#ff8a3d); color: #fff;
    }
    #${POPOVER_ID} .head .t {
      flex: 1; font-size: 13px; font-weight: 700;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    #${POPOVER_ID} .head .ctx {
      font-size: 11px; background: rgba(255,255,255,.22);
      padding: 1px 7px; border-radius: 9px;
    }
    #${POPOVER_ID} .head .ctx.drawer,
    #${POPOVER_ID} .head .ctx.search { background: rgba(34,197,94,.7); }
    #${POPOVER_ID} .head .ctx.form { background: rgba(124,58,237,.7); }
    #${POPOVER_ID} .head .ctx.list { background: rgba(107,114,128,.7); }
    #${POPOVER_ID} .head button {
      background: rgba(255,255,255,.2); color: #fff; border: 0;
      width: 24px; height: 24px; border-radius: 6px; cursor: pointer;
      font-size: 14px; line-height: 1; padding: 0;
    }
    #${POPOVER_ID} .head button:hover { background: rgba(255,255,255,.35); }
    #${POPOVER_ID} .body { padding: 6px; overflow-y: auto; flex: 1; min-height: 60px; }
    #${POPOVER_ID} .body::-webkit-scrollbar { width: 5px; }
    #${POPOVER_ID} .body::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
    #${POPOVER_ID} .empty {
      text-align: center; color: #999; padding: 32px 8px; font-size: 12px; line-height: 1.7;
    }
    #${POPOVER_ID} .empty code { background:#f3f4f6; padding:1px 5px; border-radius:3px; }

    #${POPOVER_ID} .item {
      padding: 9px 10px; border: 1px solid #f0f0f0; border-radius: 8px;
      margin: 5px 4px; background: #fff; transition: all .15s;
    }
    #${POPOVER_ID} .item:hover { border-color: #ff8a3d; background: #fff8f0; }
    #${POPOVER_ID} .item.busy { opacity: .55; }
    #${POPOVER_ID} .item .l1 {
      display: flex; gap: 6px; align-items: center;
      font-size: 12px; color: #6b7280;
    }
    #${POPOVER_ID} .item .l1 .code {
      background: #1e3a8a; color: #fff; padding: 1px 6px;
      border-radius: 3px; font-family: ui-monospace, monospace; font-size: 11px;
    }
    #${POPOVER_ID} .item .l1 .cat {
      background: #fff3e0; color: #d35400; padding: 1px 6px; border-radius: 3px;
    }
    #${POPOVER_ID} .item .name {
      font-weight: 600; color: #1f2937; font-size: 13px; margin: 4px 0 3px;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    #${POPOVER_ID} .item .orig {
      font-size: 11px; color: #7c3a00; background: #fff7ed;
      border-left: 2px solid #ff8a3d; padding: 3px 6px; border-radius: 3px;
      word-break: break-all;
    }
    #${POPOVER_ID} .item .actions {
      display: flex; gap: 6px; margin-top: 7px; justify-content: flex-end;
    }
    #${POPOVER_ID} .item .actions button {
      border: 0; padding: 5px 11px; border-radius: 5px; cursor: pointer;
      font-size: 12px; font-weight: 600;
    }
    #${POPOVER_ID} .item .actions .fill {
      background: linear-gradient(135deg,#ff5e5e,#ff8a3d); color: #fff;
    }
    #${POPOVER_ID} .item .actions .fill:disabled { background: #ccc; cursor: not-allowed; }
    #${POPOVER_ID} .item .actions .rm {
      background: #f3f4f6; color: #6b7280;
    }
    #${POPOVER_ID} .item .actions .rm:hover { background: #fee2e2; color: #b91c1c; }
    #${POPOVER_ID} .item.ok { opacity: .5; }

    /* 顶部小提示条 */
    #${POPOVER_ID} .hintbar {
      background: #fffbeb; color: #92400e; font-size: 11px; line-height: 1.5;
      padding: 7px 10px; border-bottom: 1px solid #fde68a;
    }
    #${POPOVER_ID} .hintbar.ok { background: #f0fdf4; color: #166534; border-bottom-color: #bbf7d0; }
    #${POPOVER_ID} .hintbar.err { background: #fef2f2; color: #991b1b; border-bottom-color: #fecaca; }

    /* 诊断面板：搜索失败时显示，方便把信息反馈给我 */
    #${POPOVER_ID} .head .diag {
      background: rgba(255,255,255,.2); color: #fff; border: 0;
      width: 24px; height: 24px; border-radius: 6px; cursor: pointer;
      font-size: 13px; line-height: 1; padding: 0;
    }
    #${POPOVER_ID} .head .diag:hover { background: rgba(255,255,255,.35); }
    #${POPOVER_ID} .diag-panel {
      background: #0f172a; color: #cbd5e1; font-size: 11px; line-height: 1.55;
      padding: 9px 11px; max-height: 240px; overflow: auto;
      font-family: ui-monospace, Menlo, Consolas, monospace; white-space: pre-wrap;
      border-bottom: 1px solid #1e293b;
    }
    #${POPOVER_ID} .diag-panel .ok { color: #4ade80; }
    #${POPOVER_ID} .diag-panel .no { color: #f87171; }
    #${POPOVER_ID} .diag-panel b { color: #fbbf24; }

    /* 条目卡片内的步骤状态条 */
    #${POPOVER_ID} .item .status {
      font-size: 11px; color: #475569; margin-top: 6px; min-height: 14px;
      border-top: 1px dashed #eee; padding-top: 5px;
    }
    #${POPOVER_ID} .item .status.err { color: #b91c1c; }
    #${POPOVER_ID} .item .status.ok { color: #15803d; }

    /* 全自动录入模式：开关 + 一键按钮 */
    #${POPOVER_ID} .auto-bar {
      display: flex; align-items: center; gap: 8px;
      padding: 8px 10px; background: #f8fafc; border-bottom: 1px solid #eee;
      font-size: 12px;
    }
    #${POPOVER_ID} .auto-bar .switch {
      display: flex; align-items: center; gap: 5px; cursor: pointer; color: #374151;
      user-select: none;
    }
    #${POPOVER_ID} .auto-bar .switch input { width: auto; cursor: pointer; }
    #${POPOVER_ID} .auto-bar .rlabel {
      display: flex; align-items: center; gap: 4px; color: #374151; white-space: nowrap;
    }
    #${POPOVER_ID} .auto-bar .rlabel select {
      font: inherit; font-size: 12px; padding: 3px 6px; border: 1px solid #d1d5db;
      border-radius: 5px; background: #fff; cursor: pointer;
    }
    #${POPOVER_ID} .auto-bar .autorun {
      margin-left: auto; border: 0; border-radius: 6px; padding: 6px 12px;
      background: linear-gradient(135deg,#7c3aed,#6d28d9); color: #fff;
      font-size: 12px; font-weight: 600; cursor: pointer;
    }
    #${POPOVER_ID} .auto-bar .autorun:disabled { background: #aaa; cursor: not-allowed; }
    #${POPOVER_ID} .auto-bar .autorun.running { background: #16a34a; }
  `);

  // ===================== 工具函数 =====================
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function api(path, method, body) {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: method || 'GET',
        url: API_BASE + path,
        headers: { 'Content-Type': 'application/json' },
        data: body ? JSON.stringify(body) : undefined,
        onload: (r) => {
          try { resolve(JSON.parse(r.responseText)); }
          catch (e) { reject(e); }
        },
        onerror: () => reject(new Error('网络错误')),
        ontimeout: () => reject(new Error('超时')),
      });
    });
  }

  // 全局 toast（不影响 popover）
  function toast(msg, ms) {
    let t = document.getElementById('ddgl-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'ddgl-toast';
      Object.assign(t.style, {
        position: 'fixed', top: '20px', left: '50%', transform: 'translateX(-50%)',
        background: '#1f2937', color: '#fff', padding: '10px 18px', borderRadius: '8px',
        fontSize: '13px', zIndex: '100001', opacity: '0', transition: 'opacity .25s',
        maxWidth: '80vw', boxShadow: '0 6px 24px rgba(0,0,0,.25)',
        fontFamily: '-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif',
      });
      document.body.appendChild(t);
    }
    t.textContent = msg;
    requestAnimationFrame(() => t.style.opacity = '.96');
    clearTimeout(t._h);
    t._h = setTimeout(() => { t.style.opacity = '0'; }, ms || 2200);
  }

  // 条目卡片内的步骤状态（即时可见，便于排查）
  function setStatus(card, msg, cls) {
    if (!card) return;
    let s = card.querySelector('.status');
    if (!s) {
      s = document.createElement('div');
      s.className = 'status';
      card.appendChild(s);
    }
    s.className = 'status' + (cls ? ' ' + cls : '');
    s.textContent = msg;
    console.log('[autofill] ' + msg);
  }

  function lastDayOfMonth() {
    const d = new Date();
    const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
    return `${last.getFullYear()}-${String(last.getMonth()+1).padStart(2,'0')}-${String(last.getDate()).padStart(2,'0')}`;
  }

  function setNativeValue(el, value) {
    const proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function isVisible(el) {
    if (!el) return false;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  // ===================== 上下文探测 =====================
  // 找含"问题描述"的内层表单（Dialog / Drawer 内层 / 通用面板）
  function findOpenModal() {
    const wrappers = [
      ...document.querySelectorAll('.el-dialog__wrapper'),
      ...document.querySelectorAll('.el-dialog'),
      ...document.querySelectorAll('.el-drawer__wrapper'),
      ...document.querySelectorAll('.el-drawer'),
      ...document.querySelectorAll('.el-drawer__body-wrapper'),
    ];
    for (const w of wrappers) {
      if (!isVisible(w)) continue;
      // 必须有"问题描述"，但同时不能含四个筛选标签（即不是结果录入抽屉本身）
      const hasDesc = !!findFormItem(w, '问题描述');
      const hasCat1 = !!findFormItem(w, '一级分类');
      if (hasDesc && !hasCat1) {
        return w.querySelector('.el-dialog__body, .el-drawer__body, .el-form, form') || w;
      }
    }
    // 兜底：全页找问题描述 form-item
    const allItems = document.querySelectorAll('.el-form-item');
    for (const item of allItems) {
      const lbl = item.querySelector('.el-form-item__label');
      if (!lbl || !lbl.textContent.includes('问题描述')) continue;
      if (!isVisible(item)) continue;
      return item.closest('.el-form, form, .el-drawer__body, .el-dialog__body') || item.parentElement;
    }
    return null;
  }

  // 找"督导结果录入"抽屉（含一级分类/二级分类/检查条目 三个核心筛选）
  function findResultDrawer() {
    const wrappers = [
      ...document.querySelectorAll('.el-drawer__wrapper'),
      ...document.querySelectorAll('.el-drawer'),
      ...document.querySelectorAll('.el-dialog__wrapper'),
      ...document.querySelectorAll('.el-dialog'),
    ];
    let bestDrawer = null, bestScore = 0;
    for (const w of wrappers) {
      if (!isVisible(w)) continue;
      const hasCat1 = !!findFormItem(w, '一级分类');
      const hasCat2 = !!findFormItem(w, '二级分类');
      const hasItem = !!findFormItem(w, '检查条目');
      // 至少包含两个核心标签，且优先选分高的（四个标签都包含 > 三个 > 两个）
      const score = (hasCat1?1:0) + (hasCat2?1:0) + (hasItem?1:0) + (findFormItem(w,'状态')?1:0);
      if (score >= 2 && score > bestScore) {
        bestScore = score; bestDrawer = w;
      }
    }
    return bestDrawer;
  }

  // 找"列表页的督导行"——返回该行 + 该行的"问题/编辑/查看"链接
  function findListPageRow() {
    // 在主区域里找"+问题/问题/编辑问题/查看"按钮（不在抽屉内）
    const all = document.querySelectorAll('button, a, .el-button, span[role="button"]');
    for (const el of all) {
      if (!isVisible(el)) continue;
      if (el.closest('.el-drawer, .el-drawer__wrapper, .el-dialog, .el-dialog__wrapper')) continue;
      const t = (el.textContent || '').trim();
      // 列表行的操作列里常见"+问题/问题/编辑问题/查看"
      if (/^\+?问题$|^编辑问题$|^查看$/.test(t)) {
        const row = el.closest('tr') || el.closest('.el-table__row');
        return { row, action: el };
      }
    }
    return null;
  }

  // 当前页面上下文：form(内层表单) | search(含「检查条目」搜索框的页面，可直接搜) | list(纯列表页)
  function detectContext() {
    if (findOpenModal()) return 'form';
    if (findDrawerSearchInput(document)) return 'search';
    return 'list';
  }

  // ===================== 通用辅助 =====================
  function findFormItem(scope, labelText) {
    const root = scope || document;
    const items = root.querySelectorAll('.el-form-item');
    for (const item of items) {
      const lbl = item.querySelector('.el-form-item__label');
      if (lbl && lbl.textContent.trim().replace(/[:：*\s]/g, '').includes(labelText)) {
        return item;
      }
    }
    return null;
  }

  function findButtonByText(scope, text) {
    const all = scope.querySelectorAll('button, a, span');
    for (const el of all) {
      if (!isVisible(el)) continue;
      if (el.textContent.trim() === text) return el;
    }
    return null;
  }

  function findTextElement(scope, text) {
    const all = scope.querySelectorAll('*');
    for (const el of all) {
      if (el.children.length > 0) continue;
      if (el.textContent.trim() === text) return el;
    }
    for (const el of all) {
      if (el.children.length > 0) continue;
      if (el.textContent.trim().includes(text)) return el;
    }
    return null;
  }

  function rowCellTexts(row) {
    return Array.from(row.querySelectorAll('td .cell, td'))
      .map(c => c.textContent.trim()).filter(Boolean);
  }

  async function setSelectFirst(formItem) {
    const wrapper = formItem.querySelector('.el-select');
    if (!wrapper) return false;
    const input = wrapper.querySelector('.el-input__inner, input');
    if (input && input.value.trim()) return true;
    const caret = wrapper.querySelector('.el-select__caret') || wrapper;
    caret.click();
    await sleep(280);
    const dropdowns = document.querySelectorAll('.el-select-dropdown');
    for (const dd of dropdowns) {
      if (window.getComputedStyle(dd).display === 'none' || !dd.offsetParent) continue;
      const items = dd.querySelectorAll('.el-select-dropdown__item');
      for (const it of items) {
        if (it.classList.contains('is-disabled') || it.classList.contains('selected')) continue;
        it.click();
        await sleep(200);
        return true;
      }
    }
    return false;
  }

  async function setDateToLastDay(formItem) {
    const input = formItem.querySelector('input');
    if (!input) return false;
    input.focus();
    await sleep(60);
    setNativeValue(input, '');
    await sleep(60);
    setNativeValue(input, lastDayOfMonth());
    await sleep(60);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
    input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
    input.blur();
    await sleep(120);
    return true;
  }

  // ===================== 核心填表 =====================
  function highlightInnerForm(modal) {
    try {
      modal.classList.add('ddgl-auto-filled');
      let on = true;
      const blink = setInterval(() => {
        modal.classList.toggle('ddgl-auto-filled', on);
        on = !on;
      }, 350);
      setTimeout(() => { clearInterval(blink); modal.classList.add('ddgl-auto-filled'); }, 1800);
    } catch (e) {}
  }

  async function fillInnerForm(modal, item) {
    const errs = [];

    // 1. 问题描述
    const descItem = findFormItem(modal, '问题描述');
    if (!descItem) { toast('❌ 未找到"问题描述"字段'); return false; }
    const ta = descItem.querySelector('textarea, input');
    if (!ta) { toast('❌ "问题描述"无文本框'); return false; }
    const text = (item.orig && String(item.orig).trim())
      ? String(item.orig).trim()
      : ((item.short || item.name || '') + (item.desc ? '。' + item.desc : ''));
    setNativeValue(ta, '');
    await sleep(80);
    setNativeValue(ta, text);

    // 2. 扣分 = 0
    const scoreItem = findFormItem(modal, '扣分');
    if (scoreItem) {
      const input = scoreItem.querySelector('input');
      if (input) setNativeValue(input, '0');
      else errs.push('扣分(input)未找到');
    } else errs.push('未找到"扣分"字段');

    // 3. 整改负责人（如空选第一个）
    const ownerItem = findFormItem(modal, '整改负责人');
    if (ownerItem) {
      const ok = await setSelectFirst(ownerItem);
      if (!ok) errs.push('整改负责人无法选择');
    } else errs.push('未找到"整改负责人"字段');

    // 4. 整改期限 = 本月最后一天
    const dateItem = findFormItem(modal, '整改期限');
    if (dateItem) {
      const ok = await setDateToLastDay(dateItem);
      if (!ok) errs.push('整改期限无法设置');
    } else errs.push('未找到"整改期限"字段');

    // 5. 整改类型 = 当前选中值（默认 限时整改；表单无此字段则跳过，不报错）
    const typeItem = findFormItem(modal, '整改类型');
    if (typeItem) {
      const ok = await setSelectByText(typeItem, rectifyType);
      if (!ok) errs.push('整改类型无法选择');
    }

    highlightInnerForm(modal);

    // 6. 录入后自动点击「确定」完成提交（仅在已成功写入问题描述后）
    const okConfirm = await clickConfirm(modal);
    if (errs.length) toast('已填写（部分字段待确认）：' + errs.join('；') + (okConfirm ? '，已自动点确定' : ''));
    else toast('✅ 已自动填写并点确定（整改类型=' + rectifyType + '）');
    return true;
  }

  // 在下拉（el-select）中按文本选择：优先含目标文本的选项，否则选第一个可用项
  async function setSelectByText(formItem, text) {
    const wrapper = formItem.querySelector('.el-select');
    if (!wrapper) return false;
    const caret = wrapper.querySelector('.el-select__caret') || wrapper;
    caret.click();
    await sleep(300);
    const dropdowns = document.querySelectorAll('.el-select-dropdown');
    let picked = false;
    for (const dd of dropdowns) {
      if (!isVisible(dd)) continue;
      const opts = dd.querySelectorAll('.el-select-dropdown__item');
      let target = null;
      for (const o of opts) {
        if (o.classList.contains('is-disabled')) continue;
        if ((o.textContent || '').includes(text)) { target = o; break; }
      }
      if (!target) {
        for (const o of opts) { if (!o.classList.contains('is-disabled')) { target = o; break; } }
      }
      if (target) { target.click(); picked = true; await sleep(200); break; }
    }
    return picked;
  }

  // 在当前表单/页面里找并点击「确定」按钮（退路：保存/提交）
  async function clickConfirm(modal) {
    const scope = modal || document;
    const btns = scope.querySelectorAll('button, .el-button');
    for (const b of btns) {
      if (!isVisible(b)) continue;
      if ((b.textContent || '').replace(/\s/g, '') === '确定') { b.click(); return true; }
    }
    for (const b of btns) {
      if (!isVisible(b)) continue;
      const t = (b.textContent || '').replace(/\s/g, '');
      if (/确定|保存|提交/.test(t)) { b.click(); return true; }
    }
    return false;
  }

  // 在抽屉里找"检查条目"搜索框（多策略：标签 / 占位符 / 远程搜索下拉 / 任意结构）
  // 返回 { input, kind } 或 null
  function findDrawerSearchInput(scope) {
    const labels = ['检查条目', '检查项', '检查内容', '条目'];
    // 1) el-form-item 内：标签含 检查条目 / 检查项 / 检查内容 / 条目
    for (const lab of labels) {
      const fi = findFormItem(scope, lab);
      if (fi) {
        const inp = fi.querySelector('input');
        if (inp && isVisible(inp)) return { input: inp, kind: 'input', label: lab };
      }
    }
    // 2) 任意位置（不限定 el-form-item）：叶子元素文本等于"检查条目/检查项/..."，找它的兄弟/父级 input
    for (const el of scope.querySelectorAll('*')) {
      if (el.children.length > 0) continue;        // 只看叶子
      if (!isVisible(el)) continue;
      const t = (el.textContent || '').trim().replace(/[:：*\s·•・]/g, '');
      if (!t) continue;
      for (const lab of labels) {
        if (t === lab) {
          const inp = findNearbyInput(el);
          if (inp && isVisible(inp)) return { input: inp, kind: 'input', label: lab + '(label-任意结构)' };
        }
      }
    }
    // 3) 任意 input 的 placeholder 含 检查 / 条目
    for (const inp of scope.querySelectorAll('input')) {
      if (!isVisible(inp)) continue;
      const ph = (inp.getAttribute('placeholder') || '');
      if (/检查|条目|检查项|检查内容/.test(ph)) return { input: inp, kind: 'input', label: 'placeholder:' + ph };
    }
    // 4) 远程搜索下拉 el-select（filterable/remote）：标签或 placeholder 含 检查/条目
    for (const sel of scope.querySelectorAll('.el-select')) {
      if (!isVisible(sel)) continue;
      const fi = sel.closest('.el-form-item');
      const lblEl = fi && fi.querySelector('.el-form-item__label');
      const txt = lblEl ? lblEl.textContent : '';
      const ph = sel.querySelector('input') ? (sel.querySelector('input').getAttribute('placeholder') || '') : '';
      if (/检查|条目|检查项/.test(txt) || /检查|条目/.test(ph)) {
        const inp = sel.querySelector('input');
        if (inp) return { input: inp, kind: 'select', label: txt || ph };
      }
    }
    return null;
  }

  // 给定一个 label-like 元素，找它"附近"的 input（先同级，再父级内，再祖父级内）
  function findNearbyInput(labelEl) {
    // a) 自己就是 input
    if (labelEl.tagName === 'INPUT') return labelEl;
    // b) 父级内 input
    const p = labelEl.parentElement;
    if (p) {
      const inp = p.querySelector('input');
      if (inp) return inp;
    }
    // c) 下一个兄弟 input
    let n = labelEl.nextElementSibling;
    if (n && n.tagName === 'INPUT') return n;
    if (n && n.querySelector) {
      const inp = n.querySelector('input');
      if (inp) return inp;
    }
    // d) 祖父级内 input（同一行的其他 cell）
    const pp = p ? p.parentElement : null;
    if (pp) {
      const inp = pp.querySelector('input');
      if (inp) return inp;
    }
    // e) 父级下一个兄弟（label 和 input 在同一 form-item 的兄弟节点）
    const next = p ? p.nextElementSibling : null;
    if (next) {
      const inp = next.querySelector('input');
      if (inp) return inp;
    }
    return null;
  }

  // 在抽屉里找"查询/搜索"按钮（宽松匹配：包含即可，忽略空白/图标）
  function findDrawerQueryBtn(scope) {
    for (const b of scope.querySelectorAll('button, .el-button')) {
      const t = (b.textContent || '').replace(/\s/g, '');
      if (/查询|搜索|检索|筛选|查 询/.test(t)) return b;
    }
    // 退路：带 search 图标的按钮
    for (const b of scope.querySelectorAll('button')) {
      if (b.querySelector('i.el-icon-search, [class*="icon-search"], svg')) return b;
    }
    return null;
  }

  // 在表格里找匹配行（按 短标题 + 二级分项 / 一级分类，分数取最高）；scope 可为 drawer 或 document
  function findRowInTable(scope, item) {
    const table = scope.querySelector('.el-table');
    if (!table) return null;
    const rows = table.querySelectorAll('tbody tr.el-table__row, .el-table__body tr, tr.el-table__row');
    const short = (item.short || item.name || '').trim();
    const cat2 = (item.cat2 || '').trim();
    const cat1 = (item.cat1 || '').trim();
    let best = null, bestScore = 0;
    for (const row of rows) {
      if (!isVisible(row)) continue;
      const cells = rowCellTexts(row);
      const shortMatch = short && cells.some(c => c.includes(short));
      const cat2Match = cat2 && cells.some(c => c === cat2 || c.includes(cat2));
      const cat1Match = cat1 && cells.some(c => c === cat1 || c.includes(cat1));
      let score = 0;
      if (shortMatch && cat2Match) score = 5;
      else if (shortMatch && cat1Match) score = 4;
      else if (cat2Match && cat1Match) score = 3;
      else if (shortMatch) score = 2;
      else if (cat1Match) score = 1;
      if (score > bestScore) { bestScore = score; best = row; }
    }
    return best;
  }

  // 在页面（drawer 或整页）的"检查条目"搜索框里输入并触发查询
  async function searchInDrawer(scope, keyword, card) {
    const found = findDrawerSearchInput(scope);
    if (!found) {
      const e = new Error('未找到「检查条目」搜索框（已尝试 标签/占位符/远程下拉 三种方式）');
      e.code = 'NO_SEARCH_BOX';
      throw e;
    }
    const { input, kind } = found;
    const inputDesc = kind === 'select'
      ? '远程搜索下拉（' + found.label + '）'
      : '文本输入框（' + found.label + '）';
    setStatus(card, '① 在「' + inputDesc + '」输入：' + keyword, '');
    input.focus();
    setNativeValue(input, '');
    await sleep(120);
    setNativeValue(input, keyword);
    await sleep(250);
    input.dispatchEvent(new Event('input', { bubbles: true }));

    if (kind === 'select') {
      // 远程搜索下拉：等下拉出现，选第一个含关键词或第一项
      await sleep(500);
      const dropdowns = document.querySelectorAll('.el-select-dropdown');
      let picked = false;
      for (const dd of dropdowns) {
        if (!isVisible(dd)) continue;
        const opts = dd.querySelectorAll('.el-select-dropdown__item');
        for (const o of opts) {
          if (o.classList.contains('is-disabled')) continue;
          o.click(); picked = true; break;
        }
        if (picked) break;
      }
      setStatus(card, picked ? '② 已选择下拉项，等待列表刷新…' : '② 下拉无选项（可能需先输入更多字符）', picked ? '' : 'err');
      await sleep(1000);
    } else {
      // 文本输入：Enter + 点击「查询」按钮
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
      input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }));
      await sleep(200);
      const qb = findDrawerQueryBtn(scope);
      if (qb) { qb.click(); setStatus(card, '② 已点击「' + qb.textContent.replace(/\s/g, '') + '」按钮，等待列表刷新…', ''); }
      else { setStatus(card, '② 未找到查询按钮，已触发回车，等待列表刷新…', ''); }
      await sleep(1100);
    }
  }

  // 判断一个元素是否"可点击"（含 cursor:pointer / onclick / 标签是 A 或 BUTTON / role=button）
  function isClickableEl(el) {
    if (!el) return false;
    const tag = el.tagName;
    if (tag === 'A' || tag === 'BUTTON') return true;
    if (el.getAttribute('role') === 'button') return true;
    if (el.onclick) return true;
    try {
      const cs = window.getComputedStyle(el);
      if (cs && cs.cursor === 'pointer') return true;
    } catch (e) {}
    return false;
  }

  // 向上爬 N 层找第一个"可点击"祖先
  function findClickableAncestor(el, maxDepth) {
    let p = el, depth = 0;
    while (p && depth < (maxDepth || 5)) {
      if (isClickableEl(p)) return p;
      p = p.parentElement;
      depth++;
    }
    return null;
  }

  // 规范化"操作文本"：全角＋→半角+，去空白；兼容「＋问题」「+ 问题」等变体
  function cleanPlus(t) {
    return (t || '').replace(/[＋+＋]/g, '+').replace(/\s/g, '');
  }
  // 判断某元素的 textContent 是否像"打开问题表单"的操作入口
  function isActionText(t) {
    if (!t) return false;
    const c = cleanPlus(t);
    if (c === '问题' || c === '+问题') return true;
    return /问题登记|新增问题|录入问题|添加问题|查看问题|编辑问题|检查条目|登记问题/.test(t);
  }

  // 在行内找"问题/+问题/编辑问题/检查条目"等操作入口
  // 关键：不要求它是叶子元素 —— 兼容 <span><i class="el-icon-plus"></i>问题</span> 这种带图标子节点的结构
  // 策略：取 textContent 含操作关键词且【最短】的元素（即最内层那个链接），对它（或其可点击祖先）派发 click
  // 返回 { ok, label, via } 或 { ok: false }
  function findActionEl(row) {
    let best = null, bestLen = 999;
    for (const el of row.querySelectorAll('*')) {
      const t = (el.textContent || '').replace(/\s/g, '');
      if (!t) continue;
      if (!isActionText(t)) continue;
      if (t.length < bestLen) { bestLen = t.length; best = el; }   // 取最短 → 最内层
    }
    return best;
  }

  function clickRowEntryLink(row) {
    const target = findActionEl(row);
    if (target) {
      // 优先点可点击祖先（A/BUTTON/role=button/onclick/cursor:pointer），否则直接点最内层元素
      // el.click() 派发的事件会冒泡，span 上的 Vue @click 也能触发
      const anc = findClickableAncestor(target, 8);
      const clickEl = anc || target;
      try {
        clickEl.click();
        return { ok: true, label: (target.textContent || '').trim(), via: (clickEl === target ? 'self(' + target.tagName + ')' : 'ancestor(' + clickEl.tagName + ')') };
      } catch (e) {}
    }
    // 退路：操作列（最后一列 / __action / cursor:pointer）兜底
    const cells = row.querySelectorAll('td:last-child, .el-table_1_column_last, [class*="__action"]');
    for (const cell of cells) {
      for (const el of cell.querySelectorAll('*')) {
        if (!isVisible(el)) continue;
        const cs = window.getComputedStyle(el);
        if (cs.cursor === 'pointer') {
          const t = (el.textContent || '').trim();
          if (t && t.length <= 16) { el.click(); return { ok: true, label: t, via: 'cursor-pointer' }; }
        }
      }
    }
    return { ok: false, label: '', via: 'none' };
  }

  // 把某行的完整 HTML + 行内"问题"相关元素清单 dump 出来，便于定位"+问题"真实结构
  // 不限于叶子元素（兼容 <span><i></i>问题</span> 带图标子节点的结构）
  function dumpRowHtml(row) {
    if (!row) return '';
    let s = '【匹配行完整 HTML】\n' + truncateHtml(row.outerHTML, 5000);
    // 用与点击一致的"最短匹配文本"逻辑列出"问题"相关元素，并附带其 HTML 片段
    const items = [];
    for (const el of row.querySelectorAll('*')) {
      const t = (el.textContent || '').replace(/\s/g, '');
      if (!t || !isActionText(t)) continue;
      const clickable = isClickableEl(el)
        ? '可点击'
        : (findClickableAncestor(el, 5) ? '祖先可点击' : '不可点击');
      items.push('· "' + t + '" <' + el.tagName + ' class="' + (el.className || '') + '"> → ' + clickable +
        '\n  HTML: ' + truncateHtml(el.outerHTML, 320));
    }
    if (items.length) s += '\n\n【匹配行内"问题"相关元素（' + items.length + '）】\n' + items.join('\n');
    else s += '\n\n【匹配行内"问题"相关元素】未找到（说明本行确实没有 +问题 入口，可能需先展开/进入下一级）';
    // 额外：把最后一个单元格（通常是操作列）原样 dump，避免被整行截断掩盖
    const tds = row.querySelectorAll('td');
    if (tds.length) {
      const lastTd = tds[tds.length - 1];
      s += '\n\n【匹配行最后一个单元格 HTML】\n' + truncateHtml(lastTd.outerHTML, 2000);
    }
    return s;
  }

  // 诊断：把当前页面（整页）的搜索相关 DOM 信息汇总，便于反馈
  function diagnosePage() {
    const r = { lines: [] };
    const sb = findDrawerSearchInput(document);
    r.searchBox = !!sb;
    if (sb) r.lines.push('<span class="ok">✓ 找到搜索框</span> = <b>' + (sb.label || '') + '</b> (' + (sb.kind === 'select' ? '远程下拉' : '文本输入') + ')');
    else r.lines.push('<span class="no">✗ 未找到「检查条目」搜索框（已尝试 标签/占位符/远程下拉/任意结构）</span>');
    const qb = findDrawerQueryBtn(document);
    r.queryBtn = !!qb;
    r.lines.push(qb ? ('<span class="ok">✓ 查询按钮</span> = <b>' + qb.textContent.replace(/\s/g, '') + '</b>') : '<span class="no">✗ 未找到查询按钮</span>');
    // 列出所有可见的 el-form-item 标签（帮助看清标准 form 结构）
    const allFormItems = document.querySelectorAll('.el-form-item');
    const labelList = [];
    for (const fi of allFormItems) {
      if (!isVisible(fi)) continue;
      const lbl = fi.querySelector('.el-form-item__label');
      if (lbl) {
        const raw = (lbl.textContent || '').trim();
        const norm = raw.replace(/[:：*\s·•・]/g, '');
        if (norm) labelList.push(norm + (raw !== norm ? '(raw="' + raw + '")' : ''));
      }
    }
    if (labelList.length) {
      r.lines.push('所有 el-form-item 标签（' + labelList.length + '）：<b>' + labelList.join(' / ').slice(0, 600) + '</b>');
    } else {
      r.lines.push('（页面内没有可见的 el-form-item，可能用了非标准表单结构）');
    }
    // 列出含"检查/条目"文字的叶子元素（帮助找出非标准 label）
    const checkEls = [];
    for (const el of document.querySelectorAll('*')) {
      if (el.children.length > 0) continue;
      if (!isVisible(el)) continue;
      const t = (el.textContent || '').trim();
      if (t && t.length < 30 && /检查|条目/.test(t)) checkEls.push(t);
    }
    if (checkEls.length) {
      r.lines.push('含"检查/条目"文字的叶子元素（' + checkEls.length + '）：<b>' + Array.from(new Set(checkEls)).join(' | ').slice(0, 500) + '</b>');
    }
    const table = document.querySelector('.el-table');
    if (table) {
      const rows = table.querySelectorAll('tbody tr.el-table__row, .el-table__body tr, tr.el-table__row');
      r.lines.push('表格行数：<b>' + rows.length + '</b>');
      const sample = [];
      for (let i = 0; i < Math.min(3, rows.length); i++) {
        const txt = rowCellTexts(rows[i]).slice(0, 4).join(' | ');
        if (txt) sample.push('· ' + txt);
      }
      if (sample.length) r.lines.push('示例行：\n' + sample.join('\n'));
    } else r.lines.push('<span class="no">✗ 页面内无 .el-table 表格</span>');
    return r;
  }

  function truncateHtml(s, n) {
    s = String(s || '');
    return s.length > n ? s.slice(0, n) + '\n...(已截断)' : s;
  }

  // 导出当前页面关键结构，便于把真实 DOM 反馈给我以修正选择器
  function dumpPageStructure() {
    const parts = [];
    const sb = findDrawerSearchInput(document);
    if (sb) {
      const fi = sb.input.closest('.el-form-item, form, .el-form-item__content') || sb.input.parentElement;
      parts.push('【搜索框(input) HTML】\n' + truncateHtml(sb.input.outerHTML, 600));
      parts.push('【搜索框所在容器 HTML】\n' + truncateHtml(fi ? fi.outerHTML : sb.input.parentElement.outerHTML, 1400));
    }
    const qb = findDrawerQueryBtn(document);
    if (qb) {
      // 把"查询"按钮所在 form 区域也 dump 出来，看清查询区的整体结构
      const qbForm = qb.closest('form, .el-form, .search-bar, .filter-bar, .query-bar, .el-row') || qb.parentElement;
      parts.push('【查询按钮 HTML】\n' + truncateHtml(qb.outerHTML, 400));
      parts.push('【查询按钮所在区域 HTML】\n' + truncateHtml(qbForm.outerHTML, 1800));
    }
    // 列出所有可见的 form-item 简短信息（只列可见的，限 30 条）
    const allFormItems = document.querySelectorAll('.el-form-item');
    const fiLines = [];
    for (const fi of allFormItems) {
      if (!isVisible(fi)) continue;
      const lbl = fi.querySelector('.el-form-item__label');
      const inp = fi.querySelector('input, textarea');
      const tag = (lbl ? (lbl.textContent || '').trim().replace(/[:：*\s·•・]/g, '') : '?');
      if (tag === '?') continue;
      fiLines.push('· 标签="' + tag + '" input=' + (inp ? (inp.tagName + (inp.placeholder ? '(ph=' + inp.placeholder + ')' : '')) : '无'));
      if (fiLines.length >= 30) break;
    }
    if (fiLines.length) parts.push('【所有 el-form-item 简表】\n' + fiLines.join('\n'));
    // 含"检查/条目"文字的叶子元素（用于发现非标准 label）
    const checkEls = [];
    for (const el of document.querySelectorAll('*')) {
      if (el.children.length > 0) continue;
      if (!isVisible(el)) continue;
      const t = (el.textContent || '').trim();
      if (t && t.length < 30 && /检查|条目/.test(t)) checkEls.push(t);
    }
    if (checkEls.length) parts.push('【含"检查/条目"的叶子元素】\n' + Array.from(new Set(checkEls)).join(' | ').slice(0, 500));
    const table = document.querySelector('.el-table');
    if (table) {
      const head = table.querySelector('.el-table__header-wrapper, thead, .el-table__header');
      if (head) parts.push('【表头 HTML】\n' + truncateHtml(head.outerHTML, 600));
      const rows = table.querySelectorAll('tbody tr.el-table__row, .el-table__body-wrapper tr.el-table__row, .el-table__body tr, tr.el-table__row');
      for (let i = 0; i < Math.min(2, rows.length); i++) {
        parts.push('【表格行' + (i + 1) + ' HTML】\n' + truncateHtml(rows[i].outerHTML, 1200));
      }
    }
    return parts.join('\n\n');
  }

  function showDiag(rep, dump) {
    const el = document.getElementById('ddgl-diag');
    if (!el) return;
    el.style.display = 'block';
    let html = rep.lines.join('\n');
    if (dump) {
      html += '\n\n<b>— 页面结构（点「复制结构」粘贴反馈给我）—</b>\n'
            + '<button id="ddgl-copy-dump" style="margin:4px 0;background:#2563eb;color:#fff;border:0;border-radius:4px;padding:4px 10px;cursor:pointer;">📋 复制结构</button>\n'
            + truncateHtml(dump, 6000);
    }
    el.innerHTML = html;
    const copyBtn = el.querySelector('#ddgl-copy-dump');
    if (copyBtn) copyBtn.addEventListener('click', () => {
      const text = el.innerText;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          () => toast('已复制页面结构，请粘贴反馈', 2600),
          () => toast('复制失败，请手动选择文本复制', 2600)
        );
      } else {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); toast('已复制页面结构，请粘贴反馈', 2600); }
        catch (e) { toast('复制失败，请手动选择文本复制', 2600); }
        document.body.removeChild(ta);
      }
    });
    console.log('[autofill-diag] ' + rep.lines.join(' | ').replace(/<[^>]+>/g, ''));
  }

  // 列表页：找可打开「督导结果录入」抽屉的入口（+问题 / 新增问题 / 问题录入 等）
  // 兼容 button / a / 可点击 span / 可点击 div / 含 onclick 的元素（含 <i>+文本 结构）
  function findListPageNewProblem() {
    // 1) 明确文字匹配（button/a/.el-button）
    const btns = document.querySelectorAll('button, .el-button, a');
    for (const el of btns) {
      if (!isVisible(el)) continue;
      if (el.closest('.el-drawer, .el-drawer__wrapper, .el-dialog, .el-dialog__wrapper')) continue;
      const t = (el.textContent || '').replace(/\s/g, '');
      if (isActionText(t)) return el;
    }
    // 2) 任意元素（不限标签、不限叶子）含"问题/+问题"等操作文本 → 取最短最内层，点自己或祖先
    let best = null, bestLen = 999;
    for (const el of document.querySelectorAll('*')) {
      if (el.closest('.el-drawer, .el-drawer__wrapper, .el-dialog, .el-dialog__wrapper')) continue;
      if (!isVisible(el)) continue;
      const t = (el.textContent || '').replace(/\s/g, '');
      if (!t || !isActionText(t)) continue;
      if (t.length < bestLen) { bestLen = t.length; best = el; }
    }
    if (best) {
      const anc = findClickableAncestor(best, 4);
      return anc || best;
    }
    // 3) 退路：列表行操作列里的"问题/编辑问题/查看"链接
    const lr = findListPageRow();
    if (lr && lr.action) return lr.action;
    return null;
  }

  // 依次尝试多个关键词搜索 + 定位行（搜索框可能按 一级分类 / 短标题 / 二级分项 索引，逐一尝试）
  async function trySearchAndFind(scope, item, card) {
    const short = (item.short || item.name || '').trim();
    const cat2 = (item.cat2 || '').trim();
    const cat1 = (item.cat1 || '').trim();
    // 顺序：一级分类优先（搜索框多按一级分类索引），其次短标题，再次二级分项
    const keys = [];
    if (cat1) keys.push(cat1);
    if (short && short !== cat1) keys.push(short);
    if (cat2 && cat2 !== cat1 && cat2 !== short) keys.push(cat2);
    if (!keys.length) keys.push(short || cat2 || cat1);
    for (let i = 0; i < keys.length; i++) {
      const kw = keys[i];
      setStatus(card, '① 用关键词搜索：' + kw, '');
      await searchInDrawer(scope, kw, card);
      const row = findRowInTable(scope, item);
      if (row) return row;
      setStatus(card, '· 关键词「' + kw + '」未匹配到行' + (i < keys.length - 1 ? '，换下一个…' : ''), '');
    }
    return null;
  }

  // ===================== 主入口：智能判断 =====================
  async function autofillSmart(item, card) {
    try {
      const ctx = detectContext();
      setStatus(card, '上下文：' + ({ form: '已开内层表单', search: '搜索页就绪（含检查条目搜索框）', list: '列表页' }[ctx] || ctx), '');

      // 1) 优先：内层录入表单已开 → 直接填
      let modal = findOpenModal();
      if (modal) {
        setStatus(card, '✓ 内层表单已开，直接填写…', 'ok');
        return await fillInnerForm(modal, item);
      }

      // 2) 搜索页（含「检查条目」搜索框）→ 直接搜 + 找行 + 打开内层 + 填（全程自动，无需手动打开）
      const sb = findDrawerSearchInput(document);
      if (sb) {
        const scope = sb.input.closest('.el-drawer, .el-drawer__wrapper, .el-dialog, .el-dialog__wrapper') || document;
        const keywordFirst = (item.cat1 || item.short || item.name || '').trim();
        if (!keywordFirst) {
          setStatus(card, '✗ 该条目无一级分类/短标题，无法搜索', 'err');
          toast('⚠ 该条目无一级分类/短标题，无法搜索');
          return false;
        }
        toast('🔍 在搜索框输入：' + keywordFirst);
        const row = await trySearchAndFind(scope, item, card);
        if (!row) {
          setStatus(card, '✗ 搜索后未匹配到行（请点 🔧 看诊断）', 'err');
          toast('❌ 当前页面未匹配到对应项目（一级"' + (item.cat1 || '') + '" / 短标题"' + (item.short || '') + '"）', 3800);
          showDiag(diagnosePage(), dumpPageStructure());
          return false;
        }
        row.scrollIntoView({ block: 'center', behavior: 'instant' });
        row.style.background = '#fef3c7';
        setTimeout(() => { row.style.background = ''; }, 2000);
        setStatus(card, '③ 已定位行并高亮，正在点击打开表单…', '');
        const linkRes = clickRowEntryLink(row);
        if (!linkRes.ok) {
          setStatus(card, '✗ 匹配行内没找到"问题/+问题"链接', 'err');
          toast('❌ 匹配行内没找到"问题/+问题"链接，点 🔧 看匹配行结构', 3800);
          showDiag(diagnosePage(), dumpPageStructure() + '\n\n' + dumpRowHtml(row));
          return false;
        }
        setStatus(card, '③ 已点击「' + linkRes.label + '」（' + linkRes.via + '），等待表单…', '');
        for (let i = 0; i < 30; i++) {
          await sleep(200);
          modal = findOpenModal();
          if (modal) break;
        }
        if (!modal) {
          setStatus(card, '✗ 点击行后未打开内层表单', 'err');
          toast('❌ 点击行后未打开内层表单', 3800);
          return false;
        }
        setStatus(card, '④ 内层表单已开，填写中…', '');
        const okFill = await fillInnerForm(modal, item);
        if (okFill) setStatus(card, '✓ 已自动填写，请人工核对后点「确定」', 'ok');
        return okFill;
      }

      // 3) 纯列表页 → 尝试自动点开「+问题/问题录入」入口，打开后再走搜索流程
      const trigger = findListPageNewProblem();
      if (trigger) {
        const tTxt = (trigger.textContent || '').replace(/\s/g, '');
        setStatus(card, '① 列表页：点击「' + (tTxt || '问题') + '」尝试打开录入页…', '');
        trigger.click();
        await sleep(1600);
        const sb2 = findDrawerSearchInput(document);
        if (!sb2) {
          setStatus(card, '✗ 点击后未出现「检查条目」搜索框', 'err');
          toast('⚠ 已点击「' + tTxt + '」但未进入含搜索框的录入页，请手动进入后再点 🚀', 4500);
          return false;
        }
        const scope = sb2.input.closest('.el-drawer, .el-drawer__wrapper, .el-dialog, .el-dialog__wrapper') || document;
        const keywordFirst = (item.cat1 || item.short || item.name || '').trim();
        toast('🔍 已进入录入页，搜索：' + keywordFirst);
        const row = await trySearchAndFind(scope, item, card);
        if (!row) {
          setStatus(card, '✗ 搜索后未匹配到行', 'err');
          toast('❌ 录入页未匹配到对应项目', 3800);
          showDiag(diagnosePage(), dumpPageStructure());
          return false;
        }
        row.scrollIntoView({ block: 'center', behavior: 'instant' });
        row.style.background = '#fef3c7';
        setTimeout(() => { row.style.background = ''; }, 2000);
        setStatus(card, '③ 已定位行并高亮，正在点击打开表单…', '');
        const linkRes = clickRowEntryLink(row);
        if (!linkRes.ok) {
          setStatus(card, '✗ 匹配行内没找到"问题/+问题"链接', 'err');
          toast('❌ 匹配行内没找到链接，点 🔧 看匹配行结构', 3800);
          showDiag(diagnosePage(), dumpPageStructure() + '\n\n' + dumpRowHtml(row));
          return false;
        }
        setStatus(card, '③ 已点击「' + linkRes.label + '」（' + linkRes.via + '），等待表单…', '');
        for (let i = 0; i < 30; i++) {
          await sleep(200);
          modal = findOpenModal();
          if (modal) break;
        }
        if (!modal) {
          setStatus(card, '✗ 点击行后未打开内层表单', 'err');
          toast('❌ 点击行后未打开内层表单', 3800);
          return false;
        }
        setStatus(card, '④ 内层表单已开，填写中…', '');
        const okFill = await fillInnerForm(modal, item);
        if (okFill) setStatus(card, '✓ 已自动填写，请人工核对后点「确定」', 'ok');
        return okFill;
      }

      setStatus(card, '⚠ 当前页面既无「检查条目」搜索框，也无「问题」入口', 'err');
      toast('⚠ 请确认你已打开含「检查条目」搜索框的录入页（或督导列表里点一条记录进入）', 4500);
      return false;
    } catch (e) {
      const msg = (e && e.message) || String(e);
      setStatus(card, '✗ 异常：' + msg, 'err');
      console.error('[autofill] 异常:', e);
      toast('❌ 录入失败：' + msg, 4000);
      return false;
    }
  }

  // ===================== UI 注入 =====================
  function makeFab() {
    if (document.getElementById(FAB_ID)) return;
    const btn = document.createElement('button');
    btn.id = FAB_ID;
    btn.innerHTML = '📋 待录入 <span class="count">--</span>';
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      togglePopover();
    });
    document.body.appendChild(btn);
  }

  function makePopover() {
    if (document.getElementById(POPOVER_ID)) return;
    const pop = document.createElement('div');
    pop.id = POPOVER_ID;
    pop.innerHTML = `
      <div class="head">
        <span class="t">📋 待录入 (<span class="count">0</span>)</span>
        <span class="ctx list" id="ddgl-ctx">列表页</span>
        <button class="diag" title="诊断当前抽屉（搜索失败时用它把信息反馈给我）" id="ddgl-diag-btn">🔧</button>
        <button class="refresh" title="刷新" id="ddgl-refresh">↻</button>
        <button class="close" title="关闭" id="ddgl-close">✕</button>
      </div>
      <div class="auto-bar">
        <label class="rlabel" title="录入时自动在表单「整改类型」下拉里选中的值">整改类型
          <select id="ddgl-rectype">
            <option>限时整改</option>
            <option>立即整改</option>
            <option>限期整改</option>
            <option>立行立改</option>
            <option>长期整改</option>
          </select>
        </label>
        <label class="switch" title="勾选后点「🚀 全自动录入」会依次把队列里所有条目自动录入（自动选整改类型、自动点确定）">
          <input type="checkbox" id="ddgl-auto-mode"> <span>全自动录入模式</span>
        </label>
        <button id="ddgl-auto-run" class="autorun">🚀 全自动录入</button>
      </div>
      <div class="hintbar" id="ddgl-hint" style="display:none;"></div>
      <div class="diag-panel" id="ddgl-diag" style="display:none;"></div>
      <div class="body" id="ddgl-body">
        <div class="empty">暂无待录入<br>在工具页（inspector_matcher.html）选用条目后点「🚀 一键录入」</div>
      </div>`;
    document.body.appendChild(pop);
    pop.querySelector('#ddgl-close').addEventListener('click', hidePopover);
    pop.querySelector('#ddgl-refresh').addEventListener('click', () => { renderList(); refreshCtx(); });
    pop.querySelector('#ddgl-diag-btn').addEventListener('click', () => {
      const rep = diagnosePage();
      const dump = dumpPageStructure();
      showDiag(rep, dump);
      if (!rep.searchBox) toast('未找到「检查条目」搜索框，已导出页面结构请粘贴反馈', 3500);
      else toast('诊断已输出到面板，请确认框的归属正确（标签=检查条目？），不对就把结构粘贴反馈给我', 3500);
    });
    // 全自动录入模式开关
    const autoChk = pop.querySelector('#ddgl-auto-mode');
    if (autoChk) {
      autoChk.checked = !!autoMode;
      autoChk.addEventListener('change', (e) => {
        autoMode = e.target.checked;
        try { localStorage.setItem('ddgl-auto-mode', autoMode ? '1' : ''); } catch (err) {}
        toast(autoMode ? '已开启全自动录入模式' : '已关闭全自动录入模式', 1500);
      });
    }
    const autoRunBtn = pop.querySelector('#ddgl-auto-run');
    if (autoRunBtn) autoRunBtn.addEventListener('click', () => autoFillAll());
    // 整改类型下拉（默认 限时整改）
    const rectypeSel = pop.querySelector('#ddgl-rectype');
    if (rectypeSel) {
      rectypeSel.value = rectifyType;
      rectypeSel.addEventListener('change', (e) => {
        rectifyType = e.target.value;
        try { localStorage.setItem('ddgl-rectype', rectifyType); } catch (err) {}
        toast('整改类型将设为：' + rectifyType, 1500);
      });
    }
    // 点击 popover 内部不冒泡关闭
    pop.addEventListener('click', (e) => e.stopPropagation());
    // 点击外部关闭
    document.addEventListener('click', (e) => {
      const pop = document.getElementById(POPOVER_ID);
      if (!pop || !pop.classList.contains('show')) return;
      if (pop.contains(e.target)) return;
      if (e.target.id === FAB_ID || e.target.closest(`#${FAB_ID}`)) return;
      hidePopover();
    });
  }

  function togglePopover() {
    const pop = document.getElementById(POPOVER_ID);
    const fab = document.getElementById(FAB_ID);
    if (!pop) return;
    if (pop.classList.contains('show')) {
      hidePopover();
    } else {
      showPopover();
    }
  }
  function showPopover() {
    if (!document.getElementById(POPOVER_ID)) makePopover();
    const pop = document.getElementById(POPOVER_ID);
    pop.classList.add('show');
    document.getElementById(FAB_ID).classList.add('active');
    renderList();
    refreshCtx();
  }
  function hidePopover() {
    const pop = document.getElementById(POPOVER_ID);
    if (pop) pop.classList.remove('show');
    const fab = document.getElementById(FAB_ID);
    if (fab) fab.classList.remove('active');
  }

  function refreshCtx() {
    const el = document.getElementById('ddgl-ctx');
    if (!el) return;
    const ctx = detectContext();
    el.className = 'ctx ' + ctx;
    if (ctx === 'form') el.textContent = '✓ 已开表单';
    else if (ctx === 'search') el.textContent = '✓ 搜索页就绪';
    else el.textContent = '列表页';

    // 提示条
    const hint = document.getElementById('ddgl-hint');
    if (!hint) return;
    if (ctx === 'list') {
      hint.className = 'hintbar';
      hint.style.display = 'block';
      hint.textContent = '请打开含「检查条目」搜索框的录入页（督导列表点一条记录进入），再回来点 🚀。';
    } else if (ctx === 'search') {
      hint.className = 'hintbar ok';
      hint.style.display = 'block';
      hint.textContent = '已检测到「检查条目」搜索框。点 🚀 后会自动搜索、定位行、点开表单、填字段，全程无需手动。';
    } else {
      hint.className = 'hintbar ok';
      hint.style.display = 'block';
      hint.textContent = '已检测到内层表单。点 🚀 将直接填字段。';
    }
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  async function renderList() {
    const body = document.querySelector(`#${POPOVER_ID} #ddgl-body`);
    const headCount = document.querySelector(`#${POPOVER_ID} .head .count`);
    let data;
    try { data = await api('/api/pending', 'GET'); }
    catch (e) {
      body.innerHTML = '<div class="empty">⚠️ 无法连接本地服务（' + API_BASE + '）<br>请先运行 <code>start.bat</code> 启动服务。</div>';
      if (headCount) headCount.textContent = '✗';
      return;
    }
    const items = data.items || [];
    if (headCount) headCount.textContent = items.length;
    if (items.length === 0) {
      body.innerHTML = '<div class="empty">暂无待录入<br><br>在工具页（inspector_matcher.html）选用条目后点「🚀 一键录入」</div>';
      return;
    }
    body.innerHTML = items.map((it) => `
      <div class="item" data-id="${escapeHtml(it.id)}">
        <div class="l1">
          <span class="code">${escapeHtml(it.code || '')}</span>
          <span class="cat">${escapeHtml(it.cat1 || '')} / ${escapeHtml(it.cat2 || '')}</span>
        </div>
        <div class="name" title="${escapeHtml(it.short || it.name || '')}">${escapeHtml(it.short || it.name || '')}</div>
        <div class="orig" title="${escapeHtml(it.orig || '')}">原文：${escapeHtml(it.orig || '')}</div>
        <div class="actions">
          <button class="rm" data-id="${escapeHtml(it.id)}" title="从队列移除">移除</button>
          <button class="fill" data-id="${escapeHtml(it.id)}">🚀 一键录入</button>
        </div>
      </div>`).join('');

    body.querySelectorAll('button.rm').forEach((b) => {
      b.addEventListener('click', async (e) => {
        e.stopPropagation();
        await api('/api/remove', 'POST', { id: b.dataset.id });
        renderList(); updateFabCount();
      });
    });
    body.querySelectorAll('button.fill').forEach((b) => {
      b.addEventListener('click', async (e) => {
        e.stopPropagation();
        const it = items.find((x) => x.id === b.dataset.id);
        if (!it) return;
        const card = b.closest('.item');
        b.disabled = true; b.textContent = '处理中…';
        if (card) card.classList.add('busy');
        const ok = await autofillSmart(it, card);
        b.disabled = false; b.textContent = '🚀 一键录入';
        if (card) card.classList.remove('busy');
        if (ok) {
          card.classList.add('ok');
          setTimeout(async () => {
            await api('/api/remove', 'POST', { id: it.id });
            renderList(); updateFabCount();
          }, 800);
        } else {
          // 失败时再刷一次上下文（抽屉/表单状态可能变了）
          refreshCtx();
        }
      });
    });
  }

  // 简单转义，用于属性选择器里的 id（id 多为字母数字，这里只转义引号与反斜杠）
  function cssEscape(s) {
    return String(s == null ? '' : s).replace(/["\\]/g, '\\$&');
  }

  // 全自动录入：依次把队列里所有条目自动录入（含自动选整改类型、自动点确定）
  async function autoFillAll() {
    const runBtn = document.getElementById('ddgl-auto-run');
    // 先尝试关掉可能残留的表单，避免后续搜索失败
    let stray = findOpenModal();
    if (stray) {
      const cb = findButtonByText(stray, '取消') || findButtonByText(stray, '关闭') || findButtonByText(stray, '✕');
      if (cb) { cb.click(); await sleep(400); }
    }
    let data;
    try { data = await api('/api/pending', 'GET'); }
    catch (e) { toast('⚠ 无法连接本地服务', 3000); return; }
    const items = (data.items || []).slice();
    if (!items.length) { toast('队列为空，无可录入项', 2500); return; }
    if (runBtn) { runBtn.disabled = true; runBtn.classList.add('running'); runBtn.textContent = '⏳ 录入中…'; }
    toast('🚀 全自动录入开始：共 ' + items.length + ' 条', 2500);
    let done = 0, fail = 0;
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const card = document.querySelector(`#${POPOVER_ID} .item[data-id="${cssEscape(it.id)}"]`);
      setStatus(card, '全自动录入 ' + (i + 1) + '/' + items.length + '：' + (it.short || it.name || ''), '');
      // 若上一条表单未自动关闭，先关闭
      let m2 = findOpenModal();
      if (m2) {
        const cb = findButtonByText(m2, '取消') || findButtonByText(m2, '关闭') || findButtonByText(m2, '✕');
        if (cb) { cb.click(); await sleep(400); }
      }
      const ok = await autofillSmart(it, card);
      if (ok) {
        done++;
        await sleep(1600);  // 等表单关闭与列表刷新
        try { await api('/api/remove', 'POST', { id: it.id }); } catch (e) {}
      } else {
        fail++;
        toast('⚠ 第 ' + (i + 1) + ' 条录入失败，跳过', 2500);
        await sleep(800);
      }
      updateFabCount();
    }
    if (runBtn) { runBtn.disabled = false; runBtn.classList.remove('running'); runBtn.textContent = '🚀 全自动录入'; }
    renderList();
    toast('✅ 全自动录入完成：成功 ' + done + ' / 失败 ' + fail, 4000);
  }

  async function updateFabCount() {
    const btn = document.getElementById(FAB_ID);
    if (!btn) return;
    try {
      const data = await api('/api/pending', 'GET');
      const n = (data.items || []).length;
      btn.querySelector('.count').textContent = n;
      btn.classList.remove('offline');
      const headCount = document.querySelector(`#${POPOVER_ID} .head .count`);
      if (headCount) headCount.textContent = n;
    } catch (e) {
      btn.querySelector('.count').textContent = '✗';
      btn.title = '本地服务未启动（请运行 start.bat）';
      btn.classList.add('offline');
    }
  }

  // ===================== 启动 =====================
  function init() {
    makeFab();
    makePopover();
    try { autoMode = !!localStorage.getItem('ddgl-auto-mode'); } catch (e) {}
    try { const rt = localStorage.getItem('ddgl-rectype'); if (rt) rectifyType = rt; } catch (e) {}
    updateFabCount();
    setInterval(updateFabCount, 5000);
    // 每 2 秒刷新 popover 内的上下文状态
    setInterval(() => {
      const pop = document.getElementById(POPOVER_ID);
      if (pop && pop.classList.contains('show')) refreshCtx();
    }, 2000);
  }

  if (document.body) init();
  else document.addEventListener('DOMContentLoaded', init);

})();
