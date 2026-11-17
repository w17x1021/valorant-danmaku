"""语音开关来回切 5 次，确认不会卡死（之前 GPU 模式下关掉再开就卡住）。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import App, enable_dpi_awareness


def main() -> None:
    enable_dpi_awareness()
    app = App()
    log = []
    step = {"i": 0}

    def tick():
        i = step["i"]
        if i >= 10:
            print("\n".join(log), flush=True)
            app.root.after(300, app.quit)
            return
        t0 = time.time()
        app.toggle_voice()
        time.sleep(0.35)
        v = app.voice
        state = "none" if v is None else ("on" if v.active.is_set() else "off")
        log.append(f"toggle#{i+1}: state={state} status={getattr(v,'status',None)} "
                   f"{(time.time()-t0)*1000:.0f}ms")
        step["i"] += 1
        app.root.after(500, tick)

    app.root.after(2500, tick)
    app.run()
    print("exited cleanly", flush=True)


if __name__ == "__main__":
    main()
