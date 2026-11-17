"""Windows OCR 桥接：常驻一个 Windows PowerShell 5.1 子进程，复用 WinRT OCR 引擎。

为什么走 PowerShell：Windows.Media.Ocr 是 WinRT 接口，Python 侧没有可靠的
免安装调用方式，而 Windows 自带的 PowerShell 5.1 可以直接投影 WinRT 类型。
常驻进程把引擎和语言包加载一次，单帧识别约 20~60ms。

图片以 base64 通过 stdin 传过去（不落盘），避免 UWP 文件访问限制。
"""
from __future__ import annotations

import base64
import io
import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


def powershell_exe() -> str:
    """固定用 Windows PowerShell 5.1：WinRT 投影只有 5.1 稳，pwsh 7 没有。

    不能只写 "powershell.exe" 交给 PATH —— 精简过 PATH 的机器（或被别的
    PowerShell 抢先的会话）会直接 FileNotFoundError，整个 OCR 起不来。
    """
    cand = Path(os.environ.get("SystemRoot", r"C:\Windows")) / \
        "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if cand.exists():
        return str(cand)
    return "powershell.exe"


@dataclass
class OcrLine:
    lang: str
    text: str
    x: int
    y: int
    w: int
    h: int


class WindowsOcr:
    def __init__(self, worker: Path, langs: list[str], startup_timeout: float = 30.0):
        self.worker = Path(worker)
        self.langs = langs
        self._proc: subprocess.Popen | None = None
        self._q: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self.available: list[str] = []
        self.last_error = ""
        self._start(startup_timeout)

    # ------------------------------------------------------------------
    def _start(self, timeout: float) -> None:
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = subprocess.Popen(
            [powershell_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(self.worker)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creation,
        )
        self._q = queue.Queue()
        threading.Thread(target=self._reader, args=(self._proc, self._q),
                         daemon=True, name="ocr-stdout").start()
        try:
            hello = json.loads(self._q.get(timeout=timeout))
        except queue.Empty as exc:
            raise RuntimeError("OCR 工作进程启动超时") from exc
        if not hello.get("ready"):
            raise RuntimeError(f"OCR 工作进程启动失败: {hello}")
        self.available = hello.get("available", [])

    @staticmethod
    def _reader(proc: subprocess.Popen, q: queue.Queue) -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if line:
                q.put(line)
        q.put(None)

    # ------------------------------------------------------------------
    def recognize(self, image: Image.Image | str | Path, timeout: float = 10.0) -> list[OcrLine]:
        if not isinstance(image, Image.Image):
            image = Image.open(image)
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        payload = base64.b64encode(buf.getvalue()).decode("ascii")
        with self._lock:
            if self._proc is None or self._proc.poll() is not None:
                self._start(25)
            assert self._proc is not None and self._proc.stdin is not None
            req = json.dumps({"b64": payload, "langs": self.langs})
            try:
                self._proc.stdin.write(req + "\n")
                self._proc.stdin.flush()
                raw = self._q.get(timeout=timeout)
            except queue.Empty:
                self.last_error = "OCR 超时，重启工作进程"
                self.close()
                self._start(25)
                return []
            except (OSError, ValueError) as exc:
                self.last_error = f"OCR 管道异常: {exc}"
                self.close()
                return []
        if raw is None:
            self.last_error = "OCR 工作进程退出"
            self.close()
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self.last_error = f"OCR 返回非法 JSON: {raw[:120]}"
            return []
        if not data.get("ok"):
            self.last_error = data.get("error", "OCR 失败")
            return []
        return [OcrLine(l["lang"], l["text"], l["x"], l["y"], l["w"], l["h"])
                for l in data.get("lines", []) if l.get("text")]

    # ------------------------------------------------------------------
    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def list_ocr_languages(worker: Path) -> list[str]:
    ocr = WindowsOcr(worker, ["en-US"])
    try:
        return ocr.available
    finally:
        ocr.close()


if __name__ == "__main__":  # 手动调试
    w = Path(__file__).with_name("ocr_worker.ps1")
    o = WindowsOcr(w, ["en-US", "zh-Hans-CN"])
    print("available:", o.available)
    t0 = time.time()
    for _ in range(3):
        print(o.recognize(Path(__file__).parents[2] / "tools" / "_ocr_in.png"))
    print(f"{int((time.time()-t0)*1000)}ms / 3 次")
    o.close()
