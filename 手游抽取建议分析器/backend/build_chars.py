# -*- coding: utf-8 -*-
"""以原神官方角色索引(bbs.mihoyo.com)为权威基准重建角色库。
属性(element/weapon) 100% 采用官方索引；rarity/version 按发布信息补全。
每个角色带 en(英文名, 用于 ambr.top 头像) 与 jmp(jmp.blue slug, 1.x-5.x 本地头像回退)。
"""
import json, os, urllib.request

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "genshin_characters.json")
AVATAR_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

# 字段: (id, name, en, jmp_slug, element, weapon, rarity, version, aliases, status, note)
# status: released / upcoming ; note 仅 6.x 前瞻标注
R = [
    # ---------- 1.0 ----------
    ("jean","琴","Jean","jean","风","单手剑",5,"1.0",["琴","琴团长","代理团长"],"released",""),
    ("diluc","迪卢克","Diluc","diluc","火","双手剑",5,"1.0",["迪卢克","卢姥爷"],"released",""),
    ("klee","可莉","Klee","klee","火","法器",5,"1.0",["可莉","蹦蹦"],"released",""),
    ("venti","温迪","Venti","venti","风","弓",5,"1.0",["温迪","风神","巴巴托斯"],"released",""),
    ("keqing","刻晴","Keqing","keqing","雷","单手剑",5,"1.0",["刻晴","刻皇"],"released",""),
    ("mona","莫娜","Mona","mona","水","法器",5,"1.0",["莫娜","莫娜老师"],"released",""),
    ("qiqi","七七","Qiqi","qiqi","冰","单手剑",5,"1.0",["七七"],"released",""),
    ("amber","安柏","Amber","amber","火","弓",4,"1.0",["安柏"],"released",""),
    ("kaeya","凯亚","Kaeya","kaeya","冰","单手剑",4,"1.0",["凯亚"],"released",""),
    ("lisa","丽莎","Lisa","lisa","雷","法器",4,"1.0",["丽莎"],"released",""),
    ("barbara","芭芭拉","Barbara","barbara","水","法器",4,"1.0",["芭芭拉","偶像"],"released",""),
    ("bennett","班尼特","Bennett","bennett","火","单手剑",4,"1.0",["班尼特","点赞哥","六星火神"],"released",""),
    ("noelle","诺艾尔","Noelle","noelle","岩","双手剑",4,"1.0",["诺艾尔","女仆"],"released",""),
    ("fischl","菲谢尔","Fischl","fischl","雷","弓",4,"1.0",["菲谢尔","皇女"],"released",""),
    ("beidou","北斗","Beidou","beidou","雷","双手剑",4,"1.0",["北斗"],"released",""),
("razor","雷泽","Razor","razor","雷","双手剑",4,"1.0",["雷泽"],"released",""),
    ("sucrose","砂糖","Sucrose","sucrose","风","法器",4,"1.0",["砂糖"],"released",""),
    ("xingqiu","行秋","Xingqiu","xingqiu","水","单手剑",4,"1.0",["行秋","六星水神"],"released",""),
    ("xiangling","香菱","Xiangling","xiangling","火","长柄武器",4,"1.0",["香菱","万民堂"],"released",""),
    ("ningguang","凝光","Ningguang","ningguang","岩","法器",4,"1.0",["凝光","天权"],"released",""),
    # ---------- 1.1 ----------
    ("zhongli","钟离","Zhongli","zhongli","岩","长柄武器",5,"1.1",["钟离","岩王帝君","钟师傅","老爷子"],"released",""),
    ("diona","迪奥娜","Diona","diona","冰","弓",4,"1.1",["迪奥娜","猫尾酒保"],"released",""),
    ("chongyun","重云","Chongyun","chongyun","冰","双手剑",4,"1.1",["重云"],"released",""),
    ("xinyan","辛焱","Xinyan","xinyan","火","双手剑",4,"1.1",["辛焱"],"released",""),
    # ---------- 1.2 ----------
    ("albedo","阿贝多","Albedo","albedo","岩","单手剑",5,"1.2",["阿贝多","教授"],"released",""),
    ("ganyu","甘雨","Ganyu","ganyu","冰","弓",5,"1.2",["甘雨","椰羊"],"released",""),
    # ---------- 1.3 ----------
    ("xiao","魈","Xiao","xiao","风","长柄武器",5,"1.3",["魈","降魔大圣","小哥"],"released",""),
    ("hu-tao","胡桃","HuTao","hu-tao","火","长柄武器",5,"1.3",["胡桃","往生堂主"],"released",""),
    # ---------- 1.4 ----------
    ("kokomi","珊瑚宫心海","Kokomi","kokomi","水","法器",5,"1.4",["珊瑚宫心海","心海","舰长"],"released",""),
    ("rosaria","罗莎莉亚","Rosaria","rosaria","冰","长柄武器",4,"1.4",["罗莎莉亚","修女"],"released",""),
    # ---------- 1.5 ----------
    ("eula","优菈","Eula","eula","冰","双手剑",5,"1.5",["优菈","狼末"],"released",""),
    ("yanfei","烟绯","Yanfei","yanfei","火","法器",4,"1.5",["烟绯"],"released",""),
    # ---------- 1.6 ----------
    ("arataki-itto","荒泷一斗","AratakiItto","arataki-itto","岩","双手剑",5,"1.6",["荒泷一斗","一斗","阿丑"],"released",""),
    ("kazuha","枫原万叶","Kazuha","kazuha","风","单手剑",5,"1.6",["枫原万叶","万叶","叶天帝"],"released",""),
    # ---------- 2.0 ----------
    ("ayaka","神里绫华","Ayaka","ayaka","冰","单手剑",5,"2.0",["神里绫华","绫华","白鹭公主"],"released",""),
    ("yoimiya","宵宫","Yoimiya","yoimiya","火","弓",5,"2.0",["宵宫","烟花妹"],"released",""),
    # ---------- 2.1 ----------
    ("raiden","雷电将军","Raiden","raiden","雷","长柄武器",5,"2.1",["雷电将军","雷神","影","巴尔泽布"],"released",""),
    ("kujou-sara","九条裟罗","KujouSara","kujou-sara","雷","弓",4,"2.1",["九条裟罗","九条"],"released",""),
    ("aloy","埃洛伊","Aloy","aloy","冰","弓",5,"2.1",["埃洛伊"],"released",""),
    # ---------- 2.2 ----------
    ("tartaglia","达达利亚","Tartaglia","tartaglia","水","弓",5,"2.2",["达达利亚","公子","巧克力"],"released",""),
    ("thoma","托马","Thoma","thoma","火","长柄武器",4,"2.2",["托马"],"released",""),
    # ---------- 2.3 ----------
    ("gorou","五郎","Gorou","gorou","岩","弓",4,"2.3",["五郎","海祇岛"],"released",""),
    # ---------- 2.4 ----------
    ("shenhe","申鹤","Shenhe","shenhe","冰","长柄武器",5,"2.4",["申鹤","冻鳐"],"released",""),
    ("yunjin","云堇","Yunjin","yunjin","岩","长柄武器",4,"2.4",["云堇","戏班"],"released",""),
    # ---------- 2.5 ----------
    ("yae-miko","八重神子","YaeMiko","yae-miko","雷","法器",5,"2.5",["八重神子","神子","宫司"],"released",""),
    # ---------- 2.6 ----------
    ("ayato","神里绫人","Ayato","ayato","水","单手剑",5,"2.6",["神里绫人","绫人","社奉行"],"released",""),
    ("kuki-shinobu","久岐忍","KukiShinobu","kuki-shinobu","雷","单手剑",4,"2.6",["久岐忍"],"released",""),
    # ---------- 2.7 ----------
    ("yelan","夜兰","Yelan","yelan","水","弓",5,"2.7",["夜兰","兰姐","夜天后"],"released",""),
    ("sayu","早柚","Sayu","sayu","风","双手剑",4,"2.7",["早柚","忍者"],"released",""),
    # ---------- 2.8 ----------
    ("shikanoin-heizou","鹿野院平藏","ShikanoinHeizou","shikanoin-heizou","风","法器",4,"2.8",["鹿野院平藏","平藏"],"released",""),
    # ---------- 3.0 ----------
    ("tighnari","提纳里","Tighnari","tighnari","草","弓",5,"3.0",["提纳里","提老师"],"released",""),
    ("collei","柯莱","Collei","collei","草","弓",4,"3.0",["柯莱"],"released",""),
    ("dori","多莉","Dori","dori","雷","双手剑",4,"3.0",["多莉"],"released",""),
    # ---------- 3.1 ----------
    ("cyno","赛诺","Cyno","cyno","雷","长柄武器",5,"3.1",["赛诺","大风纪官"],"released",""),
    ("nilou","妮露","Nilou","nilou","水","单手剑",5,"3.1",["妮露","祖拜尔"],"released",""),
    ("candace","坎蒂丝","Candace","candace","水","长柄武器",4,"3.1",["坎蒂丝"],"released",""),
    ("layla","莱依拉","Layla","layla","冰","单手剑",4,"3.1",["莱依拉"],"released",""),
    # ---------- 3.2 ----------
    ("nahida","纳西妲","Nahida","nahida","草","法器",5,"3.2",["纳西妲","草神","布耶尔","兰那罗"],"released",""),
    # ---------- 3.3 ----------
    ("wanderer","流浪者","Wanderer","wanderer","风","法器",5,"3.3",["流浪者","散兵","国崩","倾奇者"],"released",""),
    ("faruzan","珐露珊","Faruzan","faruzan","风","弓",4,"3.3",["珐露珊","学院"],"released",""),
    # ---------- 3.4 ----------
    ("alhaitham","艾尔海森","Alhaitham","alhaitham","草","单手剑",5,"3.4",["艾尔海森","海哥","书记官"],"released",""),
    ("yaoyao","瑶瑶","Yaoyao","yaoyao","草","长柄武器",4,"3.4",["瑶瑶"],"released",""),
    # ---------- 3.5 ----------
    ("dehya","迪希雅","Dehya","dehya","火","双手剑",5,"3.5",["迪希雅","炽鬃之狮"],"released",""),
    ("mika","米卡","Mika","mika","冰","长柄武器",4,"3.5",["米卡","侦查骑士"],"released",""),
    # ---------- 3.6 ----------
    ("baizhu","白术","Baizhu","baizhu","草","法器",5,"3.6",["白术","白大夫"],"released",""),
    ("kaveh","卡维","Kaveh","kaveh","草","双手剑",4,"3.6",["卡维"],"released",""),
    # ---------- 4.0 ----------
    ("lyney","林尼","Lyney","lyney","火","弓",5,"4.0",["林尼"],"released",""),
    ("lynette","琳妮特","Lynette","lynette","风","单手剑",4,"4.0",["琳妮特"],"released",""),
    ("freminet","菲米尼","Freminet","freminet","冰","双手剑",4,"4.0",["菲米尼"],"released",""),
    # ---------- 4.1 ----------
    ("neuvillette","那维莱特","Neuvillette","neuvillette","水","法器",5,"4.1",["那维莱特","龙王","水龙王"],"released",""),
    ("wriothesley","莱欧斯利","Wriothesley","wriothesley","冰","法器",5,"4.1",["莱欧斯利","公爵"],"released",""),
    # ---------- 4.2 ----------
    ("furina","芙宁娜","Furina","furina","水","单手剑",5,"4.2",["芙宁娜","水神","芙芙","枫丹女神"],"released",""),
    ("charlotte","夏洛蒂","Charlotte","charlotte","冰","法器",4,"4.2",["夏洛蒂","记者"],"released",""),
    # ---------- 4.3 ----------
    ("navia","娜维娅","Navia","navia","岩","双手剑",5,"4.3",["娜维娅","枫丹剑"],"released",""),
    ("chevreuse","夏沃蕾","Chevreuse","chevreuse","雷","长柄武器",4,"4.3",["夏沃蕾"],"released",""),
    # ---------- 4.4 ----------
    ("chiori","千织","Chiori","chiori","岩","单手剑",5,"4.4",["千织"],"released",""),
    ("xianyun","闲云","Xianyun","xianyun","风","法器",5,"4.4",["闲云","留云借风真君"],"released",""),
    # ---------- 4.5 ----------
    ("kirara","绮良良","Kirara","kirara","草","单手剑",4,"4.5",["绮良良","猫猫","箱箱"],"released",""),
    # ---------- 4.6 ----------
    ("arlecchino","阿蕾奇诺","Arlecchino","arlecchino","火","长柄武器",5,"4.6",["阿蕾奇诺","仆人","父亲"],"released",""),
    ("gaming","嘉明","Gaming","gaming","火","双手剑",4,"4.6",["嘉明","舞狮"],"released",""),
    # ---------- 4.7 ----------
    ("clorinde","克洛琳德","Clorinde","clorinde","雷","单手剑",5,"4.7",["克洛琳德"],"released",""),
    ("sigewinne","希格雯","Sigewinne","sigewinne","水","弓",5,"4.7",["希格雯","护士长"],"released",""),
    ("sethos","赛索斯","Sethos","sethos","雷","弓",4,"4.7",["赛索斯"],"released",""),
    # ---------- 4.8 ----------
    ("emilie","艾梅莉埃","Emilie","emilie","草","长柄武器",5,"4.8",["艾梅莉埃","调香师"],"released",""),
    # ---------- 5.0 ----------
    ("mualani","玛拉妮","Mualani","mualani","水","法器",5,"5.0",["玛拉妮"],"released",""),
    ("kinich","基尼奇","Kinich","kinich","草","双手剑",5,"5.0",["基尼奇"],"released",""),
    ("kachina","卡齐娜","Kachina","kachina","岩","长柄武器",4,"5.0",["卡齐娜","纳塔"],"released",""),
    # ---------- 5.1 ----------
    ("xilonen","希诺宁","Xilonen","xilonen","岩","单手剑",5,"5.1",["希诺宁","希诺伦"],"released",""),
    ("ororon","欧洛伦","Ororon","ororon","雷","弓",4,"5.1",["欧洛伦"],"released",""),
    # ---------- 5.2 ----------
    ("chasca","恰斯卡","Chasca","chasca","风","弓",5,"5.2",["恰斯卡"],"released",""),
    ("lanyan","蓝砚","Lanyan","lanyan","风","法器",4,"5.2",["蓝砚","枫丹"],"released",""),
    # ---------- 5.3 ----------
    ("mavuika","玛薇卡","Mavuika","mavuika","火","双手剑",5,"5.3",["玛薇卡","火神","队长"],"released",""),
    # ---------- 5.4 ----------
    ("yumemizuki","梦见月瑞希","YumemizukiMizuki","yumemizuki","风","法器",5,"5.4",["梦见月瑞希","瑞希"],"released",""),
    # ---------- 5.5 ----------
    ("varesa","瓦雷莎","Varesa","varesa","雷","法器",5,"5.5",["瓦雷莎"],"released",""),
    ("iansan","伊安珊","Iansan","iansan","雷","长柄武器",4,"5.5",["伊安珊"],"released",""),
    # ---------- 5.6 ----------
    ("escoffier","爱可菲","Escoffier","escoffier","冰","长柄武器",5,"5.6",["爱可菲","冰系辅助"],"released",""),
    ("talia","塔利雅","Talia","talia","水","单手剑",4,"5.6",["塔利雅"],"released",""),
    ("ifa","伊法","Ifa","ifa","风","法器",4,"5.6",["伊法"],"released",""),
    # ---------- 5.7 ----------
    ("skirk","丝柯克","Skirk","skirk","冰","单手剑",5,"5.7",["丝柯克","公子师傅"],"released",""),
    # ---------- 5.8 ----------
    ("citlali","茜特菈莉","Citlali","citlali","冰","法器",5,"5.8",["茜特菈莉","茜特菈利","龙妈"],"released",""),
    ("ineffa","伊涅芙","Ineffa","ineffa","雷","长柄武器",5,"5.8",["伊涅芙","机械少女"],"released",""),
    # ---------- 6.0 挪德卡莱 ----------
    ("lauma","菈乌玛","Lauma","", "草","法器",5,"6.0",["菈乌玛","月反馈"],"released","挪德卡莱 6.0 新角色"),
    ("flins","菲林斯","Flins","", "雷","长柄武器",5,"6.0",["菲林斯","执灯人"],"released","挪德卡莱 6.0 新角色"),
    ("aino","爱诺","Aino","", "水","双手剑",4,"6.0",["爱诺","蛋卷工坊"],"released","挪德卡莱 6.0 新角色"),
    # ---------- 6.1 ----------
    ("nefer","奈芙尔","Nefer","", "草","法器",5,"6.1",["奈芙尔","秘闻馆"],"released","挪德卡莱 6.1 新角色"),
    # ---------- 6.2 ----------
    ("durinn","杜林","Durin","", "火","单手剑",5,"6.2",["杜林","小杜林"],"released","挪德卡莱 6.2 新角色"),
    ("jahoda","雅珂达","Jahoda","", "风","弓",4,"6.2",["雅珂达","蛋卷工坊"],"released","挪德卡莱 6.2 新角色"),
    # ---------- 6.3 ----------
("columbina","哥伦比娅","Columbina","", "水","法器",5,"6.3",["哥伦比娅","少女","第三席","月之少女"],"released","挪德卡莱 6.3 新角色"),
    ("yeloya","叶洛亚","Yeloya","", "岩","长柄武器",4,"6.3",["叶洛亚"],"released","挪德卡莱 6.3 新角色"),
    ("zibai","兹白","Zibai","", "岩","单手剑",5,"6.3",["兹白","月结晶"],"released","挪德卡莱 6.3 新角色"),
    # ---------- 6.4 ----------
    ("varka","法尔伽","Varka","", "风","双手剑",5,"6.4",["法尔伽","大团长","西风骑士团"],"released","挪德卡莱 6.4 新角色"),
    # ---------- 6.5 ----------
    ("linea","莉奈娅","Linea","", "岩","弓",5,"6.5",["莉奈娅","冒险家协会"],"released","挪德卡莱 6.5 新角色"),
    # ---------- 6.6 ----------
    ("nicole","尼可·莱恩","Nicole","", "火","法器",5,"6.6",["尼可","魔女会N"],"released","挪德卡莱 6.6 新角色"),
    ("lune","洛恩","Lune","", "冰","长柄武器",4,"6.6",["洛恩","西风副队长"],"released","挪德卡莱 6.6 新角色"),
    # ---------- 6.7 ----------
    ("sandrone","木偶·桑多涅","Sandrone","", "冰","双手剑",5,"6.7",["桑多涅","木偶","第七席"],"released","挪德卡莱 6.7 新角色"),
    ("brunni","布伦妮","Brunni","", "风","法器",4,"6.7",["布伦妮"],"released","挪德卡莱 6.7 新角色"),
    # ---------- 6.8 前瞻 ----------
    ("alice","艾莉丝","Alice","", "火","法器",5,"6.8",["艾莉丝","魔女会","可莉妈妈"],"upcoming","挪德卡莱 6.8 前瞻角色，尚未上线"),
    # ---------- 7.0 至冬 ----------
    ("odette","奥黛塔","Odette","", "冰","单手剑",5,"7.0",["奥黛塔","奥黛塔·苏佩茜娃","雪鹄座"],"released","至冬 7.0 新角色"),
    ("alyosha","阿罗夏","Alyosha","", "雷","长柄武器",4,"7.0",["阿罗夏","迅捷犬座"],"released","至冬 7.0 新角色"),
    # ---------- 旅行者(特殊) ----------
    ("traveler","旅行者","Traveler","traveler","风","单手剑",5,"1.0",["旅行者","空","荧","主角"],"released","可切换 风/岩/雷/草/水/火/冰 七元素"),
]

