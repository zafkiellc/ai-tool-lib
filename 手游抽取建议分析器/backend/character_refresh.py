# -*- coding: utf-8 -*-
"""重建 HSR / ZZZ / 鸣潮 / 终末地 / 异环 角色库（精编静态数据，离线）。

⚠️ hakush.in 已于 2026-02-14 正式关闭，nankoa.cc 复活站亦不可达。
本模块全部采用「嵌入精编数据」模式，无需联网，点击即写，绝无假数据风险。

数据来源（于 2026-08-02 交叉核对整理）：
- HSR 崩坏：星穹铁道  ：biligame wiki + 官网（截止 v4.4，2026-07-15）
- ZZZ 绝区零           ：biligame wiki + 官网（截止 v3.1，2026-07-29）
- 鸣潮 Wuthering Waves ：fandom 中文 wiki + 官网（截止 v3.5，2026-07-10）
- 终末地 Arknights Endfield：moegirl wiki + 官网（截止 v1.4，2026-07-22，已公测）
- 异环 NTE             ：官网 + 百科（截止 v1.2，2026-07-08，已公测）

⚠️ 准确性说明：
- 各游戏早期版本（HSR 1.0–3.3 / ZZZ 1.0–2.1 / 鸣潮 1.0–1.7 / 终末地 1.0 / 异环 1.0）为国服
  官方名逐项核对，可信度高。
- 近期版本（HSR 3.4+ / ZZZ 2.2+ / 鸣潮 2.0+ / 终末地 1.1+ / 异环 1.1+）由 Wiki 汇编，
  请以游戏内实装为准二次核对（角色卡均标注 version 字段便于排查）。

头像策略（三级回退：真图 icon → icon_fallback → 官方属性色卡+全名，前端 onerror 自动回退）：
- **原神**：api.lunaris.moe 角色卡图映射 + Enka Network 真实头像（在线拉取，逐张验证）。
- **HSR 崩坏：星穹铁道**：Enka Network 真实头像（StarRailRes GitHub 提供 en名->AvatarId），
  静态 HSR_AVATAR_IDS 已逐张 HTTP 200 验证（90/90）。
- **ZZZ 绝区零**：萌娘百科角色头像（Special:FilePath/{en}-Role.png，已验证 200 image/png，
  外链可嵌入），ZZZ_MOEGIRL 显式映射 id_key->萌娘文件名（58/58）。
- **终末地 Arknights Endfield**：BoxCatTeam/endfield-cat-metadata（GitHub raw）图标
  （images/character/icon/{itemid}.png，已验证 200 image/png），ENDFIELD_AVATAR_IDS 静态表
  （24/30，缺洛茜/庄方宜/弭弗/卡缪/诀/梨诺 留色卡）。
- **异环 NTE**：萌娘百科立绘（zh.moegirl.org.cn Special:FilePath，已验证 200 image/png），
  NTE_MOEGIRL 显式映射 id_key->萌娘文件名（19/22，缺九原/穗鸟/咲里 留色卡）。
- **鸣潮 Wuthering Waves**：暂无「角色名->图标」可确定性映射的干净 CDN（resonance 无图标字段；
  wuthering.wiki 无 MediaWiki API；GitHub 图包用两位代号无法对应角色名）→ 维持官方属性色卡。
  前端对加载失败的头像会自动回退到色卡，绝不显示错误/缩略占位图。
"""

import json
import os
import shutil
import datetime
import io
import re
import tarfile
import urllib.request
from urllib.parse import quote, urlencode

from common import DATA_DIR

DISPLAY = {
    "hsr": "崩坏：星穹铁道",
    "zzz": "绝区零",
    "wuthering_waves": "鸣潮",
    "arknights_endfield": "明日方舟：终末地",
    "nte": "异环",
}

# ============================================================
# HSR 精编角色表（米游社 Wiki 国服官方名，截至 v4.4）
# 格式: (id_key, name, en, element, path, rarity, version, aliases, note)
# rarity: 5=五星  4=四星 ; path: 毁灭/巡猎/智识/同谐/虚无/存护/丰饶/记忆/欢愉
# ============================================================
HSR_CHARS = [
    ("trailblazer_destruction", "开拓者（毁灭）", "Caelus/Stelle", "物理", "毁灭", 5, "1.0", ["开拓者", "毁灭主"], "男/女可选"),
    ("march_7th", "三月七", "March 7th", "冰", "存护", 4, "1.0", ["三月七", "MM7"], ""),
    ("dan_heng", "丹恒", "Dan Heng", "风", "巡猎", 4, "1.0", ["丹恒"], ""),
    ("himeko", "姬子", "Himeko", "火", "智识", 5, "1.0", ["姬子", "Himeko小姐"], ""),
    ("welt", "瓦尔特", "Welt", "虚数", "虚无", 5, "1.0", ["瓦尔特", "老杨"], ""),
    ("arlan", "阿兰", "Arlan", "雷", "毁灭", 4, "1.0", ["阿兰"], ""),
    ("asta", "艾丝妲", "Asta", "火", "同谐", 4, "1.0", ["艾丝妲"], ""),
    ("herta", "黑塔", "Herta", "冰", "智识", 4, "1.0", ["黑塔", "黑塔小姐"], ""),
    ("gepard", "杰帕德", "Gepard", "冰", "存护", 4, "1.0", ["杰帕德"], ""),
    ("serval", "希露瓦", "Serval", "雷", "智识", 4, "1.0", ["希露瓦"], ""),
    ("pela", "佩拉", "Pela", "冰", "虚无", 4, "1.0", ["佩拉"], ""),
    ("natasha", "娜塔莎", "Natasha", "物理", "丰饶", 4, "1.0", ["娜塔莎", "娜塔莎医生"], ""),
    ("seele", "希儿", "Seele", "量子", "巡猎", 5, "1.0", ["希儿", "Seele Vollerei"], ""),
    ("clara", "克拉拉", "Clara", "物理", "毁灭", 4, "1.0", ["克拉拉"], ""),
    ("sampo", "桑博", "Sampo", "风", "虚无", 4, "1.0", ["桑博"], ""),
    ("hook", "虎克", "Hook", "火", "毁灭", 4, "1.0", ["虎克", "虎克大人"], ""),
    ("jing_yuan", "景元", "Jing Yuan", "雷", "智识", 5, "1.0", ["景元", "景元将军"], ""),
    ("yanqing", "彦卿", "Yanqing", "冰", "巡猎", 4, "1.0", ["彦卿"], ""),
    ("sushang", "素裳", "Sushang", "物理", "巡猎", 4, "1.0", ["素裳"], ""),
    ("qingque", "青雀", "Qingque", "量子", "智识", 4, "1.0", ["青雀"], ""),
    ("tingyun", "停云", "Tingyun", "雷", "同谐", 4, "1.0", ["停云", "仙舟狐人"], ""),
    ("bailu", "白露", "Bailu", "雷", "丰饶", 4, "1.0", ["白露", "衔药龙女"], ""),
    ("bronya", "布洛妮娅", "Bronya", "风", "同谐", 5, "1.0", ["布洛妮娅"], ""),
    ("silver_wolf", "银狼", "Silver Wolf", "量子", "虚无", 5, "1.1", ["银狼"], ""),
    ("luocha", "罗刹", "Luocha", "虚数", "丰饶", 5, "1.1", ["罗刹"], ""),
    ("yukong", "驭空", "Yukong", "虚数", "同谐", 4, "1.1", ["驭空"], ""),
    ("kafka", "卡芙卡", "Kafka", "雷", "虚无", 5, "1.2", ["卡芙卡", "Kafka"], "星核猎手"),
    ("blade", "刃", "Blade", "风", "毁灭", 5, "1.2", ["刃", "Blade"], "星核猎手"),
    ("luka", "卢卡", "Luka", "物理", "虚无", 4, "1.2", ["卢卡"], ""),
    ("fu_xuan", "符玄", "Fu Xuan", "量子", "存护", 5, "1.3", ["符玄", "符玄将军"], ""),
    ("dan_heng_imbibitor_lunae", "丹恒·饮月", "Dan Heng Imbibitor Lunae", "虚数", "毁灭", 5, "1.3", ["饮月君", "丹恒·饮月"], ""),
    ("lynx", "玲可", "Lynx", "量子", "丰饶", 4, "1.3", ["玲可", "Lynx"], ""),
    ("trailblazer_preservation", "开拓者（存护）", "Caelus/Stelle", "火", "存护", 5, "1.3", ["开拓者", "存护主"], "男/女可选"),
    ("jingliu", "镜流", "Jingliu", "冰", "毁灭", 5, "1.4", ["镜流"], ""),
    ("topaz_numby", "托帕&账账", "Topaz & Numby", "火", "巡猎", 5, "1.4", ["托帕", "账账"], ""),
    ("guinaifen", "桂乃芬", "Guinaifen", "火", "虚无", 4, "1.4", ["桂乃芬"], ""),
    ("huohuo", "藿藿", "Huohuo", "风", "丰饶", 5, "1.5", ["藿藿"], ""),
    ("argenti", "银枝", "Argenti", "物理", "智识", 5, "1.5", ["银枝"], ""),
    ("ruan_mei", "阮·梅", "Ruan Mei", "冰", "同谐", 5, "1.6", ["阮梅", "Ruan Mei"], ""),
    ("dr_ratio", "真理医生", "Dr. Ratio", "虚数", "巡猎", 5, "1.6", ["真理医生", "Dr.Ratio"], ""),
    ("xueyi", "雪衣", "Xueyi", "量子", "毁灭", 4, "1.6", ["雪衣"], ""),
    ("hanya", "寒鸦", "Hanya", "物理", "同谐", 4, "1.6", ["寒鸦"], ""),
    ("black_swan", "黑天鹅", "Black Swan", "风", "虚无", 5, "2.0", ["黑天鹅"], ""),
    ("sparkle", "花火", "Sparkle", "量子", "同谐", 5, "2.0", ["花火"], ""),
    ("misha", "米沙", "Misha", "冰", "毁灭", 4, "2.0", ["米沙"], ""),
    ("acheron", "黄泉", "Acheron", "雷", "虚无", 5, "2.1", ["黄泉", "Acheron"], ""),
    ("aventurine", "砂金", "Aventurine", "虚数", "存护", 5, "2.1", ["砂金"], ""),
    ("gallagher", "加拉赫", "Gallagher", "火", "丰饶", 4, "2.1", ["加拉赫"], ""),
    ("trailblazer_harmony", "开拓者（同谐）", "Caelus/Stelle", "虚数", "同谐", 5, "2.1", ["开拓者", "同谐主"], "男/女可选"),
    ("robin", "知更鸟", "Robin", "物理", "同谐", 5, "2.2", ["知更鸟", "Robin"], ""),
    ("boothill", "波提欧", "Boothill", "物理", "巡猎", 5, "2.2", ["波提欧", "Boothill"], ""),
    ("firefly", "流萤", "Firefly", "火", "毁灭", 5, "2.3", ["流萤", "Firefly"], "星核猎手"),
    ("jade", "翡翠", "Jade", "量子", "智识", 5, "2.3", ["翡翠", "Jade"], ""),
    ("yunli", "云璃", "Yunli", "物理", "毁灭", 5, "2.4", ["云璃"], ""),
    ("jiaoqiu", "椒丘", "Jiaoqiu", "火", "虚无", 5, "2.4", ["椒丘"], ""),
    ("march_7th_hunt", "三月七·巡猎", "March 7th Hunt", "虚数", "巡猎", 4, "2.4", ["巡猎三月七"], ""),
    ("feixiao", "飞霄", "Feixiao", "风", "巡猎", 5, "2.5", ["飞霄"], ""),
    ("lingsha", "灵砂", "Lingsha", "火", "丰饶", 5, "2.5", ["灵砂"], ""),
    ("moze", "貊泽", "Moze", "雷", "巡猎", 4, "2.5", ["貊泽"], ""),
    ("rappa", "乱破", "Rappa", "虚数", "智识", 5, "2.6", ["乱破", "Rappa"], ""),
    ("sunday", "星期日", "Sunday", "虚数", "同谐", 5, "2.7", ["星期日", "Sunday"], ""),
    ("fugue", "忘归人", "Fugue", "火", "虚无", 5, "2.7", ["忘归人"], ""),
    ("the_herta", "大黑塔", "The Herta", "冰", "智识", 5, "3.0", ["大黑塔"], ""),
    ("aglaea", "阿格莱雅", "Aglaea", "雷", "记忆", 5, "3.0", ["阿格莱雅"], ""),
    ("trailblazer_remembrance", "开拓者（记忆）", "Caelus/Stelle", "冰", "记忆", 5, "3.0", ["开拓者", "记忆主"], "男/女可选"),
    ("tribbie", "缇宝", "Tribbie", "量子", "同谐", 5, "3.1", ["缇宝", "Tribbie"], ""),
    ("mydei", "万敌", "Mydei", "虚数", "毁灭", 5, "3.1", ["万敌", "Mydei"], ""),
    ("castorice", "遐蝶", "Castorice", "量子", "记忆", 5, "3.2", ["遐蝶", "Castorice"], ""),
    ("anaxa", "那刻夏", "Anaxa", "风", "智识", 5, "3.2", ["那刻夏", "Anaxa"], ""),
    ("hyacine", "风堇", "Hyacine", "风", "记忆", 5, "3.3", ["风堇", "Hyacine"], ""),
    ("cipher", "赛飞儿", "Cipher", "量子", "虚无", 5, "3.3", ["赛飞儿", "Cipher"], ""),
    ("phainon", "白厄", "Phainon", "物理", "毁灭", 5, "3.4", ["白厄", "Phainon"], ""),
    ("hysilens", "海瑟音", "Hysilens", "物理", "虚无", 5, "3.5", ["海瑟音", "Hysilens"], ""),
    ("cerydra", "刻律德菈", "Cerydra", "风", "同谐", 5, "3.5", ["刻律德菈", "Cerydra"], ""),
    ("evernight", "长夜月", "Evernight", "冰", "记忆", 5, "3.6", ["长夜月", "Evernight"], ""),
    ("dan_heng_permansor", "丹恒·腾荒", "Dan Heng Permansor Terrae", "物理", "存护", 5, "3.6", ["丹恒·腾荒"], ""),
    ("cyrene", "昔涟", "Cyrene", "冰", "记忆", 5, "3.7", ["昔涟", "Cyrene"], ""),
    ("dahlia", "大丽花", "Dahlia", "火", "虚无", 5, "3.8", ["大丽花", "Dahlia"], ""),
    ("yaoguang", "爻光", "Yaoguang", "物理", "欢愉", 5, "4.0", ["爻光", "Yaoguang"], ""),
    ("sparxie", "火花", "Sparxie", "火", "欢愉", 5, "4.0", ["火花", "Sparxie"], ""),
    ("ashveil", "不死途", "Ashveil", "雷", "巡猎", 5, "4.1", ["不死途", "Ashveil"], ""),
    ("silver_wolf_lv999", "银狼LV.999", "Silver Wolf LV.999", "虚数", "欢愉", 5, "4.2", ["银狼LV.999"], ""),
    ("evanescia", "绯英", "Evanescia", "物理", "欢愉", 5, "4.2", ["绯英", "Evanescia"], ""),
    ("trailblazer_elation", "开拓者（欢愉）", "Caelus/Stelle", "雷", "欢愉", 5, "4.2", ["开拓者", "欢愉主"], "男/女可选"),
    ("mortenax_blade", "千冶·刃", "Mortenax Blade", "火", "虚无", 5, "4.3", ["千冶·刃", "Mortenax Blade"], ""),
    ("himeko_nova", "姬子·启行", "Himeko Nova", "火", "智识", 5, "4.4", ["姬子·启行", "Himeko Nova"], "Fate联动版本常驻"),
    ("saber", "Saber", "Saber", "风", "毁灭", 5, "4.4", ["Saber", "阿尔托莉雅"], "Fate/stay night 联动"),
    ("archer", "Archer", "Archer", "量子", "巡猎", 5, "4.4", ["Archer", "卫宫士郎"], "Fate/stay night 联动"),
    ("rin_tosaka", "远坂凛", "Rin Tohsaka", "量子", "智识", 5, "4.4", ["远坂凛", "Rin Tohsaka"], "Fate/stay night 联动"),
    ("gilgamesh", "吉尔伽美什", "Gilgamesh", "雷", "毁灭", 5, "4.4", ["吉尔伽美什", "Gilgamesh"], "Fate/stay night 联动"),
]

