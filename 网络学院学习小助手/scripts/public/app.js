const state = {
  tasks: [],
  runs: new Map(),
  currentId: null,
  draft: null,
  dirty: false
};

const $ = (id) => document.getElementById(id);

const STATUS_TEXT = {
  starting: '启动中',
  running: '运行中',
  waiting_manual: '等待手动登录',
  done: '已完成',
  stopped: '已停止',
  error: '异常'
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `请求失败 (${res.status})`);
  }
  return data;
}

function toast(message, isError = false) {
  const el = $('toast');
  el.textContent = message;
  el.classList.toggle('error', isError);
  el.classList.remove('hidden');
  clearTimeout(state.timer);
  state.timer = setTimeout(() => el.classList.add('hidden'), 3200);
}

function fmtClock(ts) {
  const d = new Date(ts);
  const p = (n) => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function currentTask() {
  return state.tasks.find((t) => t.id === state.currentId) || null;
}

function currentRun() {
  return state.runs.get(state.currentId) || null;
}

function refreshIcons() {
  if (window.lucide) lucide.createIcons();
}

async function loadTasks() {
  const tasks = await api('/api/tasks');
  state.tasks = tasks;
  for (const task of tasks) {
    if (task.run) state.runs.set(task.id, task.run);
  }
  if (!state.currentId || !tasks.some((t) => t.id === state.currentId)) {
    state.currentId = tasks[0] ? tasks[0].id : null;
    state.dirty = false;
    renderDetail();
  }
  renderSidebar();
  renderRunUI();
}

function renderSidebar() {
  const list = $('taskList');
  list.innerHTML = '';
  if (!state.tasks.length) {
    const empty = document.createElement('div');
    empty.className = 'task-list-empty';
    empty.textContent = '还没有任务';
    list.appendChild(empty);
    return;
  }
  for (const task of state.tasks) {
    const run = state.runs.get(task.id);
    const statusClass = run && run.status === 'starting' ? 'running' : (run ? run.status : '');
    const btn = document.createElement('button');
    btn.className = 'task-item' + (task.id === state.currentId ? ' active' : '');
    btn.dataset.id = task.id;

    const dot = document.createElement('span');
    dot.className = 'dot' + (statusClass ? ` ${statusClass}` : '');

    const name = document.createElement('span');
    name.className = 'name';
    const strong = document.createElement('strong');
    strong.textContent = task.name || '未命名任务';
    const small = document.createElement('small');
    small.textContent = `${task.accounts.length} 账号 · ${task.courses.length} 课程`;
    name.appendChild(strong);
    name.appendChild(small);

    btn.appendChild(dot);
    btn.appendChild(name);
    btn.addEventListener('click', () => selectTask(task.id));
    list.appendChild(btn);
  }
}

function renderDetail() {
  const task = currentTask();
  const run = currentRun();
  const hasTask = Boolean(task);

  $('saveBtn').disabled = !hasTask || !state.dirty;
  $('deleteBtn').disabled = !hasTask;
  $('startBtn').disabled = !hasTask;
  $('stopBtn').disabled = !hasTask;

  if (!task) {
    $('taskName').textContent = '未选择任务';
    $('taskMeta').textContent = '';
    $('runBadge').className = 'badge';
    $('runBadge').textContent = '';
    $('logs').innerHTML = '<div class="log-empty">暂无日志</div>';
    setEditorDisabled(true);
    refreshIcons();
    return;
  }

  state.draft = structuredClone(task);
  $('taskName').textContent = task.name || '未命名任务';
  $('name').value = task.name || '';
  $('loginUrl').value = task.loginUrl || '';
  $('loginMode').value = task.loginMode === 'manual' ? 'manual' : 'auto';
  $('browserChannel').value = ['auto', 'msedge', 'chrome', 'chromium'].includes(task.browserChannel) ? task.browserChannel : 'auto';
  $('headless').checked = task.headless !== false;
  $('keepAlive').checked = Boolean(task.keepAlive);
  $('waitSecondsAfterLogin').value = task.waitSecondsAfterLogin || 0;
  $('maxMinutesPerLesson').value = task.maxMinutesPerLesson || 60;

  renderAccounts(task.accounts);
  renderCourses(task.courses);
  $('runCourses').value = '';
  renderRunUI();
  refreshIcons();
}

function renderAccounts(accounts) {
  const list = $('accountsList');
  list.innerHTML = '';
  if (!accounts.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = '还没有账号';
    list.appendChild(empty);
    return;
  }
  accounts.forEach((account, index) => {
    const row = document.createElement('div');
    row.className = 'row account';
    row.dataset.index = String(index);

    const username = document.createElement('input');
    username.type = 'text';
    username.placeholder = '账号';
    username.value = account.username || '';

    const passwordWrap = document.createElement('div');
    passwordWrap.style.cssText = 'display:flex;gap:6px;min-width:0;';
    const password = document.createElement('input');
    password.type = 'password';
    password.placeholder = '密码';
    password.value = account.password || '';
    passwordWrap.appendChild(password);

    const actions = document.createElement('div');
    actions.className = 'row-actions';
    const eyeBtn = document.createElement('button');
    eyeBtn.type = 'button';
    eyeBtn.className = 'btn icon ghost';
    eyeBtn.title = '显示/隐藏密码';
    eyeBtn.dataset.action = 'toggle';
    eyeBtn.innerHTML = '<i data-lucide="eye"></i>';
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn icon danger-ghost';
    removeBtn.title = '删除账号';
    removeBtn.dataset.action = 'remove';
    removeBtn.innerHTML = '<i data-lucide="trash-2"></i>';
    actions.appendChild(eyeBtn);
    actions.appendChild(removeBtn);

    row.appendChild(username);
    row.appendChild(passwordWrap);
    row.appendChild(actions);
    list.appendChild(row);
  });
  refreshIcons();
}

function renderCourses(courses) {
  const list = $('coursesList');
  list.innerHTML = '';
  if (!courses.length) {
    const empty = document.createElement('div');
    empty.className = 'empty';
    empty.textContent = '还没有课程链接';
    list.appendChild(empty);
    return;
  }
  courses.forEach((course, index) => {
    const row = document.createElement('div');
    row.className = 'row course';
    row.dataset.index = String(index);

    const name = document.createElement('input');
    name.type = 'text';
    name.placeholder = '课程名称';
    name.value = course.name || '';

    const url = document.createElement('input');
    url.type = 'url';
    url.placeholder = 'https://example.com/course/1';
    url.value = course.url || '';

    const actions = document.createElement('div');
    actions.className = 'row-actions';
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn icon danger-ghost';
    removeBtn.title = '删除课程';
    removeBtn.dataset.action = 'remove';
    removeBtn.innerHTML = '<i data-lucide="trash-2"></i>';
    actions.appendChild(removeBtn);

    row.appendChild(name);
    row.appendChild(url);
    row.appendChild(actions);
    list.appendChild(row);
  });
  refreshIcons();
}

function collectForm() {
  const task = { ...state.draft };
  task.name = $('name').value.trim();
  task.loginUrl = $('loginUrl').value.trim();
  task.loginMode = $('loginMode').value;
  task.browserChannel = $('browserChannel').value;
  task.headless = $('headless').checked;
  task.autoNext = false;
  task.keepAlive = $('keepAlive').checked;
  task.waitSecondsAfterLogin = Number($('waitSecondsAfterLogin').value) || 0;
  task.maxMinutesPerLesson = Number($('maxMinutesPerLesson').value) || 0;

  task.accounts = readRows('accountsList', ['username', 'password']);
  task.courses = readRows('coursesList', ['name', 'url']);
  return task;
}

function readRows(listId, fields) {
  const list = $(listId);
  const rows = list.querySelectorAll('.row');
  return Array.from(rows).map((row) => {
    const inputs = row.querySelectorAll('input');
    const item = {};
    inputs.forEach((input, index) => {
      item[fields[index]] = input.value.trim();
    });
    return item;
  }).filter((item) => item[fields[0]] || item[fields[fields.length - 1]]);
}

function markDirty() {
  if (!state.currentId) return;
  state.dirty = true;
  $('saveBtn').disabled = false;
}

async function saveTask() {
  if (!state.currentId) return;
  try {
    const task = collectForm();
    if (!task.name) {
      toast('任务名称不能为空', true);
      return;
    }
    await api(`/api/tasks/${state.currentId}`, {
      method: 'PUT',
      body: JSON.stringify(task)
    });
    state.dirty = false;
    await loadTasks();
    toast('配置已保存');
  } catch (error) {
    toast(error.message, true);
  }
}

async function createTask() {
  try {
    const created = await api('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({ name: '新任务' })
    });
    await loadTasks();
    selectTask(created.id, true);
    toast('已创建新任务');
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteTask() {
  if (!state.currentId) return;
  const task = currentTask();
  if (!confirm(`确定删除任务“${task.name || '未命名'}”吗？`)) return;
  try {
    await api(`/api/tasks/${state.currentId}`, { method: 'DELETE' });
    state.runs.delete(state.currentId);
    state.currentId = null;
    await loadTasks();
    toast('任务已删除');
  } catch (error) {
    toast(error.message, true);
  }
}

function selectTask(id, skipConfirm = false) {
  if (!skipConfirm && state.dirty && state.currentId && state.currentId !== id) {
    if (!confirm('有未保存的修改，切换后这些修改将丢失。继续吗？')) return;
  }
  state.currentId = id;
  state.dirty = false;
  renderDetail();
  renderSidebar();
}

async function startTask() {
  if (!state.currentId) return;
  try {
    if (state.dirty) {
      const task = collectForm();
      if (!task.name) {
        toast('任务名称不能为空', true);
        return;
      }
      await api(`/api/tasks/${state.currentId}`, {
        method: 'PUT',
        body: JSON.stringify(task)
      });
      state.dirty = false;
      await loadTasks();
    }
    const courses = parseRunCourses($('runCourses').value);
    const body = courses.length ? { courses } : {};
    await api(`/api/tasks/${state.currentId}/start`, {
      method: 'POST',
      body: JSON.stringify(body)
    });
    toast('任务已启动');
    await loadTasks();
  } catch (error) {
    toast(error.message, true);
  }
}

function parseRunCourses(text) {
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const match = line.match(/https?:\/\/\S+/);
    return {
      name: match ? line.slice(0, match.index).trim() : '',
      url: match ? match[0] : line
    };
  });
}

