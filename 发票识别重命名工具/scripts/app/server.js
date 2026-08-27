'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');
const { execFile, spawn } = require('child_process');
const { scanPaths } = require('./lib/scanner');
const { buildOperations, applyOperations } = require('./lib/renamer');

const ROOT = __dirname;
const PUBLIC = path.join(ROOT, 'public');
const PORT = Number(process.argv[2] || process.env.PORT || 27180);

function sendJson(res, code, data) {
  const body = JSON.stringify(data);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store'
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (c) => {
      data += c;
      if (data.length > 20 * 1024 * 1024) {
        reject(new Error('请求体过大'));
        req.destroy();
      }
    });
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch (e) {
        reject(e);
      }
    });
    req.on('error', reject);
  });
}

function safePublicPath(urlPath) {
  let rel = decodeURIComponent(urlPath.split('?')[0]);
  if (rel === '/') rel = '/index.html';
  const file = path.normalize(path.join(PUBLIC, rel));
  if (!file.startsWith(PUBLIC)) return null;
  return file;
}

function pickFolder() {
  return new Promise((resolve) => {
    const cmd = process.platform === 'darwin'
      ? ['osascript', '-e', 'POSIX path of (choose folder with prompt "选择要处理的文件夹")']
      : process.platform === 'win32'
        ? ['powershell', '-NoProfile', '-Command',
          '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description="选择要处理的文件夹"; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$p=$d.SelectedPath; if($p){[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($p))}}']
        : null;
    if (!cmd) return resolve(null);
    execFile(cmd[0], cmd.slice(1), { timeout: 60000, windowsHide: true }, (err, stdout) => {
      if (err) return resolve(null);
      const out = stdout.toString().trim();
      if (!out) return resolve(null);
      try {
        resolve(Buffer.from(out, 'base64').toString('utf8'));
      } catch {
        resolve(null);
      }
    });
  });
}

function pickFiles() {
  return new Promise((resolve) => {
    const script = [
      'set theFiles to choose file with prompt "选择发票 PDF/XML/ZIP 文件" of type {"pdf","xml","zip"} with multiple selections allowed',
      'set out to ""',
      'repeat with f in theFiles',
      '  set out to out & POSIX path of f & linefeed',
      'end repeat',
      'return out'
    ].join('\n');
    const cmd = process.platform === 'darwin'
      ? ['osascript', '-e', script]
      : process.platform === 'win32'
        ? ['powershell', '-NoProfile', '-Command',
          '[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Add-Type -AssemblyName System.Windows.Forms; $o=New-Object System.Windows.Forms.OpenFileDialog; $o.Multiselect=$true; $o.Filter="发票文件 (*.pdf;*.xml;*.zip)|*.pdf;*.xml;*.zip"; if($o.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$joined=$o.FileNames -join "`n"; if($joined){[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($joined))}}']
        : null;
    if (!cmd) return resolve([]);
    execFile(cmd[0], cmd.slice(1), { timeout: 60000, windowsHide: true }, (err, stdout) => {
      if (err) return resolve([]);
      const out = stdout.toString().trim();
      if (!out) return resolve([]);
      try {
        const decoded = Buffer.from(out, 'base64').toString('utf8');
        resolve(decoded.split(/\r?\n/).map((s) => s.trim()).filter(Boolean));
      } catch {
        resolve([]);
      }
    });
  });
}

function openPath(p) {
  if (!p) return;
  const isUrl = /^https?:\/\//i.test(p);
  if (!isUrl && !fs.existsSync(p)) return;
  const cmd = process.platform === 'darwin' ? ['open', p]
    : process.platform === 'win32' ? ['cmd', '/c', 'start', '', p]
      : ['xdg-open', p];
  const child = spawn(cmd[0], cmd.slice(1), { detached: true, stdio: 'ignore' });
  child.on('error', () => {
    if (process.platform === 'darwin' && isUrl) {
      execFile('osascript', ['-e', `open location "${p}"`], () => {});
    }
  });
  child.unref();
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
  try {
    if (req.method === 'GET' && url.pathname === '/api/ping') {
      return sendJson(res, 200, { ok: true, version: '1.0.0' });
    }

    if (req.method === 'POST' && url.pathname === '/api/pick-folder') {
      return sendJson(res, 200, { path: await pickFolder() });
    }

    if (req.method === 'POST' && url.pathname === '/api/pick-files') {
      return sendJson(res, 200, { paths: await pickFiles() });
    }

    if (req.method === 'POST' && url.pathname === '/api/open-path') {
      const body = await readBody(req);
      openPath(body.path);
      return sendJson(res, 200, { ok: true });
    }

    if (req.method === 'POST' && url.pathname === '/api/scan') {
      const body = await readBody(req);
      const result = await scanPaths(body.paths || [], body.template || '{remark}_{amount}_{invoice}');
      return sendJson(res, 200, result);
    }

    if (req.method === 'POST' && url.pathname === '/api/apply') {
      const body = await readBody(req);
      const ops = buildOperations(body.rows || [], {
        mode: body.mode || 'inplace',
        outputDir: body.outputDir || '',
        extractSingleZip: !!body.extractSingleZip
      });
      const result = await applyOperations(ops, { dedupe: body.dedupe !== false });
      return sendJson(res, 200, { ...result, opCount: ops.length });
    }

    if (req.method === 'GET') {
      const file = safePublicPath(url.pathname);
      if (file && fs.existsSync(file)) {
        const type = file.endsWith('.html') ? 'text/html; charset=utf-8'
          : file.endsWith('.js') ? 'application/javascript; charset=utf-8'
            : file.endsWith('.css') ? 'text/css; charset=utf-8'
              : 'application/octet-stream';
        const data = fs.readFileSync(file);
        res.writeHead(200, { 'Content-Type': type, 'Content-Length': data.length, 'Cache-Control': 'no-store' });
        return res.end(data);
      }
    }

    sendJson(res, 404, { error: 'not found' });
  } catch (e) {
    sendJson(res, 500, { error: e.message, stack: e.stack });
  }
});

server.on('error', (err) => {
  console.error('服务启动失败:', err.message);
  process.exit(1);
});

server.listen(PORT, '127.0.0.1', () => {
  const address = server.address();
  const url = `http://127.0.0.1:${address.port}/`;
  console.log('====================================================');
  console.log('发票识别重命名工具已启动');
  console.log(url);
  console.log('若页面未自动打开，请复制上面的地址到浏览器访问');
  console.log('识别完毕后可直接关闭本窗口');
  console.log('====================================================');
  if (!process.env.SKIP_AUTO_OPEN) setTimeout(() => openPath(url), 600);
});

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    server.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 500).unref();
  });
}
