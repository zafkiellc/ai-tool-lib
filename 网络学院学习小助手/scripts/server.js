import express from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { TaskStore } from './store.js';
import { RunnerManager } from './worker.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT) || 3000;

const store = new TaskStore();

const SIA_TASK_NAME = 'SIA 中石化网络学院';
const SIA_TEMPLATE = {
  name: SIA_TASK_NAME,
  loginUrl: 'https://sia.sinopec.com/learn/',
  loginOpenButtonSelector: 'button:has-text("登 录")',
  usernameSelector: 'input[placeholder="请输入统一账号"]',
  passwordSelector: 'input[placeholder="请输入密码"]',
  loginButtonSelector: 'button:has-text("立即登录")',
  loginMode: 'auto',
  headless: true,
  videoSelector: 'video',
  playButtonSelector: '',
  nextButtonSelector: '',
  waitSecondsAfterLogin: 5,
  maxMinutesPerLesson: 60,
  autoNext: false,
  keepAlive: true,
  accounts: [],
  courses: []
};

if (!store.getTasks().length) {
  store.createTask(SIA_TEMPLATE);
  console.log(`已创建 ${SIA_TASK_NAME}模板任务`);
} else {
  const sia = store.getTasks().find((t) => t.name === SIA_TASK_NAME);
  if (sia && (
    sia.loginUrl === 'https://sia.sinopec.com/' ||
    !sia.usernameSelector ||
    sia.usernameSelector === '#authId' ||
    !sia.loginOpenButtonSelector ||
    sia.loginOpenButtonSelector === 'button:has-text("请登录")'
  )) {
    store.updateTask(sia.id, {
      loginUrl: SIA_TEMPLATE.loginUrl,
      loginOpenButtonSelector: SIA_TEMPLATE.loginOpenButtonSelector,
      usernameSelector: SIA_TEMPLATE.usernameSelector,
      passwordSelector: SIA_TEMPLATE.passwordSelector,
      loginButtonSelector: SIA_TEMPLATE.loginButtonSelector
    });
    console.log(`已更新 ${SIA_TASK_NAME}登录配置`);
  }
}

const sseClients = new Set();
const runner = new RunnerManager({
  onUpdate(state) {
    broadcast({ type: 'update', taskId: state.taskId, state });
  }
});

function broadcast(payload) {
  const data = `data: ${JSON.stringify(payload)}\n\n`;
  for (const res of sseClients) {
    res.write(data);
  }
}

const app = express();
app.use(express.json({ limit: '2mb' }));
app.use('/vendor', express.static(path.join(__dirname, 'node_modules', 'lucide', 'dist', 'umd')));
app.use(express.static(path.join(__dirname, 'public')));

function withRun(task) {
  return { ...task, run: runner.getRun(task.id) };
}

app.get('/api/tasks', (req, res) => {
  res.json(store.getTasks().map(withRun));
});

app.post('/api/tasks', (req, res) => {
  const body = req.body || {};
  if (!String(body.name || '').trim()) {
    return res.status(400).json({ error: '任务名称不能为空' });
  }
  const task = store.createTask(body);
  broadcast({ type: 'tasks' });
  res.status(201).json(withRun(task));
});

app.put('/api/tasks/:id', (req, res) => {
  const task = store.getTask(req.params.id);
  if (!task) return res.status(404).json({ error: '任务不存在' });
  const run = runner.getRun(task.id);
  if (run && ['starting', 'running', 'waiting_manual'].includes(run.status)) {
    return res.status(409).json({ error: '任务运行中，请先停止再修改' });
  }
  const updated = store.updateTask(task.id, req.body || {});
  broadcast({ type: 'tasks' });
  res.json(withRun(updated));
});

app.delete('/api/tasks/:id', async (req, res) => {
  runner.stop(req.params.id);
  const ok = store.deleteTask(req.params.id);
  if (!ok) return res.status(404).json({ error: '任务不存在' });
  broadcast({ type: 'tasks' });
  res.json({ ok: true });
});

app.post('/api/tasks/:id/start', (req, res) => {
  const task = store.getTask(req.params.id);
  if (!task) return res.status(404).json({ error: '任务不存在' });
  const courses = normalizeRunCourses(req.body && req.body.courses);
  const result = runner.start(task.id, task, courses);
  if (!result.ok) return res.status(400).json(result);
  res.json(result);
});

app.post('/api/tasks/:id/stop', (req, res) => {
  const task = store.getTask(req.params.id);
  if (!task) return res.status(404).json({ error: '任务不存在' });
  const result = runner.stop(task.id);
  if (!result.ok) return res.status(400).json(result);
  res.json(result);
});

app.post('/api/tasks/:id/continue', (req, res) => {
  const result = runner.continueManual(req.params.id);
  if (!result.ok) return res.status(400).json(result);
  res.json(result);
});

app.get('/api/events', (req, res) => {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive'
  });
  res.write(': connected\n\n');
  sseClients.add(res);
  const heartbeat = setInterval(() => {
    res.write(': ping\n\n');
  }, 25000);
  req.on('close', () => {
    clearInterval(heartbeat);
    sseClients.delete(res);
  });
});

app.get('/api/health', (req, res) => {
  res.json({ ok: true, tasks: store.getTasks().length });
});

function normalizeRunCourses(input) {
  if (!Array.isArray(input)) return null;
  const courses = [];
  for (const item of input) {
    const url = String(typeof item === 'string' ? item : item.url || '').trim();
    if (!url) continue;
    courses.push({
      name: typeof item === 'string' ? '' : String(item.name || '').trim(),
      url
    });
  }
  return courses.length ? courses : null;
}

function listen(port) {
  const server = app.listen(port, '127.0.0.1', () => {
    console.log(`network-academy-helper running at http://127.0.0.1:${port}`);
    try {
      fs.mkdirSync(path.join(__dirname, 'data'), { recursive: true });
      fs.writeFileSync(path.join(__dirname, 'data', 'port.txt'), String(port));
    } catch {
      // port hint is optional
    }
  });
  server.on('error', (error) => {
    if (error.code === 'EADDRINUSE') {
      console.log(`port ${port} in use, trying ${port + 1}`);
      listen(port + 1);
    } else {
      throw error;
    }
  });
}

listen(PORT);
