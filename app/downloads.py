"""下载队列：语音包 / 语言包 / 显卡加速包共用一个后台队列。

为什么要单独一层：
* 以前下载是一次性的 `snapshot_download`，全程只有一句"正在下载…"，
  几百 MB 的包看不到进度，网络卡住也不知道是真的在走还是死了；
* 现在所有下载都排进同一个队列，串行执行（不抢带宽），每个任务实时记录
  已下载字节、瞬时速度、剩余时间，UI 只需要定时读 `manager().snapshot()`。

线程模型：工作线程只改 Task 里的数字，tkinter 永远在主线程里读快照，
所以不会出现跨线程碰控件的问题。
"""
from __future__ import annotations

import itertools
import os
import threading
import time
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

WAITING = "waiting"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

STATUS_TEXT = {
    WAITING: "排队中",
    RUNNING: "下载中",
    DONE: "已完成",
    FAILED: "失败",
    CANCELLED: "已取消",
}

SPEED_WINDOW = 2.5          # 算瞬时速度的滑动窗口（秒）
SPEED_MIN_SAMPLES = 2


class Cancelled(RuntimeError):
    """任务被用户取消。"""


CHUNK = 256 * 1024
USER_AGENT = "valorant-danmaku/1.0 (+https://github.com/w17x1021/valorant-danmaku)"


def fetch_file(url: str, dest: Path, expected: int = 0, task: "Task | None" = None,
               attempts: int = 3, timeout: float = 60.0) -> None:
    """下载单个文件到 dest：先写 `.part`，支持 Range 续传，逐块汇报进度。

    expected 是已知的文件字节数（0 = 不知道），用来校验和算百分比。
    """
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = ""
    for attempt in range(attempts):
        if task:
            task.check_cancel()
        try:
            have = part.stat().st_size if part.exists() else 0
            if expected and have > expected:
                part.unlink(missing_ok=True)
                have = 0
            if expected and have == expected:
                part.replace(dest)
                return
            headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
            if have:
                headers["Range"] = f"bytes={have}-"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                mode = "ab"
                skip = have
                if have and getattr(resp, "status", 200) != 206:
                    # 服务器不认 Range：从头写，已经记过的字节不重复上报
                    mode, have = "wb", 0
                with open(part, mode) as out:
                    while True:
                        if task:
                            task.check_cancel()
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        out.write(chunk)
                        have += len(chunk)
                        if skip:
                            cut = min(skip, len(chunk))
                            skip -= cut
                            if task and cut < len(chunk):
                                task.advance(len(chunk) - cut)
                        elif task:
                            task.advance(len(chunk))
            size = part.stat().st_size
            if expected and size != expected:
                raise OSError(f"文件大小不对：{size} / {expected}")
            part.replace(dest)
            return
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < attempts:
                time.sleep(min(3.0, 0.8 * (attempt + 1)))
    raise RuntimeError(last or "下载失败")


def dir_size(path: Path) -> int:
    """目录里所有文件的总字节数（算 PaddleOCR 这种没有回调整的下载用）。"""
    total = 0
    try:
        for f in Path(path).rglob("*"):
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                continue
    except OSError:
        pass
    return total


def fmt_size(size: float) -> str:
    """字节数 -> 1.2 MB 这种。"""
    size = max(0.0, float(size or 0))
    if size < 1024:
        return f"{size:.0f} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 / 1024:.1f} MB"
    return f"{size / 1024 ** 3:.2f} GB"


def fmt_speed(speed: float) -> str:
    if not speed or speed <= 0:
        return "—"
    return f"{fmt_size(speed)}/s"


def fmt_eta(seconds: float | None) -> str:
    if seconds is None or seconds <= 0 or seconds == float("inf"):
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} 秒"
    if seconds < 3600:
        return f"{seconds // 60} 分 {seconds % 60} 秒"
    return f"{seconds // 3600} 小时 {(seconds % 3600) // 60} 分"


