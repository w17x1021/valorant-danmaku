"""直接操作 Windows 剪贴板。

Tk 的 clipboard_append 是"延迟渲染"：要等目标程序来要数据时，Tk 事件循环还得空着才能回；
游戏在前台时事件循环经常忙，粘出来就是空的。这里用 Win32 API 直接把数据塞进去，
放完就不归程序管了，切窗口/关程序都不丢。
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

_u32 = ctypes.windll.user32
_k32 = ctypes.windll.kernel32

_u32.OpenClipboard.argtypes = [wintypes.HWND]
_u32.OpenClipboard.restype = wintypes.BOOL
_u32.EmptyClipboard.restype = wintypes.BOOL
_u32.CloseClipboard.restype = wintypes.BOOL
_u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_u32.SetClipboardData.restype = wintypes.HANDLE
_u32.GetClipboardData.argtypes = [wintypes.UINT]
_u32.GetClipboardData.restype = wintypes.HANDLE
_k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_k32.GlobalAlloc.restype = wintypes.HGLOBAL
_k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_k32.GlobalLock.restype = ctypes.c_void_p
_k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]


def _open(retries: int = 12) -> bool:
    for _ in range(retries):
        if _u32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def set_text(text: str) -> bool:
    """写字符串进剪贴板，成功返回 True。"""
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not _open():
        return False
    try:
        _u32.EmptyClipboard()
        handle = _k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        ptr = _k32.GlobalLock(handle)
        if not ptr:
            _k32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        _k32.GlobalUnlock(handle)
        if not _u32.SetClipboardData(CF_UNICODETEXT, handle):
            _k32.GlobalFree(handle)
            return False
        return True          # 数据交给系统了，不要 free
    finally:
        _u32.CloseClipboard()


def get_text() -> str:
    if not _open():
        return ""
    try:
        handle = _u32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = _k32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _k32.GlobalUnlock(handle)
    finally:
        _u32.CloseClipboard()
