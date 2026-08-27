// 测试：用系统 Edge（channel: msedge）替代内置 Chromium，验证 SIA 全链路
import { chromium } from 'playwright';
import { TaskStore } from '../store.js';
import { RunnerManager } from '../worker.js';

const channel = process.argv[2] || 'msedge';
const mask = (u) => (u ? (u.length <= 4 ? `${u.slice(0, 1)}***` : `${u.slice(0, 2)}***${u.slice(-1)}`) : '');

const store = new TaskStore();
const task = store.getTasks().find((t) => t.accounts && t.accounts.length);
const account = task.accounts[0]; // 第一个账号

let logIdx = 0;
const runner = new RunnerManager({
  onUpdate: (s) => {
    while (logIdx < s.logs.length) {
      const l = s.logs[logIdx];
      logIdx += 1;
      console.log(`  [log:${l.level}] ${l.message}`);
    }
  }
});
const state = { taskId: task.id, status: 'starting', accountLabel: '', courseLabel: '', lessonsDone: 0, startedAt: Date.now(), message: '', logs: [] };

console.log(`===== 测试 channel=${channel} =====`);
let browser;
try {
  browser = await chromium.launch({ channel, headless: true, args: ['--disable-http2'] });
  console.log(`[启动] channel=${channel} 启动成功，浏览器版本 ${browser.version()}`);
} catch (e) {
  console.log(`[启动] 失败: ${String(e.message || e).slice(0, 300)}`);
  process.exit(1);
}

const context = await browser.newContext({
  locale: 'zh-CN',
  viewport: { width: 1280, height: 800 },
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
});
const page = await context.newPage();

try {
  console.log(`===== 登录 ${mask(account.username)} =====`);
  await runner.login(task, page, state, account);
  console.log(`[登录] 成功`);
  const course = task.courses[0];
  await runner.openCoursePage(page, course, state);
  await page.waitForTimeout(4000);
  const r = await runner.detectCompletedState(page);
  const video = await runner.probeVideo(page, task);
  console.log(`[检测] 跳过判定: ${r.skip}${r.reason ? `（${r.reason}）` : ''} | 视频: ${video && video.found ? '已找到' : '未找到'}`);
  console.log(`[结论] channel=${channel} 全链路可用`);
} catch (e) {
  console.log(`[异常] ${String(e.message || e).slice(0, 300)}`);
} finally {
  await context.close().catch(() => {});
  await browser.close();
}
process.exit(0);
