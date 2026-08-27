'use strict';

const fs = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');
const iconv = require('iconv-lite');
const { parsePdf, parseXml, buildName } = require('./parser');

const EXTS = new Set(['.pdf', '.xml', '.zip']);

function walkFiles(dir, out) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const ent of entries) {
    if (ent.name.startsWith('.')) continue;
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      walkFiles(full, out);
    } else if (ent.isFile() && EXTS.has(path.extname(ent.name).toLowerCase())) {
      out.push(full);
    }
  }
  return out;
}

function expandPaths(paths) {
  const files = [];
  for (const p of paths || []) {
    if (!p || typeof p !== 'string') continue;
    try {
      const stat = fs.statSync(p);
      if (stat.isDirectory()) walkFiles(p, files);
      else if (stat.isFile()) files.push(p);
    } catch {
      // keep going; missing paths are reported by the UI
    }
  }
  return files;
}

function decodeZipName(name) {
  if (/[^\u0000-\u00ff]/.test(name)) return name;
  const bytes = Buffer.from(name, 'latin1');
  const utf8 = bytes.toString('utf8');
  if (!utf8.includes('\uFFFD')) return utf8;
  try {
    return iconv.decode(bytes, 'gb18030');
  } catch {
    return name;
  }
}

function baseName(file) {
  const ext = path.extname(file);
  return path.basename(file, ext);
}

function makeSource(kind, filePath, type, extra) {
  return {
    id: `${kind}:${filePath}:${extra.entryName || ''}`,
    kind,
    type,
    filePath,
    display: extra.display || filePath,
    originalName: path.basename(filePath),
    originalBase: baseName(filePath),
    ext: extra.ext || path.extname(filePath).toLowerCase(),
    containerZip: extra.containerZip || null,
    entryName: extra.entryName || null,
    meta: extra.meta || null,
    zip: extra.zip || null,
    newName: null,
    status: 'pending',
    warnings: [],
    paired: []
  };
}

function mergeMeta(group) {
  const pdf = group.find((s) => s.meta && (s.type === 'pdf' || s.type === 'zip'));
  const xml = group.find((s) => s.meta && s.type === 'xml');
  const all = group.map((s) => s.meta).filter(Boolean);
  const pick = (field, prefer = []) => {
    for (const m of prefer) if (m && m[field]) return m[field];
    for (const m of all) if (m && m[field]) return m[field];
    return null;
  };
  const stations = [];
  for (const m of all) for (const s of m.stations || []) if (!stations.includes(s)) stations.push(s);
  const meta = {
    invoiceNo: pick('invoiceNo'),
    amount: pick('amount'),
    station: pick('station', [pdf]),
    project: pick('project'),
    title: pick('title', [pdf]),
    stations,
    multipleStations: stations.length > 1,
    multiSite: all.some((m) => m.multiSite),
    rawProject: pick('rawProject')
  };
  return meta;
}

async function readZipSources(zipPath) {
  const zip = new AdmZip(zipPath);
  const entries = zip.getEntries().filter((e) => !e.isDirectory);
  const invoiceEntries = [];
  const allEntries = [];
  for (const entry of entries) {
    const name = decodeZipName(entry.entryName);
    const ext = path.extname(name).toLowerCase();
    allEntries.push({ entry, name, ext });
    if (ext === '.pdf' || ext === '.xml') {
      const buffer = entry.getData();
      let meta = null;
      try {
        meta = ext === '.pdf' ? await parsePdf(buffer) : parseXml(buffer);
      } catch (e) {
        meta = { invoiceNo: null, amount: null, station: null, project: null, title: null, stations: [], error: e.message };
      }
      invoiceEntries.push({ entry, name, ext, meta });
    }
  }
  if (invoiceEntries.length === 0) {
    return [makeSource('zip', zipPath, 'zip', {
      display: zipPath,
      meta: { invoiceNo: null, amount: null, station: null, project: null, title: null, stations: [], multiSite: false },
      zip: { single: false, entries: [] },
      warnings: ['压缩包内未找到发票 PDF/XML']
    })];
  }

  const sources = [];
  if (invoiceEntries.length === 1) {
    const one = invoiceEntries[0];
    sources.push(makeSource('zip', zipPath, 'zip', {
      display: zipPath,
      meta: one.meta,
      zip: {
        single: true,
        innerExt: one.ext,
        innerEntryName: one.name,
        entries: allEntries.map((e) => ({ name: e.name, ext: e.ext }))
      }
    }));
  } else {
    for (const one of invoiceEntries) {
      const source = makeSource('zip-entry', zipPath, one.ext === '.pdf' ? 'pdf' : 'xml', {
        display: `${path.basename(zipPath)} -> ${one.name}`,
        containerZip: zipPath,
        entryName: one.name,
        ext: one.ext,
        meta: one.meta,
        zip: {
          single: false,
          entries: allEntries.map((e) => ({ name: e.name, ext: e.ext }))
        }
      });
      sources.push(source);
    }
  }
  return sources;
}

