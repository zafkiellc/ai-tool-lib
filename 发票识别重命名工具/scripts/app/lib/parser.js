'use strict';

const pdfParse = require('pdf-parse');
const iconv = require('iconv-lite');

function compactText(text) {
  return text
    .replace(/\u3000/g, '')
    .replace(/[ \t]/g, '')
    .replace(/备\n注/g, '备注')
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
    .join('\n');
}

function extractInvoiceNo(text) {
  const compact = text.replace(/[\s\u3000]/g, '');
  const m = compact.match(/发票号码[:：]?\s*(\d{10,30})/);
  if (m) return m[1];
  const m2 = text.match(/\b(\d{20})\b/);
  return m2 ? m2[1] : null;
}

function extractAmount(text) {
  const compact = text.replace(/[\s\u3000]/g, '');
  const m = compact.match(/圆整[¥￥]?\s*([0-9,]+\.\d{2})/);
  if (m) return m[1].replace(/,/g, '');
  const matches = [...text.matchAll(/[¥￥]\s*([0-9,]+\.\d{2})/g)];
  if (matches.length === 0) return null;
  return matches[matches.length - 1][1].replace(/,/g, '');
}

function cleanStation(raw) {
  let s = raw.trim();
  for (const prefix of ['中国石化', '中石化', '中国石油', '中石油', '石化']) {
    const idx = s.lastIndexOf(prefix);
    if (idx !== -1) {
      s = s.slice(idx + prefix.length);
      break;
    }
  }
  s = s.replace(/^[\d０-９]+/, '');
  if (s.includes('号')) s = s.replace(/.*[\d０-９]+号/, '');
  s = s
    .split(/[省市区县镇乡村\-]/)
    .map((x) => x.trim())
    .filter(Boolean)
    .pop() || s;
  return s;
}

function findStations(text) {
  const joined = text.replace(/\n/g, '');
  const re = /[\u4e00-\u9fffA-Za-z0-9·（）()]{1,24}?(?:加油站|充电站|加气站)/g;
  const out = [];
  let m;
  while ((m = re.exec(joined)) !== null) {
    const station = cleanStation(m[0]);
    if (!out.includes(station)) out.push(station);
  }
  return out;
}

function remarkSection(text) {
  const idx = text.lastIndexOf('备注');
  if (idx === -1) return text;
  return text.slice(idx + 2);
}

function extractProject(text) {
  const remark = remarkSection(text);
  const patterns = [
    /项目名称[:：]\s*([^\n]+)/,
    /工程名称[:：]\s*([^\n]+)/,
    /(?:^|\n)注\s*([^\n]+)/
  ];
  for (const re of patterns) {
    const m = remark.match(re) || text.match(re);
    if (m) {
      const p = m[1].trim();
      if (p && !/^(开票人|项目地址)/.test(p)) return p;
    }
  }
  return null;
}

function extractRemarkTitle(remarkText, station) {
  const lines = remarkText.split('\n');
  const meaningful = [];
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i].trim();
    if (!l || !/[\u4e00-\u9fff]/.test(l) || /[::：]/.test(l)) continue;
    if (/^(开票人|项目地址|项目名称|购买方|销售方|购方|销方|土地增值税|跨地|收款人|复核人)/.test(l)) continue;
    if (l.includes('银行账号') || l.includes('电话') || l.includes('地址')) continue;
    if (/^(?:湖北省|武汉市|[\d０-９]+号)/.test(l)) continue;
    meaningful.push({ text: l, index: i });
  }
  if (meaningful.length === 0) return null;
  const last = meaningful[meaningful.length - 1];
  let title = last.text;
  for (let i = last.index + 1; i < lines.length; i++) {
    const next = lines[i].trim();
    if (!next || !/[\u4e00-\u9fff]/.test(next) || /[::：]/.test(next)) break;
    if (/^(开票人|项目地址|项目名称)/.test(next)) break;
    title += next;
  }
  return title;
}