# ambr.top 头像缺失时使用的 Fandom 兜底（已逐条 GET 验证 200）。
# talia / yeloya / lune / brunni 暂无稳定图源，保持为空并交给前端色卡兜底。
FANDOM_FALLBACK = {
    "kujou-sara": "https://static.wikia.nocookie.net/gensin-impact/images/d/df/Kujou_Sara_Icon.png/revision/latest?cb=20220210040844",
    "ororon": "https://static.wikia.nocookie.net/gensin-impact/images/5/5e/Ororon_Icon.png/revision/latest?cb=20241014100711",
    "yumemizuki": "https://static.wikia.nocookie.net/gensin-impact/images/f/f6/Yumemizuki_Mizuki_Icon.png/revision/latest?cb=20250212014631",
    "skirk": "https://static.wikia.nocookie.net/gensin-impact/images/0/03/Skirk_Icon.png/revision/latest?cb=20250618025127",
    "sandrone": "https://static.wikia.nocookie.net/gensin-impact/images/c/c8/Sandrone_Icon.png/revision/latest?cb=20260701024112",
    "traveler": "https://static.wikia.nocookie.net/gensin-impact/images/5/59/Traveler_Icon.png/revision/latest?cb=20211220013610",
    "linea": "https://static.wikia.nocookie.net/gensin-impact/images/a/a9/Linnea_Icon.png/revision/latest?cb=20260408075838",
}

