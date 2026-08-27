import { chromium } from 'playwright';

const CHANNELS = process.argv.includes('--chromium') ? [null] : ['msedge', null];

async function tryLaunch(headless, channel) {
  const options = { headless, args: ['--disable-http2'] };
  if (channel) options.channel = channel;
  const browser = await chromium.launch(options);
  const version = browser.version();
  await browser.close();
  return { version, used: channel ? (channel === 'msedge' ? '系统 Edge' : '系统 Chrome') : '内置 Chromium' };
}

async function launchWithFallback(headless) {
  let lastError = null;
  for (const channel of CHANNELS) {
    try {
      return await tryLaunch(headless, channel);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

try {
  const headless = await launchWithFallback(true);
  console.log(`[headless] 无头浏览器启动成功（${headless.used}），Chromium ${headless.version}`);
  try {
    const headed = await launchWithFallback(false);
    console.log(`[headed] 有头浏览器启动成功（${headed.used}），Chromium ${headed.version}`);
  } catch (error) {
    console.log(`[headed] 跳过（手动登录模式需要 Windows 桌面会话）：${error.message || error}`);
  }
  console.log('[result] PASS');
} catch (error) {
  console.error('[result] FAIL');
  console.error(error && (error.stack || error.message || error));
  process.exitCode = 1;
}