@dataclass
class Task:
    """一个下载任务。数字都不是精确同步的，UI 读个大概就够。"""

    id: int
    title: str
    detail: str = ""
    total: int = 0                      # 总字节数，0 = 还不知道
    done: int = 0
    status: str = WAITING
    note: str = ""                      # 当前在干什么（第几个文件 / 正在解压…）
    error: str = ""
    created: float = field(default_factory=time.time)
    started: float = 0.0
    finished: float = 0.0
    cancel: threading.Event = field(default_factory=threading.Event)
    _samples: deque = field(default_factory=deque, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _fn: Callable | None = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------------
    # 工作线程调用
    def set_total(self, total: int, add: bool = False) -> None:
        with self._lock:
            total = max(0, int(total or 0))
            self.total = (self.total + total) if add else total

    def advance(self, n: int) -> None:
        """新增 n 字节（已下载）。"""
        if n <= 0:
            return
        with self._lock:
            self._add(n)

    def set_done(self, n: int) -> None:
        """直接报告绝对进度（用于没法按字节回调的下载器，比如 PaddleOCR）。"""
        with self._lock:
            n = max(0, int(n or 0))
            if n > self.done:
                self._add(n - self.done)

    def _add(self, n: int) -> None:
        self.done += n
        now = time.time()
        self._samples.append((now, self.done))
        while len(self._samples) > 2 and self._samples[1][0] < now - SPEED_WINDOW:
            self._samples.popleft()

    def set_note(self, text: str) -> None:
        with self._lock:
            self.note = text

    @property
    def cancelled(self) -> bool:
        return self.cancel.is_set()

    def check_cancel(self) -> None:
        if self.cancel.is_set():
            raise Cancelled("已取消")

    # ------------------------------------------------------------------
    # UI 线程读
    @property
    def speed(self) -> float:
        """最近 2.5 秒的平均速度（字节/秒）。"""
        with self._lock:
            samples = list(self._samples)
        if len(samples) < SPEED_MIN_SAMPLES:
            return 0.0
        (t0, b0), (t1, b1) = samples[0], samples[-1]
        span = t1 - t0
        if span <= 0.05:
            return 0.0
        return max(0.0, (b1 - b0) / span)

    @property
    def fraction(self) -> float | None:
        """0~1；总大小未知时返回 None（UI 画不确定进度条）。"""
        with self._lock:
            total, done = self.total, self.done
        if total <= 0:
            return None
        return max(0.0, min(1.0, done / total))

    @property
    def eta(self) -> float | None:
        speed = self.speed
        with self._lock:
            total, done = self.total, self.done
        if speed <= 0 or total <= 0 or done >= total:
            return None
        return (total - done) / speed

    def snapshot(self) -> dict:
        frac = self.fraction
        return {
            "id": self.id,
            "title": self.title,
            "detail": self.detail,
            "status": self.status,
            "status_text": STATUS_TEXT.get(self.status, self.status),
            "total": self.total,
            "done": self.done,
            "fraction": frac,
            "speed": self.speed if self.status == RUNNING else 0.0,
            "eta": self.eta,
            "note": self.note,
            "error": self.error,
        }


class DownloadManager:
    """串行下载队列。add() 之后工作线程自己排队干活。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: list[Task] = []
        self._queue: deque[Task] = deque()
        self._cur: Task | None = None
        self._ids = itertools.count(1)
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    def add(self, title: str, fn: Callable[[Task], None], detail: str = "") -> Task:
        """排一个任务。fn(task) 在工作线程里跑，抛异常=失败。"""
        with self._lock:
            task = Task(id=next(self._ids), title=title, detail=detail)
            task._fn = fn
            self._tasks.append(task)
            self._queue.append(task)
            thread = self._thread
        if thread is None or not thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name="downloads")
            self._thread.start()
        return task

    # ------------------------------------------------------------------
    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    self._thread = None
                    return
                task = self._queue.popleft()
                self._cur = task
                task.status = RUNNING
                task.started = time.time()
            try:
                if task._fn is not None:
                    task._fn(task)
                with self._lock:
                    if task.status == RUNNING:
                        task.status = DONE
            except Cancelled:
                with self._lock:
                    task.status = CANCELLED
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    if task.cancel.is_set():
                        task.status = CANCELLED
                    else:
                        task.status = FAILED
                        task.error = f"{type(exc).__name__}: {exc}"
            finally:
                with self._lock:
                    task.finished = time.time()
                    if self._cur is task:
                        self._cur = None
                    task._samples.clear()

    # ------------------------------------------------------------------
    def cancel(self, task_id: int) -> None:
        """取消排队中 / 下载中的任务。"""
        with self._lock:
            for task in self._tasks:
                if task.id != task_id:
                    continue
                task.cancel.set()
                if task.status == WAITING:
                    task.status = CANCELLED
                    try:
                        self._queue.remove(task)
                    except ValueError:
                        pass
                return

    def cancel_all(self) -> None:
        with self._lock:
            ids = [t.id for t in self._tasks
                   if t.status in (WAITING, RUNNING)]
        for task_id in ids:
            self.cancel(task_id)

    def clear_finished(self) -> None:
        with self._lock:
            self._tasks = [t for t in self._tasks
                           if t.status in (WAITING, RUNNING)]

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks if t.status in (WAITING, RUNNING))

    def current(self) -> Task | None:
        with self._lock:
            return self._cur

    def snapshot(self) -> dict:
        """给 UI 用的整表快照。"""
        with self._lock:
            tasks = list(self._tasks)
        rows = [t.snapshot() for t in tasks]
        running = [r for r in rows if r["status"] == RUNNING]
        waiting = [r for r in rows if r["status"] == WAITING]
        return {
            "tasks": rows,
            "running": len(running),
            "queued": len(waiting),
            "speed": sum(r["speed"] for r in running),
        }


_MANAGER = DownloadManager()


def manager() -> DownloadManager:
    """全局唯一的下载队列。"""
    return _MANAGER
