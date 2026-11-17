"""验证弹幕去重：同一句连发 3 次只出一条，新的一句追加在后面。"""
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import App, enable_dpi_awareness
from app.ocr.chat_reader import ChatEvent
from app.translator import Translation


def watchdog(seconds=45):
    def kill():
        time.sleep(seconds)
        print("WATCHDOG 超时强退", flush=True)
        os._exit(2)
    threading.Thread(target=kill, daemon=True).start()


def main() -> None:
    watchdog()
    enable_dpi_awareness()
    app = App()

    def go():
        ev = ChatEvent("text", "Kirito", "Two enemies at B", "en")
        res = Translation(text="两个敌人在B点", provider="test", src_lang="en")
        for _ in range(3):
            app._render(ev, res)
        texts = [e["text"] for e in app.overlay.entries]
        print("同一句连发3次 ->", texts, flush=True)

        app._render(ChatEvent("text", "Kirito", "Rotate now", "en"),
                    Translation(text="现在转点", provider="test", src_lang="en"))
        texts = [e["text"] for e in app.overlay.entries]
        print("再来一句新的   ->", texts, flush=True)
        app.root.after(300, app.quit)

    app.root.after(1200, go)
    app.run()
    print("done", flush=True)


if __name__ == "__main__":
    main()
