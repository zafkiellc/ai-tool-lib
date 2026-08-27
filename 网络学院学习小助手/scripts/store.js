import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');
const DATA_FILE = path.join(DATA_DIR, 'tasks.json');

const DEFAULTS = {
  name: '',
  loginUrl: '',
  loginOpenButtonSelector: '',
  usernameSelector: '#username',
  passwordSelector: '#password',
  loginButtonSelector: 'button[type="submit"]',
  loginMode: 'auto',
  headless: true,
  videoSelector: 'video',
  playButtonSelector: '',
  nextButtonSelector: '',
  waitSecondsAfterLogin: 5,
  maxMinutesPerLesson: 60,
  autoNext: false,
  keepAlive: false,
  accounts: [],
  courses: []
};

function load() {
  try {
    const raw = fs.readFileSync(DATA_FILE, 'utf8');
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed.tasks) ? parsed.tasks : [];
  } catch {
    return [];
  }
}

function persist(tasks) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const tmp = `${DATA_FILE}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify({ tasks }, null, 2));
  fs.renameSync(tmp, DATA_FILE);
}

function normalize(input) {
  const task = { ...DEFAULTS, ...input, accounts: [], courses: [] };
  task.accounts = Array.isArray(input.accounts) ? input.accounts.map((a) => ({
    username: String(a.username || '').trim(),
    password: String(a.password || ''),
    enabled: a.enabled !== false
  })).filter((a) => a.username) : [];
  task.courses = Array.isArray(input.courses) ? input.courses.map((c) => ({
    name: String(c.name || '').trim(),
    url: String(c.url || '').trim()
  })).filter((c) => c.url) : [];
  return task;
}

export class TaskStore {
  constructor() {
    this.tasks = load();
  }

  save() {
    persist(this.tasks);
  }

  getTasks() {
    return this.tasks;
  }

  getTask(id) {
    return this.tasks.find((t) => t.id === id) || null;
  }

  createTask(input) {
    const task = normalize({ ...DEFAULTS, ...input });
    task.id = crypto.randomUUID();
    task.createdAt = Date.now();
    task.updatedAt = Date.now();
    this.tasks.unshift(task);
    this.save();
    return task;
  }

  updateTask(id, input) {
    const task = this.getTask(id);
    if (!task) return null;
    const next = normalize({ ...task, ...input });
    next.id = task.id;
    next.createdAt = task.createdAt;
    next.updatedAt = Date.now();
    const index = this.tasks.findIndex((t) => t.id === id);
    this.tasks[index] = next;
    this.save();
    return next;
  }

  deleteTask(id) {
    const before = this.tasks.length;
    this.tasks = this.tasks.filter((t) => t.id !== id);
    this.save();
    return this.tasks.length !== before;
  }
}