function cleanProject(project, station) {
  if (!project) return project;
  let p = project.trim();
  if (station && p.startsWith(station)) p = p.slice(station.length);
  p = p.replace(/^[:：\s]+/, '');
  p = p.replace(/[，。；;、\s]+$/, '');
  return p || project.trim();
}

function buildTitle(station, project, rawProject) {
  if (rawProject && station && rawProject.includes(station)) {
    const cleaned = cleanProject(rawProject, station);
    if (cleaned) return station + cleaned;
  }
  if (station && project) return station + project;
  return station || project || '';
}

function parsePdfText(text) {
  const norm = compactText(text);
  const remark = remarkSection(norm);
  const stationsAll = findStations(norm);
  const stationsRemark = findStations(remark);
  const stations = stationsRemark.length > 0 ? stationsRemark : stationsAll;
  const station = stations[0] || null;
  const rawProject = extractRemarkTitle(remark, station) || extractProject(norm);
  const project = rawProject === station ? '' : cleanProject(rawProject, station);
  const title = buildTitle(station, project, rawProject);
  const multiSite = stations.length > 1 || (project || '').includes('、');
  return {
    invoiceNo: extractInvoiceNo(norm),
    amount: extractAmount(norm),
    station,
    project,
    title,
    stations,
    multipleStations: stations.length > 1,
    multiSite,
    rawProject
  };
}

function parseXml(xmlText) {
  if (Buffer.isBuffer(xmlText)) {
    const head = xmlText.slice(0, 200).toString('latin1');
    const encMatch = head.match(/encoding=["']([^"']+)["']/i);
    const enc = encMatch && /^(gb|GB)/.test(encMatch[1]) ? encMatch[1] : 'utf8';
    xmlText = iconv.decode(xmlText, enc);
  }
  const tag = (name) => {
    const m = xmlText.match(new RegExp(`<${name}>([\\s\\S]*?)</${name}>`));
    return m ? m[1].trim() : null;
  };
  const invoiceNo = tag('InvoiceNumber') || tag('EIid');
  const amount = tag('TotalTax-includedAmount') || tag('TotaltaxIncludedAmount');
  const specMod = tag('SpecMod') || '';
  const meaUnits = tag('MeaUnits') || '';
  const info = tag('InformationValue') || '';
  const itemName = tag('ItemName') || '';
  const text = [specMod, info, itemName, meaUnits].join('\n');
  const stations = findStations(text);
  const station = stations[0] || null;
  let project = meaUnits || null;
  if (!project) {
    const m = info.match(/项目名称[:：]\s*([^\n]+)/) || info.match(/^([^\n]+)$/);
    if (m) project = m[1].trim();
  }
  project = project === station ? '' : cleanProject(project, station);
  const title = buildTitle(station, project, project);
  return {
    invoiceNo,
    amount: amount ? amount.replace(/,/g, '') : null,
    station,
    project,
    title,
    stations,
    multipleStations: stations.length > 1,
    multiSite: stations.length > 1 || (project || '').includes('、'),
    rawProject: project
  };
}

async function parsePdf(buffer) {
  const r = await pdfParse(buffer);
  return parsePdfText(r.text);
}

function sanitizeName(name) {
  const cleaned = name
    .replace(/[\\/:*?"<>|\x00-\x1f]/g, '_')
    .replace(/\s+/g, ' ')
    .replace(/[. ]+$/, '')
    .trim();
  return cleaned.slice(0, 180);
}

function buildName(meta, template) {
  const values = {
    remark: meta.title || '',
    station: meta.station || '',
    project: meta.project || '',
    amount: meta.amount || '',
    invoice: meta.invoiceNo || ''
  };
  let out = template || '{remark}_{amount}_{invoice}';
  for (const [k, v] of Object.entries(values)) {
    out = out.split(`{${k}}`).join(v);
  }
  out = out.replace(/_+/g, '_').replace(/^_+|_+$/g, '');
  return sanitizeName(out);
}

module.exports = {
  parsePdf,
  parseXml,
  parsePdfText,
  buildName,
  sanitizeName
};
