"""冒烟测试：开主面板 → 打开设置窗 → 打开「我说的话」→ 正常退出。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import App, enable_dpi_awareness

enable_dpi_awareness()
app = App()


def step_settings():
    try:
        from app.ui.settings import SettingsDialog
        dlg = SettingsDialog(app.panel, app)
        print("settings ok", flush=True)
        app.root.after(400, dlg.destroy)
    except Exception as exc:  # noqa: BLE001
        print("settings FAILED:", type(exc).__name__, exc, flush=True)


app.root.after(700, step_settings)
app.root.after(1400, app.open_selftalk)
app.root.after(2200, app.restart_selftalk)
app.root.after(3000, app.close_selftalk)
app.root.after(3600, app.quit)
app.run()
print("clean exit", flush=True)
