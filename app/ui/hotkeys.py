"""全局快捷键（RegisterHotKey），支持"第一个被占就自动换下一个"。"""
from __future__ import annotations

import ctypes
import queue
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CTRL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
CTRL_ALT = MOD_CTRL | MOD_ALT

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                               wintypes.UINT, wintypes.UINT]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT,
                                      wintypes.WPARAM, wintypes.LPARAM]

VK = {"F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
      "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B}


class GlobalHotkeys(threading.Thread):
    """spec: {热键id: [(修饰键, 虚拟键, 显示名), ...]}，按顺序尝试，第一个注册成功就用它。"""

    def __init__(self, spec: dict[int, list[tuple[int, int, str]]], out: queue.Queue):
        super().__init__(daemon=True, name="hotkeys")
        self.spec = spec
        self.out = out
        self.thread_id = 0
        self.bound: dict[int, str] = {}
        self.ready = threading.Event()

    def run(self) -> None:
        self.thread_id = int(kernel32.GetCurrentThreadId())
        for hid, candidates in self.spec.items():
            for mods, vk, label in candidates:
                if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                    self.bound[hid] = label
                    break
        self.ready.set()

        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                try:
                    self.out.put_nowait(int(msg.wParam))
                except queue.Full:
                    pass
        for hid in self.spec:
            user32.UnregisterHotKey(None, hid)

    def label(self, hid: int, fallback: str = "") -> str:
        return self.bound.get(hid, fallback)

    def stop(self) -> None:
        if self.thread_id:
            user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
