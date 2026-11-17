"""验证英雄台词过滤：该丢的丢，该留的留。"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Config
from app.voice.filters import is_agent_voice_line


def audio(sec: float, amp: float) -> np.ndarray:
    return (np.random.randn(int(16000 * sec)) * amp).astype(np.float32)


def main() -> None:
    cfg = Config()
    chat = audio(3, 0.02)      # 队友正常音量
    loud = audio(1.5, 0.12)    # 台词：响 6 倍

    cases = [
        ("Watch this!", loud, 0.02, True),
        ("Here comes the pain", loud, 0.02, True),
        ("They'll never know what hit them", loud, 0.02, True),
        ("B site two enemies", loud, 0.02, False),     # 报点必须保留
        ("push mid now", loud, 0.02, False),
        ("one shot one shot", loud, 0.02, False),
        ("Yeah alright", loud, 0.02, True),            # 又响又短、无战术词
        ("Yeah alright", chat, 0.02, False),           # 正常音量
        ("I'm going in", chat, 0.02, False),           # 正常音量、像正常说话
    ]
    ok = 0
    for text, a, rms, expect in cases:
        got = is_agent_voice_line(text, a, rms, cfg)
        mark = "OK " if got == expect else "!! "
        ok += got == expect
        print(f"{mark}{text!r:36s} 过滤={got!s:5s} 期望={expect}")
    print(f"\n{ok}/{len(cases)} 通过")

    # 关掉开关后一律不过滤
    cfg.filter_agent_lines = False
    print("关闭开关后 Watch this! ->", is_agent_voice_line("Watch this!", loud, 0.02, cfg))


if __name__ == "__main__":
    main()
