/**
 * 生成 data/genshin_equip_icons.json：中文武器名/圣遗物套装名 -> 官方图标 URL。
 *
 * 运行：node tools/gen_equip_icons.js
 * 依赖：npm i genshin-db（安装在托管 node workspace）
 *
 * 数据来自 GenshinData 官方镜像（与角色数据同一来源），未收录的名称不伪造图标。
 */
const fs = require('fs');
const path = require('path');

const GDB = 'C:/Users/吕晨/.workbuddy/binaries/node/workspace/node_modules/genshin-db';
const gdb = require(GDB);

const PROJECT = 'E:/手游抽取建议分析器';
const OUT = path.join(PROJECT, 'data/genshin_equip_icons.json');

const LOCALE = {
  matchAliases: true,
  queryLanguages: ['ChineseSimplified'],
  resultLanguage: 'ChineseSimplified',
};

function norm(s){
  return String(s || '')
    .replace(/★|☆|（|）|\(|\)|：|:|\s+/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '');
}

function single(q, kind){
  let r = kind === 'weapons' ? gdb.weapons(q, LOCALE) : gdb.artifacts(q, LOCALE);
  return Array.isArray(r) ? r[0] : r;
}

function main(){
  const weapons = {};
  const weaponsNorm = {};
  for(const n of gdb.weapons('names', { matchCategories: true, ...LOCALE })){
    const r = single(n, 'weapons');
    if(r && r.images && r.images.icon){
      weapons[n] = r.images.icon;
      weaponsNorm['__' + norm(n)] = r.images.icon;
    }
  }

  const artifacts = {};
  const artifactsNorm = {};
  for(const n of gdb.artifacts('names', { matchCategories: true, ...LOCALE })){
    const r = single(n, 'artifacts');
    if(r && r.images){
      const parts = {};
      for(const k of ['flower', 'plume', 'sands', 'goblet', 'circlet']){
        if(r.images[k]) parts[k] = r.images[k];
      }
      if(Object.keys(parts).length){
        artifacts[n] = parts;
        artifactsNorm['__' + norm(n)] = parts;
      }
    }
  }

  fs.writeFileSync(OUT, JSON.stringify({
    generated: new Date().toISOString().slice(0, 10),
    source: 'genshin-db (GenshinData 官方数据镜像)',
    weapons: weapons,
    weapons_norm: weaponsNorm,
    artifacts: artifacts,
    artifacts_norm: artifactsNorm,
  }, null, 2), 'utf8');
  console.log('武器图标 %d 个，圣遗物套装图标 %d 套', Object.keys(weapons).length, Object.keys(artifacts).length);
}

main();