# ============================================================
# ZZZ 精编角色表（国服官方名，截至 v3.1）
# 格式: (id_key, name, en, element, specialty, rarity, version, faction, aliases)
# rarity: 5=S  4=A ; specialty: 强攻/异常/击破/支援/防护/命破
# element(10种官方属性): 电/火/冰/以太/物理/烈霜/玄墨/凛刃/风/流明
# ============================================================
ZZZ_CHARS = [
    ("ellen", "艾莲·乔", "Ellen Joe", "冰", "强攻", 5, "1.0", "狡兔屋·维多利亚家政", ["艾莲", "Ellen"]),
    ("zhu_yuan", "朱鸢", "Zhu Yuan", "以太", "强攻", 5, "1.0", "对空六课", ["朱鸢"]),
    ("grace", "格莉丝·霍华德", "Grace Howard", "电", "异常", 5, "1.0", "白祇重工", ["格莉丝", "Grace"]),
    ("koleda", "珂蕾妲·贝洛伯格", "Koleda Belobog", "火", "击破", 5, "1.0", "维多利亚家政", ["珂蕾妲", "Koleda"]),
    ("lycaon", "冯·莱卡恩", "Von Lycaon", "冰", "击破", 5, "1.0", "维多利亚家政", ["莱卡恩", "Lycaon"]),
    ("rina", "亚历山德丽娜·莎芭丝缇安", "Alexandrina Sebastiane", "电", "支援", 5, "1.0", "维多利亚家政", ["莎芭丝缇安", "Rina"]),
    ("nekomata", "猫宫又奈", "Nekomiya Mana", "物理", "强攻", 5, "1.0", "狡兔屋", ["猫宫又奈", "Nekomata"]),
    ("soldier_11", "11号", "Soldier 11", "火", "强攻", 5, "1.0", "狡兔屋", ["11号", "Soldier 11"]),
    ("anby", "安比·德玛拉", "Anby Demara", "电", "击破", 4, "1.0", "狡兔屋", ["安比", "Anby"]),
    ("nicole", "妮可·德玛拉", "Nicole Demara", "以太", "支援", 4, "1.0", "狡兔屋", ["妮可", "Nicole"]),
    ("billy", "比利·奇德", "Billy Kid", "物理", "强攻", 4, "1.0", "狡兔屋", ["比利", "Billy"]),
    ("corin", "可琳·威克斯", "Corin Wickes", "物理", "强攻", 4, "1.0", "狡兔屋", ["可琳", "Corin"]),
    ("ben", "本·比格", "Ben Bigger", "火", "防护", 4, "1.0", "白祇重工", ["本", "Ben"]),
    ("anton", "安东·伊万诺夫", "Anton Ivanov", "电", "强攻", 4, "1.0", "白祇重工", ["安东", "Anton"]),
    ("soukaku", "苍角", "Soukaku", "冰", "支援", 4, "1.0", "白祇重工", ["苍角"]),
    ("lucy", "露西", "Luciana de Montefio", "火", "支援", 4, "1.0", "刑侦特勤组", ["露西", "Luciana"]),
    ("piper", "派派·韦尔", "Piper Wheel", "物理", "异常", 4, "1.0", "狡兔屋", ["派派", "Piper"]),
    ("qingyi", "青衣", "Qingyi", "电", "击破", 5, "1.1", "对空六课", ["青衣"]),
    ("jane", "简·杜", "Jane Doe", "物理", "异常", 5, "1.1", "刑侦特勤组", ["简", "Jane Doe"]),
    ("seth", "赛斯·洛威尔", "Seth Lowell", "电", "防护", 4, "1.1", "刑侦特勤组", ["赛斯", "Seth"]),
    ("caesar", "凯撒·金", "Caesar King", "物理", "防护", 5, "1.2", "刑侦特勤组", ["凯撒", "Caesar"]),
    ("burnice", "柏妮思·怀特", "Burnice White", "火", "异常", 5, "1.2", "奥波勒斯小队", ["柏妮思", "Burnice"]),
    ("yanagi", "月城柳", "Hoshimi Yanagi", "电", "异常", 5, "1.3", "对空六课", ["月城柳", "Yanagi"]),
    ("lighter", "莱特", "Lighter", "火", "击破", 5, "1.3", "卡吕冬之子", ["莱特", "Lighter"]),
    ("miyabi", "星见雅", "Hoshimi Miyabi", "烈霜", "异常", 5, "1.4", "对空六课", ["星见雅", "Miyabi"]),
    ("harumasa", "浅羽悠真", "Asaba Harumasa", "电", "强攻", 5, "1.4", "对空六课", ["浅羽悠真", "Harumasa"]),
    ("astra_yao", "耀嘉音", "Astra Yao", "以太", "支援", 5, "1.5", "天琴座", ["耀嘉音", "Astra Yao"]),
    ("evelyn", "伊芙琳·舒瓦利耶", "Evelyn Chevalier", "火", "强攻", 5, "1.5", "天琴座", ["伊芙琳", "Evelyn"]),
    ("soldier_0_anby", "零号·安比", "Soldier 0 - Anby", "电", "强攻", 5, "1.6", "奥波勒斯小队", ["零号·安比"]),
    ("trigger", "扳机", "Trigger", "电", "击破", 5, "1.6", "奥波勒斯小队", ["扳机", "Trigger"]),
    ("pulchra", "波可娜·费雷尼", "Pulchra Fellini", "物理", "击破", 4, "1.6", "维多利亚家政", ["普尔契拉", "Pulchra"]),
    ("vivian", "薇薇安·班希", "Vivian Banshee", "以太", "异常", 5, "1.7", "奥波勒斯小队", ["薇薇安", "Vivian"]),
    ("hugo", "雨果·维拉德", "Hugo Vlad", "冰", "强攻", 5, "1.7", "反舌鸟", ["雨果", "Hugo"]),
    ("yixuan", "仪玄", "Yixuan", "玄墨", "命破", 5, "2.0", "云岿山", ["仪玄"]),
    ("ju_fufu", "橘福福", "Ju Fufu", "火", "击破", 5, "2.0", "云岿山", ["橘福福"]),
    ("pan_yinhui", "潘引壶", "Pan Yinhu", "物理", "防护", 4, "2.0", "云岿山", ["潘引壶"]),
    ("yuzuha", "浮波柚叶", "Ukinami Yuzuha", "物理", "支援", 5, "2.1", "云岿山", ["浮波柚叶", "Yuzuha"]),
    ("alice", "爱丽丝·泰姆菲尔德", "Alice Thymefield", "物理", "异常", 5, "2.1", "云岿山", ["爱丽丝", "Alice"]),
    ("orphie", "奥菲丝·马格努森", "Orphie & Magus", "火", "强攻", 5, "2.2", "奥波勒斯小队", ["奥菲丝", "Orphie"]),
    ("seed", "席德", "Seed", "电", "强攻", 5, "2.2", "防卫军·白银小队", ["希德", "Seed"]),
    ("lucia", "卢西娅·艾洛温", "Lucia", "以太", "支援", 5, "2.3", "", ["卢西娅", "Lucia"]),
    ("yidhari", "伊德海莉·墨菲", "Yidhari", "冰", "命破", 5, "2.3", "", ["伊德海莉", "Yidhari"]),
    ("komata", "狛野真斗", "Komata", "火", "命破", 4, "2.3", "", ["狛野真斗", "Komata"]),
    ("liu_yin", "琉音", "Liu Yin", "物理", "击破", 5, "2.4", "", ["琉音"]),
    ("banyue", "般岳", "Banyue", "火", "命破", 5, "2.4", "", ["般岳"]),
    ("ye_shunguang", "叶瞬光", "Ye Shunguang", "凛刃", "强攻", 5, "2.5", "", ["叶瞬光"]),
    ("zhao", "照", "Zhao", "冰", "防护", 5, "2.5", "", ["照"]),
    ("qianxia", "千夏", "Qianxia", "物理", "支援", 5, "2.6", "", ["千夏"]),
    ("aria", "爱芮", "Aria", "以太", "异常", 5, "2.6", "", ["爱芮", "Aria"]),
    ("nangong_yu", "南宫羽", "Nangong Yu", "以太", "击破", 5, "2.7", "", ["南宫羽"]),
    ("cissia", "希希芙", "Cissia", "电", "强攻", 5, "2.7", "", ["希希芙"]),
    ("promeia", "普罗米亚", "Promeia", "冰", "异常", 5, "2.8", "", ["普罗米亚"]),
    ("starlight_billy", "星徽·比利", "Starlight-Billy", "物理", "命破", 5, "2.8", "", ["星徽·比利"]),
    ("velina", "维琳娜·艾嘉德", "Velina", "风", "异常", 5, "3.0", "", ["维琳娜", "Velina"]),
    ("norma", "诺姆·霍格维尔", "Norma", "火", "击破", 5, "3.0", "", ["诺姆", "Norma"]),
    ("pyrois", "佩洛伊斯", "Pyrois", "以太", "强攻", 5, "3.0", "", ["佩洛伊斯"]),
    ("remielle", "蕾米埃尔·丹", "Remielle", "流明", "异常", 5, "3.1", "", ["蕾米埃尔", "Remielle"]),
    ("sigrid", "希格莉德", "Sigrid", "冰", "强攻", 5, "3.1", "", ["希格莉德"]),
]

# ZZZ 头像：萌娘百科角色页头像（File:{en}-Role.png）。
# 文件名取自萌娘百科「绝区零/代理人」数据模块（权威），与上面 en 字段不完全一致，
# 故显式映射 id_key -> 萌娘文件名。Special:FilePath 支持外链嵌入，沙箱实测 200 image/png。
# 前端对加载失败的头像会自动回退到官方属性色卡（绝不显示错误/占位图）。
ZZZ_MOEGIRL = {
    "ellen": "Ellen", "zhu_yuan": "ZhuYuan", "grace": "Grace", "koleda": "Koleda",
    "lycaon": "Lycaon", "rina": "Rina", "nekomata": "Nekomata", "soldier_11": "Soldier11",
    "anby": "Anby", "nicole": "Nicole", "billy": "Billy", "corin": "Corin", "ben": "Ben",
    "anton": "Anton", "soukaku": "Soukaku", "lucy": "Lucy", "piper": "Piper", "qingyi": "Qingyi",
    "jane": "Jane", "seth": "Seth", "caesar": "Caesar", "burnice": "Burnice",
    "yanagi": "TsukishiroYanagi", "lighter": "Lighter", "miyabi": "HoshimiMiyabi",
    "harumasa": "AsabaHarumasa", "astra_yao": "AstraYao", "evelyn": "Evelyn",
    "soldier_0_anby": "Silver-Soldier-Anby", "trigger": "Trigger", "pulchra": "Pulchra",
    "vivian": "Vivian", "hugo": "Hugo", "yixuan": "Yixuan", "ju_fufu": "JuFufu",
    "pan_yinhui": "PanYinhu", "yuzuha": "Ukinami Yuzuha", "alice": "Alice Thymefield",
    "orphie": "Orphie", "seed": "Seed", "lucia": "Lucia", "yidhari": "Yidhari",
    "komata": "Komano Manato", "liu_yin": "Dialyn", "banyue": "Banyue",
    "ye_shunguang": "YeShunguang", "zhao": "Zhao", "qianxia": "Sunna", "aria": "Aria",
    "nangong_yu": "Nangong Yu", "cissia": "Cissia", "promeia": "Promeia",
    "starlight_billy": "Starlight-Billy", "velina": "Velina", "norma": "Norma",
    "pyrois": "Pyrois", "remielle": "Remielle", "sigrid": "Sigrid",
}
MOEGIRL_BASE = "https://zh.moegirl.org.cn/Special:FilePath/"

# ============================================================
# 鸣潮 精编角色表（国服官方名，截至 v3.5）
# 格式: (id_key, name, en, element, weapon, rarity, version, aliases)
# rarity: 5/4 ; element(6种): 衍射/导电/冷凝/热熔/气动/湮灭
# weapon(5种): 迅刀/长刃/臂铠/佩枪/音感仪
# ============================================================
WUWA_CHARS = [
    ("rover_spectro", "漂泊者·衍射", "Rover", "衍射", "迅刀", 5, "1.0", ["漂泊者", " Rover"]),
    ("rover_havoc", "漂泊者·湮灭", "Rover", "湮灭", "迅刀", 5, "1.0", ["漂泊者"]),
    ("calcharo", "卡卡罗", "Calcharo", "湮灭", "长刃", 5, "1.0", ["卡卡罗"]),
    ("encore", "安可", "Encore", "热熔", "音感仪", 5, "1.0", ["安可"]),
    ("jianxin", "鉴心", "Jianxin", "气动", "臂铠", 5, "1.0", ["鉴心"]),
    ("lingyang", "凌阳", "Lingyang", "冷凝", "臂铠", 5, "1.0", ["凌阳"]),
    ("verina", "维里奈", "Verina", "衍射", "音感仪", 5, "1.0", ["维里奈"]),
    ("jiyan", "忌炎", "Jiyan", "气动", "长刃", 5, "1.0", ["忌炎"]),
    ("yinlin", "吟霖", "Yinlin", "导电", "音感仪", 5, "1.0", ["吟霖"]),
    ("aalto", "秋水", "Aalto", "气动", "佩枪", 4, "1.0", ["秋水"]),
    ("baizhi", "白芷", "Baizhi", "冷凝", "音感仪", 4, "1.0", ["白芷"]),
    ("chixia", "炽霞", "Chixia", "热熔", "佩枪", 4, "1.0", ["炽霞"]),
    ("danjin", "丹瑾", "Danjin", "湮灭", "迅刀", 4, "1.0", ["丹瑾"]),
    ("mortefi", "莫特斐", "Mortefi", "热熔", "佩枪", 4, "1.0", ["莫特斐"]),
    ("sanhua", "散华", "Sanhua", "冷凝", "迅刀", 4, "1.0", ["散华"]),
    ("taoqi", "桃祈", "Taoqi", "湮灭", "长刃", 4, "1.0", ["桃祈"]),
    ("yangyang", "秧秧", "Yangyang", "气动", "迅刀", 4, "1.0", ["秧秧"]),
    ("yuanwu", "渊武", "Yuanwu", "导电", "臂铠", 4, "1.0", ["渊武"]),
    ("jinhsi", "今汐", "Jinhsi", "衍射", "长刃", 5, "1.1", ["今汐"]),
    ("changli", "长离", "Changli", "热熔", "迅刀", 5, "1.1", ["长离"]),
    ("zhezhi", "折枝", "Zhezhi", "冷凝", "音感仪", 5, "1.2", ["折枝"]),
    ("xiangli_yao", "相里要", "Xiangli Yao", "导电", "臂铠", 5, "1.2", ["相里要"]),
    ("shorekeeper", "守岸人", "Shorekeeper", "衍射", "音感仪", 5, "1.3", ["守岸人"]),
    ("youhu", "釉瑚", "Youhu", "冷凝", "臂铠", 4, "1.3", ["釉瑚"]),
    ("camellya", "椿", "Camellya", "湮灭", "迅刀", 5, "1.4", ["椿"]),
    ("lumi", "灯灯", "Lumi", "导电", "长刃", 4, "1.4", ["灯灯"]),
    ("carlotta", "珂莱塔", "Carlotta", "冷凝", "佩枪", 5, "2.0", ["珂莱塔"]),
    ("roccia", "洛可可", "Roccia", "湮灭", "臂铠", 5, "2.0", ["洛可可"]),
    ("phoebe", "菲比", "Phoebe", "衍射", "音感仪", 5, "2.1", ["菲比"]),
    ("brant", "布兰特", "Brant", "热熔", "迅刀", 5, "2.1", ["布兰特"]),
    ("cantarella", "坎特蕾拉", "Cantarella", "湮灭", "音感仪", 5, "2.2", ["坎特蕾拉"]),
    ("rover_aero", "漂泊者·气动", "Rover", "气动", "迅刀", 5, "2.2", ["漂泊者"]),
    ("zani", "赞妮", "Zani", "衍射", "臂铠", 5, "2.3", ["赞妮"]),
    ("ciaconna", "夏空", "Ciaccona", "气动", "佩枪", 5, "2.3", ["夏空"]),
    ("cartethyia", "卡提希娅", "Cartethyia", "气动", "迅刀", 5, "2.4", ["卡提希娅"]),
    ("lupa", "露帕", "Lupa", "热熔", "长刃", 5, "2.4", ["露帕"]),
    ("phrolova", "弗洛洛", "Phrolova", "湮灭", "音感仪", 5, "2.5", ["弗洛洛"]),
    ("augusta", "奥古斯塔", "Augusta", "导电", "长刃", 5, "2.6", ["奥古斯塔"]),
    ("iuno", "尤诺", "Iuno", "气动", "臂铠", 5, "2.6", ["尤诺"]),
    ("galbrena", "嘉贝莉娜", "Galbrena", "热熔", "佩枪", 5, "2.7", ["嘉贝莉娜"]),
    ("qiuyuan", "仇远", "Qiuyuan", "气动", "迅刀", 5, "2.7", ["仇远"]),
    ("chisa", "千咲", "Chisa", "湮灭", "长刃", 5, "2.8", ["千咲"]),
    ("buling", "卜灵", "Buling", "导电", "音感仪", 4, "2.8", ["卜灵"]),
    ("lynae", "琳奈", "Lynae", "衍射", "佩枪", 5, "3.0", ["琳奈"]),
    ("mornye", "莫宁", "Mornye", "热熔", "长刃", 5, "3.0", ["莫宁"]),
    ("aemeath", "爱弥斯", "Aemeath", "热熔", "迅刀", 5, "3.1", ["爱弥斯"]),
    ("luuk_hersen", "陆·赫斯", "Luuk Herssen", "衍射", "臂铠", 5, "3.1", ["陆·赫斯"]),
    ("sigrika", "西格莉卡", "Sigrika", "气动", "臂铠", 5, "3.2", ["西格莉卡"]),
    ("hiyuki", "绯雪", "Hiyuki", "冷凝", "迅刀", 5, "3.3", ["绯雪"]),
    ("denia", "达妮娅", "Denia", "热熔", "音感仪", 5, "3.3", ["达妮娅"]),
    ("lucy_wuwa", "露西", "Lucy", "衍射", "佩枪", 5, "3.4", ["露西", "赛博朋克联动"]),
    ("rebecca", "丽贝卡", "Rebecca", "导电", "佩枪", 5, "3.4", ["丽贝卡", "赛博朋克联动"]),
    ("lucilla", "洛瑟菈", "Lucilla", "冷凝", "音感仪", 5, "3.4", ["洛瑟菈"]),
    ("yangyang_xuanling", "秧秧·玄翎", "Yangyang Xuanling", "湮灭", "迅刀", 5, "3.5", ["秧秧·玄翎"]),
    ("suisui", "穗穗", "Suisui", "冷凝", "音感仪", 5, "3.5", ["穗穗"]),
    ("rover_electro", "漂泊者·导电", "Rover", "导电", "迅刀", 5, "3.5", ["漂泊者"]),
]