def build():
    chars = []
    for (cid, name, en, jmp, element, weapon, rarity, version, aliases, status, note) in R:
        # 头像: 主用 ambr.top(用户本机可达, 含全版本); 1.x-5.x 本地 jmp.blue 回退
        icon = "https://api.ambr.top/assets/UI/avatar/UI_Avatar_%s.png" % en if en else ""
        icon_fallback = ("/avatars/%s.webp" % jmp) if jmp else FANDOM_FALLBACK.get(cid, "")
        chars.append({
            "id": cid, "name": name, "en": en, "aliases": aliases,
            "element": element, "weapon": weapon, "rarity": rarity,
            "version": version, "status": status, "note": note,
            "icon": icon, "icon_fallback": icon_fallback,
        })
    return chars

if __name__ == "__main__":
    chars = build()
    doc = {
        "game": "genshin",
        "display_name": "原神",
        "region_note": "挪德卡莱（月之系列 6.0–6.8）已收尾；7.0「无神怜爱的雪国」至冬已于 2026-08-12 上线。属性以原神官方角色索引为准。",
        "characters": chars,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("wrote", len(chars), "characters ->", os.path.abspath(OUT))

    # 下载 1.x-5.x 本地头像(jmp.blue, 沙箱可达, 真实图片)
    ok = miss = 0
    for c in chars:
        jmp = c["id"]  # 仅当 icon_fallback 含 jmp slug
    # 用 jmp slug 列表重新下载
    slugs = {
        "jean":"jean","diluc":"diluc","klee":"klee","venti":"venti","keqing":"keqing",
        "mona":"mona","qiqi":"qiqi","amber":"amber","kaeya":"kaeya","lisa":"lisa",
        "barbara":"barbara","bennett":"bennett","noelle":"noelle","fischl":"fischl",
        "beidou":"beidou","razor":"razor","sucrose":"sucrose","zhongli":"zhongli",
        "diona":"diona","chongyun":"chongyun","xinyan":"xinyan","albedo":"albedo",
        "ganyu":"ganyu","xiao":"xiao","hu-tao":"hu-tao","kokomi":"kokomi","rosaria":"rosaria",
        "eula":"eula","yanfei":"yanfei","arataki-itto":"arataki-itto","kazuha":"kazuha",
        "ayaka":"ayaka","yoimiya":"yoimiya","raiden":"raiden","kujou-sara":"kujou-sara",
        "aloy":"aloy","tartaglia":"tartaglia","thoma":"thoma","gorou":"gorou","shenhe":"shenhe",
        "yunjin":"yunjin","yae-miko":"yae-miko","ayato":"ayato","kuki-shinobu":"kuki-shinobu",
        "yelan":"yelan","sayu":"sayu","shikanoin-heizou":"shikanoin-heizou","tighnari":"tighnari",
        "collei":"collei","dori":"dori","cyno":"cyno","nilou":"nilou","candace":"candace",
        "layla":"layla","nahida":"nahida","wanderer":"wanderer","faruzan":"faruzan",
        "alhaitham":"alhaitham","yaoyao":"yaoyao","dehya":"dehya","mika":"mika","baizhu":"baizhu",
        "kaveh":"kaveh","lyney":"lyney","lynette":"lynette","freminet":"freminet",
        "neuvillette":"neuvillette","wriothesley":"wriothesley","furina":"furina",
        "charlotte":"charlotte","navia":"navia","chevreuse":"chevreuse","chiori":"chiori",
        "xianyun":"xianyun","kirara":"kirara","arlecchino":"arlecchino","gaming":"gaming",
        "clorinde":"clorinde","sigewinne":"sigewinne","sethos":"sethos","emilie":"emilie",
        "mualani":"mualani","kinich":"kinich","kachina":"kachina","xilonen":"xilonen",
        "ororon":"ororon","chasca":"chasca","lanyan":"lanyan","mavuika":"mavuika",
        "yumemizuki":"yumemizuki","varesa":"varesa","iansan":"iansan","escoffier":"escoffier",
        "talia":"talia","ifa":"ifa","skirk":"skirk","citlali":"citlali","ineffa":"ineffa",
    }
    for cid, slug in slugs.items():
        url = "https://genshin.jmp.blue/characters/%s/icon" % slug
        dst = os.path.join(AVATAR_DIR, slug + ".webp")
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=20).read()
            if len(data) > 500:  # 真实图片
                with open(dst, "wb") as f:
                    f.write(data)
                ok += 1
            else:
                miss += 1
        except Exception as e:
            miss += 1
    print("local avatars: ok=%d miss=%d -> %s" % (ok, miss, os.path.abspath(AVATAR_DIR)))
