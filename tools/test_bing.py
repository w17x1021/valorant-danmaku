import http.cookiejar
import json
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [("User-Agent", UA), ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")]

html = opener.open("https://www.bing.com/translator", timeout=15).read().decode("utf-8", "replace")
m = re.search(r"params_AbusePreventionHelper\s*=\s*\[([^\]]+)\]", html)
print("params:", m.group(1) if m else None)
key, token, _ = m.group(1).split(",")
key = key.strip()
token = token.strip().strip('"')

text = "nice shot bro, one hp behind the box"
body = urllib.parse.urlencode({
    "fromLang": "en", "to": "zh-Hans", "text": text,
    "token": token, "key": key,
}).encode()
url = f"https://www.bing.com/ttranslatev3?isVertical=1&IG={key}&IID=translator.5028.1"
req = urllib.request.Request(url, data=body, headers={
    "User-Agent": UA,
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.bing.com/translator",
    "Origin": "https://www.bing.com",
})
try:
    resp = opener.open(req, timeout=15)
    raw = resp.read().decode("utf-8", "replace")
    print("status:", resp.status, "body:", raw[:500])
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode("utf-8", "replace")[:500])

# 日文
body = urllib.parse.urlencode({
    "fromLang": "ja", "to": "zh-Hans", "text": "ちょっと待って、こっちに敵がいる",
    "token": token, "key": key,
}).encode()
req = urllib.request.Request(url, data=body, headers={
    "User-Agent": UA,
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.bing.com/translator",
    "Origin": "https://www.bing.com",
})
try:
    resp = opener.open(req, timeout=15)
    print("ja:", resp.read().decode("utf-8", "replace")[:300])
except urllib.error.HTTPError as e:
    print("ja HTTP", e.code, e.read().decode("utf-8", "replace")[:300])