async function scanPaths(inputPaths, template) {
  const files = expandPaths(inputPaths);
  const sources = [];
  const missing = (inputPaths || []).filter((p) => p && !fs.existsSync(p));
  for (const file of files) {
    const ext = path.extname(file).toLowerCase();
    try {
      if (ext === '.pdf') {
        const meta = await parsePdf(fs.readFileSync(file));
        sources.push(makeSource('file', file, 'pdf', { display: file, meta }));
      } else if (ext === '.xml') {
        const meta = parseXml(fs.readFileSync(file));
        sources.push(makeSource('file', file, 'xml', { display: file, meta }));
      } else if (ext === '.zip') {
        const zipSources = await readZipSources(file);
        sources.push(...zipSources);
      }
    } catch (e) {
      sources.push(makeSource('file', file, ext.slice(1), {
        display: file,
        meta: { invoiceNo: null, amount: null, station: null, project: null, title: null, stations: [], error: e.message }
      }));
    }
  }

  const groups = new Map();
  for (const s of sources) {
    const no = s.meta && s.meta.invoiceNo;
    if (!no) {
      s.status = 'error';
      s.warnings.push('未识别到发票号码');
      continue;
    }
    if (!groups.has(no)) groups.set(no, []);
    groups.get(no).push(s);
  }
  for (const [no, group] of groups) {
    const canonical = mergeMeta(group);
    for (const s of group) {
      s.meta = canonical;
      s.paired = group.filter((o) => o.id !== s.id).map((o) => o.originalName);
    }
  }

  for (const s of sources) {
    if (!s.meta.invoiceNo) continue;
    const base = buildName(s.meta, template);
    if (s.type === 'zip') s.newName = `${base}.zip`;
    else s.newName = `${base}${s.ext || path.extname(s.entryName || '') || '.pdf'}`;

    const m = s.meta;
    const warnings = [];
    if (!m.amount) warnings.push('未识别到总金额');
    if (!m.station) warnings.push('未识别到加油站/站点');
    if (!m.project) warnings.push('未识别到项目');
    if (m.multipleStations) warnings.push('识别到多个站点，请核对');
    if (m.multiSite) warnings.push('备注可能涉及多个站点，请核对');
    if (m.error) warnings.push(m.error);
    s.warnings = warnings;
    if (!m.invoiceNo || !m.amount) s.status = 'error';
    else if (warnings.length > 0) s.status = 'attention';
    else s.status = 'ok';
  }

  const invoiceNos = new Set(sources.map((s) => s.meta && s.meta.invoiceNo).filter(Boolean));
  return {
    sources,
    missing,
    summary: {
      fileCount: files.length,
      sourceCount: sources.length,
      invoiceCount: invoiceNos.size,
      pairedCount: groups.size > 0 ? [...groups.values()].filter((g) => g.length > 1).length : 0,
      attentionCount: sources.filter((s) => s.status === 'attention').length,
      errorCount: sources.filter((s) => s.status === 'error').length
    }
  };
}

module.exports = { scanPaths, expandPaths };
