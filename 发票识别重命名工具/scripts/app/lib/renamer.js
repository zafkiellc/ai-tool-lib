'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const AdmZip = require('adm-zip');
const { sanitizeName } = require('./parser');

function safeJoin(base, name) {
  const parts = name.split(/[\\/]/).filter((p) => p && p !== '.' && p !== '..');
  return path.join(base, ...parts);
}

function hashBuffer(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

function hashFile(file) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    let size = 0;
    const stream = fs.createReadStream(file);
    stream.on('data', (c) => {
      size += c.length;
      hash.update(c);
    });
    stream.on('error', reject);
    stream.on('end', () => resolve({ size, hash: hash.digest('hex') }));
  });
}

async function sameFileContent(a, b) {
  try {
    const [sa, sb] = await Promise.all([hashFile(a), hashFile(b)]);
    return sa.size === sb.size && sa.hash === sb.hash;
  } catch {
    return false;
  }
}

async function sameBufferAsFile(buf, file) {
  try {
    const stat = fs.statSync(file);
    if (!stat.isFile() || stat.size !== buf.length) return false;
    const f = await hashFile(file);
    return f.hash === hashBuffer(buf);
  } catch {
    return false;
  }
}

function uniquePath(target) {
  if (!fs.existsSync(target)) return target;
  const dir = path.dirname(target);
  const ext = path.extname(target);
  const base = path.basename(target, ext);
  for (let i = 2; i < 1000; i++) {
    const candidate = path.join(dir, `${base} (${i})${ext}`);
    if (!fs.existsSync(candidate)) return candidate;
  }
  return target;
}

function rebuiltZipMatches(sourceZip, targetZip, innerEntryName, innerExt, baseName) {
  try {
    const srcEntries = new AdmZip(sourceZip).getEntries().filter((e) => !e.isDirectory);
    const dstEntries = new AdmZip(targetZip).getEntries().filter((e) => !e.isDirectory);
    if (srcEntries.length !== dstEntries.length) return false;
    const dstByName = new Map();
    for (const e of dstEntries) {
      const name = decodeZipName(e.entryName);
      if (!dstByName.has(name)) dstByName.set(name, e);
    }
    for (const e of srcEntries) {
      const name = decodeZipName(e.entryName);
      const expected = name === innerEntryName ? `${baseName}${innerExt}` : name;
      const match = dstByName.get(expected);
      if (!match) return false;
      if (hashBuffer(e.getData()) !== hashBuffer(match.getData())) return false;
    }
    return true;
  } catch {
    return false;
  }
}

function newNameWithExt(row) {
  const name = sanitizeName(row.newName || row.originalName || '');
  const ext = row.type === 'zip' ? '.zip' : row.ext || '';
  if (name.toLowerCase().endsWith(ext.toLowerCase())) return name;
  return name + ext;
}

function buildOperations(rows, opts) {
  const ops = [];
  const mode = opts.mode === 'copy' ? 'copy' : 'inplace';
  const zipGroups = new Map();

  for (const row of rows || []) {
    if (!row || row.status === 'error' || !row.newName) continue;
    const targetName = newNameWithExt(row);
    const ext = path.extname(row.entryName || row.originalName || '').toLowerCase();

    if (row.kind === 'file') {
      const dir = mode === 'copy' ? opts.outputDir : path.dirname(row.filePath);
      if (!dir) continue;
      ops.push({
        type: mode === 'copy' ? 'copy-file' : 'rename-file',
        label: row.originalName,
        source: row.filePath,
        target: path.join(dir, targetName)
      });
      continue;
    }

    if (row.kind === 'zip' && row.zip && row.zip.single) {
      if (mode === 'copy') {
        const outZip = path.join(opts.outputDir, targetName);
        ops.push({
          type: 'rebuild-zip',
          label: row.originalName,
          source: row.filePath,
          target: outZip,
          row,
          innerEntryName: row.zip.innerEntryName,
          innerExt: row.zip.innerExt,
          entries: row.zip.entries
        });
        if (opts.extractSingleZip) {
          ops.push({
            type: 'extract-single-entry',
            label: `${row.originalName} -> ${row.zip.innerEntryName}`,
            source: row.filePath,
            target: path.join(opts.outputDir, `${path.basename(targetName, '.zip')}${row.zip.innerExt}`),
            entryName: row.zip.innerEntryName
          });
        }
      } else {
        const renamedZipPath = path.join(path.dirname(row.filePath), targetName);
        ops.push({
          type: 'rename-file',
          label: row.originalName,
          source: row.filePath,
          target: renamedZipPath
        });
        if (opts.extractSingleZip) {
          ops.push({
            type: 'extract-single-entry',
            label: `${row.originalName} -> ${row.zip.innerEntryName}`,
            source: renamedZipPath,
            target: path.join(path.dirname(row.filePath), `${path.basename(targetName, '.zip')}${row.zip.innerExt}`),
            entryName: row.zip.innerEntryName
          });
        }
      }
      continue;
    }

    if (row.kind === 'zip-entry' && row.containerZip) {
      if (!zipGroups.has(row.containerZip)) {
        zipGroups.set(row.containerZip, { zipPath: row.containerZip, rows: [], entries: row.zip ? row.zip.entries : [] });
      }
      zipGroups.get(row.containerZip).rows.push(row);
    }
  }

  for (const [zipPath, group] of zipGroups) {
    const zipBase = path.basename(zipPath, path.extname(zipPath));
    const baseDir = mode === 'copy' ? opts.outputDir : path.dirname(zipPath);
    const targetDir = path.join(baseDir, `${zipBase}_重命名结果`);
    const renames = new Map();
    for (const row of group.rows) {
      const name = newNameWithExt(row);
      renames.set(row.entryName, name);
    }
    ops.push({
      type: 'extract-zip',
      label: path.basename(zipPath),
      source: zipPath,
      target: targetDir,
      renames,
      entries: group.entries
    });
  }

  return ops;
}

