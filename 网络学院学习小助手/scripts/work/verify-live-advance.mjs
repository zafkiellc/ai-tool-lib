// 真实环境进阶验证：用 ch***9（已学32.9/33分钟）跑完整 processCourse，
// 验证"播放中累计学习时长达标 → 平台判通过 → 提前完成"链路
import { chromium } from 'playwright';
import { TaskStore } from '../store.js';
import { RunnerManager } from '../worker.js';

const store = new TaskStore();
const task = store.getTasks().find((t) => t.accounts && t.accounts.length);
const account = task.accounts.find((a) => String(a.username || '').toLowerCase().startsWith('ch'));
if (!account) {
  console.error('未找到 ch*** 账号');
  process.exit(1);
}

let logIdx = 0;
const runner = new RunnerManager({
  onUpdate: (s) => {
    while (logIdx < s.logs.length) {
      const l = s.logs[logIdx];
      logIdx += 1;
      console.log(`[log:${l.level}] ${l.message}`);
    }
  }
});

const state = {
  taskId: task.id,
  status: 'running',
  accountLabel: '',
  courseLabel: '',
  lessonsDone: 0,
  startedAt: Date.now(),
  message: '',
  logs: []
};

// 覆盖单节上限为 6 分钟，避免平台上报慢时无限播放
const runTask = { ...task, maxMinutesPerLesson: 6, accounts: [account] };
const course = task.courses[0];

const browser = await chromium.launch({
  headless: runTask.headless !== false && runTask.loginMode !== 'manual',
  args: ['--disable-http2']
});
const context = await browser.newContext({
  locale: 'zh-CN',
  viewport: { width: 1280, height: 800 },
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
});
const page = await context.newPage();

try {
  console.log('===== 登录 ch***9 =====');
  await runner.login(runTask, page, state, account);
  console.log('[登录] 成功');

  console.log('===== 运行 processCourse（含播放中复核）=====');
  const t0 = Date.now();
  await runner.processCourse(page, runTask, course, state);
  console.log(`[完成] processCourse 结束，用时 ${Math.round((Date.now() - t0) / 1000)} 秒，lessonsDone=${state.lessonsDone}`);
  const statusText = state.logs.map((l) => l.message).filter((m) => /提前完成|播放完成|跳过|已通过|超过/.test(m)).slice(-6);
  console.log('===== 关键日志尾部 =====');
  statusText.forEach((m) => console.log(`  · ${m}`));
} catch (e) {
  console.log(`[异常] ${String(e.message || e).slice(0, 300)}`);
} finally {
  await context.close().catch(() => {});
  await browser.close();
}
process.exit(0);
