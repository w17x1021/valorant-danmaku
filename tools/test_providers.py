"""探测多个免密钥翻译源，输出可达性与译文质量。"""
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


def bing_variant(text, src, path_fmt, extra_body="", extra_headers=None):
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    html = op.open("https://www.bing.com/translator", timeout=15).read().decode("utf-8", "replace")
    m = re.search(r"params_AbusePreventionHelper\s*=\s*\[([^\]]+)\]", html)
    key, token, _ = [x.strip() for x in m.group(1).split(",")]
    token = token.strip('"')
    body = urllib.parse.urlencode({
        "fromLang": src, "to": "zh-Hans", "text": text, "token": token, "key": key,
    }) + extra_body
    url = path_fmt.format(ig=key)
    hdrs = {"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.bing.com/translator", "Origin": "https://www.bing.com"}
    hdrs.update(extra_headers or {})
    req = urllib.request.Request(url, data=body.encode(), headers=hdrs)
    try:
        r = op.open(req, timeout=15)
        body_out = r.read().decode("utf-8", "replace")
        return f"status={r.status} len={len(body_out)} cl={r.headers.get('Content-Length')} body={body_out[:200]}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} {e.read().decode('utf-8', 'replace')[:200]}"


VARIANTS = {
    "v1-single&": "https://www.bing.com/ttranslatev3?isVertical=1&IG={ig}&IID=translator.5028.1",
    "v2-double&&": "https://www.bing.com/ttranslatev3?isVertical=1&&IG={ig}&IID=translator.5028.1",
    "v3-no-iid": "https://www.bing.com/ttranslatev3?isVertical=1&IG={ig}",
}

for name, fmt in VARIANTS.items():
    try:
        log(f"[bing {name}]", bing_variant("nice shot bro", "en", fmt))
    except Exception as exc:  # noqa: BLE001
        log(f"[bing {name}] EXC", exc)
    try:
        log(f"[bing {name} +gender]", bing_variant(
            "nice shot bro", "en", fmt, "&tryFetchingGenderDebiasedTranslations=true"))
    except Exception as exc:  # noqa: BLE001
        log(f"[bing {name} +gender] EXC", exc)

# Yandex
try:
    q = urllib.parse.urlencode({"srv": "android", "source_lang": "en", "target_lang": "zh",
                                "text": "nice shot bro"})
    r = urllib.request.urlopen(urllib.request.Request(
        "https://translate.yandex.net/api/v1/tr.json/translate?" + q,
        headers={"User-Agent": UA}), timeout=12)
    log("[yandex]", r.status, r.read().decode("utf-8", "replace")[:200])
except Exception as exc:  # noqa: BLE001
    log("[yandex] EXC", repr(exc)[:150])

# 彩云小译公开 demo token
try:
    payload = json.dumps({"source": ["nice shot bro"], "trans_type": "en2zh",
                          "request_id": "demo", "detect": True}).encode()
    req = urllib.request.Request("https://api.interpreter.caiyunai.com/v1/translator",
                                 data=payload,
                                 headers={"content-type": "application/json",
                                          "x-authorization": "token 3975l6lr5pcbvidl6jl2",
                                          "User-Agent": UA})
    r = urllib.request.urlopen(req, timeout=12)
    log("[caiyun]", r.status, r.read().decode("utf-8", "replace")[:300])
except Exception as exc:  # noqa: BLE001
    log("[caiyun] EXC", repr(exc)[:150])

# MyMemory 质量对照
for src, text in [("en", "nice shot bro"), ("en", "one hp behind the box"),
                  ("ja", "ちょっと待って、こっちに敵がいる")]:
    try:
        q = urllib.parse.urlencode({"q": text, "langpair": f"{src}|zh-CN"})
        r = urllib.request.urlopen(urllib.request.Request(
            "https://api.mymemory.translated.net/get?" + q,
            headers={"User-Agent": UA}), timeout=12)
        d = json.loads(r.read().decode("utf-8", "replace"))
        log("[mymemory]", src, text, "->", d["responseData"]["translatedText"])
    except Exception as exc:  # noqa: BLE001
        log("[mymemory] EXC", repr(exc)[:120])

open("C:/Users/pote/Documents/deepseek-harness/default-workspace/valorant-danmaku/tools/_providers.txt",
     "w", encoding="utf-8").write("\n".join(OUT))
