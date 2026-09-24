# -*- coding: utf-8 -*-
"""Upload xlsx via API directly (more stable than UI)."""
import sys, json, urllib.request, requests
sys.stdout.reconfigure(encoding="utf-8")

XLSX = sys.argv[1]

# get token from browser
ver = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = ver["webSocketDebuggerUrl"]
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    pages = [pg for pg in ctx.pages if "sellers.mvideo.ru/mpa" in pg.url and "/login/" not in pg.url]
    if not pages:
        print("no mvideo tab")
        sys.exit(1)
    page = pages[0]
    kauth = json.loads(page.evaluate("localStorage.getItem('kauth')"))
    token = kauth["accessToken"]

# upload via API
url = "https://sellers.mvideo.ru/api/products/template/upload"
headers = {
    "Authorization": f"Bearer {token}",
    "Referer": "https://sellers.mvideo.ru/mpa/products/import",
    "Origin": "https://sellers.mvideo.ru",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}
with open(XLSX, "rb") as f:
    files = {"file": (XLSX.split("\\")[-1], f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    try:
        r = requests.post(url, headers=headers, files=files, timeout=120)
        print(f"status: {r.status_code}")
        if r.status_code == 200:
            print("UPLOAD_OK")
        else:
            print(f"UPLOAD_FAIL: {r.text[:200]}")
            sys.exit(1)
    except Exception as e:
        print(f"UPLOAD_ERR: {e}")
        sys.exit(1)
