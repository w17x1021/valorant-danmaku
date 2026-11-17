"""继续挖 Bing（cn.bing.com / edge 域）翻译通道。"""
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


def try_host(host):
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA), ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")]
    html = op.open(f"https://{host}/translator", timeout=15).read().decode("utf-8", "replace")
    m = re.search(r"params_AbusePreventionHelper\s*=\s*\[([^\]]+)\]", html)
    if not m:
        log(host, "no params, len", len(html))
        return
    key, token, _ = [x.strip() for x in m.group(1).split(",")]
    token = token.strip('"')
    cookies = {c.name: c.value for c in cj}
    log(host, "cookies:", ",".join(cookies))

    body = urllib.parse.urlencode({"fromLang": "en", "to": "zh-Hans",
                                   "text": "nice shot bro, one hp behind the box",
                                   "token": token, "key": key})
    url = f"https://{host}/ttranslatev3?isVertical=1&IG={key}&IID=translator.5028.1"
    hdrs = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"https://{host}/translator",
        "Origin": f"https://{host}",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    try:
        r = op.open(urllib.request.Request(url, data=body.encode(), headers=hdrs), timeout=15)
        txt = r.read().decode("utf-8", "replace")
        log(host, "POST", r.status, "len", len(txt), txt[:300])
    except urllib.error.HTTPError as e:
        log(host, "POST HTTP", e.code, e.read().decode("utf-8", "replace")[:300])


for h in ["cn.bing.com", "www.bing.com"]:
    try:
        try_host(h)
    except Exception as exc:  # noqa: BLE001
        log(h, "EXC", repr(exc)[:200])

open("C:/Users/pote/Documents/deepseek-harness/default-workspace/valorant-danmaku/tools/_bing2.txt",
     "w", encoding="utf-8").write("\n".join(OUT))
