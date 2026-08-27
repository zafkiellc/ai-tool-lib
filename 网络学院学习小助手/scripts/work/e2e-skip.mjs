// 端到端测试：本地模拟 SIA 课程页，验证 detectCompletedState 跳过判定
import { chromium } from 'playwright';
import http from 'node:http';
import { RunnerManager } from '../worker.js';

const BASE = `
<style>body{font-family:sans-serif}</style>
<div class="course-progress">{progressText}</div>
<div class="lesson-list">{lessonText}</div>
<video style="width:300px;height:150px"></video>
`;

const PAGES = {
  // 已通过：课程级 100% + 课时已通过
  passed: BASE
    .replace('{progressText}', '完成进度：100% 学习状态： 已通过')
    .replace('{lessonText}', '第1章:加能站电气安全管理 第1课时:加能站电气安全管理 100% 已学：33分钟 通过：33分钟 状态:已通过'),
  // 未学完：50% 继续学
  half: BASE
    .replace('{progressText}', '完成进度：50% 学习状态： 未通过')
    .replace('{lessonText}', '第1章:加能站电气安全管理 第1课时:加能站电气安全管理 50% 已学：16分钟 通过：33分钟 状态:未通过'),
  // 时长学满但状态未通过（本次会话归零重播的场景）
  timeup: BASE
    .replace('{progressText}', '完成进度：100% 学习状态： 未通过')
    .replace('{lessonText}', '第1章:加能站电气安全管理 第1课时:加能站电气安全管理 100% 已学：33分钟 通过：33分钟 状态:未通过'),
  // 多课时全部通过
  multiPassed: BASE
    .replace('{progressText}', '完成进度：100% 学习状态： 已通过')
    .replace('{lessonText}', '第1课时:甲 100% 已学：10分钟 通过：10分钟 状态:已通过 第2课时:乙 100% 已学：20分钟 通过：20分钟 状态:已通过'),
  // 多课时部分通过（不应跳过）
  multiPartial: BASE
    .replace('{progressText}', '完成进度：50% 学习状态： 未通过')
    .replace('{lessonText}', '第1课时:甲 100% 已学：10分钟 通过：10分钟 状态:已通过 第2课时:乙 50% 已学：10分钟 通过：20分钟 状态:未通过'),
  // 无课时数据（未知平台结构，不应跳过）
  unknown: BASE
    .replace('{progressText}', '完成进度：50% 学习状态： 未通过')
    .replace('{lessonText}', '学习评论资料 全部(0) 笔记(0)'),
  // 课程级 80% 未通过，但课时累计学习时长已满（33≥33）→ 应跳过（课时级判定）
  timeupOnly: BASE
    .replace('{progressText}', '完成进度：80% 学习状态： 未通过')
    .replace('{lessonText}', '第1章:加能站电气安全管理 第1课时:加能站电气安全管理 100% 已学：33分钟 通过：33分钟 状态:未通过'),
  // 课程级 80% 未通过，课时只学了一半 → 不应跳过
  halfOnly: BASE
    .replace('{progressText}', '完成进度：50% 学习状态： 未通过')
    .replace('{lessonText}', '第1章:加能站电气安全管理 第1课时:加能站电气安全管理 50% 已学：16分钟 通过：33分钟 状态:未通过')
};

const server = http.createServer((req, res) => {
  const key = req.url.replace('/', '');
  const html = PAGES[key];
  if (html) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(html);
  } else {
    res.writeHead(404);
    res.end('not found');
  }
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
console.log(`本地模拟服务器 http://127.0.0.1:${port}`);

const runner = new RunnerManager({ onUpdate: () => {} });
const browser = await chromium.launch({ headless: true, args: ['--disable-http2'] });
const page = await browser.newPage();

let passed = 0;
let failed = 0;
async function check(name, pageKey, expectSkip) {
  await page.goto(`http://127.0.0.1:${port}/${pageKey}`);
  await page.waitForTimeout(500);
  const result = await runner.detectCompletedState(page);
  const ok = result.skip === expectSkip;
  if (ok) {
    passed += 1;
    console.log(`[PASS] ${name} → skip=${result.skip}${result.reason ? `（${result.reason}）` : ''}`);
  } else {
    failed += 1;
    console.log(`[FAIL] ${name} → 实际 skip=${result.skip} 期望 skip=${expectSkip}`);
    if (result.reason) console.log(`  原因: ${result.reason}`);
  }
}

await check('已通过课程（100%+状态已通过）应跳过', 'passed', true);
await check('未学完课程（50%）不应跳过', 'half', false);
await check('累计时长已满（33≥33）应跳过', 'timeup', true);
await check('多课时全部通过应跳过', 'multiPassed', true);
await check('多课时部分通过不应跳过', 'multiPartial', false);
await check('无课时数据（未知结构）不应跳过', 'unknown', false);
await check('课时累计时长已满（仅课时级判定）应跳过', 'timeupOnly', true);
await check('课时只学一半（仅课时级判定）不应跳过', 'halfOnly', false);

await browser.close();
server.close();
console.log(`\n结果: ${passed} 通过, ${failed} 失败`);
process.exit(failed ? 1 : 0);
