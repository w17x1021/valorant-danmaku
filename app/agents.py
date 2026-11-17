"""英雄名映射：中文昵称/国服名 ⇄ 英文 ⇄ 日文片假名。

社区里几乎没人喊官方译名：钱包=Chamber、奶妈=Sage、火男=Phoenix、炸弹妹=Raze。
这里做双向替换：
* 说中文 → 先把昵称换成英文英雄名，再翻译（机翻认得 Chamber，不认得「钱包」）
* 队友说英文/日文 → 中文译文里把 Jett / チェンバー 换成「捷风 / 尚勃勒」
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Agent:
    en: str
    cn: str
    ja: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


AGENTS: tuple[Agent, ...] = (
    Agent("Jett", "捷风", "ジェット", ("捷特", "风女", "空姐")),
    Agent("Sage", "贤者", "セージ", ("奶妈", "魏凌萤", "魏玲莹", "圣者", "奶婆")),
    Agent("Sova", "苏瓦", "ソーヴァ", ("索瓦", "苏瓦", "猫头鹰")),
    Agent("Phoenix", "不死鸟", "フェニックス", ("火男", "凤凰", "火哥")),
    Agent("Reyna", "蕾娜", "レイナ", ("雷娜", "女王", "吸血")),
    Agent("Raze", "雷兹", "レイズ", ("炸弹妹", "炸弹人", "炮妹")),
    Agent("Breach", "铁臂", "ブリーチ", ("铁壁", "震荡")),
    Agent("Cypher", "零", "サイファー", ("赛法", "摄像头", "老六")),
    Agent("Omen", "幽影", "オーメン", ("幽灵", "黑影")),
    Agent("Killjoy", "奇乐", "キルジョイ", ("琴乐", "炮台妹", "工程师")),
    Agent("Skye", "斯凯", "スカイ", ("思凯", "鸟女", "训鹰")),
    Agent("Yoru", "夜露", "ヨル", ("夜路", "传送")),
    Agent("Astra", "星礈", "アストラ", ("星神", "星妈")),
    Agent("KAY/O", "KAY/O", "KAY/O", ("凯欧", "机器人", "凯")),
    Agent("Chamber", "尚勃勒", "チェンバー", ("尚伯乐", "钱包", "商伯乐")),
    Agent("Neon", "霓虹", "ネオン", ("闪电", "电女")),
    Agent("Fade", "黑梦", "フェイド", ("菲德", "黑女")),
    Agent("Harbor", "海神", "ハーバー", ("水男", "海尔博")),
    Agent("Gekko", "盖可", "ゲッコー", ("盖科", "小黄")),
    Agent("Deadlock", "铁锁", "デッドロック", ("死锁", "铁丝")),
    Agent("Iso", "壹决", "アイソ", ("一决", "伊索")),
    Agent("Clove", "暮蝶", "クローヴ", ("克洛夫", "蝶")),
    Agent("Vyse", "薇丝", "ヴァイス", ("维斯", "薇斯")),
    Agent("Tejo", "泰乔", "テホ", ("特乔",)),
    Agent("Waylay", "幻棱", "ウェイレイ", ("幻菱", "威雷")),
    Agent("Brimstone", "布史东", "ブリムストーン", ("烟男", "大烟", "老布")),
)

# 中文 -> 英文英雄名（单字名不进表，避免「零伤害」被替换）
_ZH_TO_EN: dict[str, str] = {}
for _a in AGENTS:
    for _name in (_a.cn, *_a.aliases):
        if len(_name) >= 2:
            _ZH_TO_EN[_name] = _a.en

# 英文 -> 中文（大小写敏感，避免 breach 这种普通词被误伤）
_EN_TO_ZH: dict[str, str] = {a.en: a.cn for a in AGENTS}
_JA_TO_ZH: dict[str, str] = {a.ja: a.cn for a in AGENTS if a.ja}

_ZH_KEYS = sorted(_ZH_TO_EN, key=len, reverse=True)
_JA_KEYS = sorted(_JA_TO_ZH, key=len, reverse=True)
_EN_KEYS = sorted(_EN_TO_ZH, key=len, reverse=True)


def zh_names_to_en(text: str) -> str:
    """「钱包在B点」->「Chamber 在 B 点」，方便机翻成英/日。"""
    out = text
    for key in _ZH_KEYS:
        if key in out:
            out = out.replace(key, f" {_ZH_TO_EN[key]} ")
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\s+([，。！？、])", r"\1", out)
    out = re.sub(r"([，。！？、])\s+", r"\1", out)
    return out.strip()


def names_to_zh(text: str) -> str:
    """英文/日文英雄名 -> 国服译名（用在中文译文上）。"""
    out = text
    for key in _EN_KEYS:
        out = re.sub(rf"\b{re.escape(key)}\b", _EN_TO_ZH[key], out)
    for key in _JA_KEYS:
        out = out.replace(key, _JA_TO_ZH[key])
    return out


def en_names_to_ja(text: str) -> str:
    """英文英雄名 -> 日文片假名，让日文译文更像日本玩家的说法。"""
    out = text
    for agent in AGENTS:
        if not agent.ja or agent.en == agent.ja:
            continue
        out = re.sub(rf"\b{re.escape(agent.en)}\b", agent.ja, out)
    return out


def agent_words() -> list[str]:
    """给语音识别词表用的常用说法。"""
    words: list[str] = []
    for a in AGENTS:
        words.extend([a.cn, a.en])
        words.extend(a.aliases)
    return words