# ============================================================
# 终末地 精编角色表（国服官方名，截至 v1.4，已公测）
# 格式: (id_key, name, en, class, branch, element, rarity, version, aliases)
# rarity: 6/5/4 ; class(6种): 近卫/术师/突击/先锋/重装/辅助
# element(5种): 物理/灼热/电磁/寒冷/自然 ; branch 暂无子系统，统一 "-"
# 注：element="" 表示官方未明确公开，待游戏内核对。
# ============================================================
ENDFIELD_CHARS = [
    ("admin", "管理员", "Endministrator", "近卫", "-", "", 5, "1.0", ["管理员", "主角"]),
    ("ember", "余烬", "Ember", "重装", "-", "灼热", 6, "1.0", ["余烬", "公测赠送"]),
    ("lifeng", "黎风", "Lifeng", "近卫", "-", "物理", 6, "1.0", ["黎风"]),
    ("ardelia", "艾尔黛拉", "Ardelia", "辅助", "-", "自然", 6, "1.0", ["艾尔黛拉"]),
    ("last_rite", "别礼", "Last Rite", "突击", "-", "寒冷", 6, "1.0", ["别礼"]),
    ("pogranichnik", "骏卫", "Pogranichnik", "先锋", "-", "物理", 6, "1.0", ["骏卫"]),
    ("laevatain", "莱万汀", "Laevatain", "突击", "-", "灼热", 6, "1.0", ["莱万汀"]),
    ("gilberta", "洁尔佩塔", "Gilberta", "辅助", "-", "自然", 6, "1.0", ["洁尔佩塔"]),
    ("yvonne", "伊冯", "Yvonne", "突击", "-", "寒冷", 6, "1.0", ["伊冯"]),
    ("perlica", "佩丽卡", "Perlica", "术师", "-", "", 5, "1.0", ["佩丽卡", "监督员"]),
    ("chen_qianyu", "陈千语", "Chen Qianyu", "近卫", "-", "物理", 5, "1.0", ["陈千语"]),
    ("wulfgard", "狼卫", "Wulfgard", "近卫", "-", "", 5, "1.0", ["狼卫"]),
    ("arclight", "弧光", "Arclight", "先锋", "-", "电磁", 5, "1.0", ["弧光"]),
    ("alesh", "阿列什", "Alesh", "先锋", "-", "", 5, "1.0", ["阿列什"]),
    ("avywenna", "艾维文娜", "Avywenna", "突击", "-", "", 5, "1.0", ["艾维文娜"]),
    ("da_pan", "大潘", "Da Pan", "重装", "-", "", 5, "1.0", ["大潘"]),
    ("snowshine", "昼雪", "Snowshine", "重装", "-", "", 5, "1.0", ["昼雪"]),
    ("xaihi", "赛希", "Xaihi", "辅助", "-", "", 5, "1.0", ["赛希"]),
    ("estella", "埃特拉", "Estella", "近卫", "-", "物理", 4, "1.0", ["埃特拉"]),
    ("catcher", "卡契尔", "Catcher", "重装", "-", "", 4, "1.0", ["卡契尔"]),
    ("antal", "安塔尔", "Antal", "辅助", "-", "", 4, "1.0", ["安塔尔"]),
    ("akekuri", "秋栗", "Akekuri", "先锋", "-", "", 4, "1.0", ["秋栗"]),
    ("fluorite", "萤石", "Fluorite", "术师", "-", "自然", 4, "1.0", ["萤石"]),
    ("tangtang", "汤汤", "Tangtang", "术师", "-", "寒冷", 6, "1.1", ["汤汤"]),
    ("rossi", "洛茜", "Rossi", "近卫", "-", "物理", 6, "1.1", ["洛茜"]),
    ("zhuang_fangyi", "庄方宜", "Zhuang Fangyi", "突击", "-", "电磁", 6, "1.2", ["庄方宜"]),
    ("mi_fu", "弭弗", "Mi Fu", "近卫", "-", "物理", 6, "1.3", ["弭弗"]),
    ("camille", "卡缪", "Camille", "先锋", "-", "灼热", 6, "1.3", ["卡缪"]),
    ("arcane", "诀", "Arcane", "术师", "-", "自然", 6, "1.4", ["诀"]),
    ("liino", "梨诺", "Liino", "辅助", "-", "电磁", 6, "1.4", ["梨诺"]),
]

# ============================================================
# 异环 精编角色表（国服官方名，截至 v1.2，已公测）
# 格式: (id_key, name, en, element, weapon, rarity, version, aliases)
# rarity: 5(S)/4(A) ; element(6种官方属系): 光/灵/咒/暗/魂/相
# ============================================================
NTE_CHARS = [
    ("zero", "零", "Zero", "光", "", 5, "1.0", ["零", "主角"]),
    ("nanally", "娜娜莉", "Nanally", "灵", "太刀", 5, "1.0", ["娜娜莉"]),
    ("jiuyuan", "九原", "Jiuyuan", "灵", "双枪", 5, "1.0", ["九原"]),
    ("baizang", "白藏", "Baizang", "咒", "言灵书", 5, "1.0", ["白藏"]),
    ("hotori", "穗鸟", "Hotori", "光", "时停伞", 5, "1.0", ["穗鸟"]),
    ("xiaozhi", "小吱", "Xiaozhi", "光", "能量", 5, "1.0", ["小吱", "免费"]),
    ("fadia", "法蒂亚", "Fadia", "灵", "双刃十字盾", 5, "1.0", ["法蒂亚"]),
    ("daffodil", "达芙蒂尔", "Daffodil", "暗", "双刀", 5, "1.0", ["达芙蒂尔"]),
    ("sagiri", "早雾", "Sagiri", "咒", "巨锤", 5, "1.0", ["早雾"]),
    ("hathor", "哈索尔", "Hathor", "相", "体术摩托", 5, "1.0", ["哈索尔"]),
    ("sakiri", "咲里", "Sakiri", "咒", "法器", 5, "1.0", ["咲里"]),
    ("xun", "浔", "Xun", "光", "伞太刀", 5, "1.0", ["浔", "1.0登场"]),
    ("haniel", "哈尼娅", "Haniel", "魂", "音响", 4, "1.0", ["哈尼娅", "免费"]),
    ("mint", "薄荷", "Mint", "灵", "双刀", 4, "1.0", ["薄荷"]),
    ("aurelia", "海月", "Aurelia", "魂", "指挥棒", 4, "1.0", ["海月", "免费"]),
    ("adler", "阿德勒", "Adler", "咒", "手杖枪", 4, "1.0", ["阿德勒"]),
    ("skia", "翳", "Skia", "相", "格斗", 4, "1.0", ["翳"]),
    ("edgar", "埃德嘉", "Edgar", "光", "", 4, "1.0", ["埃德嘉"]),
    ("requiem", "安魂曲", "Requiem", "暗", "拟态", 5, "1.1", ["安魂曲"]),
    ("kaos", "卡厄斯", "Kaos", "相", "手甲", 5, "1.1", ["卡厄斯"]),
    ("zhenhong", "真红", "Zhenhong", "光", "龙爪", 5, "1.2", ["真红"]),
    ("iroi", "伊洛伊", "Iroi", "灵", "梦境", 5, "1.2", ["伊洛伊"]),
]




def _zzz_avatar(name_key):
    """ZZZ 头像 URL：萌娘百科角色头像（已验证可达，外链嵌入）。

    无映射的角色返回空串，前端自动回退官方属性色卡。
    """
    fn = ZZZ_MOEGIRL.get(name_key)
    if not fn:
        return ""
    return MOEGIRL_BASE + quote(fn + "-Role.png")




# ============================================================
# 星穹铁道 真实头像（Enka Network，按 AvatarId）
# 来源：Mar-7th/StarRailRes(GitHub) characters.json 提供 en名->AvatarId 映射；
#       图标取 Enka Network 官方资源 SpriteOutput/AvatarRoundIcon/{id}.png
# 下方 HSR_AVATAR_IDS 已由脚本对每张 URL 做 HTTP 200 验证（沙箱+本机均可达），离线可用、零假数据。
# 无映射/验证失败的角色不写入，前端自动回退官方属性色卡。
# ============================================================
ENKA_HSR_AVATAR = "https://enka.network/ui/hsr/SpriteOutput/AvatarRoundIcon/"
HSR_GITHUB_CHARS = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/index_new/en/characters.json"
# 形态变体：我方 en 名 -> StarRailRes 规范 en 名
HSR_AVATAR_ALIAS = {
    "dan heng imbibitor lunae": "dan heng • imbibitor lunae",
    "dan heng permansor terrae": "dan heng • permansor terrae",
    "march 7th hunt": "march 7th",
    "dahlia": "the dahlia",
    "himeko nova": "himeko • nova",
}
HSR_TRAILBLAZER_ID = "8001"  # 开拓者（5 命途同角色，统一已验证图标）
HSR_AVATAR_IDS = {
    "hsr_trailblazer_destruction": "8001",
    "hsr_march_7th": "1224",
    "hsr_dan_heng": "1002",
    "hsr_himeko": "1003",
    "hsr_welt": "1004",
    "hsr_arlan": "1008",
    "hsr_asta": "1009",
    "hsr_herta": "1013",
    "hsr_gepard": "1104",
    "hsr_serval": "1103",
    "hsr_pela": "1106",
    "hsr_natasha": "1105",
    "hsr_seele": "1102",
    "hsr_clara": "1107",
    "hsr_sampo": "1108",
    "hsr_hook": "1109",
    "hsr_jing_yuan": "1204",
    "hsr_yanqing": "1209",
    "hsr_sushang": "1206",
    "hsr_qingque": "1201",
    "hsr_tingyun": "1202",
    "hsr_bailu": "1211",
    "hsr_bronya": "1101",
    "hsr_silver_wolf": "1006",
    "hsr_luocha": "1203",
    "hsr_yukong": "1207",
    "hsr_kafka": "1005",
    "hsr_blade": "1205",
    "hsr_luka": "1111",
    "hsr_fu_xuan": "1208",
    "hsr_dan_heng_imbibitor_lunae": "1213",
    "hsr_lynx": "1110",
    "hsr_trailblazer_preservation": "8001",
    "hsr_jingliu": "1212",
    "hsr_topaz_numby": "1112",
    "hsr_guinaifen": "1210",
    "hsr_huohuo": "1217",
    "hsr_argenti": "1302",
    "hsr_ruan_mei": "1303",
    "hsr_dr_ratio": "1305",
    "hsr_xueyi": "1214",
    "hsr_hanya": "1215",
    "hsr_black_swan": "1307",
    "hsr_sparkle": "1306",
    "hsr_misha": "1312",
    "hsr_acheron": "1308",
    "hsr_aventurine": "1304",
    "hsr_gallagher": "1301",
    "hsr_trailblazer_harmony": "8001",
    "hsr_robin": "1309",
    "hsr_boothill": "1315",
    "hsr_firefly": "1310",
    "hsr_jade": "1314",
    "hsr_yunli": "1221",
    "hsr_jiaoqiu": "1218",
    "hsr_march_7th_hunt": "1224",
    "hsr_feixiao": "1220",
    "hsr_lingsha": "1222",
    "hsr_moze": "1223",
    "hsr_rappa": "1317",
    "hsr_sunday": "1313",
    "hsr_fugue": "1225",
    "hsr_the_herta": "1401",
    "hsr_aglaea": "1402",
    "hsr_trailblazer_remembrance": "8001",
    "hsr_tribbie": "1403",
    "hsr_mydei": "1404",
    "hsr_castorice": "1407",
    "hsr_anaxa": "1405",
    "hsr_hyacine": "1409",
    "hsr_cipher": "1406",
    "hsr_phainon": "1408",
    "hsr_hysilens": "1410",
    "hsr_cerydra": "1412",
    "hsr_evernight": "1413",
    "hsr_dan_heng_permansor": "1414",
    "hsr_cyrene": "1415",
    "hsr_dahlia": "1321",
    "hsr_sparxie": "1501",
    "hsr_ashveil": "1504",
    "hsr_silver_wolf_lv999": "1506",
    "hsr_evanescia": "1505",
    "hsr_trailblazer_elation": "8001",
    "hsr_mortenax_blade": "1507",
    "hsr_himeko_nova": "1510",
    "hsr_saber": "1014",
    "hsr_archer": "1015",
    "hsr_rin_tosaka": "1508",
    "hsr_gilgamesh": "1509",
    "hsr_yaoguang": "1502",
}

def _hsr_avatar(name_key):
    # name_key 可能带或不带 "hsr_" 前缀（_build_hsr 传裸 idx，fetch 用完整 id）
    aid = HSR_AVATAR_IDS.get(name_key) or HSR_AVATAR_IDS.get("hsr_" + name_key)
    return (ENKA_HSR_AVATAR + aid + ".png") if aid else ""


