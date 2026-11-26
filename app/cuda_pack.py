r"""显卡加速包（cuBLAS + cuDNN）的按需下载与安装。

安装包里不带这 1.8GB 的库，用户点「下载显卡加速包」时才从 pip 镜像拉 wheel，
直接把里面的 nvidia/... 目录解到 <程序目录>\cuda\，启动时会自动加进 DLL 搜索路径。

下载同样走 app.downloads 队列：能看到进度条、速度，断了还能续传。
"""
from __future__ import annotations

import json
import urllib.request
import zipfile
from pathlib import Path

from .downloads import fetch_file

MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/pypi/{pkg}/json",
    "https://pypi.org/pypi/{pkg}/json",
]

PACKAGES = ["nvidia-cublas-cu12", "nvidia-cudnn-cu12"]

USER_AGENT = "valorant-danmaku/1.0"


def cuda_dir() -> Path:
    from .config import project_root
    return project_root() / "cuda"


def _wheel_info(pkg: str) -> tuple[str, int]:
    """取某个包 win_amd64 wheel 的下载地址和大小。"""
    last = ""
    for tpl in MIRRORS:
        try:
            req = urllib.request.Request(tpl.format(pkg=pkg),
                                         headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=20) as fh:
                data = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            continue
        cands = [f for f in data.get("urls", [])
                 if f["filename"].endswith(".whl") and "win_amd64" in f["filename"]]
        if cands:
            cands.sort(key=lambda f: f["filename"])
            url = cands[-1]["url"]
            size = int(cands[-1].get("size") or 0)
            return url, size
        last = "没有 win_amd64 的 wheel"
    raise RuntimeError(f"取不到 {pkg} 的下载地址：{last}")


def installed() -> bool:
    base = cuda_dir() / "nvidia"
    return ((base / "cublas" / "bin").is_dir() and (base / "cudnn" / "bin").is_dir()
            and any((base / "cublas" / "bin").glob("*.dll")))


def installed_size_mb() -> float:
    base = cuda_dir()
    if not base.is_dir():
        return 0.0
    total = sum(f.stat().st_size for f in base.rglob("*") if f.is_file())
    return total / 1024 / 1024


def install(progress=None, task=None) -> Path:
    """下载并解压到 <程序目录>\\cuda。progress(0~1) 可选，task 用于队列进度。"""
    target = cuda_dir()
    target.mkdir(parents=True, exist_ok=True)
    tmp = target / "_dl"
    tmp.mkdir(exist_ok=True)

    plan = []
    for pkg in PACKAGES:
        url, size = _wheel_info(pkg)
        plan.append((pkg, url, size))
    if task:
        task.set_total(sum(size for _, _, size in plan))

    try:
        for i, (pkg, url, size) in enumerate(plan):
            if task:
                task.check_cancel()
                task.set_note(f"{pkg}（{i + 1}/{len(plan)}）")
            whl = tmp / f"{pkg}.whl"
            fetch_file(url, whl, size, task=task, timeout=120, attempts=2)
            if task:
                task.set_note(f"解压 {pkg} …")
            with zipfile.ZipFile(whl) as zf:
                for name in zf.namelist():
                    if name.startswith("nvidia/") and "/bin/" in name and name.endswith(".dll"):
                        zf.extract(name, target)
            whl.unlink(missing_ok=True)
            if progress:
                progress((i + 1) / len(plan))
    finally:
        for f in tmp.glob("*"):
            f.unlink(missing_ok=True)
        try:
            tmp.rmdir()
        except OSError:
            pass
    return target


def install_async(done, progress=None):
    """排进下载队列，返回 Task（见 app.downloads）。"""
    from .downloads import manager

    def job(task):
        try:
            path = install(progress=progress, task=task)
        except Exception as exc:  # noqa: BLE001
            if done:
                done(False, str(exc))
            raise
        if done:
            done(True, str(path))

    return manager().add("显卡加速包", job,
                         detail="cuBLAS + cuDNN（约 1.6 GB）")
