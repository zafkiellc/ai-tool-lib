// 真实环境验证：用现有账号登录 SIA，对每个账号执行课程完成状态检测
import { chromium } from 'playwright';
import { TaskStore } from '../store.js';
import { RunnerManager } from '../worker.js';

const mask = (u) => (u ? (u.length <= 4 ? `${u.slice(0, 1)}***` : `${u.slice(0, 2)}***${u.slice(-1)}`) : '');

const store = new TaskStore();
const task = store.getTasks().find((t) => t.accounts && t.accounts.length);
if (!task) {
  console.error('未找到带账号的任务');
  process.exit(1);
}

let logIdx = 0;
const runner = new RunnerManager({
  onUpdate: (s) => {
    while (logIdx < s.logs.length) {
      const l = s.logs[logIdx];
      logIdx += 1;
      console.log(`    [log:${l.level}] ${l.message}`);
    }
  }
});

const state = {
  taskId: task.id,
  status: 'starting',
  accountLabel: '',
  courseLabel: '',
  lessonsDone: 0,
  startedAt: Date.now(),
  message: '',
  logs: []
};

const browser = await chromium.launch({
  headless: task.headless !== false && task.loginMode !== 'manual',
  args: ['--disable-http2']
});

let skipCount = 0;
let studyCount = 0;

for (const account of task.accounts) {
  const label = mask(account.username);
  console.log(`\n===== 账号 ${label} =====`);
  const context = await browser.newContext({
    locale: 'zh-CN',
    viewport: { width: 1280, height: 800 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();
  try {
    await runner.login(task, page, state, account);
    console.log(`  [登录] 成功`);
  } catch (e) {
    console.log(`  [登录] 失败: ${String(e.message || e).slice(0, 200)}`);
    await context.close().catch(() => {});
    continue;
  }

  for (const course of task.courses) {
    const title = course.name || course.url;
    try {
      await runner.openCoursePage(page, course, state);
      await page.waitForTimeout(4000);
      let r = await runner.detectCompletedState(page);
      if (!r.skip) {
        await page.waitForTimeout(3000);
        r = await runner.detectCompletedState(page);
      }
      const video = await runner.probeVideo(page, task);
      if (r.skip) {
        skipCount += 1;
        console.log(`  [跳过] 《${title}》\n    原因: ${r.reason}`);
      } else {
        studyCount += 1;
        console.log(`  [学习] 《${title}》无需跳过（继续播放）| 视频: ${video && video.found ? '已找到' : '未找到'}`);
        const texts = await runner.collectPageTexts(page);
        const lessonInfo = texts.map((t) => t.match(/已学[:：][^\n]{0,60}/)).filter(Boolean).map((m) => m[0]);
        if (lessonInfo.length) console.log(`    课时信息: ${lessonInfo.join(' | ')}`);
      }
    } catch (e) {
      console.log(`  [异常] 《${title}》: ${String(e.message || e).slice(0, 200)}`);
    }
  }
  await context.close().catch(() => {});
}

await browser.close();
console.log(`\n===== 验证汇总 =====`);
console.log(`账号数: ${task.accounts.length} | 判定跳过: ${skipCount} | 判定继续学习: ${studyCount}`);
process.exit(0);
