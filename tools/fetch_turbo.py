"""带重试地下载 large-v3-turbo（hf-mirror 会限流，多试几次）。"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / ".venv" / "Lib" / "site-packages"
for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cuda_nvrtc/bin"):
    p = SITE / sub
    if p.exists():
        os.add_dll_directory(str(p))
        os.environ["PATH"] = str(p) + os.pathsep + os.environ.get("PATH", "")

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

CANDIDATES = ["Systran/faster-whisper-large-v3-turbo",
              "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
              "deepdml/faster-whisper-large-v3-turbo-ct2"]

if __name__ == "__main__":
    from huggingface_hub import snapshot_download
    for attempt in range(6):
        for repo in CANDIDATES:
            try:
                t0 = time.time()
                path = snapshot_download(repo, cache_dir=str(ROOT / "models"),
                                         allow_patterns=["*.json", "*.bin", "*.txt"])
                print(f"OK {repo} -> {path} in {time.time()-t0:.0f}s", flush=True)
                sys.exit(0)
            except Exception as exc:  # noqa: BLE001
                print(f"try{attempt} {repo}: {type(exc).__name__} {str(exc)[:100]}", flush=True)
        time.sleep(20 + attempt * 15)
    print("FAILED all", flush=True)
    sys.exit(1)
