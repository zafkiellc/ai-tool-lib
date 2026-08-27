import { chromium } from 'playwright';

const MAX_LOGS = 600;
const POLL_MS = 5000;

const USERNAME_SELECTORS = [
  'input[name*="username" i]',
  'input[name*="account" i]',
  'input[name*="user" i]',
  'input[placeholder*="统一账号" i]',
  'input[type="text"][placeholder*="账号" i]',
  'input[type="text"][placeholder*="用户" i]',
  'input[type="text"][placeholder*="工号" i]',
  'input[type="text"]:visible'
];

const PASSWORD_SELECTORS = [
  'input[type="password"]'
];

const LOGIN_BUTTON_SELECTORS = [
  'button[type="submit"]',
  'input[type="submit"]',
  'button:has-text("立即登录")',
  'button:has-text("登录")',
  'button:has-text("登 录")',
  'a:has-text("登录")'
];

const LOGIN_OPEN_SELECTORS = [
  '.el-message-box button:has-text("重新登录")',
  '[class*="double-login"] button',
  'button:has-text("重新登录")',
  'a:has-text("重新登录")',
  'button:has-text("请登录")',
  'button:has-text("登 录")',
  'a:has-text("请登录")',
];

const NEXT_LESSON_SELECTORS = [
  'text=下一节',
  'text=下一课',
  'text=下一步',
  'text=继续学习',
  '[class*="next-lesson"]'
];

const PLAY_BUTTON_SELECTORS = [
  '.xgplayer-start',
  '.xgplayer-icon-play',
  '.vedio-play',
  '[class*="player"] [class*="play"]',
  'button:has-text("播放")'
];

function maskUsername(name) {
  const s = String(name || '');
  if (s.length <= 4) return s ? `${s.slice(0, 1)}***` : '';
  return `${s.slice(0, 2)}***${s.slice(-1)}`;
}

