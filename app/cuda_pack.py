r"""显卡加速包（cuBLAS + cuDNN）的按需下载与安装。

安装包里不带这 1.8GB 的库，用户点「下载显卡加速包」时才从 pip 镜像拉 wheel，
直接把里面的 nvidia/... 目录解到 <程序目录>\cuda\，启动时会自动加进 DLL 搜索路径。
"""
from __future__ import annotations

import json
import threading
import urllib.request
import zipfile
from pathlib import Path

MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/pypi/{pkg}/json",
    "https://pypi.org/pypi/{pkg}/json",
]

PACKAGES = ["nvidia-cublas-cu12", "nvidia-cudnn-cu12"]


def cuda_dir() -> Path:
    from .config import project_root
    return project_root() / "cuda"


def _wheel_url(pkg: str) -> str:
    last = ""
    for tpl in MIRRORS:
        try:
            with urllib.request.urlopen(tpl.format(pkg=pkg), timeout=20) as fh:
                data = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            continue
        cands = [f for f in data.get("urls", [])
                 if f["filename"].endswith(".whl") and "win_amd64" in f["filename"]]
        if cands:
            cands.sort(key=lambda f: f["filename"])
            return cands[-1]["url"]
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


def _download(url: str, dest: Path, progress) -> None:
    with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)


def install(progress=None) -> Path:
    """下载并解压到 <程序目录>\\cuda。progress(0~1) 可选。"""
    target = cuda_dir()
    target.mkdir(parents=True, exist_ok=True)
    tmp = target / "_dl"
    tmp.mkdir(exist_ok=True)
    try:
        for i, pkg in enumerate(PACKAGES):
            url = _wheel_url(pkg)

            def ratio(r: float, idx: int = i) -> None:
                if progress:
                    progress((idx + r) / len(PACKAGES))

            whl = tmp / f"{pkg}.whl"
            _download(url, whl, ratio)
            with zipfile.ZipFile(whl) as zf:
                for name in zf.namelist():
                    if name.startswith("nvidia/") and "/bin/" in name and name.endswith(".dll"):
                        zf.extract(name, target)
            whl.unlink(missing_ok=True)
    finally:
        for f in tmp.glob("*"):
            f.unlink(missing_ok=True)
        try:
            tmp.rmdir()
        except OSError:
            pass
    return target


def install_async(done, progress=None) -> threading.Thread:
    def run() -> None:
        try:
            path = install(progress)
            done(True, str(path))
        except Exception as exc:  # noqa: BLE001
            done(False, str(exc))

    t = threading.Thread(target=run, daemon=True, name="cuda-dl")
    t.start()
    return t
