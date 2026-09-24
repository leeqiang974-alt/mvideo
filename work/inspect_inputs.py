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
    page.goto("https://sellers.mvideo.ru/mpa/products/import", wait_until="networkidle", timeout=60000)
    time.sleep(3)
    els = page.evaluate("""() => Array.from(document.querySelectorAll('input')).map(e => ({
        ph: e.placeholder, type: e.type, vis: e.offsetParent!==null,
        cls: (e.className||'').toString().slice(0,60),
        x: e.getBoundingClientRect().x, y: e.getBoundingClientRect().y
    }))""")
    for e in els:
        print(e)