async function stopTask() {
  if (!state.currentId) return;
  try {
    await api(`/api/tasks/${state.currentId}/stop`, { method: 'POST' });
    toast('正在停止任务');
  } catch (error) {
    toast(error.message, true);
  }
}

async function continueManual() {
  if (!state.currentId) return;
  try {
    await api(`/api/tasks/${state.currentId}/continue`, { method: 'POST' });
    toast('已确认，继续学习');
  } catch (error) {
    toast(error.message, true);
  }
}

function renderRunUI() {
  const run = currentRun();
  const task = currentTask();
  if (!task) return;

  const running = Boolean(run && ['starting', 'running', 'waiting_manual'].includes(run.status));
  const waiting = Boolean(run && run.status === 'waiting_manual');

  $('taskMeta').textContent =
    `${task.accounts.length} 个账号 · ${task.courses.length} 门课程 · 已完成 ${run ? run.lessonsDone : 0} 节`;
  if (run && run.message) {
    $('taskMeta').textContent += ` · ${run.message}`;
  }

  const badge = $('runBadge');
  const status = run ? (run.status === 'starting' ? 'running' : run.status) : '';
  badge.className = 'badge' + (status ? ` ${status}` : '');
  badge.textContent = run ? (STATUS_TEXT[run.status] || run.status) : '未启动';

  renderLogs(run);

  $('startBtn').disabled = running;
  $('stopBtn').disabled = !running;
  $('continueBtn').classList.toggle('hidden', !waiting);
  $('saveBtn').disabled = running || !state.dirty;
  setEditorDisabled(running);
}