function fmtDuration(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return '';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}分${s}秒`;
}

const DURATION_UNIT_SECONDS = { 秒: 1, 分钟: 60, 小时: 3600 };

export function toSeconds(value, unit) {
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return null;
  return n * (DURATION_UNIT_SECONDS[unit] || 1);
}

/**
 * 解析页面文本中的课时学习状态（SIA 平台格式）：
 *   `第1课时:xxx 18% 已学：6分钟 通过：33分钟 状态:未通过`
 * 返回 [{ learnedSec, requiredSec, status }]
 *  - learnedSec: 累计学习时长（秒）
 *  - requiredSec: 视频时长 / 通过所需时长（秒）
 *  - status: 已通过 | 未通过 | 已完成
 */
export function parseLessonStates(text) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  const groups = [];
  const re = /已学[:：]\s*([\d.]+)\s*(秒|分钟|小时)[\s\S]{0,40}?通过[:：]\s*([\d.]+)\s*(秒|分钟|小时)[\s\S]{0,40}?状态[:：]?\s*(已通过|未通过|已完成)/g;
  let m;
  while ((m = re.exec(normalized)) !== null) {
    groups.push({
      learnedSec: toSeconds(m[1], m[2]),
      requiredSec: toSeconds(m[3], m[4]),
      status: m[5]
    });
  }
  return groups;
}

/** 单课时是否已完成：状态已通过/已完成，或累计学习时长 >= 视频时长 */
export function isLessonComplete(group) {
  if (!group) return false;
  if (group.status === '已通过' || group.status === '已完成') return true;
  if (
    Number.isFinite(group.learnedSec) &&
    Number.isFinite(group.requiredSec) &&
    group.requiredSec > 0 &&
    group.learnedSec >= group.requiredSec
  ) {
    return true;
  }
  return false;
}

export class RunnerManager {
  constructor({ onUpdate }) {
    this.onUpdate = onUpdate;
    this.runs = new Map();
    this.pendingManual = new Map();
    this.stopRequests = new Set();
  }

  getRun(taskId) {
    return this.runs.get(taskId) || null;
  }

  /** 根据配置解析浏览器启动通道顺序（按优先级） */
  resolveBrowserChannels(configured) {
    switch (String(configured || '').toLowerCase()) {
      case 'msedge':
        return ['msedge'];
      case 'chrome':
        return ['chrome', 'msedge'];
      case 'chromium':
        return [null];
      case 'auto':
      default:
        // 默认优先系统 Edge（Win10/11 自带，可减小包体），失败回退内置 Chromium
        return ['msedge', null];
    }
  }

  async launchBrowser(task, state) {
    const headless = task.headless !== false && task.loginMode !== 'manual';
    const channels = this.resolveBrowserChannels(task.browserChannel);
    const args = ['--disable-http2'];
    let lastError = null;
    for (const channel of channels) {
      try {
        const options = { headless, args };
        if (channel) {
          options.channel = channel;
          const label = channel === 'msedge' ? '系统 Edge' : '系统 Chrome';
          this.log(state, 'info', `启动浏览器：${label}（${headless ? '无头模式' : '显示窗口'}）`);
        } else {
          this.log(state, 'info', `启动浏览器：内置 Chromium（${headless ? '无头模式' : '显示窗口'}）`);
        }
        return await chromium.launch(options);
      } catch (error) {
        lastError = error;
        const label = channel ? (channel === 'msedge' ? '系统 Edge' : '系统 Chrome') : '内置 Chromium';
        this.log(state, 'warn', `${label}启动失败：${String(error.message || error).slice(0, 120)}，尝试下一种`);
      }
    }
    throw lastError || new Error('所有浏览器均启动失败');
  }

  isStopped(taskId) {
    return this.stopRequests.has(taskId);
  }

  start(taskId, task, overrideCourses) {
    const existing = this.runs.get(taskId);
    if (existing && !['done', 'stopped', 'error'].includes(existing.status)) {
      return { ok: false, error: '任务正在运行，请先停止' };
    }
    const courses = overrideCourses && overrideCourses.length
      ? overrideCourses
      : task.courses;
    if (!task.accounts.length) {
      return { ok: false, error: '至少需要 1 个账号' };
    }
    if (!courses.length) {
      return { ok: false, error: '至少填写 1 个课程链接' };
    }
    const hasCourseUrl = courses.some((course) => course && String(course.url || '').trim());
    if (task.loginMode !== 'manual' && !task.loginUrl && !hasCourseUrl) {
      return { ok: false, error: '自动登录需要填写登录地址或课程链接' };
    }

    const state = {
      taskId,
      status: 'starting',
      accountLabel: '',
      courseLabel: '',
      lessonsDone: 0,
      startedAt: Date.now(),
      message: '',
      logs: []
    };
    this.runs.set(taskId, state);
    this.emit(state);
    this.runTask({ ...task, courses }, state).catch(() => {});
    return { ok: true };
  }

  async runTask(task, state) {
    let browser;
    try {
      browser = await this.launchBrowser(task, state);
      state.browser = browser;
      state.status = 'running';
      state.message = '任务运行中';
      this.emit(state);

      for (const account of task.accounts) {
        if (this.isStopped(task.id)) break;
        state.accountLabel = maskUsername(account.username);
        this.emit(state);
        this.log(state, 'info', `开始处理账号 ${state.accountLabel}`);

        const context = await browser.newContext({
          locale: 'zh-CN',
          viewport: { width: 1280, height: 800 },
          userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        });
        const page = await context.newPage();
        await this.login(task, page, state, account);
        if (this.isStopped(task.id)) {
          await context.close().catch(() => {});
          break;
        }

        for (const course of task.courses) {
          if (this.isStopped(task.id)) break;
          await this.processCourse(page, task, course, state);
        }
        await context.close().catch(() => {});
        this.log(state, 'info', `账号 ${state.accountLabel} 处理完毕`);
      }

      if (this.isStopped(task.id)) {
        state.status = 'stopped';
        state.message = '任务已停止';
        this.log(state, 'warn', '任务已停止');
      } else {
        state.status = 'done';
        state.message = '全部账号处理完成';
        this.log(state, 'info', `全部完成，共学完 ${state.lessonsDone} 节`);
      }
    } catch (error) {
      if (this.isStopped(task.id)) {
        state.status = 'stopped';
        state.message = '任务已停止';
        this.log(state, 'warn', '任务已停止');
      } else {
        state.status = 'error';
        state.message = error.message || String(error);
        this.log(state, 'error', `任务异常：${state.message}`);
      }
    } finally {
      if (browser) await browser.close().catch(() => {});
      state.browser = null;
      this.emit(state);
      this.stopRequests.delete(task.id);
      this.pendingManual.delete(task.id);
    }
  }

  async gotoWithRetry(page, url, state, what) {
    const attempts = 4;
    let lastError = null;
    for (let i = 1; i <= attempts; i += 1) {
      if (this.isStopped(state.taskId)) {
        throw new Error('任务已停止');
      }
      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
        return;
      } catch (error) {
        lastError = error;
        if (this.isStopped(state.taskId)) {
          throw new Error('任务已停止');
        }
        if (i < attempts) {
          this.log(state, 'warn', `${what}：页面打开失败，正在重试 ${i}/${attempts - 1}：${error.message || error}`);
          await page.waitForTimeout(2000 * i);
        }
      }
    }
    throw lastError || new Error(`页面打开失败：${url}`);
  }

  async login(task, page, state, account) {
    const label = maskUsername(account.username);
    if (task.loginMode === 'manual') {
      state.status = 'waiting_manual';
      state.message = `等待手动登录 ${label}`;
      this.log(state, 'info', `${label}：打开登录页，请在浏览器窗口内完成登录`);
      await this.gotoWithRetry(page, task.loginUrl || task.courses[0].url, state, `${label}：登录页`);
      this.emit(state);
      await new Promise((resolve) => {
        this.pendingManual.set(task.id, resolve);
      });
      state.status = 'running';
      state.message = `已确认登录 ${label}`;
      this.log(state, 'info', `${label}：已确认登录，开始学习课程`);
      this.emit(state);
      return;
    }

    const loginUrl = this.resolveLoginUrl(task);
    this.log(state, 'info', `${label}：打开登录首页 ${this.shortUrl(loginUrl)}`);
    await this.gotoWithRetry(page, loginUrl, state, `${label}：登录首页`);
    await this.waitForLoginLanding(page, task, state, account.username);

    if (await this.isLoggedIn(page, task, account.username)) {
      this.log(state, 'info', `${label}：当前会话已登录，跳过登录步骤`);
      return;
    }

    await this.openLoginDialog(page, task, state);

    const usernameField = await this.findField(page, task.usernameSelector, 'username', state);
    const passwordField = await this.findField(page, task.passwordSelector, 'password', state);
    if (!usernameField) {
      throw new Error('未找到账号输入框，请填写账号选择器');
    }
    if (!passwordField) {
      throw new Error('未找到密码输入框，请填写密码选择器');
    }

    await this.fillText(usernameField, account.username);
    await this.fillText(passwordField, account.password);

    const loginButton = await this.findLoginButton(page, task.loginButtonSelector, state);
    if (loginButton) {
      await loginButton.click();
      this.log(state, 'info', `${label}：已点击登录按钮`);
    } else {
      await passwordField.press('Enter');
      this.log(state, 'warn', `${label}：未找到登录按钮，已按回车提交`);
    }
    const waitMs = Math.max(0, Number(task.waitSecondsAfterLogin) || 0) * 1000;
    if (waitMs > 0) {
      await page.waitForTimeout(waitMs);
    }
    const loginConfirmed = await this.waitForLoginApplied(page, task, state, account);
    if (!loginConfirmed) {
      throw new Error('登录后未确认到已登录状态，请检查账号密码或是否需要验证码');
    }
    this.log(state, 'info', `${label}：登录成功（当前 ${this.shortUrl(page.url())}），开始进入课程`);
  }

  async waitForLoginLanding(page, task, state, username) {
    const deadline = Date.now() + 15000;
    let lastUrl = page.url();
    while (Date.now() < deadline) {
      if (this.isStopped(state.taskId)) throw new Error('任务已停止');
      const url = page.url();
      if (url !== lastUrl) {
        lastUrl = url;
        await page.waitForTimeout(500);
      }
      const loggedIn = await this.isLoggedIn(page, task, username);
      const hasLoginButton = await this.hasVisible(page, this.loginOpenSelectors(task));
      if (loggedIn || hasLoginButton) {
        await page.waitForTimeout(600);
        return;
      }
      await page.waitForTimeout(800);
    }
  }

  async waitForLoginApplied(page, task, state, account) {
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      if (this.isStopped(state.taskId)) throw new Error('任务已停止');
      if (await this.isLoggedIn(page, task, account?.username)) return true;
      const text = await page.locator('body').innerText().catch(() => '');
      if (/(账号或密码|密码错误|用户名或密码|验证码错误|账号被锁定)/.test(text)) {
        throw new Error('登录未成功，请检查账号密码或平台是否需要验证码');
      }
      await page.waitForTimeout(1000);
    }
    return false;
  }

  async fillText(locator, value) {
    await locator.click();
    await locator.fill(String(value || ''));
    const typed = await locator.inputValue().catch(() => '');
    if (typed === String(value || '')) return;
    await locator.fill('');
    await locator.type(String(value || ''), { delay: 15 });
  }

  resolveLoginUrl(task) {
    const configured = String(task.loginUrl || '').trim();
    const courseUrl = String(task.courses?.[0]?.url || '').trim();
    const looksLikeCourse = (value) => /(vedio\/play|courseId|lessonId|chapterId|course\/)/.test(value);
    try {
      const url = new URL(configured || courseUrl);
      if (!configured || looksLikeCourse(configured)) {
        if (/sia\.sinopec\.com/.test(url.hostname)) {
          return 'https://sia.sinopec.com/learn/';
        }
        return `${url.protocol}//${url.host}`;
      }
      return configured;
    } catch {
      return configured || courseUrl;
    }
  }

  async hasVisible(page, selector) {
    for (const raw of String(selector || '').split(',')) {
      const part = raw.trim();
      if (!part) continue;
      try {
        const locator = page.locator(`${part}:visible`).first();
        if (await locator.count()) return true;
      } catch {
        // try next selector
      }
    }
    return false;
  }

  loginOpenSelectors(task) {
    return [
      task.loginOpenButtonSelector,
      ...LOGIN_OPEN_SELECTORS
    ].filter(Boolean).join(', ');
  }

  async isLoggedIn(page, task, username) {
    username = String(username || task.accounts?.[0]?.username || '');
    const url = page.url();
    const text = await page.locator('body').innerText().catch(() => '');
    if (!text) return false;
    if (/(learningSpace|study_train|个人中心|注销登录)/.test(text) && !/(请登录|重新登录)/.test(text)) {
      return true;
    }
    if (username && text.includes(username)) return true;
    if (/(learningSpace|study_train|logout|loginOut)/i.test(url)) return true;
    const hasLogin = await this.hasVisible(page, this.loginOpenSelectors(task));
    const hasLoginForm = await page.locator('input[type="password"]:visible').count().catch(() => 0) > 0;
    if (hasLogin || hasLoginForm) return false;
    return true;
  }

  async openLoginDialog(page, task, state) {
    const selectors = [task.loginOpenButtonSelector, ...LOGIN_OPEN_SELECTORS].filter(Boolean);
    for (const selector of selectors) {
      try {
        const locator = page.locator(selector).first();
        await locator.waitFor({ state: 'visible', timeout: 5000 });
        await locator.click({ timeout: 5000 });
        const dialogReady = await page.locator('input[type="password"]:visible, input[placeholder*="账号"]:visible')
          .first()
          .waitFor({ state: 'visible', timeout: 2500 })
          .then(() => true)
          .catch(() => false);
        if (dialogReady) {
          this.log(state, 'info', `已点击登录入口：${selector}`);
          return true;
        }
        this.log(state, 'warn', `点击登录入口 ${selector} 后未出现登录表单，尝试下一个入口`);
      } catch {
        if (this.isStopped(state.taskId)) throw new Error('任务已停止');
        // try next candidate
      }
    }
    this.log(state, 'info', '未找到登录入口按钮，直接尝试识别登录表单');
    return false;
  }

  async findField(page, preferred, kind, state) {
    const label = kind === 'username' ? '账号' : '密码';
    if (preferred) {
      try {
        const locator = page.locator(`${preferred}:visible`).last();
        await locator.waitFor({ state: 'visible', timeout: 10000 });
        return locator;
      } catch {
        if (this.isStopped(state.taskId)) throw new Error('任务已停止');
        this.log(state, 'warn', `选择器 ${preferred} 未匹配，尝试自动识别${label}输入框`);
      }
    }
    const selectors = kind === 'username' ? USERNAME_SELECTORS : PASSWORD_SELECTORS;
    for (const selector of selectors) {
      try {
        const locator = page.locator(`${selector}:visible`).last();
        await locator.waitFor({ state: 'visible', timeout: 2500 });
        this.log(state, 'info', `已自动识别${label}输入框：${selector}`);
        return locator;
      } catch {
        if (this.isStopped(state.taskId)) throw new Error('任务已停止');
        // try next candidate
      }
    }
    return null;
  }

  async findLoginButton(page, preferred, state) {
    if (preferred) {
      try {
        const locator = page.locator(`${preferred}:visible`).last();
        await locator.waitFor({ state: 'visible', timeout: 8000 });
        return locator;
      } catch {
        if (this.isStopped(state.taskId)) throw new Error('任务已停止');
        this.log(state, 'warn', `登录按钮选择器 ${preferred} 未匹配，尝试自动识别`);
      }
    }
    for (const selector of LOGIN_BUTTON_SELECTORS) {
      try {
        const locator = page.locator(`${selector}:visible`).last();
        await locator.waitFor({ state: 'visible', timeout: 2500 });
        this.log(state, 'info', `已自动识别登录按钮：${selector}`);
        return locator;
      } catch {
        if (this.isStopped(state.taskId)) throw new Error('任务已停止');
        // try next candidate
      }
    }
    return null;
  }

  async processCourse(page, task, course, state) {
    const startedAt = Date.now();
    const title = course.name || course.url;
    state.courseLabel = title;
    state.message = `正在学习：${title}`;
    this.emit(state);
    this.log(state, 'info', `进入课程 ${title}`);

    await this.openCoursePage(page, course, state);
    await this.reenterCourseIfRedirected(page, task, course, state);

    // 进入课程后先核对学习状态：累计学习时长 >= 视频时长，或状态已通过 → 跳过本课
    const doneState = await this.detectCompletedState(page);
    if (doneState.skip) {
      state.lessonsDone += 1;
      state.message = `已完成 ${state.lessonsDone} 节（已通过，跳过）`;
      this.log(state, 'info', `跳过课程「${title}」：${doneState.reason}，无需重新学习`);
      return;
    }

    let found = await this.ensureVideoPlaying(page, task, state);
    if (!found) {
      const courseState = await this.waitForCourseContent(page, task, course, state);
      if (courseState.found) {
        found = courseState.found;
      } else if (courseState.completed) {
        state.lessonsDone += 1;
        state.message = `已完成 ${state.lessonsDone} 节（课程已通过）`;
        const reason = courseState.skipReason ? `（${courseState.skipReason}）` : '';
        this.log(state, 'info', `课程已识别且已通过，无需学习，计入 ${state.lessonsDone} 节${reason}`);
        return;
      } else if (courseState.recognized) {
        this.log(state, 'warn', `已进入课程页，但未找到视频或播放按钮，跳过 ${title}`);
        return;
      } else {
        this.log(state, 'warn', `未识别到课程内容（${this.shortUrl(page.url())}），跳过 ${title}`);
        return;
      }
    }

    let lastHeartbeat = Date.now();
    let lastProgressLog = Date.now();
    let lastLoggedPercent = -1;
    let lastPausedLog = 0;
    let lastStatusCheck = Date.now();
    while (!this.isStopped(task.id)) {
      const info = await this.probeVideo(page, task);
      if (!info || !info.found) {
        const again = await this.ensureVideoPlaying(page, task, state);
        if (!again) {
          this.log(state, 'warn', '视频暂时不可见，继续等待...');
          await page.waitForTimeout(POLL_MS);
          continue;
        }
      } else {
        const currentTime = Number(info.currentTime) || 0;
        const duration = Number(info.duration) || 0;
        const now = Date.now();
        if (duration > 0 && Number.isFinite(duration)) {
          const percent = Math.min(100, Math.floor((currentTime / duration) * 100));
          const played = fmtDuration(currentTime);
          const total = fmtDuration(duration);
          if (
            now - lastProgressLog >= 30000 ||
            percent === 100 ||
            (percent > 0 && percent >= lastLoggedPercent + 10)
          ) {
            lastProgressLog = now;
            lastLoggedPercent = Math.max(lastLoggedPercent, percent);
            state.message = `正在学习：${title}（${played} / ${total}，${percent}%）`;
            this.log(state, 'info', `播放进度：${played} / ${total}（${percent}%）`);
          }
        }
        // 每 30 秒核对一次平台学习状态：累计学习时长达标/状态已通过 → 提前完成本节
        if (now - lastStatusCheck >= 30000) {
          lastStatusCheck = now;
          const liveState = await this.detectCompletedState(page);
          if (liveState.skip) {
            state.lessonsDone += 1;
            state.message = `已完成 ${state.lessonsDone} 节（平台已判定通过）`;
            this.log(state, 'info', `「${title}」已被平台判定通过（${liveState.reason}），提前完成本节`);
            if (task.autoNext) {
              const clicked = await this.clickNextInFrames(page, task);
              if (clicked) {
                this.log(state, 'info', '已点击“下一节”，继续学习');
                await page.waitForTimeout(3000);
                continue;
              }
              this.log(state, 'warn', '未找到“下一节”按钮，本节处理结束');
            }
            return;
          }
        }
        if (info.ended || (duration > 0 && Number.isFinite(duration) && currentTime >= duration - 1.5)) {
          state.lessonsDone += 1;
          state.message = `已完成 ${state.lessonsDone} 节`;
          this.log(state, 'info', `本节播放完成，已学完 ${state.lessonsDone} 节`);
          if (task.autoNext && task.nextButtonSelector) {
            const clicked = await this.clickNextInFrames(page, task);
            if (clicked) {
              this.log(state, 'info', '已点击“下一节”，继续学习');
              await page.waitForTimeout(3000);
              continue;
            }
            this.log(state, 'warn', '未找到“下一节”按钮，本节处理结束');
          } else if (task.autoNext) {
            const clicked = await this.clickNextInFrames(page, task);
            if (clicked) {
              this.log(state, 'info', '已自动识别“下一节”并继续学习');
              await page.waitForTimeout(3000);
              continue;
            }
          }
          return;
        }
        if (info.paused) {
          await this.resumeVideo(page, task);
          if (now - lastPausedLog > 30000) {
            lastPausedLog = now;
            this.log(state, 'warn', '检测到视频暂停，已尝试恢复播放');
          }
        }
        if (task.keepAlive && Date.now() - lastHeartbeat > 60000) {
          lastHeartbeat = Date.now();
          await page.mouse.wheel(0, 120).catch(() => {});
          await page.mouse.wheel(0, -120).catch(() => {});
        }
        const maxMs = Math.max(0, Number(task.maxMinutesPerLesson) || 0) * 60000;
        if (maxMs > 0 && Date.now() - startedAt > maxMs) {
          this.log(state, 'warn', `本节超过 ${task.maxMinutesPerLesson} 分钟，自动进入下一节`);
          return;
        }
      }
      await page.waitForTimeout(POLL_MS);
    }
  }

  async waitForCourseContent(page, task, course, state) {
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      if (this.isStopped(state.taskId)) throw new Error('任务已停止');
      const doneState = await this.detectCompletedState(page);
      if (doneState.skip) {
        return { recognized: true, completed: true, skipReason: doneState.reason };
      }
      const video = await this.probeVideo(page, task);
      if (video && video.found) return { found: video };
      const pageState = await this.detectCoursePageState(page, course);
      if (pageState.recognized) return pageState;
      await page.waitForTimeout(2500);
    }
    return { recognized: false, completed: false };
  }

  async detectCoursePageState(page, course) {
    const title = this.courseTitleFromUrl(course);
    const isSia = /sia\.sinopec\.com/.test(page.url());
    const recognized = isSia
      ? /(学习状态|完成进度|学习进度|学习评论资料|抱歉该课程下目前还未添加学习视频)/
      : null;

    for (const frame of page.frames()) {
      const data = await frame.evaluate(() => {
        const read = (el) => (el && el.innerText ? el.innerText : '');
        const normalized = (s) => String(s || '').replace(/\s+/g, ' ').trim();
        const progressEl = document.querySelector('.course-progress')
          || document.querySelector('[class*="course-progress"]')
          || document.querySelector('[class*="progress"]')
          || document.querySelector('[class*="rate"]');
        const progress = normalized(read(progressEl));
        const looksLikeProgressPanel = /(进度|完成|学完|学习状态)/.test(progress) && /\d/.test(progress);
        return {
          body: document.body ? read(document.body) : '',
          progress,
          hasProgressPanel: Boolean(progressEl) && looksLikeProgressPanel
        };
      }).catch(() => null);
      if (!data || !data.body) continue;
      const body = data.body.replace(/\s+/g, ' ');
      if (data.hasProgressPanel) {
        const percent = this.extractPercent(data.progress);
        return { recognized: true, completed: percent === 100 };
      }
      if (title && body.includes(title)) {
        return { recognized: true, completed: this.isCompletedByProgressText(data.progress) || this.isCompletedByProgressText(body) };
      }
      if (recognized && recognized.test(body)) {
        return { recognized: true, completed: this.isCompletedByProgressText(data.progress) || this.isCompletedByProgressText(body) };
      }
    }
    return { recognized: false, completed: false };
  }

  extractPercent(text) {
    const normalized = String(text || '').replace(/\s+/g, ' ');
    const match = normalized.match(/(?:完成进度|学习进度|进度)\s*[:：]?\s*(\d{1,3})\s*%/) ||
      normalized.match(/(\d{1,3})\s*%/);
    if (!match) return null;
    const value = Number(match[1]);
    return Number.isFinite(value) ? value : null;
  }

  isCompletedByProgressText(text) {
    const normalized = String(text || '').replace(/\s+/g, ' ').trim();
    if (!normalized) return false;
    if (/(?:完成进度|学习进度)\s*[:：]?\s*100\s*%/.test(normalized)) return true;
    if (/(?:已通过|已学完|学习完成)[\s\S]{0,12}100\s*%/.test(normalized)) return true;
    if (/(?:完成|学完)\s*[:：]?\s*100\s*%/.test(normalized)) return true;
    if (/学习状态\s*[:：]\s*通过/.test(normalized)) return true;
    return false;
  }

  courseTitleFromUrl(course) {
    try {
      const hash = new URL(course.url).hash;
      const match = hash.match(/[?&]courseName=([^&]+)/);
      if (match) return decodeURIComponent(match[1]);
    } catch {
      // fall through
    }
    return String(course.name || '').trim();
  }

  async reenterCourseIfRedirected(page, task, course, state) {
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      if (this.isStopped(state.taskId)) throw new Error('任务已停止');
      if (this.isCoursePage(page.url(), course.url)) {
        if (await this.courseContentVisible(page, course)) return;
        await page.waitForTimeout(1500);
        if (await this.courseContentVisible(page, course)) return;
        this.log(state, 'warn', `课程页地址已打开但内容未加载（当前 ${this.shortUrl(page.url())}），第 ${attempt} 次重新进入课程页`);
      } else {
        this.log(state, 'warn', `课程页被跳转（当前 ${this.shortUrl(page.url())}），第 ${attempt} 次重新进入课程页`);
      }
      const info = await this.probeVideo(page, task);
      if (info && info.found) return;
      if (this.isStopped(state.taskId)) throw new Error('任务已停止');
      await this.openCoursePage(page, course, state);
    }
  }

  async openCoursePage(page, course, state) {
    const url = String(course.url || '').trim();
    try {
      const current = new URL(page.url());
      const target = new URL(url);
      if (current.origin === target.origin && current.pathname === target.pathname && target.hash) {
        this.log(state, 'info', `切换到课程路由：${this.shortUrl(url)}`);
        await page.evaluate((hash) => { location.hash = hash; }, target.hash);
        await page.waitForTimeout(2500);
        return;
      }
    } catch {
      // fall through to full navigation
    }
    await this.gotoWithRetry(page, url, state, '课程页');
    await page.waitForTimeout(2500);
  }

  async courseContentVisible(page, course) {
    const title = this.courseTitleFromUrl(course);
    for (const frame of page.frames()) {
      const data = await frame.evaluate(() => {
        const read = (el) => (el && el.innerText ? el.innerText : '');
        return {
          body: document.body ? read(document.body) : '',
          progress: read(document.querySelector('.course-progress') || document.querySelector('[class*="course-progress"]')),
          video: Boolean(document.querySelector('video'))
        };
      }).catch(() => null);
      if (!data) continue;
      if (data.video) return true;
      if (data.progress && /\d/.test(data.progress)) return true;
      const body = data.body.replace(/\s+/g, ' ');
      if (title && body.includes(title)) return true;
      if (/(完成进度|学习状态|学习进度)/.test(body)) return true;
    }
    return false;
  }

  isCoursePage(current, target) {
    try {
      const cur = new URL(current);
      const tgt = new URL(target);
      if (cur.origin !== tgt.origin) return false;
      const isCourseTarget = tgt.hash.includes('vedio/play') ||
        tgt.hash.includes('courseId') ||
        tgt.pathname.includes('/course');
      if (isCourseTarget) {
        return cur.hash.includes('vedio/play') ||
          cur.hash.includes('courseId') ||
          cur.pathname.includes('/course');
      }
      return cur.href === tgt.href;
    } catch {
      return current === target;
    }
  }

  shortUrl(url) {
    try {
      const u = new URL(url);
      return `${u.origin}${u.pathname}${u.hash || ''}`;
    } catch {
      return url || '';
    }
  }

  async collectPageTexts(page) {
    const texts = [];
    for (const frame of page.frames()) {
      const body = await frame.evaluate(() => (document.body ? document.body.innerText : '')).catch(() => '');
      if (body) texts.push(String(body).replace(/\s+/g, ' '));
    }
    return texts;
  }

  /**
   * 检测课程是否已完成（无需重新学习）：
   * 1) 课程级：完成进度 100% / 学习状态已通过
   * 2) 课时级：页面上全部课时均已通过（状态已通过，或累计学习时长 >= 视频时长）
   * 返回 { skip, reason }
   */
  async detectCompletedState(page) {
    const texts = await this.collectPageTexts(page);
    const all = texts.join(' ');
    if (
      /(?:完成进度|学习进度)[\s\S]{0,8}?100\s*%/.test(all) ||
      /学习状态[:：]?\s*(?:已通过|已完成)/.test(all)
    ) {
      return { skip: true, reason: '课程完成进度 100% / 学习状态已通过' };
    }
    let groups = [];
    for (const text of texts) {
      groups = groups.concat(parseLessonStates(text));
    }
    if (groups.length) {
      const done = groups.filter((g) => isLessonComplete(g)).length;
      if (done === groups.length) {
        const detail = groups.map((g) => {
          const learned = fmtDuration(g.learnedSec) || '未知';
          const required = fmtDuration(g.requiredSec) || '未知';
          return `${learned}≥${required}${g.status ? `(${g.status})` : ''}`;
        }).join('、');
        return { skip: true, reason: `全部 ${groups.length} 个课时累计学习时长已满/已通过（${detail}）` };
      }
    }
    return { skip: false, reason: '' };
  }

  async ensureVideoPlaying(page, task, state) {
    let info = await this.probeVideo(page, task);
    if (info && info.found) {
      if (info.duration > 0) {
        this.log(state, 'info', `视频已开始播放，时长约 ${fmtDuration(info.duration)}`);
      }
      return info;
    }
    const selectors = [task.playButtonSelector, ...PLAY_BUTTON_SELECTORS].filter(Boolean);
    for (const selector of selectors) {
      this.log(state, 'info', `尝试点击播放按钮：${selector}`);
      const clicked = await this.clickInFrames(page, selector);
      await page.waitForTimeout(2500);
      info = await this.probeVideo(page, task);
      if (info && info.found) {
        if (info.duration > 0) {
          this.log(state, 'info', `视频已开始播放，时长约 ${fmtDuration(info.duration)}`);
        }
        return info;
      }
      if (!clicked) continue;
    }
    return null;
  }

  async probeVideo(page, task) {
    const selector = task.videoSelector || 'video';
    for (const frame of page.frames()) {
      const result = await frame.evaluate((sel) => {
        const v = document.querySelector(sel);
        if (!v) return null;
        return {
          found: true,
          paused: Boolean(v.paused),
          ended: Boolean(v.ended),
          currentTime: v.currentTime,
          duration: v.duration
        };
      }, selector).catch(() => null);
      if (result && result.found) {
        return { frame, ...result };
      }
    }
    return null;
  }

  async resumeVideo(page, task) {
    const selector = task.videoSelector || 'video';
    for (const frame of page.frames()) {
      const ok = await frame.evaluate((sel) => {
        const v = document.querySelector(sel);
        if (!v) return false;
        try {
          v.muted = true;
          const p = v.play();
          if (p && p.catch) p.catch(() => {});
          return true;
        } catch {
          return false;
        }
      }, selector).catch(() => false);
      if (ok) return true;
    }
    return false;
  }

  async clickInFrames(page, selector) {
    for (const frame of page.frames()) {
      try {
        const locator = frame.locator(selector).first();
        if (await locator.count()) {
          await locator.click({ timeout: 5000 });
          return true;
        }
      } catch {
        // try next frame
      }
    }
    return false;
  }

  async clickNextInFrames(page, task) {
    const selectors = [task.nextButtonSelector, ...NEXT_LESSON_SELECTORS].filter(Boolean);
    for (const selector of selectors) {
      if (await this.clickInFrames(page, selector)) return true;
    }
    return false;
  }

  stop(taskId) {
    const state = this.runs.get(taskId);
    if (!state || ['done', 'stopped', 'error'].includes(state.status)) {
      return { ok: false, error: '任务未在运行' };
    }
    this.stopRequests.add(taskId);
    const resolve = this.pendingManual.get(taskId);
    if (resolve) {
      this.pendingManual.delete(taskId);
      resolve();
    }
    if (state.browser) {
      state.browser.close().catch(() => {});
    }
    this.log(state, 'warn', '正在停止...');
    return { ok: true };
  }

  continueManual(taskId) {
    const resolve = this.pendingManual.get(taskId);
    if (!resolve) return { ok: false, error: '当前没有等待手动登录的步骤' };
    this.pendingManual.delete(taskId);
    resolve();
    return { ok: true };
  }

  log(state, level, message) {
    state.logs.push({ t: Date.now(), level, message });
    if (state.logs.length > MAX_LOGS) {
      state.logs.splice(0, state.logs.length - MAX_LOGS);
    }
    this.emit(state);
  }

  emit(state) {
    if (typeof this.onUpdate === 'function') {
      this.onUpdate(state);
    }
  }
}
