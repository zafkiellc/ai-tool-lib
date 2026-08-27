/**
 * 从 genshin-db（GenshinData 官方数据镜像）生成 data/genshin_official_stats.json
 * 覆盖全部已上线角色的真实数值：90级白值、突破加成、爆发能量、技能倍率、功能性。
 *
 * 运行：node tools/gen_official_stats.js
 * 依赖：npm i genshin-db（安装在托管 node workspace）
 *
 * 匹配策略：遍历「我的角色库」，用 en/name/aliases 向 genshin-db 查询（matchAliases 支持
 * 部分名/别名匹配，例如 Kazuha -> Kaedehara Kazuha、Raiden -> Raiden Shogun），避免
 * 全名 vs 短 id 的归一化错位。
 */
const fs = require('fs');
const path = require('path');

// genshin-db 绝对路径（托管 workspace）
const GDB = 'C:/Users/吕晨/.workbuddy/binaries/node/workspace/node_modules/genshin-db';
const gdb = require(GDB);

const PROJECT = 'E:/手游抽取建议分析器';
const charsLib = JSON.parse(fs.readFileSync(path.join(PROJECT, 'data/genshin_characters.json'), 'utf8')).characters;
const OUT = path.join(PROJECT, 'data/genshin_official_stats.json');
const FLAGS = JSON.parse(fs.readFileSync(path.join(PROJECT, 'data/genshin_functional_flags.json'), 'utf8'));

const ELEM = { Hydro:'水', Pyro:'火', Electro:'雷', Cryo:'冰', Anemo:'风', Dendro:'草', Geo:'岩' };
const WEAP = {
  WEAPON_SWORD_ONE_HAND:'单手剑', WEAPON_CLAYMORE:'双手剑', WEAPON_BOW:'弓',
  WEAPON_CATALYST:'法器', WEAPON_POLEARM:'长柄武器'
};
const AVG = { HP:13000, ATK:300, DEF:700 };

// genshin-db 的部分正式名与角色库 en 字段不一致（无空格别名或全名），需要显式映射。
// 未映射的 id 走「精确名称/别名」匹配，绝不接受前缀模糊命中（曾把 Lune 错配成 Lumine）。
const GDB_NAME_BY_ID = {
  'hu-tao': 'Hu Tao',
  'kokomi': 'Sangonomiya Kokomi',
  'arataki-itto': 'Arataki Itto',
  'kazuha': 'Kaedehara Kazuha',
  'ayaka': 'Kamisato Ayaka',
  'raiden': 'Raiden Shogun',
  'kujou-sara': 'Kujou Sara',
  'yunjin': 'Yun Jin',
  'yae-miko': 'Yae Miko',
  'ayato': 'Kamisato Ayato',
  'kuki-shinobu': 'Kuki Shinobu',
  'shikanoin-heizou': 'Shikanoin Heizou',
  'lanyan': 'Lan Yan',
  'yumemizuki': 'Yumemizuki Mizuki',
  'linea': 'Linnea', // 同一角色不同罗马音（莉奈娅 Linea / Linnea）
};

function resolveGenshinChar(my){
  if(my.id === 'traveler'){
    // 旅行者在 genshin-db 中拆为 Aether/Lumine，统一取 Aether
    let r = gdb.characters('Aether', { matchAliases: true });
    return Array.isArray(r) ? r[0] : r;
  }
  const canonical = GDB_NAME_BY_ID[my.id];
  const qlist = canonical ? [canonical] : [my.en, my.name].concat(my.aliases || []).filter(Boolean);
  const qlower = qlist.map(x => String(x).toLowerCase());
  for(const q of qlist){
    let r = gdb.characters(q, { matchAliases: true });
    if(Array.isArray(r)) r = r[0];
    if(r && r.name){
      const names = [r.name].concat(r.altnames || [], r.aliases || [])
        .filter(Boolean).map(x => String(x).toLowerCase());
      if(names.some(n => qlower.includes(n))) return r;
    }
  }
  return null;
}

function functionalFlagsFor(id, text){
  const t = (text || '').toLowerCase();
  // 兜底检测只认「强信号」，且 buff 必须同时出现队友/全队上下文 + 增益词；
  // 白名单覆盖的角色一律以人工核对结果为准（含显式 false，纠正旧 JSON 噪声）。
  const detect = () => {
    const heal = /\bheal(s|ing|ed)?\b|治疗|回血|恢复生命|incoming healing/i.test(t);
    const shield = /\bshield(s|ed|ing)?\b|护盾|伤害抵挡|damage absorption/i.test(t);
    const team = /all party|party members|nearby characters|active character|team|全队|队伍|队友|附近的角色/i.test(t);
    const gain = /increase|boost|gain|bonus|buff|增伤|提高|加成|减抗/i.test(t);
    const buff = team && gain;
    return { heal, shield, buff };
  };
  const d = detect();
  return {
    heal: (FLAGS.heal && id in FLAGS.heal) ? !!FLAGS.heal[id] : d.heal,
    shield: (FLAGS.shield && id in FLAGS.shield) ? !!FLAGS.shield[id] : d.shield,
    buff: (FLAGS.buff && id in FLAGS.buff) ? !!FLAGS.buff[id] : d.buff,
  };
}

