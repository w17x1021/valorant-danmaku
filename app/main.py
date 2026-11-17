"""程序入口：把 OCR 聊天识别、翻译、弹幕浮层串起来。"""
from __future__ import annotations

import ctypes
import json
import queue
import re
import sys
import threading
import time
import tkinter as tk
import traceback
from datetime import datetime
from pathlib import Path

from .config import Config, project_root
from .ocr.chat_reader import ChatEvent, ChatReader
from .ocr.win_ocr import WindowsOcr
from .translator import Translator
from .ui.overlay import RegionPicker, create_view
from .ui.theme import apply_ttk_style
from .tts import Speaker
from .ui.capture_picker import CapturePicker
from .ui.panel import ControlPanel
from .ui.settings import SettingsDialog

try:  # 语音是可选项，缺依赖时不能拖垮整个程序
    from .voice.listener import VoiceListener
    from .voice.selftalk import SelfTalk
    from .voice.asr import Asr
except Exception as _voice_exc:  # noqa: BLE001
    VoiceListener = None
    SelfTalk = None
    Asr = None
    _VOICE_IMPORT_ERROR = str(_voice_exc)
else:
    _VOICE_IMPORT_ERROR = ""

from .ui.hotkeys import MOD_ALT, MOD_CTRL, MOD_SHIFT, VK, GlobalHotkeys
from .ui.selftalk_panel import SelfTalkPanel

# 热键 id -> 复制哪种语言的译文
HOTKEY_COPY = {1: "ja", 2: "en"}
HOTKEY_TOGGLE_TALK = 3
HOTKEY_TOGGLE_PANEL = 4
HOTKEY_TOGGLE_DANMAKU = 5

WORKER = Path(__file__).with_name("ocr") / "ocr_worker.ps1"

SAMPLES = [
    ("Kirito", "push b site, two enemies mid", "en"),
    ("夜桜", "ちょっと待って、こっちに敵がいる", "ja"),
    ("SovaMain", "nice shot bro", "en"),
]


def enable_dpi_awareness() -> None:
    try:
        from .ui.theme import enable_dark_mode
        enable_dark_mode()
    except Exception:  # noqa: BLE001
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


