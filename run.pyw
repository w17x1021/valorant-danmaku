"""桌面快捷方式的启动入口（用 pythonw 运行，不弹黑框）。

任何启动期异常都会写进 logs/startup_error.log 并弹窗，避免"双击没反应"。

另外做了**单实例保护**：已经在运行时，再次双击快捷方式只会把已开的窗口叫到前面，
不会再开第二份（否则 OCR 和语音会各跑一遍，弹幕出现重复）。
"""
import ctypes
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

MUTEX_NAME = "Local\\ValorantDanmakuTranslator.SingleInstance"
WINDOW_TITLE = "瓦罗兰特 · 实时翻译助手"

_handle = None


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.CreateMutexW.restype = ctypes.c_void_p


def _acquire() -> bool:
    """抢单实例锁；已经有实例返回 False。"""
    global _handle
    _handle = _kernel32.CreateMutexW(None, 0, MUTEX_NAME)
    return ctypes.get_last_error() != 183      # ERROR_ALREADY_EXISTS


def _focus_existing() -> bool:
    """把已经在跑的那个窗口叫到最前面。"""
    u32 = ctypes.windll.user32
    for title in (WINDOW_TITLE, "我说的话 · 中 → 日 / 英"):
        hwnd = u32.FindWindowW(None, title)
        if hwnd:
            u32.ShowWindow(hwnd, 9)            # SW_RESTORE
            u32.SetForegroundWindow(hwnd)
            try:                               # 有些系统不让抢焦点，闪一下任务栏
                u32.FlashWindow(hwnd, True)
            except Exception:  # noqa: BLE001
                pass
            return True
    return False


def _report(msg: str) -> None:
    try:
        (ROOT / "logs").mkdir(exist_ok=True)
        (ROOT / "logs" / "startup_error.log").write_text(msg, encoding="utf-8")
    except OSError:
        pass
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("瓦罗兰特翻译助手 启动失败",
                             msg[-1500:] + "\n\n完整日志：logs\\startup_error.log")
        root.destroy()
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    try:
        if not _acquire():
            if not _focus_existing():
                _report("程序已经在运行（没找到窗口，可能还藏在后台）。\n"
                        "请在任务管理器里结束 pythonw.exe 后重试。")
            return 0
        from app.main import main as app_main
        return app_main()
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        _report(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