function renderLogs(run) {
  const logsEl = $('logs');
  const nearBottom = logsEl.scrollHeight - logsEl.scrollTop - logsEl.clientHeight < 80;
  logsEl.innerHTML = '';
  if (!run || !run.logs.length) {
    const empty = document.createElement('div');
    empty.className = 'log-empty';
    empty.textContent = '暂无日志';
    logsEl.appendChild(empty);
    return;
  }
  for (const entry of run.logs) {
    const line = document.createElement('div');
    line.className = `log-line ${entry.level}`;
    const time = document.createElement('span');
    time.className = 'time';
    time.textContent = fmtClock(entry.t);
    const msg = document.createElement('span');
    msg.className = 'msg';
    msg.textContent = entry.message;
    line.appendChild(time);
    line.appendChild(msg);
    logsEl.appendChild(line);
  }
  if (nearBottom) logsEl.scrollTop = logsEl.scrollHeight;
}

function setEditorDisabled(disabled) {
  $('editor').querySelectorAll('input, select, textarea, button').forEach((el) => {
    el.disabled = disabled;
  });
  if (disabled) {
    $('startBtn').disabled = true;
    $('stopBtn').disabled = false;
  }
}

function setupEvents() {
  $('newTaskBtn').addEventListener('click', createTask);
  $('saveBtn').addEventListener('click', saveTask);
  $('deleteBtn').addEventListener('click', deleteTask);
  $('startBtn').addEventListener('click', startTask);
  $('stopBtn').addEventListener('click', stopTask);
  $('continueBtn').addEventListener('click', continueManual);
  $('addAccountBtn').addEventListener('click', () => {
    const task = currentTask();
    if (!task) return;
    state.draft.accounts = readRows('accountsList', ['username', 'password']);
    state.draft.accounts.push({ username: '', password: '', enabled: true });
    renderAccounts(state.draft.accounts);
    markDirty();
  });
  $('addCourseBtn').addEventListener('click', () => {
    const task = currentTask();
    if (!task) return;
    state.draft.courses = readRows('coursesList', ['name', 'url']);
    state.draft.courses.push({ name: '', url: '' });
    renderCourses(state.draft.courses);
    markDirty();
  });

  $('editor').addEventListener('input', (event) => {
    if (event.target.closest('.row')) markDirty();
  });
  $('editor').addEventListener('change', (event) => {
    if (!event.target.closest('.row')) markDirty();
  });

  $('accountsList').addEventListener('click', (event) => {
    const btn = event.target.closest('button');
    if (!btn) return;
    const row = btn.closest('.row');
    const index = Number(row.dataset.index);
    const action = btn.dataset.action;
    if (action === 'remove') {
      state.draft.accounts = readRows('accountsList', ['username', 'password']);
      state.draft.accounts.splice(index, 1);
      renderAccounts(state.draft.accounts);
      markDirty();
    } else if (action === 'toggle') {
      const input = row.querySelectorAll('input')[1];
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = show
        ? '<i data-lucide="eye-off"></i>'
        : '<i data-lucide="eye"></i>';
      refreshIcons();
    }
  });

  $('coursesList').addEventListener('click', (event) => {
    const btn = event.target.closest('button');
    if (!btn || btn.dataset.action !== 'remove') return;
    const row = btn.closest('.row');
    const index = Number(row.dataset.index);
    state.draft.courses = readRows('coursesList', ['name', 'url']);
    state.draft.courses.splice(index, 1);
    renderCourses(state.draft.courses);
    markDirty();
  });
}

function setupSSE() {
  const es = new EventSource('/api/events');
  es.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'tasks') {
        loadTasks().catch(() => {});
      } else if (payload.type === 'update') {
        state.runs.set(payload.taskId, payload.state);
        if (payload.taskId === state.currentId) {
          renderRunUI();
        }
        renderSidebar();
      }
    } catch {
      // ignore malformed events
    }
  };
}

async function init() {
  setupEvents();
  setupSSE();
  try {
    await loadTasks();
  } catch (error) {
    toast(error.message, true);
  }
}

init();