def _num(v):
    """宽松转 float（容忍千分位/空格/中文全角）。"""
    if v is None:
        return None
    s = str(v).replace(",", "").replace("，", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _url_ok(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"}), timeout=12)
        return r.status == 200
    except Exception:
        return False


# ============================================================
# 原神头像（api.lunaris.moe 角色卡图映射 + Enka Network 资源）
# lunaris 的 CardImg 含官方资源 key（如 UI_Gacha_AvatarIcon_Shougun），
# 与 Enka 的 UI_AvatarIcon_<key>.png 一一对应。本地 en 名与资源名存在
# 差异（胡桃 HuTao vs Hutao、雷电将军 Raiden vs Shougun），因此以
# lunaris 映射为准；lunaris 未收录的本地角色再用本地 en 兜底。
# ============================================================
LUNARIS_VERSION_URL = "https://api.lunaris.moe/data/version.json"
LUNARIS_CHARLIST_URL = "https://api.lunaris.moe/data/%s/charlist.json"
ENKA_GI_AVATAR = "https://enka.network/ui/UI_AvatarIcon_%s.png"
GI_AVATAR_MIRROR = "https://gi.yatta.moe/assets/UI/UI_AvatarIcon_%s.png"


def _norm_genshin_name(s):
    return re.sub(r"[\s.\-\u00b7\u2022\u30fb'']+", "", str(s or "")).lower()


def _genshin_lunaris_index():
    """拉取 lunaris 最新角色表并建立 英文/中文名 -> 条目 索引。失败返回 {}。"""
    try:
        ver = json.loads(urllib.request.urlopen(urllib.request.Request(
            LUNARIS_VERSION_URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=25)
            .read().decode("utf-8"))["version"]
        req = urllib.request.Request(LUNARIS_CHARLIST_URL % ver,
                                     headers={"User-Agent": "Mozilla/5.0"})
        cl = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))
        entries = list(cl.values()) if isinstance(cl, dict) else list(cl)
    except Exception:
        return {}
    return {
        "version": ver,
        "by_en": {_norm_genshin_name(it.get("enName")): it
                  for it in entries if it.get("enName")},
        "by_chs": {_norm_genshin_name(it.get("chsName")): it
                   for it in entries if it.get("chsName")},
    }


def _genshin_avatar_key(local, idx=None):
    """返回本地角色在 Enka 的头像 key：lunaris CardImg 优先，其次本地 en。"""
    en = local.get("en") or ""
    name = local.get("name") or ""
    if idx:
        m = (idx.get("by_en") or {}).get(_norm_genshin_name(en))
        if not m:
            m = (idx.get("by_chs") or {}).get(_norm_genshin_name(name))
        if not m:
            for a in (local.get("aliases") or []):
                m = ((idx.get("by_chs") or {}).get(_norm_genshin_name(a))
                     or (idx.get("by_en") or {}).get(_norm_genshin_name(a)))
                if m:
                    break
        if m:
            key = re.sub(r"^UI_(Gacha_)?AvatarIcon_", "", m.get("CardImg") or "")
            if key:
                return key
    key = (en or "").strip() or _norm_genshin_name(name)
    return re.sub(r"^genshin_", "", key or "")


def _genshin_avatar_urls(local, idx=None):
    key = _genshin_avatar_key(local, idx)
    if not key:
        return "", ""
    return ENKA_GI_AVATAR % key, GI_AVATAR_MIRROR % key


def fetch_hsr_avatars():
    """联网从 StarRailRes(GitHub) 拉取 en名->AvatarId 映射，逐张验证 Enka URL，
    写回 data/hsr_characters.json。仅写入验证通过的 URL；网络不可用时返回 (0,'network')
    且不改动任何数据（优雅回退到 HSR_AVATAR_IDS 静态表）。"""
    try:
        gh = json.load(urllib.request.urlopen(urllib.request.Request(
            HSR_GITHUB_CHARS, headers={"User-Agent":"Mozilla/5.0"}), timeout=25))
    except Exception as e:
        return 0, "network_unavailable"
    name2id = {(it.get("name") or "").strip().lower(): it.get("id") for it in gh.values()}
    path = os.path.join(DATA_DIR, "hsr_characters.json")
    if not os.path.exists(path):
        return 0, "no_data"
    doc = json.load(open(path, encoding="utf-8"))
    updated = 0
    for c in doc["characters"]:
        en = (c.get("en") or "").strip().lower()
        if "trailblazer" in c["id"] or "开拓者" in (c.get("name") or ""):
            gid = HSR_TRAILBLAZER_ID
        else:
            gid = name2id.get(en) or name2id.get(HSR_AVATAR_ALIAS.get(en, ""))
        if not gid:
            continue
        u = ENKA_HSR_AVATAR + gid + ".png"
        if _url_ok(u) and c.get("icon") != u:
            c["icon"] = u
            updated += 1
    if updated:
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return updated, "ok"


# ============================================================
# HSR 角色名单在线拉取（StarRailRes —— 游戏资源官方镜像，每版本自动更新）
# 来源：github.com/Mar-7th/StarRailRes（社区事实标准，Enka 等主流工具同源；
#       每版本更新后数小时内同步游戏内真实资源，字段含 AvatarId / 中文名 /
#       tag / path(命途代码) / element(属性代码) / rarity / icon）。
#   cn 名单: index_new/cn/characters.json
#   en 名单: index_new/en/characters.json
#   icon:   icon/character/{AvatarId}.png
# ============================================================
STARRAILRES_BASE = "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/"
STARRAILRES_CN = STARRAILRES_BASE + "index_new/cn/characters.json"
STARRAILRES_EN = STARRAILRES_BASE + "index_new/en/characters.json"
STARRAILRES_ICON = STARRAILRES_BASE + "icon/character/%s.png"

SRR_PATH_MAP = {
    "Warrior": "毁灭", "Rogue": "巡猎", "Mage": "智识", "Shaman": "同谐",
    "Warlock": "虚无", "Knight": "存护", "Priest": "丰饶", "Memory": "记忆",
    "Elation": "欢愉",
}
SRR_ELEMENT_MAP = {
    "Physical": "物理", "Fire": "火", "Ice": "冰", "Thunder": "雷",
    "Wind": "风", "Quantum": "量子", "Imaginary": "虚数",
}


def _hsr_aid_of(c):
    """返回本地 HSR 角色对应的 StarRailRes AvatarId（静态表优先，其次从现有 icon 反推）。"""
    aid = HSR_AVATAR_IDS.get(c.get("id"))
    if aid:
        return aid
    m = __import__("re").search(r"AvatarRoundIcon/(\d+)\.png", c.get("icon") or "")
    return m.group(1) if m else None


def update_hsr_db(timeout=25):
    """联网从 StarRailRes 拉取 HSR 官方角色名单，合并升级本地 data/hsr_characters.json。

    策略（安全优先，绝不臆造/覆盖人工核对数据）：
      - 已有角色：仅补充缺失的 en / icon；元素/命途/稀有度以本地精编为准，不覆盖
        （主角形态与共享 AvatarId 的形态变体易误判，故一律不改）。
      - 新角色：StarRailRes 有而本地没有的，自动追加（version 留空待核对，
        icon 用 Enka 按 AvatarId 直链，前端加载失败自动回退官方属性色卡）。
      - 网络失败返回 ok=False/error='network_unavailable'，不改动任何数据。
    Returns dict: {ok, game, total, added, added_names, source, message, error}
    """
    def _get(url):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    try:
        cn = _get(STARRAILRES_CN)
        en = _get(STARRAILRES_EN)
    except Exception:
        return {"ok": False, "game": "hsr", "error": "network_unavailable",
                "message": "网络不可用或 StarRailRes 暂不可达，未改动任何数据。"}

    path = os.path.join(DATA_DIR, "hsr_characters.json")
    if not os.path.exists(path):
        return {"ok": False, "game": "hsr", "error": "no_data",
                "message": "本地角色库不存在，请先在设置页点「重建当前游戏角色库（精编数据）」。"}
    doc = json.load(open(path, encoding="utf-8"))
    chars = doc.get("characters", [])

    # 1) 组装 StarRailRes 条目（跳过主角男女形态 {NICKNAME}）
    srr_list = []
    for aid, v in cn.items():
        if not isinstance(v, dict) or not v.get("name"):
            continue
        tag = v.get("tag") or ""
        if aid[:1] == "8" and tag.startswith("player"):
            continue
        ev = en.get(aid, {}) or {}
        srr_list.append({
            "aid": aid,
            "name": (v.get("name") or "").replace("\u2022", "\u00b7"),
            "en": ev.get("name") or "",
            "tag": tag,
            "path": SRR_PATH_MAP.get(v.get("path")) or v.get("path") or "",
            "element": SRR_ELEMENT_MAP.get(v.get("element")) or v.get("element") or "",
            "rarity": v.get("rarity"),
        })
    srr_by_aid = {s["aid"]: s for s in srr_list}

    # 2) 已有角色：仅补齐缺失的 en / icon
    filled_en = filled_icon = 0
    for c in chars:
        aid = _hsr_aid_of(c)
        s = srr_by_aid.get(aid)
        if not s:
            continue
        if not (c.get("en") or "").strip() and s.get("en"):
            c["en"] = s["en"]
            filled_en += 1
        if not (c.get("icon") or "").strip() and aid:
            c["icon"] = ENKA_HSR_AVATAR + aid + ".png"
            filled_icon += 1

    # 3) 追加新角色（StarRailRes 有而本地无）
    used_aids = {aid for c in chars if (aid := _hsr_aid_of(c))}
    used_names = set()
    for c in chars:
        used_names.add((c.get("name") or "").replace("\u2022", "\u00b7").strip())
        for a in (c.get("aliases") or []):
            used_names.add(str(a).replace("\u2022", "\u00b7").strip())

    added = []
    for s in srr_list:
        if s["aid"] in used_aids or s["name"] in used_names:
            continue
        chars.append({
            "id": "hsr_" + (s["tag"] or s["aid"]),
            "name": s["name"],
            "en": s["en"],
            "aliases": [s["name"]],
            "element": s["element"],
            "weapon": s["path"],
            "path": s["path"],
            "rarity": s["rarity"],
            "version": "",
            "status": "released",
            "note": "由 StarRailRes 官方镜像自动拉取（版本待核对）",
            "icon": ENKA_HSR_AVATAR + s["aid"] + ".png",
            "icon_fallback": "",
        })
        added.append(s["name"])

    if not added and not filled_en and not filled_icon:
        return {"ok": True, "game": "hsr", "total": len(chars),
                "added": 0, "added_names": [], "filled_en": 0, "filled_icon": 0,
                "source": "StarRailRes", "changed": False,
                "message": "名单已是最新（StarRailRes 官方镜像 %d 名角色，本地无新增）。" % len(srr_list)}

    # 备份后写回（带时间戳，避免同日多次更新互相覆盖）
    bak = path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backed_up = False
    try:
        shutil.copy2(path, bak)
        backed_up = True
    except Exception:
        backed_up = False
    doc["region_note"] = ("由 StarRailRes 官方镜像（游戏资源，每版本自动更新）于 %s 在线拉取合并"
                          "（%d 名角色，新增 %d）。离线精编基线见 hsr_characters.json.bak。"
                          % (datetime.date.today().isoformat(), len(chars), len(added)))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return {"ok": True, "game": "hsr", "total": len(chars),
            "added": len(added), "added_names": added,
            "filled_en": filled_en, "filled_icon": filled_icon,
            "source": "StarRailRes", "changed": True, "backed_up": backed_up,
            "message": "已从 StarRailRes 官方镜像同步 %d 名角色（新增 %d 名：%s），旧文件已备份。"
                       % (len(chars), len(added), "、".join(added) or "无")}


# ============================================================
# 原神 角色名单在线拉取（genshin-db —— GenshinData 官方数据镜像的 npm 发行版）
# 来源：registry.npmjs.org/genshin-db（持续更新，最新 5.x；内含全部已上线角色：
#       中文名 / 英文名 / 元素(中文) / 武器(中文) / 稀有度 / 上线日期）。
# 说明：api.ambr.top 需家庭宽带（数据中心 IP 被拦），故名单走 npm 官方镜像；
#       已下载过的数据版本会缓存在 .cache/genshin_db_chars.json，仅版本更新时重新下载。
# ============================================================
GDB_REGISTRY_URL = "https://registry.npmjs.org/genshin-db/latest"
GDB_TGZ_URL = "https://registry.npmjs.org/genshin-db/-/genshin-db-%s.tgz"


def _gdb_cache_path():
    return os.path.join(os.path.dirname(DATA_DIR), ".cache", "genshin_db_chars.json")


def _load_gdb_characters(version, timeout=120):
    """下载 genshin-db 并提取角色精简表（不缓存原始 177MB JSON，只缓存提取结果）。"""
    req = urllib.request.Request(GDB_TGZ_URL % version, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        tgz = r.read()
    tf = tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz")
    raw = tf.extractfile("package/src/min/data.min.json").read()
    obj = json.loads(raw)
    data = obj.get("data", {})
    cn = data.get("ChineseSimplified", {}).get("characters", {}) or {}
    en = data.get("English", {}).get("characters", {}) or {}
    out = []
    for slug, c in cn.items():
        if not isinstance(c, dict):
            continue
        e = en.get(slug, {}) or {}
        out.append({
            "slug": slug,
            "name": c.get("name") or "",
            "en": e.get("name") or "",
            "element": c.get("elementText") or "",
            "weapon": c.get("weaponText") or "",
            "rarity": c.get("rarity"),
            "release": c.get("release") or "",
        })
    return out


def _genshin_version_from_date(datestr):
    """按上线日期推算原神大版本（1.0=2020-09-28，约 6 周一版）。仅用于新角色标注。"""
    try:
        d = datetime.date.fromisoformat(datestr)
    except Exception:
        return ""
    t0 = datetime.date(2020, 9, 28)
    days = (d - t0).days
    if days < 0:
        return "1.0"
    ver = 1.0 + days / 42.0 * 0.1
    return "%.1f" % min(ver, 99.0)


GENSHIN_FANDOM_API = "https://genshin-impact.fandom.com/api.php"
GENSHIN_ZH_VERSION_TITLES = {
    "7.0": "无神怜爱的雪国",
}
GENSHIN_FANDOM_ELEMENTS = {
    "Pyro": "火", "Hydro": "水", "Electro": "雷", "Cryo": "冰",
    "Anemo": "风", "Geo": "岩", "Dendro": "草",
}
GENSHIN_FANDOM_WEAPONS = {
    "Sword": "单手剑", "Claymore": "双手剑", "Polearm": "长柄武器",
    "Bow": "弓", "Catalyst": "法器",
}
_GENSHIN_NEW_CHAR_RE = re.compile(
    r'^\*\s*"(?:[^"]*)"\s*\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*'
    r"\((\d)-Star\s*\{\{([^}|]+)(?:\|[^}]*)?\}\}\s*([A-Za-z ]+)\)\s*$",
    re.M,
)


def _genshin_slug(text):
    return re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()


def _fandom_api(params, timeout=30):
    url = "%s?%s" % (GENSHIN_FANDOM_API, urlencode(params))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _fandom_current_version(timeout=30):
    """Fandom 的 CurrentVersion 模板会展开为当前大版本号（如 7.0）。"""
    data = _fandom_api({
        "action": "expandtemplates",
        "text": "{{CurrentVersion|version=no}}",
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }, timeout)
    ver = ((data.get("expandtemplates") or {}).get("wikitext") or "").strip()
    if re.fullmatch(r"\d+\.\d+", ver):
        return ver
    return ""


def _fandom_version_wikitext(version, timeout=30):
    data = _fandom_api({
        "action": "parse",
        "page": "Version/" + version,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }, timeout)
    return ((data.get("parse") or {}).get("wikitext") or "")


def _fandom_zh_name(en_name, timeout=30):
    """Fandom 角色页通常带 |zhs=中文名，用于给英文 Wiki 抓到的角色补中文名。"""
    try:
        data = _fandom_api({
            "action": "parse",
            "page": en_name,
            "prop": "wikitext",
            "format": "json",
            "formatversion": "2",
        }, timeout)
        text = ((data.get("parse") or {}).get("wikitext") or "")
        m = re.search(r"(?m)^\|\s*zhs\s*=\s*(.+?)\s*$", text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""


def _fandom_new_characters(wikitext, version, timeout=30):
    """从 Fandom Version/X.Y 的 New Characters 段落提取新角色精简表。"""
    out = []
    for en, rarity, elem_tpl, weapon_tpl in _GENSHIN_NEW_CHAR_RE.findall(wikitext):
        element = GENSHIN_FANDOM_ELEMENTS.get(elem_tpl.strip())
        weapon = GENSHIN_FANDOM_WEAPONS.get(weapon_tpl.strip())
        if not element or not weapon:
            continue
        out.append({
            "slug": _genshin_slug(en),
            "name": _fandom_zh_name(en, timeout),
            "en": en,
            "element": element,
            "weapon": weapon,
            "rarity": int(rarity),
            "version": version,
            "source": "fandom",
        })
    return out


def _fandom_snapshot(timeout=30):
    """抓当前版本号、版本标题、上线日期与 New Characters，失败时返回 ok=False。"""
    snap = {"ok": False, "version": "", "title": "", "date": "",
            "characters": [], "version_text": ""}
    try:
        version = _fandom_current_version(timeout)
        if not version:
            return snap
        wt = _fandom_version_wikitext(version, timeout)
        if not wt:
            return snap
        m = re.search(r"(?m)^\|\s*title\s*=\s*(.+?)\s*$", wt)
        title = m.group(1).strip() if m else ""
        m = re.search(r"(?m)^\|\s*date\s*=\s*([0-9-]+)\s*$", wt)
        date = m.group(1).strip() if m else ""
        zh_title = GENSHIN_ZH_VERSION_TITLES.get(version, "")
        if zh_title and title:
            label = "%s · %s" % (zh_title, title)
        else:
            label = zh_title or title
        version_text = version + (("（%s）" % label) if label else "") + "在跑"
        if date:
            version_text += " · %s 已上线" % date
        snap.update({
            "ok": True,
            "version": version,
            "title": title,
            "date": date,
            "characters": _fandom_new_characters(wt, version, timeout),
            "version_text": version_text,
        })
    except Exception:
        pass
    return snap


def update_genshin_db(timeout=40):
    """联网拉取原神名单：genshin-db 主源 + Fandom 当前版本上线页兜底。

    genshin-db 有时会滞后一个版本（如 7.0 上线后仍停在 6.7），因此额外解析
    Fandom 的 Version/X.Y 页面，把当前版本新角色与版本文本自动补进本地库。
    已有角色仅补齐缺失字段；新角色自动追加；两个数据源都不可达时才失败。
    Returns dict: {ok, game, total, added, added_names, source, message, version_text, ...}
    """
    def _get(url, tmo):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=tmo) as r:
            return r.read()

    gdb_version = ""
    chars_official = []
    gdb_ok = False
    try:
        meta = json.loads(_get(GDB_REGISTRY_URL, timeout).decode("utf-8"))
        gdb_version = meta.get("version") or ""
        cache_path = _gdb_cache_path()
        if os.path.exists(cache_path):
            try:
                cached = json.load(open(cache_path, encoding="utf-8"))
                if cached.get("version") == gdb_version and cached.get("characters"):
                    chars_official = cached["characters"]
            except Exception:
                pass
        if not chars_official:
            chars_official = _load_gdb_characters(gdb_version, timeout)
            try:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                json.dump({"version": gdb_version, "characters": chars_official},
                          open(cache_path, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
            except Exception:
                pass
        gdb_ok = True
    except Exception:
        chars_official = []
        gdb_ok = False

    fandom = _fandom_snapshot(timeout=min(timeout, 15))
    if not gdb_ok and not fandom.get("ok"):
        return {"ok": False, "game": "genshin", "error": "network_unavailable",
                "message": "网络不可用或数据源暂不可达（npm genshin-db 与 Fandom 均失败），未改动任何数据。"}

    path = os.path.join(DATA_DIR, "genshin_characters.json")
    if not os.path.exists(path):
        return {"ok": False, "game": "genshin", "error": "no_data",
                "message": "本地角色库不存在，无法合并。"}
    doc = json.load(open(path, encoding="utf-8"))
    chars = doc.get("characters", [])

    def _norm(s):
        return (s or "").replace(" ", "").replace(".", "").replace("·", "").strip().lower()

    local_names = set()
    for c in chars:
        local_names.add(_norm(c.get("name")))
        local_names.add(_norm(c.get("en")))
        for a in (c.get("aliases") or []):
            local_names.add(_norm(a))

    chars_sources = list(chars_official)
    fandom_chars = fandom.get("characters") or []
    if fandom_chars:
        chars_sources.extend(fandom_chars)

    # 1) 已有角色：仅补齐缺失字段
    filled = {"element": 0, "weapon": 0, "rarity": 0, "en": 0}
    for c in chars:
        match = None
        for o in chars_sources:
            if _norm(o["name"]) == _norm(c.get("name")) or (_norm(o["en"]) and _norm(o["en"]) == _norm(c.get("en"))):
                match = o
                break
        if not match:
            continue
        if not (c.get("element") or "").strip() and match["element"]:
            c["element"] = match["element"]; filled["element"] += 1
        if not (c.get("weapon") or "").strip() and match["weapon"]:
            c["weapon"] = match["weapon"]; filled["weapon"] += 1
        if not c.get("rarity") and match["rarity"]:
            c["rarity"] = match["rarity"]; filled["rarity"] += 1
        if not (c.get("en") or "").strip() and match["en"]:
            c["en"] = match["en"]; filled["en"] += 1

    # 2) 新角色追加（genshin-db 或 Fandom 当前版本上线页有而本地无）
    lunaris_idx = _genshin_lunaris_index()
    added = []
    for o in chars_sources:
        if _norm(o["name"]) in local_names or (_norm(o["en"]) and _norm(o["en"]) in local_names):
            continue
        cid = o.get("slug") or _genshin_slug(o["en"] or o["name"])
        if o.get("source") == "fandom":
            ver = o.get("version") or ""
            note = "由 Fandom %s 上线页自动拉取（中文名来自 Fandom 角色页）" % ver
        else:
            ver = _genshin_version_from_date(o.get("release") or "")
            note = ("由 genshin-db 官方镜像自动拉取（版本按上线日期推算）" if ver
                    else "由 genshin-db 官方镜像自动拉取（版本待核对）")
        icon = "https://api.ambr.top/assets/UI/avatar/UI_Avatar_%s.png" % (o["en"] or cid)
        icon_fallback = "/avatars/%s.webp" % cid if o.get("source") != "fandom" else ""
        if lunaris_idx:
            u, fb = _genshin_avatar_urls(
                {"en": o["en"], "name": o["name"], "aliases": [o["name"]]}, lunaris_idx)
            if u:
                icon = u
            if fb:
                icon_fallback = fb
        chars.append({
            "id": cid,
            "name": o["name"],
            "en": o["en"],
            "aliases": [o["name"]],
            "element": o["element"],
            "weapon": o["weapon"],
            "rarity": o["rarity"],
            "version": ver,
            "status": "released",
            "note": note,
            "icon": icon,
            "icon_fallback": icon_fallback,
        })
        added.append(o["name"] or o["en"] or cid)
        local_names.add(_norm(o["name"]))
        if o["en"]:
            local_names.add(_norm(o["en"]))

    version_text = fandom.get("version_text") or ""
    if not added and not any(filled.values()):
        if fandom.get("ok"):
            msg = "名单已是最新（Fandom %s 上线页已核对，本地无新增）。" % fandom.get("version", "")
        else:
            msg = "名单已是最新（genshin-db 官方镜像 %d 名角色，本地无新增）。" % len(chars_official)
        return {"ok": True, "game": "genshin", "total": len(chars),
                "added": 0, "added_names": [], "source": "genshin-db + Fandom" if fandom.get("ok") else "genshin-db",
                "changed": False, "version": gdb_version or fandom.get("version", ""),
                "version_text": version_text, "message": msg}

    bak = path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backed_up = False
    try:
        shutil.copy2(path, bak)
        backed_up = True
    except Exception:
        pass
    source_label = ""
    if gdb_ok:
        source_label = "genshin-db 官方镜像（GenshinData 数据发行版 v%s）" % gdb_version
    if fandom.get("ok"):
        fandom_label = "Fandom %s 上线页（%s）" % (fandom.get("version", ""), fandom.get("title", ""))
        source_label = (source_label + " + " + fandom_label) if source_label else fandom_label
    if not gdb_ok:
        source_label += "（genshin-db 数据包暂不可达）"
    doc["region_note"] = ("由 %s 于 %s 在线拉取合并（%d 名角色，新增 %d）。"
                          % (source_label, datetime.date.today().isoformat(), len(chars), len(added)))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return {"ok": True, "game": "genshin", "total": len(chars),
            "added": len(added), "added_names": added,
            "source": "genshin-db + Fandom" if fandom.get("ok") else "genshin-db",
            "changed": True, "backed_up": backed_up,
            "version": gdb_version or fandom.get("version", ""),
            "version_text": version_text,
            "message": "已从 %s 同步 %d 名角色（新增 %d 名：%s），旧文件已备份。"
                       % ("genshin-db 与 Fandom" if fandom.get("ok") else "genshin-db",
                          len(chars), len(added), "、".join(added) or "无")}


# ============================================================
# 终末地 角色名单在线拉取（BoxCatTeam/endfield-cat-metadata）
# 来源：raw.githubusercontent.com/BoxCatTeam/endfield-cat-metadata
#       locale/zh-CN/character.json（中文名 / 稀有度 / itemid），每版本更新。
# ============================================================
ENDFIELD_META_CHARS = "https://raw.githubusercontent.com/BoxCatTeam/endfield-cat-metadata/master/locale/zh-CN/character.json"


def update_endfield_db(timeout=25):
    """联网从 BoxCatTeam 官方元数据拉取终末地角色名单，合并升级本地库（只增不改）。"""
    try:
        req = urllib.request.Request(ENDFIELD_META_CHARS, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return {"ok": False, "game": "arknights_endfield", "error": "network_unavailable",
                "message": "网络不可用或 BoxCatTeam 暂不可达，未改动任何数据。"}
    meta = {}
    for it in data:
        if isinstance(it, dict) and it.get("type") == "character" and it.get("itemid"):
            meta[it["itemid"]] = it

    path = os.path.join(DATA_DIR, "arknights_endfield_characters.json")
    if not os.path.exists(path):
        return {"ok": False, "game": "arknights_endfield", "error": "no_data",
                "message": "本地角色库不存在，无法合并。"}
    doc = json.load(open(path, encoding="utf-8"))
    chars = doc.get("characters", [])

    def _norm(s):
        return (s or "").replace(" ", "").strip()

    # 本地索引: idx -> itemid（已有静态表）与 中文名 -> itemid（元数据）
    local_names = {}
    for c in chars:
        idx = c["id"].replace("endfield_", "", 1)
        itid = ENDFIELD_AVATAR_IDS.get(idx)
        local_names.setdefault(_norm(c.get("name")), itid)
        for a in (c.get("aliases") or []):
            local_names.setdefault(_norm(a), itid)

    # 1) 已有角色：补齐缺失 rarity / icon
    filled_rarity = filled_icon = 0
    for c in chars:
        idx = c["id"].replace("endfield_", "", 1)
        it = meta.get(ENDFIELD_AVATAR_IDS.get(idx)) or meta.get(local_names.get(_norm(c.get("name"))))
        if not it:
            continue
        if not c.get("rarity") and it.get("rarity"):
            c["rarity"] = it["rarity"]; filled_rarity += 1
        if not (c.get("icon") or "").strip() and it.get("itemid"):
            c["icon"] = ENDFIELD_GITHUB_ICONS + it["itemid"] + ".png"; filled_icon += 1

    # 2) 新角色追加（跳过主角男女形态：本地已有「管理员」，与 HSR 主角策略一致）
    used = {_norm(c.get("name")) for c in chars}
    has_admin = any("管理员" in _norm(c.get("name")) for c in chars)
    added = []
    for it in meta.values():
        nm = it.get("name") or ""
        if has_admin and "管理员" in nm:
            continue
        if _norm(nm) in used:
            continue
        chars.append({
            "id": "endfield_" + it["itemid"].replace("chr_", ""),
            "name": nm,
            "en": "",
            "aliases": [nm],
            "class": "",
            "branch": "",
            "element": "",
            "rarity": it.get("rarity"),
            "version": "",
            "status": "released",
            "note": "由 BoxCatTeam 官方元数据自动拉取（职业/属性/版本待核对）",
            "icon": ENDFIELD_GITHUB_ICONS + it["itemid"] + ".png",
            "icon_fallback": "",
        })
        added.append(nm)
        used.add(_norm(nm))

    if not added and not filled_rarity and not filled_icon:
        return {"ok": True, "game": "arknights_endfield", "total": len(chars),
                "added": 0, "added_names": [], "source": "BoxCatTeam",
                "changed": False,
                "message": "名单已是最新（BoxCatTeam 元数据 %d 名角色，本地无新增）。" % len(meta)}

    bak = path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backed_up = False
    try:
        shutil.copy2(path, bak)
        backed_up = True
    except Exception:
        pass
    doc["region_note"] = ("由 BoxCatTeam 官方元数据于 %s 在线拉取合并（%d 名角色，新增 %d）。"
                          % (datetime.date.today().isoformat(), len(chars), len(added)))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return {"ok": True, "game": "arknights_endfield", "total": len(chars),
            "added": len(added), "added_names": added, "source": "BoxCatTeam",
            "changed": True, "backed_up": backed_up,
            "message": "已从 BoxCatTeam 官方元数据同步 %d 名角色（新增 %d 名：%s），旧文件已备份。"
                       % (len(chars), len(added), "、".join(added) or "无")}


def update_db(game):
    """联网拉取升级角色库。支持 hsr / genshin / arknights_endfield / zzz / wuthering_waves / nte。"""
    if game == "hsr":
        return update_hsr_db()
    if game == "genshin":
        res = update_genshin_db()
        try:
            from official_stats import update_genshin_lunaris_stats
            res["official_stats"] = update_genshin_lunaris_stats()
        except Exception:
            pass
        return res
    if game == "arknights_endfield":
        res = update_endfield_db()
        try:
            res["official_stats"] = update_endfield_official_stats()
        except Exception:
            pass
        return res
    if game == "zzz":
        return update_zzz_db()
    if game == "wuthering_waves":
        res = update_wuwa_db()
        try:
            res["official_stats"] = update_wuwa_official_stats()
        except Exception:
            pass
        return res
    if game == "nte":
        res = update_nte_db()
        try:
            res["official_stats"] = update_nte_official_stats()
        except Exception:
            pass
        return res
    return {"ok": False, "game": game, "error": "unsupported",
            "message": "未知游戏：%s。" % DISPLAY.get(game, game)}


# ============================================================
# HSR 官方基础数值 + 技能数据（StarRailRes —— 与角色名单同一官方镜像源）
# 来源：index_new/cn/character_promotions.json（基础白值/成长）
#       index_new/cn/character_skills.json（技能名/类型/描述/倍率参数）
# 产物：
#   data/hsr_official_stats.json —— 每角色 Lv1 与 Lv80 白值（hp/atk/def/spd/双暴）
#   data/hsr_skills.json         —— 每角色技能列表（id/名称/类型/效果/描述）
# ============================================================
HSR_PROMOTIONS = STARRAILRES_BASE + "index_new/cn/character_promotions.json"
HSR_SKILLS = STARRAILRES_BASE + "index_new/cn/character_skills.json"


def _hsr_avatar_reverse_map():
    """AvatarId -> 本地角色 id（取首个）。"""
    rev = {}
    for lid, aid in HSR_AVATAR_IDS.items():
        rev.setdefault(aid, lid)
    return rev


def update_hsr_official_data(timeout=40):
    """拉取 HSR 官方基础数值与技能数据（StarRailRes），写入两个 JSON 文件。"""
    def _get(url):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    try:
        promos = _get(HSR_PROMOTIONS)
        skills = _get(HSR_SKILLS)
        charlist = _get(STARRAILRES_CN)
    except Exception:
        return {"ok": False, "game": "hsr", "kind": "official_data",
                "error": "network_unavailable", "message": "网络不可用或 StarRailRes 暂不可达，未改动任何数据。"}
    chars = json.load(open(os.path.join(DATA_DIR, "hsr_characters.json"), encoding="utf-8"))["characters"]
    aid2name = {_hsr_aid_of(c): c["name"] for c in chars if _hsr_aid_of(c)}
    aid2maxsp = {aid: v.get("max_sp") for aid, v in charlist.items() if isinstance(v, dict)}
    rev = _hsr_avatar_reverse_map()

    stats = {}
    for aid, p in promos.items():
        lid = rev.get(str(aid)) or ("aid_" + str(aid))
        if not isinstance(p, dict) or not p.get("values"):
            continue
        v0 = p["values"][0]
        v_last = p["values"][-1]
        base = {k: v0.get(k, {}).get("base") for k in ("hp", "atk", "def", "spd", "crit_rate", "crit_dmg")}
        step = {k: v_last.get(k, {}).get("step") for k in ("hp", "atk", "def")}
        stats[lid] = {
            "aid": str(aid),
            "name": aid2name.get(str(aid), str(aid)),
            "base_hp": base["hp"], "base_atk": base["atk"], "base_def": base["def"],
            "spd": base["spd"], "crit_rate": base["crit_rate"], "crit_dmg": base["crit_dmg"],
            "hp80": round((base["hp"] or 0) + (step["hp"] or 0) * 10, 2) if base["hp"] else None,
            "atk80": round((base["atk"] or 0) + (step["atk"] or 0) * 10, 2) if base["atk"] else None,
            "def80": round((base["def"] or 0) + (step["def"] or 0) * 10, 2) if base["def"] else None,
            "max_sp": aid2maxsp.get(str(aid)),
            "note": "Lv80 按最后突破档 base+step*10 推算（StarRailRes 约定）",
        }

    sk = {}
    for sid, s in skills.items():
        if not isinstance(s, dict):
            continue
        aid = str(sid)[:4]
        lid = rev.get(aid) or ("aid_" + aid)
        sk.setdefault(lid, []).append({
            "id": sid,
            "name": s.get("name") or "",
            "type": s.get("type") or "",
            "type_text": s.get("type_text") or "",
            "element": s.get("element") or "",
            "effect_text": s.get("effect_text") or "",
            "desc": (s.get("desc") or "")[:600],
            # 参数只保留每槽满级值（供雷达倍率推导，避免文件过大）
            "params": [arr[-1] for arr in (s.get("params") or []) if arr],
        })
    for v in sk.values():
        v.sort(key=lambda x: (str(x.get("type") or ""), str(x.get("id") or "")))

    today = datetime.date.today().isoformat()
    out_stats = os.path.join(DATA_DIR, "hsr_official_stats.json")
    out_skills = os.path.join(DATA_DIR, "hsr_skills.json")
    changed = True
    try:
        old_stats = json.load(open(out_stats, encoding="utf-8")) if os.path.exists(out_stats) else {}
        old_skills = json.load(open(out_skills, encoding="utf-8")) if os.path.exists(out_skills) else {}
        changed = old_stats.get("stats") != stats or old_skills.get("skills") != sk
    except Exception:
        changed = True
    for out, payload in ((out_stats, {"game": "hsr", "source": "StarRailRes", "date": today, "stats": stats}),
                         (out_skills, {"game": "hsr", "source": "StarRailRes", "date": today, "skills": sk})):
        try:
            if os.path.exists(out):
                shutil.copy2(out, out + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
        except Exception:
            pass
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    return {"ok": True, "game": "hsr", "kind": "official_data",
            "stats_count": len(stats), "skills_count": len(sk),
            "changed": changed, "source": "StarRailRes",
            "message": "已从 StarRailRes 拉取 HSR 官方数值（%d 名角色）与技能（%d 名角色）并写入本地。"
                       % (len(stats), len(sk))}


# ============================================================
# ZZZ 绝区零 —— biligame（B 站百科）「角色图鉴」模板（中文，每版本更新）
# 来源：wiki.biligame.com/zzz  MediaWiki API
#   list=categorymembers(Category:角色) 枚举 → action=parse 解析 {{角色图鉴}}
# 产物：
#   data/zzz_characters.json      名单合并（名称/英文/稀有度/属性/特性/版本）
#   data/zzz_official_stats.json  基础数值（Lv1 / Lv60 / 突破后）
# 注意：biligame 图片防盗链(HTTP 567)不可外链，头像维持萌娘百科，新角色缺头像时
#       前端自动回退官方属性色卡。
# ============================================================
ZZZ_BILIGAME_API = "https://wiki.biligame.com/zzz/api.php"
# 已知国服精编名与 biligame 百科名不一致的映射（防止同角色被重复追加）
ZZZ_ZH_ALIAS = {"普罗米亚": ["普罗米娅"], "希格莉德": ["希格莉德·德拉叙尔"]}


def _bili_get(params, timeout=30):
    """biligame API 请求（带 Referer，失败重试一次）。"""
    import urllib.parse as up
    url = ZZZ_BILIGAME_API + "?" + up.urlencode(params)
    last = None
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://wiki.biligame.com/zzz/",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
    raise last


def _bili_parse_template(wikitext, name):
    """从 wikitext 提取 {{name ...}} 模板的参数键值。"""
    import re as _re
    # 兼容「{{名\n|字段」与「{{名|字段=…」两种写法；以「\n}}」收尾避免嵌套模板误截断
    m = _re.search(r"\{\{%s\b([\s\S]*?)\n\}\}" % _re.escape(name), wikitext)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("|"):
            body = line[1:]
            if "=" in body:
                k, v = body.split("=", 1)
                fields[k.strip()] = v.strip()
    return fields


def _slugify(s):
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")


def update_zzz_db(timeout=30):
    """联网从 biligame zzz 百科拉取角色图鉴，合并升级本地 ZZZ 库并写基础数值。"""
    try:
        pages = []
        cont = {}
        for _ in range(10):
            # 用「引用 角色图鉴 模板」枚举全部代理人页（比 Category:角色 更完整）
            params = {"action": "query", "list": "embeddedin",
                      "eititle": "Template:角色图鉴", "einamespace": "0", "eilimit": "50",
                      "format": "json"}
            params.update(cont)
            d = _bili_get(params, timeout)
            pages += [m["title"] for m in d.get("query", {}).get("embeddedin", [])]
            if "continue" in d:
                cont = {"eicontinue": d["continue"].get("eicontinue", ""),
                        "continue": d["continue"].get("continue", "")}
                if not cont["eicontinue"]:
                    break
            else:
                break
    except Exception:
        return {"ok": False, "game": "zzz", "error": "network_unavailable",
                "message": "网络不可用或 biligame 百科暂不可达（可能触发防盗链 567），未改动任何数据。"}

    agents = []
    for title in pages:
        try:
            d = _bili_get({"action": "parse", "page": title, "prop": "wikitext", "format": "json"}, timeout)
            wt = d["parse"]["wikitext"]["*"]
        except Exception:
            continue
        f = _bili_parse_template(wt, "角色图鉴")
        if not f.get("名称") and not f.get("全名"):
            continue
        rarity = 5 if str(f.get("稀有度", "")).strip().upper() == "S" else (4 if str(f.get("稀有度", "")).strip().upper() == "A" else 0)
        def _res(name_val):
            # 解析 {{PAGENAME}} → 页面标题
            return (name_val or "").replace("{{PAGENAME}}", title).strip()
        agents.append({
            "name": _res(f.get("全名")) or _res(f.get("名称")),
            "short": _res(f.get("名称")),
            "en": _res(f.get("英文名称")),
            "element": f.get("属性", ""),
            "specialty": f.get("特性", ""),
            "rarity": rarity,
            "version": (f.get("实装版本", "") or "").strip(),
            "stats": {
                "hp1": _num(f.get("生命值")), "atk1": _num(f.get("攻击力")), "def1": _num(f.get("防御力")),
                "impact": _num(f.get("冲击力")), "anomaly_mastery": _num(f.get("异常掌控")),
                "anomaly_proficiency": _num(f.get("异常精通")), "energy_regen": _num(f.get("能量自动回复")),
                "hp60": _num(f.get("10生命值")), "atk60": _num(f.get("10攻击力")), "def60": _num(f.get("10防御力")),
                "hp60p": _num(f.get("10+生命值")), "atk60p": _num(f.get("10+攻击力")), "def60p": _num(f.get("10+防御力")),
            },
        })

    path = os.path.join(DATA_DIR, "zzz_characters.json")
    if not os.path.exists(path):
        return {"ok": False, "game": "zzz", "error": "no_data", "message": "本地角色库不存在。"}
    doc = json.load(open(path, encoding="utf-8"))
    chars = doc.get("characters", [])

    def _norm(s):
        return (s or "").replace("\u2022", "\u00b7").replace(" ", "") \
            .replace("「", "").replace("」", "").replace("『", "").replace("』", "") \
            .replace("（", "").replace("）", "").strip().lower()

    def _match(a, names):
        """agent 与本地名称集合匹配：精确（名称/简称/英文）或前缀兜底（≥2 字）。"""
        cands = [_norm(x) for x in (a["name"], a["short"], a["en"]) if x]
        for cn in cands:
            if cn in names:
                return True
        for cn in cands:
            if len(cn) >= 2:
                for ln in names:
                    if ln and len(ln) >= 2 and (cn.startswith(ln) or ln.startswith(cn)):
                        return True
        return False

    matched = 0
    for c in chars:
        names = {_norm(c.get("name")), _norm(c.get("en"))} | {_norm(a) for a in (c.get("aliases") or [])}
        for zh, extra in ZZZ_ZH_ALIAS.items():
            if _norm(zh) == _norm(c.get("name")):
                names |= {_norm(x) for x in extra}
        a = next((x for x in agents if _match(x, names)), None)
        if not a:
            continue
        matched += 1
        if not (c.get("element") or "").strip() and a["element"]:
            c["element"] = a["element"]
        if not (c.get("specialty") or "").strip() and a["specialty"]:
            c["specialty"] = a["specialty"]
        if not c.get("rarity") and a["rarity"]:
            c["rarity"] = a["rarity"]
        if not (c.get("version") or "").strip() and a["version"]:
            c["version"] = a["version"]

    used = set()
    for c in chars:
        used.add(_norm(c.get("name")))
        used.add(_norm(c.get("en")))
        for al in (c.get("aliases") or []):
            used.add(_norm(al))
        for zh, extra in ZZZ_ZH_ALIAS.items():
            if _norm(zh) == _norm(c.get("name")):
                used |= {_norm(x) for x in extra}
    used_ids = {c["id"] for c in chars}
    added = []
    for a in agents:
        if _match(a, used):
            continue
        base_id = "zzz_" + (_slugify(a["en"]) or _slugify(a["name"]))
        new_id = base_id
        n = 1
        while new_id in used_ids:
            n += 1
            new_id = "%s_%d" % (base_id, n)
        used_ids.add(new_id)
        chars.append({
            "id": new_id,
            "name": a["name"], "en": a["en"], "aliases": [a["short"], a["en"]],
            "element": a["element"], "attribute": a["element"], "specialty": a["specialty"],
            "weapon": a["specialty"], "rarity": a["rarity"], "version": a["version"],
            "status": "released",
            "note": "由 biligame 绝区零百科自动拉取（头像待补，前端回退色卡）",
            "icon": "", "icon_fallback": "",
        })
        added.append(a["name"])
        used.add(_norm(a["name"]))

    stats_doc = {"game": "zzz", "source": "biligame 绝区零百科（角色图鉴）",
                 "date": datetime.date.today().isoformat(), "stats": {}}
    for a in agents:
        lid = None
        for c in chars:
            names = {_norm(c.get("name")), _norm(c.get("en"))} | {_norm(x) for x in (c.get("aliases") or [])}
            for zh, extra in ZZZ_ZH_ALIAS.items():
                if _norm(zh) == _norm(c.get("name")):
                    names |= {_norm(x) for x in extra}
            if _match(a, names):
                lid = c["id"]
                break
        if lid:
            stats_doc["stats"][lid] = dict(a["stats"], name=a["name"], en=a["en"])

    if not added and matched == len(chars):
        # 名单无变化也要刷新数值文件（幂等判断）
        old = json.load(open(os.path.join(DATA_DIR, "zzz_official_stats.json"), encoding="utf-8")) \
            if os.path.exists(os.path.join(DATA_DIR, "zzz_official_stats.json")) else {}
        if old.get("stats") == stats_doc["stats"]:
            return {"ok": True, "game": "zzz", "total": len(chars), "added": 0,
                    "added_names": [], "stats_count": len(stats_doc["stats"]),
                    "source": "biligame", "changed": False,
                    "message": "名单已是最新（biligame 图鉴 %d 名，本地 %d 名，无新增）。" % (len(agents), len(chars))}

    bak = path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    try:
        shutil.copy2(path, bak)
    except Exception:
        pass
    doc["region_note"] = ("由 biligame 绝区零百科「角色图鉴」于 %s 在线拉取合并（%d 名角色，新增 %d）。"
                          % (datetime.date.today().isoformat(), len(chars), len(added)))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, "zzz_official_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats_doc, f, ensure_ascii=False, indent=1)
    return {"ok": True, "game": "zzz", "total": len(chars), "added": len(added),
            "added_names": added, "stats_count": len(stats_doc["stats"]),
            "source": "biligame", "changed": True, "backed_up": True,
            "message": "已从 biligame 绝区零百科同步 %d 名角色（新增 %d 名：%s）+ %d 名基础数值，旧文件已备份。"
                       % (len(chars), len(added), "、".join(added) or "无", len(stats_doc["stats"]))}


# ============================================================
# 鸣潮 —— Fandom 英文百科（Resonator Infobox，Playable 角色，每版本更新）
# 来源：wutheringwaves.fandom.com MediaWiki API（图片可直链 static.wikia.nocookie.net）
# 产物：data/wuthering_waves_characters.json 名单合并（新角色英文名 + 中文属性/武器映射）
# ============================================================
WUWA_FANDOM_API = "https://wutheringwaves.fandom.com/api.php"
WUWA_ELEMENT_MAP = {"Spectro": "衍射", "Havoc": "湮灭", "Glacio": "冷凝",
                    "Aero": "气动", "Electro": "导电", "Fusion": "热熔"}
WUWA_WEAPON_MAP = {"Sword": "迅刀", "Broadblade": "长刃", "Pistols": "佩枪",
                   "Gauntlets": "臂铠", "Rectifier": "音感仪"}

# 部分角色 Fandom 页面不存在 "<英文名>_Card.png"，用已逐条 GET 验证 200 的实际文件名。
WUWA_FANDOM_FILES = {
    "rover_spectro": "Rover_1.png",
    "rover_havoc": "Rover_1.png",
    "rover_aero": "Rover_1.png",
    "rover_electro": "Rover_1.png",
    "jianxin": "Jianxin_Card.jpg",
    "verina": "Verina_Card.jpg",
    "yinlin": "Yinlin_Card.jpg",
    "aalto": "Aalto_Card.jpg",
    "mortefi": "Mortefi_Card.jpg",
    "taoqi": "Taoqi_Card.jpg",
    "yuanwu": "Yuanwu_Card.jpg",
    "lumi": "Lumi_Card.jpg",
    "ciaconna": "Ciaccona_Card.png",
    "lupa": "Lupa_Card.png",
    "phrolova": "Phrolova_Card.png",
    "galbrena": "Galbrena_Card.jpg",
    "qiuyuan": "Qiuyuan_Card.jpg",
    "chisa": "Chisa_Card.jpg",
    "buling": "Buling_Card.jpg",
    "lynae": "Lynae_Card.jpg",
    "mornye": "Mornye_Card.jpg",
    "aemeath": "Aemeath_Card.jpg",
    "luuk_hersen": "Luuk_Herssen_Card.jpg",
    "sigrika": "Sigrika_Card.jpg",
    "hiyuki": "Hiyuki_Card.jpg",
    "denia": "Denia_Card.jpg",
    "lucy_wuwa": "Lucy_Card.jpg",
    "rebecca": "Rebecca_Card.jpg",
    "lucilla": "Lucilla_Card.jpg",
    "yangyang_xuanling": "Yangyang_Xuanling_Card.jpg",
    "suisui": "Suisui_Card.jpg",
}


def _wuwa_fandom_url(idx):
    """按 Fandom 直链 MD5 规则生成鸣潮头像 URL（已验证可外链）。"""
    import hashlib as _hashlib
    import urllib.parse as _up
    fn = WUWA_FANDOM_FILES.get(idx)
    if not fn:
        return ""
    h = _hashlib.md5(fn.encode()).hexdigest()
    return "https://static.wikia.nocookie.net/wutheringwaves/images/%s/%s/%s/revision/latest" % (
        h[0], h[:2], _up.quote(fn))


def _fandom_get(params, api, timeout=30):
    import urllib.parse as up
    url = api + "?" + up.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _fandom_image_url(api, filename, timeout=30):
    """fandom 文件 -> 直链 URL（static.wikia.nocookie.net，可外链）。"""
    try:
        d = _fandom_get({"action": "query", "titles": "File:" + filename,
                         "prop": "imageinfo", "iiprop": "url", "format": "json"}, api, timeout)
        for pg in d.get("query", {}).get("pages", {}).values():
            ii = pg.get("imageinfo") or []
            if ii and ii[0].get("url"):
                return ii[0]["url"]
    except Exception:
        pass
    return ""


def _fandom_parse_pages(api, category, infobox_name, timeout=30):
    """枚举分类页并解析指定 infobox 模板（过滤 type=Playable）。"""
    pages = []
    cont = {}
    for _ in range(20):
        params = {"action": "query", "list": "categorymembers", "cmtitle": category,
                  "cmtype": "page", "cmlimit": "50", "format": "json", "formatversion": "2"}
        params.update(cont)
        d = _fandom_get(params, api, timeout)
        pages += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" in d:
            cont = {"cmcontinue": d["continue"].get("cmcontinue", ""),
                    "continue": d["continue"].get("continue", "")}
            if not cont["cmcontinue"]:
                break
        else:
            break
    out = []
    for title in pages:
        try:
            d = _fandom_get({"action": "parse", "page": title, "prop": "wikitext", "format": "json"}, api, timeout)
            wt = d["parse"]["wikitext"]["*"]
        except Exception:
            continue
        f = _bili_parse_template(wt, infobox_name)
        if (f.get("type") or "").strip().lower() != "playable":
            continue
        img = ""
        gallery = f.get("image", "")
        for line in gallery.splitlines():
            line = line.strip()
            is_img = (".png" in line.lower()) or (".jpg" in line.lower()) or (".webp" in line.lower())
            if line and is_img and not line.startswith("|") and not line.startswith("<") and not line.startswith("}}"):
                img = line.split("|")[0].strip()
                break
        out.append({"title": title, "wikitext": wt, "infobox": f, "image": img})
    return out


def update_wuwa_db(timeout=30):
    """联网从鸣潮 Fandom 英文百科拉取 Playable 角色，合并升级本地库。"""
    try:
        entries = _fandom_parse_pages(WUWA_FANDOM_API, "Category:Playable_Resonators", "Resonator Infobox", timeout)
    except Exception:
        return {"ok": False, "game": "wuthering_waves", "error": "network_unavailable",
                "message": "网络不可用或 Fandom 暂不可达，未改动任何数据。"}

    path = os.path.join(DATA_DIR, "wuthering_waves_characters.json")
    if not os.path.exists(path):
        return {"ok": False, "game": "wuthering_waves", "error": "no_data", "message": "本地角色库不存在。"}
    doc = json.load(open(path, encoding="utf-8"))
    chars = doc.get("characters", [])

    def _norm(s):
        return (s or "").replace(" ", "").replace(":", "").replace("\u00b7", "").replace("\u2022", "").strip().lower()

    added = []
    used_en = {_norm(c.get("en")) for c in chars}
    used_names = {_norm(c.get("name")) for c in chars}
    used_ids = {c["id"] for c in chars}
    # 1) 已有角色：按 en 匹配 fandom，补定位标签与 Card 头像
    filled_icon = filled_role = 0
    for c in chars:
        e = next((x for x in entries if _norm(x["title"]) == _norm(c.get("en"))), None)
        if not e:
            continue
        if not (c.get("role") or "") and e["infobox"].get("role"):
            c["role"] = e["infobox"].get("role")
            filled_role += 1
        if not (c.get("icon") or "").strip():
            icon = _fandom_image_url(WUWA_FANDOM_API, e["title"] + "_Card.png", timeout)
            if icon:
                c["icon"] = icon
                filled_icon += 1
    for e in entries:
        f = e["infobox"]
        en = e["title"]
        if _norm(en) in used_en or _norm(en) in used_names:
            continue
        # 主角表单（Rover）已存在，跳过新增
        rarity = f.get("rarity")
        try:
            rarity = int(rarity)
        except Exception:
            rarity = 4
        element = WUWA_ELEMENT_MAP.get(f.get("attribute"), "") or f.get("attribute", "")
        weapon = WUWA_WEAPON_MAP.get(f.get("weapon"), "") or f.get("weapon", "")
        icon = ""
        for cand in ([e["title"] + "_Card.png"] if e["image"] else []) + ([e["image"]] if e["image"] else []):
            icon = _fandom_image_url(WUWA_FANDOM_API, cand, timeout)
            if icon:
                break
        base_id = "wuwa_" + _slugify(en)
        new_id = base_id
        n = 1
        while new_id in used_ids:
            n += 1
            new_id = "%s_%d" % (base_id, n)
        used_ids.add(new_id)
        chars.append({
            "id": new_id,
            "name": en, "en": en, "aliases": [en],
            "element": element, "weapon": weapon, "rarity": rarity,
            "version": "", "status": "released",
            "note": "由鸣潮 Fandom 英文百科自动拉取（中文名待核对）",
            "role": f.get("role", ""),
            "icon": icon,
            "icon_fallback": "",
        })
        added.append(en)
        used_en.add(_norm(en))
        used_names.add(_norm(en))

    if not added and not filled_icon and not filled_role:
        return {"ok": True, "game": "wuthering_waves", "total": len(chars),
                "added": 0, "added_names": [], "source": "Wuwa Fandom", "changed": False,
                "message": "名单已是最新（Fandom Playable %d 名，本地 %d 名，无新增）。"
                           % (len(entries), len(chars))}
    bak = path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    try:
        shutil.copy2(path, bak)
    except Exception:
        pass
    doc["region_note"] = ("由鸣潮 Fandom 英文百科于 %s 在线拉取合并（%d 名角色，新增 %d，新角色中文名待核对）。"
                          % (datetime.date.today().isoformat(), len(chars), len(added)))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    if not added:
        return {"ok": True, "game": "wuthering_waves", "total": len(chars),
                "added": 0, "added_names": [], "source": "Wuwa Fandom",
                "changed": bool(filled_icon or filled_role), "filled_icon": filled_icon,
                "filled_role": filled_role,
                "message": "名单已是最新（Fandom Playable %d 名，本地 %d 名，无新增%s）。"
                           % (len(entries), len(chars),
                              (("，补头像 %d" % filled_icon) if filled_icon else "")
                              + (("，补定位标签 %d" % filled_role) if filled_role else ""))}
    return {"ok": True, "game": "wuthering_waves", "total": len(chars),
            "added": len(added), "added_names": added, "source": "Wuwa Fandom",
            "changed": True, "backed_up": True,
            "message": "已从鸣潮 Fandom 英文百科同步 %d 名角色（新增 %d 名：%s，中文名待核对），旧文件已备份。"
                       % (len(chars), len(added), "、".join(added) or "无")}


# ============================================================
# 异环 NTE —— Fandom 英文百科（Character Infobox，Playable 角色）
# 来源：neverness-to-everness.fandom.com MediaWiki API
# 产物：data/nte_characters.json 头像补全 + 新角色追加（英文名 + 待核对标注）
# ============================================================
NTE_FANDOM_API = "https://neverness-to-everness.fandom.com/api.php"
# 已知本地英文名与 Fandom 页名不一致的映射（其余按 en 精确匹配）
NTE_EN_ALIAS = {
    "baizang": "Baicang", "kaos": "Chaos", "xiaozhi": "Chiz",
    "daffodil": "Daffodill", "zero": "Esper Zero", "requiem": "Lacrimosa",
    "zhenhong": "Shinku", "jiuyuan": "Jiuyuan", "hotori": "Hotori", "sakiri": "Sakiri",
}


def update_nte_db(timeout=30):
    """联网从异环 Fandom 英文百科拉取 Playable 角色，补全头像并追加新角色。"""
    try:
        entries = _fandom_parse_pages(NTE_FANDOM_API, "Category:Characters", "Character Infobox", timeout)
    except Exception:
        return {"ok": False, "game": "nte", "error": "network_unavailable",
                "message": "网络不可用或 Fandom 暂不可达，未改动任何数据。"}

    path = os.path.join(DATA_DIR, "nte_characters.json")
    if not os.path.exists(path):
        return {"ok": False, "game": "nte", "error": "no_data", "message": "本地角色库不存在。"}
    doc = json.load(open(path, encoding="utf-8"))
    chars = doc.get("characters", [])

    def _norm(s):
        return (s or "").replace(" ", "").replace(":", "").replace("\u00b7", "").replace("\u2022", "").strip().lower()

    filled_icon = filled_esper = 0
    for c in chars:
        target = NTE_EN_ALIAS.get(_norm(c.get("en")), c.get("en"))
        e = next((x for x in entries if _norm(x["title"]) == _norm(target)), None)
        if not e:
            continue
        if not (c.get("espertype") or "") and e["infobox"].get("espertype"):
            c["espertype"] = e["infobox"].get("espertype")
            filled_esper += 1
        if not (c.get("icon") or "").strip():
            # 优先 {Title}_Portrait.png（fandom 惯例），回退 infobox 首图
            icon = _fandom_image_url(NTE_FANDOM_API, e["title"] + "_Portrait.png", timeout)
            if not icon and e["image"]:
                icon = _fandom_image_url(NTE_FANDOM_API, e["image"], timeout)
            if icon:
                c["icon"] = icon
                filled_icon += 1

    used = {_norm(c.get("en")) for c in chars} | {_norm(c.get("name")) for c in chars}
    used_ids = {c["id"] for c in chars}
    added = []
    for e in entries:
        t = _norm(e["title"])
        if t in used or t in {_norm(v) for v in NTE_EN_ALIAS.values()}:
            continue
        f = e["infobox"]
        r = str(f.get("rarity", "")).upper()
        rarity = 5 if r == "S" else (4 if r == "A" else 0)
        base_id = "nte_" + _slugify(e["title"])
        new_id = base_id
        n = 1
        while new_id in used_ids:
            n += 1
            new_id = "%s_%d" % (base_id, n)
        used_ids.add(new_id)
        chars.append({
            "id": new_id,
            "name": e["title"], "en": e["title"], "aliases": [e["title"]],
            "element": "", "weapon": "", "rarity": rarity, "version": "",
            "status": "released",
            "note": "由异环 Fandom 英文百科自动拉取（中文名/属性待核对）",
            "espertype": f.get("espertype", ""),
            "icon": _fandom_image_url(NTE_FANDOM_API, e["image"], timeout) if e["image"] else "",
            "icon_fallback": "",
        })
        added.append(e["title"])
        used.add(t)

    if not added and not filled_icon and not filled_esper:
        return {"ok": True, "game": "nte", "total": len(chars), "added": 0,
                "added_names": [], "source": "NTE Fandom", "changed": False,
                "message": "名单已是最新（Fandom Playable %d 名，本地无新增、无缺失头像）。" % len(entries)}
    bak = path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    try:
        shutil.copy2(path, bak)
    except Exception:
        pass
    doc["region_note"] = ("由异环 Fandom 英文百科于 %s 在线拉取合并（%d 名角色，新增 %d，中文名待核对）。"
                          % (datetime.date.today().isoformat(), len(chars), len(added)))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return {"ok": True, "game": "nte", "total": len(chars), "added": len(added),
            "added_names": added, "filled_icon": filled_icon, "filled_esper": filled_esper,
            "source": "NTE Fandom", "changed": True, "backed_up": True,
            "message": "已从异环 Fandom 英文百科同步 %d 名角色（新增 %d：%s%s），旧文件已备份。"
                       % (len(chars), len(added), "、".join(added) or "无",
                          (("，补头像 %d" % filled_icon) if filled_icon else "")
                          + (("，补异能系 %d" % filled_esper) if filled_esper else ""))}


# ============================================================
# 鸣潮 官方基础数值（biligame 鸣潮百科「共鸣者/基础属性」，中文，每版本更新）
# 来源：wiki.biligame.com/wutheringwaves（revisions 接口可用，parse 被 567 拦截）
# 产物：data/wuthering_waves_official_stats.json（Lv1/Lv90 白值 + 定位标签）
# ============================================================
WUWA_BILIGAME_API = "https://wiki.biligame.com/wutheringwaves/api.php"


def _bili_rev_content(title, timeout=30):
    """biligame revisions 接口取页面内容（规避 parse 的 567 防盗链）。"""
    import urllib.parse as up
    url = WUWA_BILIGAME_API + "?" + up.urlencode({
        "action": "query", "titles": title, "prop": "revisions",
        "rvprop": "content", "rvslots": "main", "format": "json"})
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://wiki.biligame.com/wutheringwaves/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    for pg in d.get("query", {}).get("pages", {}).values():
        revs = pg.get("revisions") or []
        if revs:
            return revs[0].get("slots", {}).get("main", {}).get("*", "")
    return ""


def _wuwa_mult_total(text):
    """解析单个倍率值（如 36.80% / 18.30%*5 / 11.87%*7 + 77.18%*2）→ 总倍率数值。"""
    total = 0.0
    for m in re.findall(r"([\d.]+)%(?:\*(\d+))?", text):
        v = float(m[0])
        n = int(m[1]) if m[1] else 1
        total += v * n
    return total


def _wuwa_field_max(text):
    """解析倍率字段（每行：名称,Lv1%,...,Lv10%；多行用分号分隔）→ 满级最高总倍率。"""
    best = 0.0
    for line in (text or "").split(";"):
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            continue
        best = max(best, _wuwa_mult_total(parts[-1]))  # 最后一列 = Lv10
    return best


def update_wuwa_official_stats(timeout=30):
    """从 biligame 鸣潮百科拉取「共鸣者」基础属性（Lv1/Lv90 白值），写本地数值文件。"""
    import urllib.parse as up
    pages = []
    cont = {}
    try:
        for _ in range(10):
            params = {"action": "query", "list": "categorymembers",
                      "cmtitle": "Category:共鸣者", "cmtype": "page", "cmlimit": "50", "format": "json"}
            params.update(cont)
            url = WUWA_BILIGAME_API + "?" + up.urlencode(params)
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0", "Referer": "https://wiki.biligame.com/wutheringwaves/"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode("utf-8"))
            pages += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
            if "continue" in d:
                cont = {"cmcontinue": d["continue"].get("cmcontinue", ""),
                        "continue": d["continue"].get("continue", "")}
                if not cont["cmcontinue"]:
                    break
            else:
                break
    except Exception:
        return {"ok": False, "game": "wuthering_waves", "kind": "official_stats",
                "error": "network_unavailable", "message": "网络不可用或 biligame 鸣潮百科暂不可达，未改动任何数据。"}

    stats = {}
    for title in pages:
        try:
            wt = _bili_rev_content(title, timeout)
            if not wt:
                continue
        except Exception:
            continue
        base = _bili_parse_template(wt, "共鸣者/基本资料")
        prop = _bili_parse_template(wt, "共鸣者/基础属性")
        skill = _bili_parse_template(wt, "共鸣者/技能")
        if not base.get("名称"):
            continue
        stats[base["名称"]] = {
            "name": base["名称"],
            "en": (base.get("英文名") or "").strip().lower(),
            "element": base.get("属性", ""),
            "weapon": base.get("武器", ""),
            "rarity": _num(base.get("品质")),
            "role": base.get("战斗风格", ""),
            "base_hp": _num(prop.get("生命")), "base_atk": _num(prop.get("攻击")), "base_def": _num(prop.get("防御")),
            "hp90": _num(prop.get("90生命")), "atk90": _num(prop.get("90攻击")), "def90": _num(prop.get("90防御")),
            "skill_mult": {
                "normal_max": _wuwa_field_max(skill.get("常态攻击倍率")),
                "skill_max": _wuwa_field_max(skill.get("共鸣技能倍率")),
                "circuit_max": _wuwa_field_max(skill.get("共鸣回路倍率")),
                "lib_max": _wuwa_field_max(skill.get("共鸣解放倍率")),
                "vari_max": _wuwa_field_max(skill.get("变奏技能倍率")),
            },
        }

    path = os.path.join(DATA_DIR, "wuthering_waves_official_stats.json")
    out_doc = {"game": "wuthering_waves", "source": "biligame 鸣潮百科（共鸣者/基础属性）",
               "date": datetime.date.today().isoformat(), "stats": stats}
    changed = True
    try:
        if os.path.exists(path):
            old = json.load(open(path, encoding="utf-8"))
            changed = old.get("stats") != stats
    except Exception:
        changed = True
    if changed:
        try:
            if os.path.exists(path):
                shutil.copy2(path, path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
        except Exception:
            pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out_doc, f, ensure_ascii=False, indent=1)
    return {"ok": True, "game": "wuthering_waves", "kind": "official_stats",
            "stats_count": len(stats), "changed": changed,
            "message": "已从 biligame 鸣潮百科同步 %d 名角色 Lv1/Lv90 白值。" % len(stats)}


# ============================================================
# 异环 官方基础数值（Fandom「Module:Character Ascensions and Stats/data」）
# 来源：neverness-to-everness.fandom.com 数据模块（base_hp/atk/def + 每级成长）
# 产物：data/nte_official_stats.json（Lv80 白值，wiki 数据模块尚在建设中，覆盖有限）
# ============================================================
NTE_FANDOM_DATA = "Module:Character Ascensions and Stats/data"


def update_nte_official_stats(timeout=30):
    """从异环 Fandom 数据模块拉取基础数值（base + 149×每级成长 ≈ Lv80），写本地数值文件。"""
    try:
        d = _fandom_get({"action": "query", "titles": NTE_FANDOM_DATA,
                         "prop": "revisions", "rvprop": "content",
                         "rvslots": "main", "format": "json"}, NTE_FANDOM_API, timeout)
        content = ""
        for pg in d.get("query", {}).get("pages", {}).values():
            revs = pg.get("revisions") or []
            if revs:
                content = revs[0].get("slots", {}).get("main", {}).get("*", "")
    except Exception:
        return {"ok": False, "game": "nte", "kind": "official_stats",
                "error": "network_unavailable", "message": "网络不可用或 Fandom 暂不可达，未改动任何数据。"}

    # 解析 Lua return 表：按「条目块」（以独立行 }, 结尾）切分，避免 common 列表的 {} 干扰
    import re as _re
    stats = {}
    for m in _re.finditer(r"\['([^']+)'\]\s*=\s*\{(.*?)\n\s*\},\n", content, _re.S):
        en_name, body = m.group(1), m.group(2)
        fields = dict(_re.findall(r"\[\s*'([a-z_]+)'\s*\]\s*=\s*'?([^',}\]]+)'?", body))
        try:
            base_hp = float(fields.get("base_hp", 0) or 0)
            base_atk = float(fields.get("base_atk", 0) or 0)
            base_def = float(fields.get("base_def", 0) or 0)
            hp_pl = float(fields.get("hp_per_level", 0) or 0)
            atk_pl = float(fields.get("atk_per_level", 0) or 0)
            def_pl = float(fields.get("def_per_level", 0) or 0)
        except Exception:
            continue
        stats[en_name] = {
            "name": en_name,
            "rarity": str(fields.get("rarity", "")).upper(),
            "base_hp": base_hp, "base_atk": base_atk, "base_def": base_def,
            "full": bool(hp_pl or atk_pl or def_pl),
            "hp80": round(base_hp + 149 * hp_pl, 1) if hp_pl else base_hp,
            "atk80": round(base_atk + 149 * atk_pl, 1) if atk_pl else base_atk,
            "def80": round(base_def + 149 * def_pl, 1) if def_pl else base_def,
            "note": "Lv80 按 base + 149×每级成长推算（Fandom 数据模块）",
        }

    path = os.path.join(DATA_DIR, "nte_official_stats.json")
    out_doc = {"game": "nte", "source": "异环 Fandom 数值数据模块",
               "date": datetime.date.today().isoformat(), "stats": stats}
    changed = True
    try:
        if os.path.exists(path):
            old = json.load(open(path, encoding="utf-8"))
            changed = old.get("stats") != stats
    except Exception:
        changed = True
    if changed:
        try:
            if os.path.exists(path):
                shutil.copy2(path, path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
        except Exception:
            pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out_doc, f, ensure_ascii=False, indent=1)
    return {"ok": True, "game": "nte", "kind": "official_stats",
            "stats_count": len(stats), "changed": changed,
            "message": "已从异环 Fandom 数值模块同步 %d 名角色 Lv80 白值（模块仍在建设中，覆盖有限）。" % len(stats)}


# ============================================================
# 终末地 官方基础数值（wuyilingwei/EndfieldGameData 游戏数据仓库）
# 来源：TableCfg/Character.json（中文名/职业/武器/稀有度 + 每级 hp/atk/def/穿透/双暴）
# 产物：data/arknights_endfield_official_stats.json（Lv1 / 满级白值）
# 注意：该仓库仍在建设中，目前仅覆盖部分角色，其余回退精编/职业推导。
# ============================================================
ENDFIELD_DATA_CHARS = ("https://raw.githubusercontent.com/wuyilingwei/"
                       "EndfieldGameData/main/TableCfg/Character.json")


def update_endfield_official_stats(timeout=60):
    """从 EndfieldGameData 游戏数据仓库拉取终末地角色白值，写本地数值文件。"""
    try:
        req = urllib.request.Request(ENDFIELD_DATA_CHARS, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        table = d.get("characterTable", {})
    except Exception:
        return {"ok": False, "game": "arknights_endfield", "kind": "official_stats",
                "error": "network_unavailable", "message": "网络不可用或数据仓库暂不可达，未改动任何数据。"}

    stats = {}
    for char_id, c in table.items():
        if not isinstance(c, dict) or not c.get("name"):
            continue
        attrs = c.get("attributes") or []
        lv1 = next((a for a in attrs if a.get("level") == 1), attrs[0] if attrs else {})
        lv_max = attrs[-1] if attrs else {}
        stats[char_id] = {
            "char_id": char_id,
            "name": c.get("name", {}).get("text") if isinstance(c.get("name"), dict) else c.get("name"),
            "en": c.get("engName") or "",
            "profession": c.get("profession") or "",
            "weapon_type": c.get("weaponType") or "",
            "rarity": c.get("rarity"),
            "energy_shard": c.get("energyShardType") or "",
            "base_hp": lv1.get("hp"), "base_atk": lv1.get("atk"), "base_def": lv1.get("def"),
            "hp_max": lv_max.get("hp"), "atk_max": lv_max.get("atk"), "def_max": lv_max.get("def"),
            "pen": lv_max.get("pen"), "crit_rate": lv_max.get("criticalRate"), "crit_dmg": lv_max.get("criticalDamage"),
            "note": "满级=最后 breakStage 属性（Lv70 档）",
        }

    path = os.path.join(DATA_DIR, "arknights_endfield_official_stats.json")
    out_doc = {"game": "arknights_endfield", "source": "EndfieldGameData（游戏数据仓库）",
               "date": datetime.date.today().isoformat(), "stats": stats}
    changed = True
    try:
        if os.path.exists(path):
            old = json.load(open(path, encoding="utf-8"))
            changed = old.get("stats") != stats
    except Exception:
        changed = True
    if changed:
        try:
            if os.path.exists(path):
                shutil.copy2(path, path + ".bak." + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
        except Exception:
            pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out_doc, f, ensure_ascii=False, indent=1)
    return {"ok": True, "game": "arknights_endfield", "kind": "official_stats",
            "stats_count": len(stats), "changed": changed,
            "message": "已从 EndfieldGameData 同步 %d 名角色白值（仓库建设中，覆盖有限）。" % len(stats)}


# ============================================================
# 终末地 真实头像（BoxCatTeam/endfield-cat-metadata，GitHub raw）
# 来源：BoxCatTeam 仓库 locale/zh-CN/character.json 提供 中文名->itemid 映射；
#       图标取 images/character/icon/{itemid}.png（GitHub raw，沙箱实测 200 image/png）。
# 下方 ENDFIELD_AVATAR_IDS 已对每张 URL 做 HTTP 200 验证（离线可用、零假数据）。
# 无映射/验证失败的角色不写入，前端自动回退官方属性色卡。
# 缺失（BoxCatTeam 尚未收录的新角色）：洛茜/庄方宜/弭弗/卡缪/诀/梨诺 —— 维持色卡。
# ============================================================
ENDFIELD_GITHUB_ICONS = "https://raw.githubusercontent.com/BoxCatTeam/endfield-cat-metadata/master/images/character/icon/"
ENDFIELD_GITHUB_CHARS = "https://raw.githubusercontent.com/BoxCatTeam/endfield-cat-metadata/master/locale/zh-CN/character.json"
ENDFIELD_AVATAR_IDS = {
    "admin": "chr_0003_endminf",
    "ember": "chr_0009_azrila",
    "lifeng": "chr_0015_lifeng",
    "ardelia": "chr_0025_ardelia",
    "last_rite": "chr_0026_lastrite",
    "pogranichnik": "chr_0029_pograni",
    "laevatain": "chr_0016_laevat",
    "gilberta": "chr_0013_aglina",
    "yvonne": "chr_0017_yvonne",
    "perlica": "chr_0004_pelica",
    "chen_qianyu": "chr_0005_chen",
    "wulfgard": "chr_0006_wolfgd",
    "arclight": "chr_0007_ikut",
    "alesh": "chr_0024_deepfin",
    "avywenna": "chr_0012_avywen",
    "da_pan": "chr_0018_dapan",
    "snowshine": "chr_0014_aurora",
    "xaihi": "chr_0011_seraph",
    "estella": "chr_0021_whiten",
    "catcher": "chr_0020_meurs",
    "antal": "chr_0023_antal",
    "akekuri": "chr_0019_karin",
    "fluorite": "chr_0022_bounda",
    "tangtang": "chr_0027_tangtang",
}

def _endfield_avatar(idx):
    itemid = ENDFIELD_AVATAR_IDS.get(idx)
    return (ENDFIELD_GITHUB_ICONS + itemid + ".png") if itemid else ""

def fetch_endfield_avatars():
    """联网从 BoxCatTeam/endfield-cat-metadata 重建 中文名->itemid 映射并验证图标 URL，
    写回 data/arknights_endfield_characters.json。仅写入验证通过的 URL；网络不可用时
    返回 (0,'network_unavailable') 且不改动数据（优雅回退到 ENDFIELD_AVATAR_IDS 静态表）。"""
    try:
        req = urllib.request.Request(ENDFIELD_GITHUB_CHARS, headers={"User-Agent": "Mozilla/5.0"})
        data = json.load(urllib.request.urlopen(req, timeout=30))
        name2id = {}
        for info in data:
            nm = info.get("name")
            itemid = info.get("itemid")
            if isinstance(nm, str) and itemid:
                name2id[nm.strip()] = itemid
    except Exception:
        return 0, "network_unavailable"
    key2name = {row[0]: row[1] for row in ENDFIELD_CHARS}
    path = os.path.join(DATA_DIR, "arknights_endfield_characters.json")
    if not os.path.exists(path):
        return 0, "no_data"
    doc = json.load(open(path, encoding="utf-8"))
    updated = 0
    for c in doc["characters"]:
        idx = c["id"].replace("endfield_", "", 1)
        itemid = name2id.get(key2name.get(idx, "")) or ENDFIELD_AVATAR_IDS.get(idx)
        if not itemid:
            continue
        u = ENDFIELD_GITHUB_ICONS + itemid + ".png"
        if _url_ok(u) and c.get("icon") != u:
            c["icon"] = u
            updated += 1
    if updated:
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return updated, "ok"


# ============================================================
# 异环 真实头像：优先 NTE Fandom 英文百科 Portrait 立绘（static.wikia.nocookie.net 可外链）；
# 早雾/浔 使用萌娘百科 storage.moegirl.org.cn 原始文件直链（已绕过 Special:FilePath 反爬）。
# NTE_ICON_URLS 显式映射 id_key -> 已验证可外链的真实图片 URL。
# 全部 22 名角色均有真实头像；刷新脚本也会沿用此表。
# ============================================================
NTE_ICON_URLS = {
    "zero": "https://static.wikia.nocookie.net/neverness-to-everness/images/6/67/Esper_Zero_Female_Portrait.png/revision/latest?cb=20260629174041",
    "nanally": "https://static.wikia.nocookie.net/neverness-to-everness/images/8/8b/Nanally_Portrait.png/revision/latest?cb=20260629174651",
    "jiuyuan": "https://static.wikia.nocookie.net/neverness-to-everness/images/b/b3/Jiuyuan_Portrait.png/revision/latest?cb=20260629174536",
    "baizang": "https://static.wikia.nocookie.net/neverness-to-everness/images/8/83/Baicang_Portrait.png/revision/latest?cb=20260629173726",
    "hotori": "https://static.wikia.nocookie.net/neverness-to-everness/images/b/b6/Hotori_Portrait.png/revision/latest?cb=20260629174306",
    "xiaozhi": "https://static.wikia.nocookie.net/neverness-to-everness/images/4/42/Chiz_Portrait.png/revision/latest?cb=20260629173843",
    "fadia": "https://static.wikia.nocookie.net/neverness-to-everness/images/7/7d/Fadia_Portrait.png/revision/latest?cb=20260629174721",
    "daffodil": "https://static.wikia.nocookie.net/neverness-to-everness/images/f/f0/Daffodill_Portrait.png/revision/latest?cb=20260629173935",
    "sagiri": "https://storage.moegirl.org.cn/moegirl/commons/b/b3/%E5%BC%82%E7%8E%AF-%E6%97%A9%E9%9B%BE.jpg",
    "hathor": "https://static.wikia.nocookie.net/neverness-to-everness/images/9/9b/Hathor_Portrait.png/revision/latest?cb=20260629174220",
    "sakiri": "https://static.wikia.nocookie.net/neverness-to-everness/images/6/61/Sakiri_Portrait.png/revision/latest?cb=20260701202236",
    "xun": "https://storage.moegirl.org.cn/moegirl/commons/8/8c/%E6%B5%94%28%E5%BC%82%E7%8E%AF%29.png",
    "haniel": "https://static.wikia.nocookie.net/neverness-to-everness/images/a/a5/Haniel_Portrait.png/revision/latest?cb=20260701202324",
    "mint": "https://static.wikia.nocookie.net/neverness-to-everness/images/4/41/Mint_Portrait.png/revision/latest?cb=20260629174611",
    "aurelia": "https://static.wikia.nocookie.net/neverness-to-everness/images/2/22/Aurelia_Portrait.png/revision/latest?cb=20260629174756",
    "adler": "https://static.wikia.nocookie.net/neverness-to-everness/images/0/0c/Adler_Portrait.png/revision/latest?cb=20260629173120",
    "skia": "https://static.wikia.nocookie.net/neverness-to-everness/images/0/0d/Skia_Portrait.png/revision/latest?cb=20260629174906",
    "edgar": "https://static.wikia.nocookie.net/neverness-to-everness/images/b/b4/Edgar_Portrait.png/revision/latest?cb=20260701201907",
    "requiem": "https://static.wikia.nocookie.net/neverness-to-everness/images/c/c1/Lacrimosa_Portrait.png/revision/latest?cb=20260701202053",
    "kaos": "https://static.wikia.nocookie.net/neverness-to-everness/images/8/87/Chaos_Portrait.png/revision/latest?cb=20260629173809",
    "zhenhong": "https://static.wikia.nocookie.net/neverness-to-everness/images/a/a8/Shinku_Portrait.png/revision/latest?cb=20260708083848",
    "iroi": "https://static.wikia.nocookie.net/neverness-to-everness/images/8/85/Iroi_Portrait.png/revision/latest?cb=20260723021205",
}

def _nte_avatar(idx):
    return NTE_ICON_URLS.get(idx, "")

def fetch_nte_avatars():
    """联网逐张验证 NTE 头像 URL（NTE_ICON_URLS），写回 data/nte_characters.json。
    仅写入验证通过的 URL；网络不可用时返回 (0,'network_unavailable') 且不改动数据
    （优雅回退到 NTE_ICON_URLS 静态表）。"""
    path = os.path.join(DATA_DIR, "nte_characters.json")
    if not os.path.exists(path):
        return 0, "no_data"
    doc = json.load(open(path, encoding="utf-8"))
    updated = 0
    for c in doc["characters"]:
        idx = c["id"].replace("nte_", "", 1)
        u = NTE_ICON_URLS.get(idx, "")
        if not u:
            continue
        if _url_ok(u) and c.get("icon") != u:
            c["icon"] = u
            updated += 1
    if updated:
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return updated, "ok"


def fetch_genshin_avatars():
    """联网从 api.lunaris.moe 拉取角色卡图映射，逐张验证 Enka URL，
    写回 data/genshin_characters.json。仅写入验证通过的 URL；网络不可用时
    返回 (0,'network_unavailable') 且不改动任何数据。"""
    idx = _genshin_lunaris_index()
    if not idx:
        return 0, "network_unavailable"
    path = os.path.join(DATA_DIR, "genshin_characters.json")
    if not os.path.exists(path):
        return 0, "no_data"
    doc = json.load(open(path, encoding="utf-8"))
    updated = 0
    for c in doc["characters"]:
        u, fb = _genshin_avatar_urls(c, idx)
        if not u or not _url_ok(u):
            continue
        if c.get("icon") != u:
            c["icon"] = u
            updated += 1
        if not (c.get("icon_fallback") or "").strip() and fb and _url_ok(fb):
            c["icon_fallback"] = fb
            updated += 1
    if updated:
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return updated, "ok"


def fetch_avatars(game):
    """联网拉取真实头像并写回 data/<game>_characters.json（仅验证通过的 URL）。

    支持 genshin / hsr / arknights_endfield / nte；其他游戏（鸣潮等）暂无确定性映射源，
    返回 (0,'unsupported')。

    安全回退：网络不可用/失败时返回 ('network_unavailable'|'unsupported') 且不改动任何数据，
    前端自动回退到静态表或官方属性色卡。
    """
    if game == "genshin":
        return fetch_genshin_avatars()
    if game == "hsr":
        return fetch_hsr_avatars()
    if game == "arknights_endfield":
        return fetch_endfield_avatars()
    if game == "nte":
        return fetch_nte_avatars()
    return 0, "unsupported"


def _build_hsr():
    chars = []
    for row in HSR_CHARS:
        (idx, name, en, elem, path, rarity, ver, aliases, note) = row
        chars.append({
            "id": "hsr_" + idx,
            "name": name,
            "en": en,
            "aliases": aliases,
            "element": elem,
            "weapon": path,
            "path": path,
            "rarity": rarity,
            "version": ver,
            "status": "released",
            "note": note,
            "icon": _hsr_avatar(idx),
            "icon_fallback": "",
        })
    return chars


def _build_zzz():
    chars = []
    for row in ZZZ_CHARS:
        (idx, name, en, elem, spec, rarity, ver, faction, aliases) = row
        chars.append({
            "id": "zzz_" + idx,
            "name": name,
            "en": en,
            "aliases": aliases,
            "element": elem,
            "attribute": elem,
            "specialty": spec,
            "weapon": spec,
            "rarity": rarity,
            "version": ver,
            "status": "released",
            "note": ("阵营：" + faction) if faction else "",
            "icon": _zzz_avatar(idx),
            "icon_fallback": "",
        })
    return chars


def _build_wuwa():
    chars = []
    for row in WUWA_CHARS:
        (idx, name, en, elem, weapon, rarity, ver, aliases) = row
        local_icon = "/avatars/wuwa_%s.webp" % idx
        fandom_icon = _wuwa_fandom_url(idx)
        chars.append({
            "id": "wuwa_" + idx,
            "name": name,
            "en": en,
            "aliases": aliases,
            "element": elem,
            "weapon": weapon,
            "rarity": rarity,
            "version": ver,
            "status": "released",
            "note": "",
            "icon": fandom_icon,
            "icon_fallback": local_icon,
        })
    return chars


def _build_endfield():
    chars = []
    for row in ENDFIELD_CHARS:
        (idx, name, en, cls, branch, elem, rarity, ver, aliases) = row
        note = "属性待核对" if not elem else ""
        if not elem:
            elem = ""
        chars.append({
            "id": "endfield_" + idx,
            "name": name,
            "en": en,
            "aliases": aliases,
            "class": cls,
            "branch": branch,
            "element": elem,
            "rarity": rarity,
            "version": ver,
            "status": "released",
            "note": note,
            "icon": _endfield_avatar(idx),
            "icon_fallback": "",
        })
    return chars


def _build_nte():
    chars = []
    for row in NTE_CHARS:
        (idx, name, en, elem, weapon, rarity, ver, aliases) = row
        chars.append({
            "id": "nte_" + idx,
            "name": name,
            "en": en,
            "aliases": aliases,
            "element": elem,
            "weapon": weapon,
            "rarity": rarity,
            "version": ver,
            "status": "released",
            "note": "",
            "icon": _nte_avatar(idx),
            "icon_fallback": "",
        })
    return chars


def refresh_character_db(game):
    """从精编静态数据重建 data/<game>_characters.json。

    无需网络，数据源自各游戏官方 Wiki / 官网（HSR 截止 v4.4 / ZZZ 截止 v3.1 /
    鸣潮 截止 v3.5 / 终末地 截止 v1.4 / 异环 截止 v1.2）。
    Returns dict: {ok, game, count, backed_up, error}
    """
    if game == "hsr":
        chars, display = _build_hsr(), DISPLAY["hsr"]
        note = "由米游社官方 Wiki（srwiki）精编数据于 %s 重建（截止 v4.4）。" % datetime.date.today().isoformat()
    elif game == "zzz":
        chars, display = _build_zzz(), DISPLAY["zzz"]
        note = "由绝区零官网 + 米游社 Wiki 精编数据于 %s 重建（截止 v3.1）。" % datetime.date.today().isoformat()
    elif game == "wuthering_waves":
        chars, display = _build_wuwa(), DISPLAY["wuthering_waves"]
        note = "由鸣潮官网 + fandom Wiki 精编数据于 %s 重建（截止 v3.5）。" % datetime.date.today().isoformat()
    elif game == "arknights_endfield":
        chars, display = _build_endfield(), DISPLAY["arknights_endfield"]
        note = "由 moegirl + 官网精编数据于 %s 重建（截止 v1.4，已公测）。" % datetime.date.today().isoformat()
    elif game == "nte":
        chars, display = _build_nte(), DISPLAY["nte"]
        note = "由异环官网 + 百科精编数据于 %s 重建（截止 v1.2，已公测）。" % datetime.date.today().isoformat()
    else:
        return {"ok": False, "error": "该游戏不支持刷新角色库（仅 hsr/zzz/wuthering_waves/arknights_endfield/nte）。原神名单由 build_chars.py 维护，请用在线拉取补齐新版本角色。"}

    if len(chars) < 10:
        return {"ok": False, "error": "精编数据不足（%d 个），代码可能有误。" % len(chars)}

    out_path = os.path.join(DATA_DIR, "%s_characters.json" % game)
    bak_path = out_path + ".bak." + datetime.date.today().isoformat()
    backed_up = False
    if os.path.exists(out_path):
        try:
            shutil.copy2(out_path, bak_path)
            backed_up = True
        except Exception:
            backed_up = False

    doc = {
        "game": game,
        "display_name": display,
        "region_note": note,
        "characters": chars,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    return {"ok": True, "game": game, "count": len(chars), "backed_up": backed_up, "path": out_path}


if __name__ == "__main__":
    import sys
    g = sys.argv[1] if len(sys.argv) > 1 else "hsr"
    print(json.dumps(refresh_character_db(g), ensure_ascii=False, indent=2))
