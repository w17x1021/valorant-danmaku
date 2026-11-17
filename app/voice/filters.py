"""过滤「英雄自己说话」的台词。

游戏音频是混在一起的：枪声、技能音、以及英雄的语音台词（"Watch this!" 之类）
都会从环回设备里录进来，被当成队友说话去翻译。

这里加两道路障（都很保守，宁可漏掉台词，也不误删队友的报点）：

1. **台词库精确匹配**：只收那些又长又好认的整句，正常人报点不会这么说。
2. **音量判据**：英雄台词是"贴脸"播的，比语音频道里队友的声音响得多；
   如果一句又响又短，而且不含任何战术词（点/敌人/推/包…），就当作台词丢掉。
"""
from __future__ import annotations

import re

SR = 16000

# 只收「整句、够长、不像报点」的台词，避免误伤
AGENT_PHRASES = {
    # 英文
    "watch this", "here comes the pain", "who's next", "you should see the other guy",
    "they'll never know what hit them", "i'm not here to make friends",
    "let's have some fun", "you're gonna love this", "no one can stop me",
    "don't get in my way", "you can't hit what you can't see",
    "another one bites the dust", "say hello to my little friend",
    "i'm in the zone", "time to play", "let's go", "i got this", "nice and easy",
    "you've got to be kidding me", "that's what i'm talking about",
    "hold my beer", "check this out", "who wants some",
    # 日文（够长的才会收）
    "いくよ", "見てて", "任せて", "やったるで", "ちょっと待って",
}

# 含这些词就不当台词（保护报点）
TACTICAL = (
    "site", "b site", "a site", "mid", "spike", "push", "rotate", "flank", "enemy",
    "enemies", "one shot", "low", "eco", "save", "retake", "defuse", "plant",
    "点", "中", "路", "包", "敌人", "人", "血", "推", "打", "来", "退", "撤",
    "サイト", "敵", "スパイク", "設置", "解除",
)

_PUNCT = re.compile(r"[^\w\s\u3040-\u30ff\u3400-\u9fff]+")
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    t = _PUNCT.sub(" ", text.lower())
    return _SPACE.sub(" ", t).strip()


def _rms(audio) -> float:
    try:
        import numpy as np
        if audio is None or len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    except Exception:  # noqa: BLE001
        return 0.0


def is_agent_voice_line(text: str, audio=None, chat_rms: float = 0.0,
                        cfg=None) -> bool:
    """True = 认为这句是英雄台词，应当丢掉。"""
    if cfg is not None and not bool(getattr(cfg, "filter_agent_lines", True)):
        return False
    norm = normalize(text)
    if not norm:
        return False

    # 1) 台词库
    if norm in AGENT_PHRASES:
        return True
    for phrase in AGENT_PHRASES:
        if len(phrase) >= 12 and norm.startswith(phrase):
            return True

    # 2) 不含战术词 + 又响又短 → 台词
    if any(w in norm for w in TACTICAL):
        return False
    if not chat_rms or audio is None:
        return False
    dur = len(audio) / float(SR)
    level = _rms(audio)
    gain = float(getattr(cfg, "agent_line_gain", 2.4) if cfg is not None else 2.4)
    return bool(dur <= 3.2 and level > chat_rms * max(1.6, gain))