class App:
    def __init__(self) -> None:
        self.cfg = Config.load()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("瓦罗兰特实时翻译弹幕")
        try:
            from .config import asset_path
            self.root.iconbitmap(default=str(asset_path("app.ico")))
        except Exception:  # noqa: BLE001
            pass

        self.events: queue.Queue[ChatEvent] = queue.Queue()
        self.renders: queue.Queue = queue.Queue()
        self.ui_queue: queue.Queue = queue.Queue()
        self.stop = threading.Event()
        self.paused = False

        apply_ttk_style(self.root)
        self.overlay = create_view(self.root, self.cfg)
        self.panel = ControlPanel(self.root, self)
        self.panel.set_region(self.cfg.chat_region)

        self.translator = Translator(self.cfg)
        self.tts = Speaker(self.cfg)
        self.translator_lock = threading.Lock()

        self.ocr: WindowsOcr | None = None
        self.reader: ChatReader | None = None
        self.ocr_error = ""
        self.voice: VoiceListener | None = None
        self.asr = None          # Whisper 模型（队友语音和我说话的共用一份）
        self._start_ocr()
        self._start_voice()

        threading.Thread(target=self._translate_loop, daemon=True,
                         name="translator").start()
        threading.Thread(target=self._warmup, daemon=True, name="warmup").start()

        self.translated = 0
        self.root.after(40, self._poll)
        self.root.after(1000, self._tick_status)

        # ---- 我说的话（中 -> 日/英） ----
        self.selftalk: SelfTalk | None = None
        self.selftalk_window: SelfTalkPanel | None = None
        self.last_selftalk: dict = {}
        self.hotkey_q: queue.Queue = queue.Queue()
        self.hotkeys = GlobalHotkeys(self._hotkey_spec(), self.hotkey_q)
        self.hotkeys.start()
        self.hotkeys.ready.wait(1.5)
        try:
            self.panel.set_hotkey_hint()
        except Exception:  # noqa: BLE001
            pass

        # 记住上次框的聊天区域：只有第一次、或者屏幕变了导致区域越界才重新框
        if self.cfg.chat_region and not self._region_valid(self.cfg.chat_region):
            print("[提示] 上次的聊天区域已超出屏幕范围（换过显示器/分辨率？），重新框一次")
            self.cfg.chat_region = None
            self.cfg.save()
        if self.cfg.chat_region:
            self.panel.set_last(f"已恢复上次的聊天区域 {self.cfg.chat_region[2]}×{self.cfg.chat_region[3]}")
        else:
            self.root.after(700, self.pick_region)

    # ------------------------------------------------------------------
    @staticmethod
    def _region_valid(region) -> bool:
        try:
            if not region or len(region) != 4:
                return False
            x, y, w, h = (int(v) for v in region)
        except (TypeError, ValueError):
            return False
        if w < 40 or h < 20:
            return False
        u32 = ctypes.windll.user32
        vx, vy = u32.GetSystemMetrics(76), u32.GetSystemMetrics(77)
        vw, vh = u32.GetSystemMetrics(78), u32.GetSystemMetrics(79)
        return (x >= vx - 8 and y >= vy - 8
                and x + w <= vx + vw + 8 and y + h <= vy + vh + 8)
    def _start_ocr(self) -> None:
        if not self.cfg.ocr_enabled:
            return
        try:
            self.ocr = WindowsOcr(WORKER, list(self.cfg.ocr_langs))
        except Exception as exc:  # noqa: BLE001
            self.ocr_error = str(exc)
            return
        missing = [l for l in self.cfg.ocr_langs
                   if l.split("-")[0] not in [a.split("-")[0] for a in self.ocr.available]]
        if missing:
            print(f"[提示] 系统缺少这些 OCR 语言包: {missing}，对应语言会识别失败。")
        self.reader = ChatReader(self.cfg, self.ocr, self.events, self.stop)
        self.reader.start()

    def _start_voice(self) -> None:
        if VoiceListener is None:
            self.voice = None
            self.panel.set_voice("语音：未安装组件（双击 安装语音.bat）")
            return
        if not self.cfg.voice_enabled:
            self.panel.set_voice("语音：已关闭")
            return
        try:
            self.voice = VoiceListener(self.cfg, self.events, self._voice_status,
                                       asr=self._ensure_asr())
            self.voice.start()
            self.voice.set_active(bool(self.cfg.voice_enabled))
            self.panel.set_voice("语音：启动中…")
        except Exception as exc:  # noqa: BLE001
            self.voice = None
            self.panel.set_voice(f"语音不可用：{exc}"[:60])

    def _voice_status(self, kind: str, msg: str) -> None:
        if kind == "ready":
            text = "语音：识别中"
        elif kind == "error":
            text = "语音：出错"
        elif kind == "loading":
            text = "语音：加载模型…"
        else:
            text = msg
        self.ui_queue.put(lambda t=text: self.panel.set_voice(t))

    def toggle_tts(self) -> None:
        """语音播报开关（看不见弹幕时用耳朵听）。"""
        self.cfg.tts_enabled = not bool(self.cfg.tts_enabled)
        self.cfg.save()
        self.tts.set_enabled(self.cfg.tts_enabled)
        self.panel.set_tts(self.cfg.tts_enabled)

    def toggle_voice(self) -> None:
        """开关队友语音：只是暂停/恢复，不销毁线程和模型，避免再开时卡住。"""
        if self.voice is None:
            self.cfg.voice_enabled = True
            self.cfg.save()
            self._start_voice()
            return
        want = not self.voice.active.is_set()
        try:
            self.voice.set_active(want)
        except Exception as exc:  # noqa: BLE001
            self.panel.set_voice(f"语音不可用：{exc}"[:60])
            return
        self.cfg.voice_enabled = want
        self.cfg.save()
        self.panel.set_voice("语音：识别中" if want else "语音：已关闭")
        self.toast("队友语音已开启" if want else "队友语音已关闭")

    def restart_voice(self) -> None:
        """换设备/换模型后重启语音线程。"""
        if self.voice is not None:
            try:
                self.voice.shutdown()
            except Exception:  # noqa: BLE001
                pass
            self.voice = None
        self.cfg.voice_enabled = True
        self._start_voice()

    # ---------- 我说的话（中 -> 日/英） ----------
    def _ensure_asr(self):
        if Asr is None:
            raise RuntimeError("未安装语音组件")
        if self.asr is None:
            self.asr = Asr(self.cfg, on_status=self._asr_status)
        return self.asr

    def _asr_status(self, kind: str, msg: str) -> None:
        self.ui_queue.put(lambda m=msg: self.panel.set_voice(f"语音：{m}"))

    def _self_status(self, kind: str, msg: str) -> None:
        if self.selftalk_window is not None:
            self.ui_queue.put(lambda m=msg: self.selftalk_window.set_status(m))

    def open_selftalk(self) -> None:
        if self.selftalk_window is not None:
            self.selftalk_window.deiconify()
            self.selftalk_window.lift()
            return
        if SelfTalk is None:
            self.panel.warn("缺少语音组件", "请先双击 安装语音.bat")
            return
        self.selftalk_window = SelfTalkPanel(self.root, self)
        try:
            self.selftalk = SelfTalk(self.cfg, self.translator,
                                     on_result=self._on_self_result,
                                     on_status=self._self_status,
                                     asr=self._ensure_asr())
            self.selftalk.start()
            self.selftalk_window.set_status("麦克风已启动，说中文试试")
        except Exception as exc:  # noqa: BLE001
            self.selftalk = None
            self.selftalk_window.set_status(f"麦克风不可用：{exc}"[:60])

    def toggle_selftalk(self) -> None:
        """F8：开/关「我说的话」窗口。"""
        if self.selftalk_window is None:
            self.open_selftalk()
        else:
            self.close_selftalk()

    def close_selftalk(self) -> None:
        if self.selftalk is not None:
            self.selftalk.stop_all()
            self.selftalk = None
        if self.selftalk_window is not None:
            try:
                self.selftalk_window.destroy()
            except tk.TclError:
                pass
            self.selftalk_window = None

    def restart_selftalk(self) -> None:
        if self.selftalk_window is None:
            return
        if self.selftalk is not None:
            self.selftalk.stop_all()
            self.selftalk = None
        try:
            self.selftalk = SelfTalk(self.cfg, self.translator,
                                     on_result=self._on_self_result,
                                     on_status=self._self_status,
                                     asr=self._ensure_asr())
            self.selftalk.start()
            self.selftalk_window.set_status("麦克风已切换")
        except Exception as exc:  # noqa: BLE001
            self.selftalk_window.set_status(f"麦克风不可用：{exc}"[:60])

    def _on_self_result(self, res: dict) -> None:
        self.ui_queue.put(lambda r=dict(res): self._show_self(r))

    def _show_self(self, res: dict) -> None:
        self.last_selftalk = dict(res)
        if self.selftalk_window is not None:
            self.selftalk_window.update_result(res)
        auto = str(getattr(self.cfg, "selftalk_auto_copy", "off"))
        if auto in ("ja", "en") and res.get(auto):
            self._copy(res[auto], auto, quiet=True)

    def copy_selftext(self, which: str) -> None:
        if not self.last_selftalk:
            self._flash("还没有识别到内容")
            return
        text = self.last_selftalk.get(which) or ""
        if not text:
            self._flash("这一条还没有译文")
            return
        self._copy(text, which)

    def _copy(self, text: str, which: str, quiet: bool = False) -> None:
        from .ui.clipboard import get_text, set_text
        ok = set_text(text)
        if ok:
            ok = get_text().strip() == text.strip()
        name = "日语" if which == "ja" else "英语"
        if not ok:
            self.toast("复制失败，剪贴板被别的程序占用了")
            self._flash("复制失败，再按一次试试")
            return
        if not quiet:
            self._flash(f"已复制{name}，去游戏聊天框 Ctrl+V")
            self.toast(f"已复制{name}")

    def _flash(self, msg: str) -> None:
        if self.selftalk_window is not None:
            self.selftalk_window.set_status(msg)

    # ------------------------------------------------------------------
    def _warmup(self) -> None:
        try:
            results = self.translator.warmup()
        except Exception as exc:  # noqa: BLE001
            results = [("all", False, str(exc))]
        ok = [r for r in results if r[1]]
        text = "翻译源：" + ("、".join(r[0] for r in ok) if ok else "全部不可用（先直显原文）")
        self.ui_queue.put(lambda: self.panel.set_status(text))

    # ------------------------------------------------------------------
    def _translate_loop(self) -> None:
        from concurrent.futures import ThreadPoolExecutor
        pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="tr")

        def work(ev: ChatEvent) -> None:
            try:
                res = self.translator.translate(ev.text, ev.lang)
            except Exception as exc:  # noqa: BLE001
                print(f"[翻译异常] {exc}", flush=True)
                return
            if res is not None:
                self.renders.put((ev, res))

        while not self.stop.is_set():
            try:
                ev = self.events.get(timeout=0.2)
            except queue.Empty:
                continue
            pool.submit(work, ev)

    def _poll(self) -> None:
        try:
            while True:
                ev, res = self.renders.get_nowait()
                self._render(ev, res)
        except queue.Empty:
            pass
        try:
            while True:
                task = self.ui_queue.get_nowait()
                task()
        except queue.Empty:
            pass
        try:
            while True:
                hid = self.hotkey_q.get_nowait()
                if hid == HOTKEY_TOGGLE_TALK:
                    self.toggle_selftalk()
                    continue
                if hid == HOTKEY_TOGGLE_PANEL:
                    self.toggle_panel()
                    continue
                if hid == HOTKEY_TOGGLE_DANMAKU:
                    self.toggle_danmaku()
                    continue
                which = HOTKEY_COPY.get(hid)
                if which:
                    self.copy_selftext(which)
        except queue.Empty:
            pass
        self.root.after(40, self._poll)

    def _render(self, ev: ChatEvent, res) -> None:
        cfg = self.cfg
        # 同一条内容短时间内又出现（OCR 重复读同一行 / 语音切段重叠），直接丢掉，
        # 否则弹幕里会看到同一句话冒出两遍
        key = re.sub(r"\s+", "", f"{ev.source}|{ev.speaker}|{res.text}")
        now = time.time()
        seen = getattr(self, "_recent", None)
        if seen is None:
            seen = self._recent = {}
        window = float(getattr(cfg, "dedupe_window_s", 25.0) or 25.0)
        if key in seen and now - seen[key] < window:
            return
        seen[key] = now
        if len(seen) > 200:
            for k, ts in list(seen.items()):
                if now - ts > window:
                    seen.pop(k, None)

        color = {"en": cfg.color_en, "ja": cfg.color_ja, "zh": cfg.color_zh}.get(ev.lang, cfg.color_zh)
        if ev.source == "voice":
            color = cfg.color_voice
            prefix = "🎤 "
        else:
            tag = {"en": "EN", "ja": "JA", "zh": "中"}.get(ev.lang, "?")
            prefix = f"[{tag}] " if cfg.show_source_tag else ""
        speaker = f"{ev.speaker}: " if (cfg.show_speaker and ev.speaker) else ""
        self.overlay.push(prefix + speaker + res.text, color)
        try:
            if self.tts.enabled:
                self.tts.say(res.text)
        except Exception:  # noqa: BLE001
            pass
        self.translated += 1
        self.panel.set_last(f"{speaker}{ev.text}  →  {res.text}")
        if cfg.log_enabled:
            self._log(ev, res)

    def _log(self, ev: ChatEvent, res) -> None:
        try:
            path = project_root() / "logs" / "chat.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "source": ev.source, "speaker": ev.speaker,
                    "text": ev.text, "lang": ev.lang,
                    "zh": res.text, "provider": res.provider,
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _tick_status(self) -> None:
        if not self.cfg.ocr_enabled:
            text = f"OCR 已关闭 · 已翻译 {self.translated} 条"
        elif self.ocr_error:
            text = f"OCR 不可用：{self.ocr_error[:60]}"
        else:
            stats = self.reader.stats if self.reader else {}
            state = "已暂停" if self.paused else "运行中"
            last = "—"
            if stats.get("frames"):
                last = time.strftime("%H:%M:%S")
            text = (f"OCR {state} · 已翻译 {self.translated} 条 · "
                    f"抓帧 {stats.get('frames', 0)} · 最后 {last}")
            if stats.get("error"):
                text += f" · {stats['error'][:40]}"
        self.panel.set_status(text)
        self.panel.set_paused(self.paused)
        if self.voice is not None:
            st = self.voice.status
            if st == "running":
                dev = " · GPU" if getattr(self.voice.asr, "device_used", "") == "cuda" else ""
                self.panel.set_voice(f"语音：识别中{dev} · {self.voice.utterances} 句")
            elif st == "error":
                self.panel.set_voice(f"语音出错：{self.voice.capture.error[:38]}")
            elif st == "loading":
                self.panel.set_voice("语音：加载模型…")
            elif st == "idle":
                self.panel.set_voice("语音：已关闭")
        self.root.after(1000, self._tick_status)

    # ------------------------------------------------------------------
    def pick_region(self) -> None:
        RegionPicker(self.root, self._on_region)

    def pick_region_capture(self) -> None:
        """截图选区域：给独占全屏 / 覆盖不上去时用。"""
        CapturePicker(self.root, self._on_region)

    def _on_region(self, region) -> None:
        if not region:
            return
        self.cfg.chat_region = [int(v) for v in region]
        self.cfg.danmaku_band = "top" if not self.cfg.danmaku_region else self.cfg.danmaku_band
        self.cfg.save()                      # 立刻写盘：下次启动直接沿用
        self.panel.set_region(self.cfg.chat_region)
        self.panel.set_last("已记住聊天区域，下次启动不用再框")
        if self.reader:
            self.reader._last_hash = ""       # 让下一帧强制识别
            self.reader.msg_filter = type(self.reader.msg_filter)()
        self.overlay.apply_region()

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.reader:
            self.reader.pause(self.paused)
        self.panel.set_paused(self.paused)

    def toggle_danmaku(self) -> None:
        self.overlay.set_visible(not self.overlay.visible)
        self.panel.set_danmaku_visible(self.overlay.visible)
        self.toast("弹幕已开启" if self.overlay.visible else "弹幕已隐藏（F7 恢复）")

    def toggle_panel(self) -> None:
        """F6：把控制面板收起来/放出来，玩游戏时桌面更干净。"""
        try:
            if self.panel.winfo_viewable():
                self.panel.withdraw()
                self.toast("面板已收起（F6 恢复）")
            else:
                self.panel.deiconify()
                self.panel.lift()
                self.toast("面板已显示")
        except tk.TclError:
            pass

    @property
    def hotkey_labels(self) -> dict[str, str]:
        h = self.hotkeys
        return {
            "panel": h.label(HOTKEY_TOGGLE_PANEL, "F6"),
            "danmaku": h.label(HOTKEY_TOGGLE_DANMAKU, "F7"),
            "talk": h.label(HOTKEY_TOGGLE_TALK, "F8"),
            "ja": h.label(1, "F9"),
            "en": h.label(2, "F10"),
        }

    # ---------- 快捷键（可自定义 + 自动避让） ----------
    @staticmethod
    def _parse_key(label: str) -> tuple[int, int] | None:
        """'F9' / 'Ctrl+Alt+F9' -> (修饰键, 虚拟键码)。"""
        text = (label or "").strip().upper().replace(" ", "")
        mods = 0
        while "+" in text:
            head, text = text.split("+", 1)
            if head in ("CTRL", "CONTROL"):
                mods |= MOD_CTRL
            elif head == "ALT":
                mods |= MOD_ALT
            elif head == "SHIFT":
                mods |= MOD_SHIFT
            else:
                return None
        if text in VK:
            return mods, VK[text]
        return None

    def _hotkey_spec(self) -> dict[int, list[tuple[int, int, str]]]:
        plan = [
            (HOTKEY_TOGGLE_PANEL, getattr(self.cfg, "hotkey_panel", "F6"),
             ["F6", "Ctrl+Alt+F6"]),
            (HOTKEY_TOGGLE_DANMAKU, getattr(self.cfg, "hotkey_danmaku", "F7"),
             ["F7", "Ctrl+Alt+F7"]),
            (HOTKEY_TOGGLE_TALK, getattr(self.cfg, "hotkey_talk", "F8"),
             ["F8", "F11", "Ctrl+Alt+F8"]),
            (1, getattr(self.cfg, "hotkey_ja", "F9"), ["F9", "Ctrl+Alt+F9", "F1"]),
            (2, getattr(self.cfg, "hotkey_en", "F10"), ["F10", "Ctrl+Alt+F10", "F2"]),
        ]
        spec: dict[int, list[tuple[int, int, str]]] = {}
        for hid, primary, fallbacks in plan:
            seen: list[tuple[int, int]] = []
            cands: list[tuple[int, int, str]] = []
            for label in [primary, *fallbacks]:
                parsed = self._parse_key(label)
                if parsed and parsed not in seen:
                    seen.append(parsed)
                    cands.append((parsed[0], parsed[1], label))
            if cands:
                spec[hid] = cands
        return spec

    def reload_hotkeys(self) -> None:
        """设置里改了键位后重新注册。"""
        try:
            self.hotkeys.stop()
        except Exception:  # noqa: BLE001
            pass
        self.hotkeys = GlobalHotkeys(self._hotkey_spec(), self.hotkey_q)
        self.hotkeys.start()
        self.hotkeys.ready.wait(1.2)
        try:
            self.panel.set_hotkey_hint()
        except Exception:  # noqa: BLE001
            pass
        self.toast("快捷键已更新")

    def toast(self, text: str) -> None:
        """屏幕下方闪一条提示，1.4 秒消失。"""
        try:
            from .ui.widgets import Toast
            Toast(self.root, text)
        except Exception:  # noqa: BLE001
            pass

    def toggle_display_mode(self) -> None:
        """字幕框 <-> 滚动弹幕。"""
        mode = "scroll" if getattr(self.cfg, "display_mode", "box") == "box" else "box"
        self.set_display_mode(mode)

    def set_display_mode(self, mode: str) -> None:
        if getattr(self.cfg, "display_mode", "box") == mode:
            self.panel.set_display_mode(mode)
            return
        self.cfg.display_mode = mode
        self.cfg.save()
        try:
            self.overlay.close()
        except Exception:  # noqa: BLE001
            pass
        self.overlay = create_view(self.root, self.cfg)
        self.panel.set_display_mode(mode)

    def test_danmaku(self) -> None:
        for speaker, text, lang in SAMPLES:
            res = self.translator.translate(text, lang)
            if res:
                self._render(ChatEvent("text", speaker, text, lang), res)

    def open_models(self) -> None:
        """模型管理：语音包 / 语言包的选用、下载、导入。"""
        from .ui.models import ModelManager
        try:
            win = getattr(self, "_models_win", None)
            if win is not None and win.winfo_exists():
                win.lift()
                return
        except tk.TclError:
            pass
        self._models_win = ModelManager(self.panel, self)

    def open_settings(self) -> None:
        SettingsDialog(self.panel, self)

    def reload_translator(self) -> None:
        with self.translator_lock:
            self.translator.flush_cache()
            self.translator = Translator(self.cfg)
        threading.Thread(target=self._warmup, daemon=True).start()

    # ------------------------------------------------------------------
    def quit(self) -> None:
        self.stop.set()
        try:
            self.hotkeys.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.tts.close()
        except Exception:  # noqa: BLE001
            pass
        if self.selftalk is not None:
            self.selftalk.stop_all()
            self.selftalk = None
        if self.voice is not None:
            self.voice.stop_all()
            self.voice = None
        self.cfg.save()
        try:
            self.cfg.panel_geometry = self.panel.geometry()
            self.cfg.save()
        except tk.TclError:
            pass
        try:
            self.translator.flush_cache()
        except Exception:  # noqa: BLE001
            pass
        if self.reader:
            self.reader.join(timeout=1.5)
        if self.ocr:
            self.ocr.close()
        self.overlay.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    enable_dpi_awareness()
    try:
        App().run()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        try:
            from tkinter import messagebox
            messagebox.showerror("启动失败", traceback.format_exc()[-1200:])
        except Exception:  # noqa: BLE001
            pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
