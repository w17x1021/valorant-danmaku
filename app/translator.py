"""英/日 -> 中文 翻译。多个免密钥翻译源自动排序、失败自动降级，并带本地缓存。"""
from __future__ import annotations

import gzip
import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import Config, project_root

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

KANA_RE = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
CJK_SPACE_RE = re.compile(r"(?<=[\u3000-\u30ff\u3400-\u9fff])\s+(?=[\u3000-\u30ff\u3400-\u9fff])")


def detect_language(text: str) -> str:
    """返回 ja / zh / en / und。有假名即日语（日语里也有汉字，所以先看假名）。"""
    if KANA_RE.search(text):
        return "ja"
    han = len(HAN_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    if han and han >= latin:
        return "zh"
    if latin:
        return "en"
    return "und"


def normalize_cjk(text: str) -> str:
    """OCR 会给中文/日文每个字之间插空格，这里去掉。"""
    return CJK_SPACE_RE.sub("", text)


def clean_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = normalize_cjk(text)
    return text


# ----------------------------------------------------------------------
# HTTP helpers
# ----------------------------------------------------------------------
def _request(url: str, data: bytes | None = None, headers: dict | None = None,
             timeout: float = 8.0, method: str | None = None) -> str:
    hdrs = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


@dataclass
class Translation:
    text: str
    provider: str
    src_lang: str

    @property
    def ok(self) -> bool:
        return bool(self.text)


# ----------------------------------------------------------------------
# Providers
# ----------------------------------------------------------------------
class Provider:
    name = "base"
    label = ""

    def translate(self, text: str, src: str, tgt: str) -> str:  # pragma: no cover
        raise NotImplementedError

    def probe(self) -> bool:
        try:
            return bool(self.translate("hello", "en", "zh-Hans"))
        except Exception:
            return False


class BingProvider(Provider):
    """必应网页翻译（cn.bing.com，国内可直连，质量接近商业机翻）。"""

    name = "bing"
    label = "必应翻译"
    HOST = "cn.bing.com"
    PAGE = f"https://{HOST}/translator"
    API = f"https://{HOST}/ttranslatev3?isVertical=1&IG={{ig}}&IID=translator.5028.1"
    PARAM_RE = re.compile(r"params_AbusePreventionHelper\s*=\s*\[([^\]]+)\]")

    def __init__(self) -> None:
        self._key = ""
        self._token = ""
        self._expire = 0.0
        self._lock = threading.Lock()
        self._cookies: dict[str, str] = {}
        self._conn: http.client.HTTPSConnection | None = None
        self._conn_lock = threading.Lock()

    def _refresh(self, timeout: float) -> None:
        req = urllib.request.Request(self.PAGE, headers={
            "User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", "replace")
            cookie_parts = []
            for c in (resp.headers.get_all("Set-Cookie") or []):
                cookie_parts.append(c.split(";", 1)[0])
            self._cookie_header = "; ".join(cookie_parts)
        m = self.PARAM_RE.search(html)
        if not m:
            raise RuntimeError("必应翻译参数获取失败")
        key, token, _ = [x.strip() for x in m.group(1).split(",")]
        self._key = key
        self._token = token.strip('"')
        self._expire = time.time() + 45 * 60

    def _ensure(self, timeout: float, force: bool = False) -> None:
        with self._lock:
            if force or not self._token or time.time() > self._expire:
                self._refresh(timeout)

    def _post_keepalive(self, url: str, body: bytes, headers: dict, timeout: float) -> str:
        """复用 TLS 连接：省掉每次翻译重新握手的 200~300ms。"""
        path = url.split(self.HOST, 1)[-1]
        with self._conn_lock:
            for attempt in (0, 1):
                try:
                    if self._conn is None:
                        self._conn = http.client.HTTPSConnection(self.HOST, timeout=timeout)
                    self._conn.request("POST", path, body=body, headers=headers)
                    resp = self._conn.getresponse()
                    data = resp.read().decode("utf-8", "replace")
                    if resp.status >= 400:
                        raise RuntimeError(f"HTTP {resp.status}")
                    return data
                except Exception:  # noqa: BLE001
                    try:
                        if self._conn is not None:
                            self._conn.close()
                    except Exception:  # noqa: BLE001
                        pass
                    self._conn = None
                    if attempt:
                        raise
            return ""

    def translate(self, text: str, src: str, tgt: str, timeout: float = 8.0,
                  _retry: bool = True) -> str:
        src_code = {"en": "en", "ja": "ja", "zh": "zh-Hans"}.get(src, "auto-detect")
        tgt_code = "zh-Hans" if tgt.startswith("zh") else tgt
        if src_code == tgt_code:
            return text
        self._ensure(timeout)
        body = urllib.parse.urlencode({
            "fromLang": src_code, "to": tgt_code, "text": text,
            "token": self._token, "key": self._key,
        }).encode()
        headers = {
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": self.PAGE,
            "Origin": f"https://{self.HOST}",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        if getattr(self, "_cookie_header", ""):
            headers["Cookie"] = self._cookie_header
        raw = self._post_keepalive(self.API.format(ig=self._key), body, headers, timeout)
        if not raw.strip():
            # token 失效时必应返回 200 空包，刷新后重试一次
            if _retry:
                self._ensure(timeout, force=True)
                return self.translate(text, src, tgt, timeout, _retry=False)
            raise RuntimeError("必应翻译返回空结果")
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("statusCode"):
            raise RuntimeError(f"必应翻译错误: {data.get('statusCode')}")
        return data[0]["translations"][0]["text"]


class GoogleProvider(Provider):
    name = "google"
    label = "Google 翻译"
    API = ("https://translate.googleapis.com/translate_a/single"
           "?client=gtx&sl={src}&tl={tgt}&dt=t&q={q}")

    def translate(self, text: str, src: str, tgt: str, timeout: float = 8.0) -> str:
        src_code = {"en": "en", "ja": "ja", "zh": "zh-CN"}.get(src, "auto")
        tgt_code = "zh-CN" if tgt.startswith("zh") else tgt
        url = self.API.format(src=src_code, tgt=tgt_code, q=urllib.parse.quote(text))
        raw = _request(url, timeout=timeout)
        data = json.loads(raw)
        return "".join(seg[0] for seg in data[0] if seg and seg[0])


class MyMemoryProvider(Provider):
    name = "mymemory"
    label = "MyMemory"
    API = "https://api.mymemory.translated.net/get?q={q}&langpair={src}|{tgt}"

    def translate(self, text: str, src: str, tgt: str, timeout: float = 8.0) -> str:
        src_code = {"en": "en", "ja": "ja-JP", "zh": "zh-CN"}.get(src, "en")
        tgt_code = {"zh-Hans": "zh-CN", "zh": "zh-CN", "ja": "ja-JP", "en": "en-US"}.get(tgt, "zh-CN")
        url = self.API.format(q=urllib.parse.quote(text), src=src_code, tgt=tgt_code)
        data = json.loads(_request(url, timeout=timeout))
        if int(data.get("responseStatus", 0)) != 200:
            raise RuntimeError(f"MyMemory: {data.get('responseDetails')}")
        out = (data.get("responseData") or {}).get("translatedText") or ""
        if not out or out.upper() == text.upper() or "MYMEMORY WARNING" in out.upper():
            raise RuntimeError("MyMemory 无有效结果")
        return out


class YoudaoProvider(Provider):
    """有道快速接口：150ms 左右出结果，机翻质量一般，胜在快。

    适合"先看到再说"的实时场景；翻错了还有 game_terms 的后处理兜一层。
    """

    name = "youdao"
    label = "有道（快）"
    API = "https://aidemo.youdao.com/trans?q={q}&from={src}&to={tgt}"

    def translate(self, text: str, src: str, tgt: str, timeout: float = 6.0) -> str:
        src_code = {"en": "en", "ja": "ja", "zh": "zh-CHS"}.get(src, "auto")
        tgt_code = {"zh-Hans": "zh-CHS", "zh": "zh-CHS", "ja": "ja", "en": "en"}.get(
            tgt, "zh-CHS")
        url = self.API.format(q=urllib.parse.quote(text), src=src_code, tgt=tgt_code)
        raw = _request(url, timeout=timeout,
                       headers={"User-Agent": UA, "Referer": "https://fanyi.youdao.com/"})
        data = json.loads(raw)
        out = (data.get("translation") or [""])[0].strip()
        if not out:
            raise RuntimeError("有道无结果")
        return out


class OpenAIProvider(Provider):
    """任意 OpenAI 兼容接口（DeepSeek / 通义 / Ollama ...），需要填 key。"""

    name = "openai"
    label = "大模型翻译"

    SYSTEM = (
        "你是《无畏契约/瓦罗兰特》(VALORANT) 的实时聊天翻译官。"
        "把用户给的原话翻译成{target}，口语、简短、像玩家在游戏里打字。"
        "使用玩家常用术语：mid=中路，rotate=转点，eco=经济局，rush=快攻，push=推进，"
        "A/B site=A/B 点，spike=爆能器，flank=绕后，nice=漂亮。"
        "只输出译文本身，不要解释、不要引号。"
    )
    TARGET_NAMES = {"zh-Hans": "简体中文", "ja": "日语", "en": "英语"}

    def __init__(self, base: str, key: str, model: str) -> None:
        self.base = base.rstrip("/")
        self.key = key
        self.model = model

    def translate(self, text: str, src: str, tgt: str, timeout: float = 15.0) -> str:
        if not self.key:
            raise RuntimeError("未配置大模型 key")
        target_name = self.TARGET_NAMES.get(tgt, "简体中文")
        body = json.dumps({
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 200,
            "messages": [
                {"role": "system", "content": self.SYSTEM.format(target=target_name)},
                {"role": "user", "content": f"[{src}] {text}"},
            ],
        }, ensure_ascii=False).encode("utf-8")
        raw = _request(f"{self.base}/chat/completions", data=body, timeout=timeout,
                       headers={"Authorization": f"Bearer {self.key}",
                                "Content-Type": "application/json"})
        data = json.loads(raw)
        return (data["choices"][0]["message"]["content"] or "").strip().strip('"')


# ----------------------------------------------------------------------
# 短句战术术语直译（整句命中时直接用，比机翻更稳）
# ----------------------------------------------------------------------
CALLOUTS: dict[str, str] = {
    "rotate": "转点",
    "rotate now": "现在转点",
    "eco": "经济局",
    "eco round": "经济局",
    "save": "保枪",
    "full save": "全保",
    "rush b": "快攻 B 点",
    "rush a": "快攻 A 点",
    "push": "推进",
    "push now": "现在推进",
    "fall back": "后撤",
    "fallback": "后撤",
    "hold": "守住",
    "watch flank": "注意绕后",
    "flank": "绕后",
    "one hp": "残血一个",
    "one shot": "一枪一个",
    "nice": "漂亮",
    "nice shot": "好枪",
    "nt": "打得不错",
    "gj": "干得好",
    "gg": "打得好",
    "wp": "打得漂亮",
    "gl hf": "好运，玩得开心",
    "mid": "中路",
    "a site": "A 点",
    "b site": "B 点",
    "c site": "C 点",
    "on site": "进点了",
    "spike down": "爆能器掉了",
    "plant": "下包",
    "defuse": "拆包",
    "mid control": "中路控制权",
    "rotate a": "转 A 点",
    "rotate b": "转 B 点",
}

# 机翻常见的生硬说法，做一次轻量后处理
POST_EDITS = [
    ("爆能器", "爆能器"),
    ("斯派克", "爆能器"),
    ("凤梨", "爆能器"),
    ("特工", "特工"),
    ("中杀", "中路"),
    ("旋转", "转点"),
]


class Translator:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.cache_path = project_root() / "cache" / "translations.json"
        self._cache: dict[str, str] = {}
        self._lock = threading.Lock()
        self._dirty = False
        self._bad_until: dict[str, float] = {}
        self._load_cache()
        self.providers: list[Provider] = []
        self._build_providers()
        self.last_error = ""

    # ---------------- providers ----------------
    def _build_providers(self) -> None:
        table = {
            "youdao": YoudaoProvider,
            "bing": BingProvider,
            "google": GoogleProvider,
            "mymemory": MyMemoryProvider,
        }
        order = list(self.cfg.provider_order) or ["youdao", "bing", "mymemory"]
        if self.cfg.openai_key and "openai" not in order:
            order.insert(0, "openai")
        for name in order:
            if name == "openai":
                self.providers.append(OpenAIProvider(self.cfg.openai_base,
                                                     self.cfg.openai_key,
                                                     self.cfg.openai_model))
            elif name in table:
                self.providers.append(table[name]())

    def warmup(self, timeout: float = 5.0) -> list[tuple[str, bool, str]]:
        """启动时探测各源可用性，返回 [(名称, 是否可用, 信息)]。"""
        results: list[tuple[str, bool, str]] = []
        for p in self.providers:
            t0 = time.time()
            try:
                out = p.translate("good luck", "en", self.cfg.target_lang, timeout=min(timeout, 4.0))  # type: ignore[call-arg]
                results.append((p.name, bool(out), f"{out} · {int((time.time()-t0)*1000)}ms"))
            except Exception as exc:  # noqa: BLE001
                results.append((p.name, False, f"{type(exc).__name__}: {exc}"[:80]))
                self._bad_until[p.name] = time.time() + 30
        return results

    # ---------------- cache ----------------
    def _load_cache(self) -> None:
        try:
            if self.cache_path.exists():
                self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._cache = {}

    def flush_cache(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            data = self._cache
            self._dirty = False
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    # ---------------- main ----------------
    def translate(self, text: str, src: str | None = None) -> Optional[Translation]:
        text = clean_text(text)
        if not text:
            return None
        src = src or detect_language(text)
        if src == "zh":
            return Translation(text, "原文", "zh")

        if src in ("en", "ja"):
            # 先把 Jett / チェンバー 换成「捷风 / 尚勃勒」，机翻才不会音译成「杰特/切姆伯」
            from .agents import names_to_zh
            text = names_to_zh(text)

        key = f"{src}|{text.lower()}"
        with self._lock:
            hit = self._cache.get(key)
        if hit:
            return Translation(hit, "缓存", src)

        short = text.lower().strip(" .!?~")
        if src == "en" and short in CALLOUTS:
            out = CALLOUTS[short]
            self._store(key, out)
            return Translation(out, "术语", src)

        now = time.time()
        last_exc: Exception | None = None
        for p in self.providers:
            if self._bad_until.get(p.name, 0) > now:
                continue
            try:
                out = p.translate(text, src, self.cfg.target_lang,  # type: ignore[call-arg]
                                  timeout=self.cfg.translate_timeout)
                out = clean_text(out)
                if out:
                    if str(self.cfg.target_lang).startswith("zh"):
                        from .agents import names_to_zh
                        from .game_terms import polish_zh
                        out = polish_zh(names_to_zh(out))
                    self._store(key, out)
                    return Translation(out, p.name, src)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self._bad_until[p.name] = now + 45
                self.last_error = f"{p.name}: {exc}"
        # 全部失败：网络问题时也不要吞掉消息
        if last_exc is not None:
            return Translation(text, "未翻译", src)
        return Translation(text, "未翻译", src)

    def _store(self, key: str, value: str) -> None:
        with self._lock:
            self._cache[key] = value
            self._dirty = True
            if len(self._cache) > 5000:
                for k in list(self._cache)[:1000]:
                    self._cache.pop(k, None)

    def translate_to(self, text: str, src: str, tgt: str) -> Optional[Translation]:
        """指定源语言和目标语言（用于「我说的话」翻成日文/英文）。"""
        text = clean_text(text)
        if not text:
            return None
        if src == tgt:
            return Translation(text, "原文", src)
        if src == "zh":
            from .game_terms import normalize_zh
            text = normalize_zh(text)
        key = f"{src}>{tgt}|{text.lower()}"
        with self._lock:
            hit = self._cache.get(key)
        if hit:
            return Translation(hit, "缓存", src)
        now = time.time()
        for p in self.providers:
            if self._bad_until.get(p.name, 0) > now:
                continue
            try:
                out = p.translate(text, src, tgt, timeout=self.cfg.translate_timeout)  # type: ignore[call-arg]
                out = clean_text(out)
                if out:
                    if tgt == "ja":
                        from .agents import en_names_to_ja
                        out = en_names_to_ja(out)
                    self._store(key, out)
                    return Translation(out, p.name, src)
            except Exception as exc:  # noqa: BLE001
                self._bad_until[p.name] = now + 45
                self.last_error = f"{p.name}: {exc}"
        return Translation(text, "未翻译", src)
