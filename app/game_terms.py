"""游戏黑话表：把中文口语先「翻译」成英文术语，再交给机翻。

机翻不懂「B点 / 下包 / 架枪 / 残血」这些说法，直接翻会变成
「attack point B」「put down the bag」「hold the gun」，很别扭。
先把它们替换成英文术语（B site / plant the spike / hold the angle / low hp），
再翻成日文或英文，结果会自然很多。
"""
from __future__ import annotations

import re

# (正则, 替换成) —— 顺序有讲究，长词在前
ZH_TERMS: list[tuple[str, str]] = [
    (r"([A-Ca-cAaｂｃ])\s*[点點]", r"\1 site"),
    (r"包[点點]", "site"),
    (r"下包|放包|装包|安包", "plant the spike"),
    (r"拆包|解包", "defuse the spike"),
    (r"中路|中央路|中间", "mid"),
    (r"绕后|偷后|抄后", "flank"),
    (r"转点|换点|轮转", "rotate"),
    (r"经济局|省钱局|存钱局", "eco round"),
    (r"快攻|强推|rush", "rush"),
    (r"架枪|卡点|守点", "hold the angle"),
    (r"残血|血皮|低血", "low hp"),
    (r"满血", "full hp"),
    (r"大招|终极技能", "ultimate"),
    (r"烟雾弹|烟雾|封烟", "smoke"),
    (r"闪光弹|闪光|闪", "flash"),
    (r"撤退|后撤|撤", "fall back"),
    (r"集火|打他", "focus fire"),
    (r"报点", "call out"),
    (r"换血", "trade"),
    (r"掉包|包掉了", "spike is down"),
    (r"守包", "hold the spike"),
    (r"给我奶一口|奶一口|给我奶|奶我|回血|加血|治疗", "heal me"),
    (r"拉人|复活", "revive"),
    (r"探点|探信息", "get info"),
]

_COMPILED = [(re.compile(p), r) for p, r in ZH_TERMS]


def normalize_zh(text: str) -> str:
    """把中文游戏口语换成英文术语（含英雄名），方便机翻。"""
    from .agents import zh_names_to_en
    out = zh_names_to_en(text)
    for pattern, repl in _COMPILED:
        out = pattern.sub(lambda m, r=repl: " " + m.expand(r) + " ", out)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\s+([，。！？、,.!?])", r"\1", out)
    out = re.sub(r"([，。！？、])\s+", r"\1", out)
    return out.strip()


def has_term(text: str) -> bool:
    return any(p.search(text) for p, _ in _COMPILED)

# ---------------------------------------------------------------- 反向：英文黑话 -> 中文说法
EN_TERMS: list[tuple[str, str]] = [
    (r"\bone shot\b|\bone tap\b|\bone hp\b|\blit\b", "残血"),
    (r"\beco( round)?\b", "经济局"),
    (r"\brush(ing)?\b", "快攻"),
    (r"\bflank(ing)?\b", "绕后"),
    (r"\brotat(e|ing)\b", "转点"),
    (r"\bplant(ing)?\b", "下包"),
    (r"\bdefus(e|ing)\b", "拆包"),
    (r"\bnice shot\b", "好枪"),
    (r"\bgood game|\bgg\b", "打得好"),
    (r"\bhold(ing)? the angle\b", "架枪"),
    (r"\bmid\b", "中路"),
    (r"\b([ABC])\s*site\b", r"\1点"),
    (r"\bspike\b", "包"),
    (r"\bult(imate)?\b", "大招"),
    (r"\bsmoke[sd]?\b", "烟雾"),
    (r"\bflash(es|ed)?\b", "闪光"),
    (r"\bfall back\b|\bfalling back\b", "后撤"),
]

_EN_TERMS_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in EN_TERMS]


def normalize_en(text: str) -> str:
    """英文黑话 -> 中文说法，让中文译文更像玩家说话。"""
    out = text
    for pattern, repl in _EN_TERMS_COMPILED:
        out = pattern.sub(lambda m, r=repl: " " + r + " ", out)
    out = re.sub(r"[ \t]+", " ", out)
    return out.strip()

# ---------------------------------------------------------------- 中文译文润色
ZH_POLISH: list[tuple[str, str]] = [
    # —— spike / 下包 ——
    ("炸弹已安放", "包已下好"),
    ("正在安放", "正在下包"),
    ("安放尖刺", "下包"),
    ("安放钉子", "下包"),
    ("插尖刺", "下包"),
    ("插钉子", "下包"),
    ("种钉子", "下包"),
    ("种植", "下包"),
    ("被种植", "已下好"),
    ("已安放", "已下好"),
    ("尖刺", "爆能器"),
    ("钉子", "包"),
    ("拆除", "拆包"),
    # —— 血量 ——
    ("只有一个百分点", "残血"),
    ("低血量", "残血"),
    ("血量低", "残血"),
    ("是一个低", "是残血"),
    ("一个低", "一个残血"),
    ("是一击", "残血"),
    ("是一枪", "残血"),
    ("一击", "一枪"),
    # —— 地图 / 战术 ——
    ("旋转", "转点"),
    ("正在赶来", "在冲"),
    ("经济回合", "经济局"),
    ("节约回合", "经济局"),
    ("中间路", "中路"),
    ("中央路", "中路"),
    ("侧翼", "绕后"),
    ("后方包抄", "绕后"),
    ("B网站", "B点"),
    ("A网站", "A点"),
    # —— 其它 ——
    ("好球", "好枪"),
]

_ZH_POLISH_RE = [(re.compile(p), r) for p, r in ZH_POLISH]


def polish_zh(text: str) -> str:
    """把机翻出来的生硬说法换成玩家习惯的讲法。"""
    out = text
    for pattern, repl in _ZH_POLISH_RE:
        out = pattern.sub(repl, out)
    return out
