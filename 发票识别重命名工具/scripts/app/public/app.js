'use strict';

const state = {
  sources: [],
  template: '{remark}_{amount}_{invoice}',
  mode: 'inplace',
  outputDir: '',
  extractSingleZip: false,
  dedupe: true
};

const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `请求失败 (${res.status})`);
  return data;
}

function sanitizeName(name) {
  return String(name || '')
    .replace(/[\\/:*?"<>|\x00-\x1f]/g, '_')
    .replace(/\s+/g, ' ')
    .replace(/[. ]+$/, '')
    .trim()
    .slice(0, 180);
}

function previewBase(meta, template) {
  const values = {
    remark: meta.title || '',
    station: meta.station || '',
    project: meta.project || '',
    amount: meta.amount || '',
    invoice: meta.invoiceNo || ''
  };
  let out = template || '{remark}_{amount}_{invoice}';
  for (const [k, v] of Object.entries(values)) {
    out = out.split(`{${k}}`).join(v);
  }
  out = out.replace(/_+/g, '_').replace(/^_+|_+$/g, '');
  return sanitizeName(out);
}

function targetName(source, base) {
  if (source.type === 'zip') return `${base}.zip`;
  const ext = source.ext || (source.entryName ? source.entryName.slice(source.entryName.lastIndexOf('.')) : '.pdf');
  return `${base}${ext}`;
}

function refreshNames() {
  for (const s of state.sources) {
    if (!s.meta || !s.meta.invoiceNo) continue;
    s.newName = targetName(s, previewBase(s.meta, state.template));
  }
  renderTable();
}

function esc(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function addLog(message, type) {
  const list = $('logList');
  const empty = list.querySelector('.log-empty');
  if (empty) empty.remove();
  const div = document.createElement('div');
  div.className = `log-line ${type || 'info'}`;
  div.textContent = message;
  list.prepend(div);
}

function appendPaths(paths) {
  const ta = $('pathInput');
  const existing = new Set(ta.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean));
  const fresh = paths.filter((p) => p && !existing.has(p));
  if (fresh.length === 0) return;
  ta.value = [...existing, ...fresh].join('\n');
}

function statusBadge(s) {
  const labels = { ok: '正常', attention: '需确认', error: '失败' };
  const cls = s.status === 'ok' ? 'ok' : s.status === 'attention' ? 'attention' : 'error';
  let html = `<span class="badge ${cls}">${labels[s.status] || s.status}</span>`;
  if (s.warnings && s.warnings.length) {
    html += `<ul class="warn-list">${s.warnings.map((w) => `<li>${esc(w)}</li>`).join('')}</ul>`;
  }
  return html;
}

function renderTable() {
  const tbody = $('tableBody');
  tbody.innerHTML = '';
  if (state.sources.length === 0) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="9">扫描后会在这里显示识别与配对结果，可直接修改新文件名</td></tr>';
    $('btnApply').disabled = true;
    $('summary').textContent = '尚未扫描';
    return;
  }

  for (const s of state.sources) {
    const tr = document.createElement('tr');
    const meta = s.meta || {};
    const typeTag = `<span class="tag">${esc(s.type === 'zip' ? '压缩包' : s.type.toUpperCase())}</span>${s.kind === 'zip-entry' ? '<span class="tag inner">压缩包内</span>' : ''}`;

    const sourceHtml = `<div>${esc(s.originalName)}</div>` +
      (s.entryName ? `<div class="source-sub">${esc(s.entryName)}</div>` : '') +
      (s.kind === 'zip-entry' && s.containerZip ? `<div class="source-sub">${esc(s.containerZip)}</div>` : '');

    const input = document.createElement('input');
    input.value = s.newName || s.originalName || '';
    input.spellcheck = false;
    input.dataset.id = s.id;
    input.addEventListener('input', () => {
      s.newName = input.value.trim();
    });

    tr.innerHTML = `
      <td class="col-source">${sourceHtml}</td>
      <td class="col-type">${typeTag}</td>
      <td class="col-invoice">${esc(meta.invoiceNo || '-')}</td>
      <td class="col-station">${esc(meta.station || '-')}</td>
      <td class="col-project">${esc(meta.project || '-')}</td>
      <td class="col-amount">${esc(meta.amount || '-')}</td>
      <td class="col-new"></td>
      <td class="col-pair">${s.paired && s.paired.length ? `<span class="badge ok">${s.paired.length + 1} 文件配对</span>` : '无'}</td>
      <td class="col-status">${statusBadge(s)}</td>
    `;
    tr.querySelector('.col-new').appendChild(input);
    tbody.appendChild(tr);
  }

  const ok = state.sources.filter((s) => s.status === 'ok').length;
  const attention = state.sources.filter((s) => s.status === 'attention').length;
  const error = state.sources.filter((s) => s.status === 'error').length;
  const invoices = new Set(state.sources.map((s) => s.meta && s.meta.invoiceNo).filter(Boolean)).size;
  $('summary').textContent = `共 ${state.sources.length} 条识别结果 · ${invoices} 张发票 · ${ok} 正常 · ${attention} 需确认 · ${error} 失败`;
  $('btnApply').disabled = state.sources.every((s) => s.status === 'error');
}

async function scan() {
  const paths = $('pathInput').value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  if (paths.length === 0) {
    addLog('请先填写文件夹或文件路径', 'err');
    return;
  }
  state.template = $('templateInput').value.trim() || '{remark}_{amount}_{invoice}';
  const btn = $('btnScan');
  btn.disabled = true;
  btn.textContent = '扫描中…';
  addLog(`开始扫描 ${paths.length} 个路径`);
  try {
    const result = await api('/api/scan', { paths, template: state.template });
    state.sources = result.sources || [];
    if (result.missing && result.missing.length) {
      addLog(`以下路径不存在：${result.missing.join('；')}`, 'err');
    }
    refreshNames();
    addLog(`扫描完成：${state.sources.length} 条识别结果，其中 ${result.summary.attentionCount} 条需确认`);
  } catch (e) {
    addLog(`扫描失败：${e.message}`, 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = '开始扫描';
  }
}

async function apply() {
  const rows = state.sources.filter((s) => s.status !== 'error' && s.newName);
  if (rows.length === 0) {
    addLog('没有可执行的重命名条目', 'err');
    return;
  }
  if (state.mode === 'copy' && !state.outputDir) {
    addLog('输出到文件夹模式需要先选择输出文件夹', 'err');
    return;
  }
  const attentionCount = rows.filter((s) => s.status === 'attention').length;
  const modeText = state.mode === 'copy' ? `输出到：${state.outputDir}` : '在原位置重命名';
  const msg = `将处理 ${rows.length} 条文件（${attentionCount} 条需确认）\n方式：${modeText}\n确定继续吗？`;
  if (!window.confirm(msg)) return;

  const payload = {
    rows: rows.map((s) => ({
      id: s.id,
      kind: s.kind,
      type: s.type,
      filePath: s.filePath,
      originalName: s.originalName,
      entryName: s.entryName,
      containerZip: s.containerZip,
      ext: s.ext,
      newName: s.newName,
      zip: s.zip,
      status: s.status
    })),
    mode: state.mode,
    outputDir: state.outputDir,
    extractSingleZip: state.extractSingleZip,
    dedupe: state.dedupe
  };

  try {
    const result = await api('/api/apply', payload);
    for (const item of result.success || []) {
      addLog(`[成功] ${item.action}：${item.label} -> ${item.to}`, 'ok');
    }
    for (const item of result.failed || []) {
      addLog(`[失败] ${item.label}：${item.error}`, 'err');
    }
    for (const item of result.skipped || []) {
      addLog(`[跳过] ${item.action}：${item.label}`, 'warn');
    }
    if ((result.success || []).length > 0 && state.mode === 'copy') {
      $('btnOpenOutput').style.display = '';
    }
    addLog(`执行完成：成功 ${(result.success || []).length}，跳过 ${(result.skipped || []).length}，失败 ${(result.failed || []).length}`);
  } catch (e) {
    addLog(`执行失败：${e.message}`, 'err');
  }
}

function bindEvents() {
  $('btnPickFolder').addEventListener('click', async () => {
    try {
      const r = await api('/api/pick-folder', {});
      if (r.path) appendPaths([r.path]);
    } catch (e) {
      addLog(`选择文件夹失败：${e.message}`, 'err');
    }
  });

  $('btnPickFiles').addEventListener('click', async () => {
    try {
      const r = await api('/api/pick-files', {});
      if (r.paths && r.paths.length) appendPaths(r.paths);
    } catch (e) {
      addLog(`选择文件失败：${e.message}`, 'err');
    }
  });

  $('btnPickOutput').addEventListener('click', async () => {
    try {
      const r = await api('/api/pick-folder', {});
      if (r.path) {
        state.outputDir = r.path;
        $('outputDir').value = r.path;
      }
    } catch (e) {
      addLog(`选择输出文件夹失败：${e.message}`, 'err');
    }
  });

  $('btnScan').addEventListener('click', scan);
  $('btnApply').addEventListener('click', apply);

  $('templateInput').addEventListener('change', () => {
    state.template = $('templateInput').value.trim() || '{remark}_{amount}_{invoice}';
    refreshNames();
    addLog('命名模板已更新');
  });

  $('btnResetTemplate').addEventListener('click', () => {
    $('templateInput').value = '{remark}_{amount}_{invoice}';
    state.template = '{remark}_{amount}_{invoice}';
    refreshNames();
    addLog('已恢复默认命名模板');
  });

  $('extractSingleZip').addEventListener('change', () => {
    state.extractSingleZip = $('extractSingleZip').checked;
  });

  $('dedupeFiles').addEventListener('change', () => {
    state.dedupe = $('dedupeFiles').checked;
  });

  $('outputDir').addEventListener('input', () => {
    state.outputDir = $('outputDir').value.trim();
  });

  document.querySelectorAll('input[name="mode"]').forEach((radio) => {
    radio.addEventListener('change', () => {
      state.mode = document.querySelector('input[name="mode"]:checked').value;
      $('outputField').style.display = state.mode === 'copy' ? '' : 'none';
    });
  });

  $('btnOpenOutput').addEventListener('click', () => {
    if (state.outputDir) api('/api/open-path', { path: state.outputDir }).catch(() => {});
  });
}

async function boot() {
  bindEvents();
  $('outputField').style.display = 'none';
  try {
    await fetch('/api/ping');
  } catch {
    const el = $('serverState');
    el.innerHTML = '<span class="dot" style="background:var(--err)"></span>本机服务未连接';
  }
}

boot();