function scalingStatOf(descs){
  const blob = descs.join(' ').toLowerCase();
  if (/max hp|maximum hp|current hp/.test(blob)) return 'HP';
  if (/defen|maximum def|\bdef\b/.test(blob)) return 'DEF';
  if (/\batk\b|attack/.test(blob)) return 'ATK';
  return 'ATK';
}

// 大世界能力（官方不评价，参考社区评测）：
// 1) 自动探测（可靠信号）：技能/被动含真实「移动速度/冲刺」增益 → sprint_buff；弓/法器天生远程位移 → dash。
// 2) 人工整理白名单（OVERWORLD_OVERRIDES）：飞行/游泳/攀爬/钩索/载具等「独特探索能力」由社区评测
//    攻略人工核对后收录（genshin-db 的英文技能描述里 "sent flying"/"lunge" 等战斗措辞会误命中，
//    不可靠，故飞行/游泳/攀爬不靠文本自动猜测，统一走此白名单，避免伪造数据）。
//    白名单覆盖的角色，其 mobility 与说明以白名单为准（覆盖自动探测）。
function detectMobility(descs, weapon){
  const blob = (descs || []).join(' ');
  const has = (re) => re.test(blob);
  if (has(/移动速度|奔跑速度|移动速度提升|冲刺.*速度|movement spd|movement speed|sprint speed|increases? movement/i)) return 'sprint_buff';
  if (['弓','法器'].includes(weapon)) return 'dash';
  return 'none';
}

// 大世界独特探索能力白名单（id -> { mobility, detail }）
// 来源：社区评测 / 角色攻略（技能探索能力人工核对）。official_stats 中该维统一标 source="review"。
// mobility 取值：glide(飞行/滑翔) / swim(水上/潜水) / climb(攀爬/钩索) / special(瞬移/滚动/载具等)
const OVERWORLD_OVERRIDES = {
  'wanderer':  { mobility: 'glide',  detail: '元素战技可腾空自由飞行（风风轮），少数能长时间飞行的角色' },
  'venti':     { mobility: 'glide',  detail: '元素战技生成上升风场，可带全队升空' },
  'xiao':      { mobility: 'special', detail: '风轮两立高频位移/登高，大世界跑图灵活' },
  'kazuha':    { mobility: 'special', detail: '随风而去借风场/自身升空越障' },
  'yelan':     { mobility: 'swim',   detail: '踏水疾行（水上冲浪），水面高速移动' },
  'sayu':      { mobility: 'special', detail: '化身超速滚动妖怪，快速位移且可安全滚下高崖' },
  'kachina':   { mobility: 'climb',  detail: '冲天榴炮可攀爬近垂直岩壁/地形' },
  'mualani':   { mobility: 'swim',   detail: '召唤冲浪板，水面高速冲浪移动' },
  'kinich':    { mobility: 'climb',  detail: '钩索摆荡/攀爬，垂直地形机动极强' },
  'xilonen':   { mobility: 'glide',  detail: '滑板滑行并长按滑翔，地形跨越能力强' },
  'mavuika':   { mobility: 'special', detail: '召唤摩托（冲天炮），地面高速载具移动' },
  'chasca':    { mobility: 'glide',  detail: '枪翼滑翔可腾空飞行，空中机动' },
  'xianyun':   { mobility: 'glide',  detail: '腾空飞行并可带全队升空（云中谪仙）' },
  'kirara':    { mobility: 'climb',  detail: '化身急送箱可攀爬，附身时爬墙' },
  'mona':      { mobility: 'swim',   detail: '替代冲刺为高速水上奔跑（踏水疾行），渡水极快' },
  'freminet':  { mobility: 'swim',   detail: '可潜入深水（佩露西姆协助），水下探索' },
  'keqing':    { mobility: 'special', detail: '雷楔瞬移，短距高频位移' },
};

function getEnergyCost(talent){
  const c3 = talent.combat3;
  if(!c3 || !c3.attributes) return 0;
  const labels = c3.attributes.labels || [];
  const params = c3.attributes.parameters || {};
  for(let i=0;i<labels.length;i++){
    if(/energy cost/i.test(labels[i])){
      const m = labels[i].match(/param(\d+)/);
      if(m){
        const arr = params['param'+m[1]];
        if(Array.isArray(arr) && arr.length) return Math.round(arr[arr.length-1]);
      }
    }
  }
  return 0;
}

