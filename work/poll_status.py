# -*- coding: utf-8 -*-
import json, urllib.request, time
from playwright.sync_api import sync_playwright
info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = info["webSocketDebuggerUrl"]
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    page = [pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    page.goto("https://sellers.mvideo.ru/mpa/upload-history/import/products", wait_until="networkidle", timeout=60000)
    time.sleep(5)
    rows = page.evaluate("""() => Array.from(document.querySelectorAll('tr')).map(tr=>tr.innerText.replace(/\\n/g,' | ').trim()).filter(t=>t.length>5)""")
    for r in rows[:12]:
        print(r[:200])
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_status_poll.png")
