"""语音播报：把译文用 Windows 自带的 TTS 念出来。

给「游戏开独占全屏、任何覆盖层都画不上去」的情况兜底——看不见字幕，至少听得见。
用一个常驻 PowerShell 进程调 System.Speech，避免每句话都启动一次进程。
"""
from __future__ import annotations

import queue
import subprocess
import threading

WORKER = r"""
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $env:VDM_TTS_VOICE
if ($voice) {
  try { $synth.SelectVoice($voice) } catch { }
} else {
  try {
    $zh = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "zh*" } | Select-Object -First 1
    if ($zh) { $synth.SelectVoice($zh.VoiceInfo.Name) }
  } catch { }
}
try { $synth.Rate = [int]$env:VDM_TTS_RATE } catch { }
[Console]::Out.WriteLine("READY")
[Console]::Out.Flush()
while ($null -ne ($line = [Console]::In.ReadLine())) {
  $t = $line.Trim()
  if ($t.Length -gt 0) {
    try { $synth.Speak($t) } catch { }
  }
  [Console]::Out.WriteLine("OK")
  [Console]::Out.Flush()
}
"""


class Speaker:
    def __init__(self, cfg, on_status=None):
        self.cfg = cfg
        self.on_status = on_status or (lambda *_: None)
        self.q: queue.Queue[str] = queue.Queue(maxsize=8)
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self.enabled = bool(getattr(cfg, "tts_enabled", False))
        self.error = ""
        if self.enabled:
            self.start()

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._proc is not None:
            return
        env = None
        try:
            import os
            env = dict(os.environ)
            env["VDM_TTS_VOICE"] = str(getattr(self.cfg, "tts_voice", "") or "")
            env["VDM_TTS_RATE"] = str(int(getattr(self.cfg, "tts_rate", 1)))
            self._proc = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-Command", WORKER],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", errors="replace", bufsize=1, env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            line = self._proc.stdout.readline().strip() if self._proc.stdout else ""
            if line != "READY":
                self.error = "TTS 启动失败"
                self._proc = None
                return
            threading.Thread(target=self._run, daemon=True, name="tts").start()
        except Exception as exc:  # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"
            self._proc = None

    def _run(self) -> None:
        while True:
            text = self.q.get()
            if text is None:
                break
            proc = self._proc
            if proc is None or proc.poll() is not None or proc.stdin is None:
                break
            try:
                with self._lock:
                    proc.stdin.write(text.replace("\n", " ") + "\n")
                    proc.stdin.flush()
                    if proc.stdout is not None:
                        proc.stdout.readline()      # 等这一句念完
            except (OSError, ValueError):
                break

    # ------------------------------------------------------------------
    def say(self, text: str) -> None:
        if not self.enabled or not text:
            return
        text = text.strip()
        limit = int(getattr(self.cfg, "tts_max_chars", 60) or 60)
        if len(text) > limit:
            text = text[:limit]
        try:
            self.q.put_nowait(text)
        except queue.Full:
            try:                                  # 丢最旧的一条，保证播的是最新的
                self.q.get_nowait()
                self.q.put_nowait(text)
            except queue.Empty:
                pass

    def set_enabled(self, flag: bool) -> None:
        self.enabled = bool(flag)
        if flag:
            self.start()

    def close(self) -> None:
        try:
            self.q.put_nowait(None)
        except queue.Full:
            pass
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except OSError:
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