function primaryMultiplier(talent, statKey){
  // 取战技/爆发中“主要伤害”倍率（level 10，索引9），取较大者
  let best = 0;
  ['combat2','combat3'].forEach(k=>{
    const c = talent[k];
    if(!c || !c.attributes) return;
    const labels = c.attributes.labels || [];
    const params = c.attributes.parameters || {};
    for(let i=0;i<labels.length;i++){
      const lab = labels[i];
      if(/dmg/i.test(lab)){
        const m = lab.match(/param(\d+)/);
        if(m){
          const arr = params['param'+m[1]];
          if(Array.isArray(arr) && arr.length){
            const v = arr[Math.min(9, arr.length-1)]; // level 10
            if(typeof v === 'number' && v > best) best = v;
          }
        }
      }
    }
  });
  return best;
}

function bucketMultiplier(rel){
  if(rel >= 2.5) return 'very_high';
  if(rel >= 1.5) return 'high';
  if(rel >= 0.8) return 'medium';
  if(rel >= 0.3) return 'low';
  return 'very_low';
}

function main(){
  const result = {};
  let matched = 0, failed = 0;
  const failedNames = [];

  for(const my of charsLib){
    if(my.status && my.status !== 'released') continue; // 未上线角色无官方数值
    const gc = resolveGenshinChar(my);
    if(!gc){ failedNames.push(my.id + '(' + (my.en || my.name) + ')'); failed++; continue; }

    const id = my.id;
    const stats90 = (gc.stats ? gc.stats(90) : {}) || {};
    const talent = gdb.talents(gc.name) || {};

    const descs = [];
    ['combat1','combat2','combat3','passive1','passive2','passive3'].forEach(k=>{
      if(talent[k] && talent[k].description) descs.push(talent[k].description);
    });
    const func = functionalFlagsFor(id, descs.join('\n'));
    const scaling = scalingStatOf(descs);
    const energy = getEnergyCost(talent);
    const mult = primaryMultiplier(talent, scaling);
    const primaryStat = scaling === 'HP' ? (stats90.hp||0)
      : scaling === 'DEF' ? (stats90.defense||0) : (stats90.attack||0);
    const avg = AVG[scaling] || 300;
    const rel = avg > 0 ? (mult * primaryStat / avg) : 0;
    const scalingRating = bucketMultiplier(rel);

    // 大世界机动性：先自动探测，再用人评测白名单覆盖（飞行/游泳/攀爬/钩索/载具等独特能力）
    let mobility = detectMobility(descs, my.weapon);
    let overworldDetail = '';
    const ov = OVERWORLD_OVERRIDES[id];
    if (ov) {
      mobility = ov.mobility;
      overworldDetail = ov.detail;
    }

    result[id] = {
      element: ELEM[gc.elementText] || my.element,
      weapon: WEAP[gc.weaponType] || my.weapon,
      base_hp: Math.round(stats90.hp || 0),
      base_atk: Math.round(stats90.attack || 0),
      base_def: Math.round(stats90.defense || 0),
      hp_pct: 0, atk_pct: 0, def_pct: 0,  // stats(90) 已含突破，pct 置 0 避免重复计算
      scaling_stat: scaling,
      energy_cost: energy,
      has_heal: func.heal, has_shield: func.shield, has_buff: func.buff,
      talent_scaling: scalingRating,
      reaction_role: (my.element === '风') ? 'driver'
        : (['水','雷','火','冰'].includes(my.element)) ? 'multiplier'
        : (func.buff ? 'trigger' : 'none'),
      mobility: mobility,
      overworld_detail: overworldDetail,  // 评测参考：该角色独特探索能力说明（空=无独特能力）
      _source: 'genshin-db (GenshinData 官方数据镜像)',
      _fetched: new Date().toISOString().slice(0,10)
    };
    matched++;
  }

  fs.writeFileSync(OUT, JSON.stringify(result, null, 2), 'utf8');
  console.log('生成完成：匹配 %d 个已上线角色，失败 %d 个', matched, failed);
  if(failedNames.length) console.log('失败（未匹配 genshin-db）：', failedNames.join(', '));
  // 抽样输出
  ['furina','hu-tao','zhongli','kaedehara-kazuha','raiden'].forEach(id=>{
    const r = result[id];
    if(r) console.log(id, '=> HP', r.base_hp, 'ATK', r.base_atk, 'DEF', r.base_def,
      '| energy', r.energy_cost, '| scaling', r.scaling_stat,
      '| heal/shield/buff', r.has_heal, r.has_shield, r.has_buff,
      '| talent', r.talent_scaling, '| reaction', r.reaction_role);
  });
}

main();