async function applyOperations(ops, options) {
  const success = [];
  const failed = [];
  const skipped = [];
  const dedupe = !options || options.dedupe !== false;
  for (const op of ops) {
    try {
      if (op.type === 'rename-file') {
        if (!fs.existsSync(op.source)) {
          skipped.push({ label: op.label, from: op.source, to: op.target, action: '文件已处理过，跳过' });
          continue;
        }
        const target = uniquePath(op.target);
        fs.renameSync(op.source, target);
        success.push({ label: op.label, from: op.source, to: target, action: '重命名' });
      } else if (op.type === 'copy-file') {
        fs.mkdirSync(path.dirname(op.target), { recursive: true });
        if (dedupe && fs.existsSync(op.target) && await sameFileContent(op.source, op.target)) {
          skipped.push({ label: op.label, from: op.source, to: op.target, action: '已存在相同文件，跳过' });
          continue;
        }
        const target = uniquePath(op.target);
        fs.copyFileSync(op.source, target);
        success.push({ label: op.label, from: op.source, to: target, action: '复制' });
      } else if (op.type === 'extract-single-entry') {
        const zip = new AdmZip(op.source);
        const entry = zip.getEntries().find((e) => decodeZipName(e.entryName) === op.entryName);
        if (!entry) throw new Error('压缩包内未找到对应文件');
        fs.mkdirSync(path.dirname(op.target), { recursive: true });
        if (dedupe && fs.existsSync(op.target) && await sameBufferAsFile(entry.getData(), op.target)) {
          skipped.push({ label: op.label, from: `${path.basename(op.source)} -> ${op.entryName}`, to: op.target, action: '已存在相同文件，跳过' });
          continue;
        }
        const target = uniquePath(op.target);
        fs.writeFileSync(target, entry.getData());
        success.push({ label: op.label, from: `${path.basename(op.source)} -> ${op.entryName}`, to: target, action: '解压重命名' });
      } else if (op.type === 'rebuild-zip') {
        const zip = new AdmZip(op.source);
        const out = new AdmZip();
        const base = path.basename(op.target, '.zip');
        for (const entry of zip.getEntries()) {
          if (entry.isDirectory) continue;
          const name = decodeZipName(entry.entryName);
          if (name === op.innerEntryName) out.addFile(`${base}${op.innerExt}`, entry.getData());
          else out.addFile(name, entry.getData());
        }
        fs.mkdirSync(path.dirname(op.target), { recursive: true });
        if (dedupe && fs.existsSync(op.target) && rebuiltZipMatches(op.source, op.target, op.innerEntryName, op.innerExt, path.basename(op.target, '.zip'))) {
          skipped.push({ label: op.label, from: op.source, to: op.target, action: '已存在相同压缩包，跳过' });
          continue;
        }
        const target = uniquePath(op.target);
        out.writeZip(target);
        success.push({ label: op.label, from: op.source, to: target, action: '生成重命名压缩包' });
      } else if (op.type === 'extract-zip') {
        const zip = new AdmZip(op.source);
        fs.mkdirSync(op.target, { recursive: true });
        let count = 0;
        let skippedCount = 0;
        for (const entry of zip.getEntries()) {
          if (entry.isDirectory) continue;
          const name = decodeZipName(entry.entryName);
          const outName = op.renames.get(name) || name;
          const dest = safeJoin(op.target, outName);
          fs.mkdirSync(path.dirname(dest), { recursive: true });
          if (dedupe && fs.existsSync(dest) && await sameBufferAsFile(entry.getData(), dest)) {
            skippedCount++;
            continue;
          }
          const finalDest = uniquePath(dest);
          fs.writeFileSync(finalDest, entry.getData());
          count++;
        }
        if (count === 0) {
          skipped.push({ label: op.label, from: op.source, to: op.target, action: `目录内文件已全部存在，跳过（${skippedCount} 个）` });
        } else {
          const extra = skippedCount ? `（跳过 ${skippedCount} 个已存在）` : '';
          success.push({ label: op.label, from: op.source, to: op.target, action: `解压并重命名 ${count} 个文件${extra}` });
        }
      }
    } catch (e) {
      failed.push({ label: op.label, source: op.source, error: e.message });
    }
  }
  return { success, failed, skipped };
}

function decodeZipName(name) {
  if (/[^\u0000-\u00ff]/.test(name)) return name;
  const bytes = Buffer.from(name, 'latin1');
  const utf8 = bytes.toString('utf8');
  if (!utf8.includes('\uFFFD')) return utf8;
  try {
    const iconv = require('iconv-lite');
    return iconv.decode(bytes, 'gb18030');
  } catch {
    return name;
  }
}

module.exports = { buildOperations, applyOperations };
