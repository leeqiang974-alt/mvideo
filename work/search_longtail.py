# -*- coding: utf-8 -*-
import json, urllib.request, time
from playwright.sync_api import sync_playwright
info=json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version",timeout=5))
ws=info["webSocketDebuggerUrl"]
TERMS=["шапка","трещотка","крабик для волос","силиконовая форма","брелок"]
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp(ws); ctx=b.contexts[0]
    page=[pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    page.goto("https://sellers.mvideo.ru/mpa/products/import",wait_until="networkidle",timeout=60000)
    time.sleep(3)
    for term in TERMS:
        try:
            inp=page.query_selector("input.mat-mdc-autocomplete-trigger")
            inp.click(); time.sleep(0.4); inp.fill(""); inp.type(term,delay=60); time.sleep(2.2)
            opts=page.evaluate("()=>Array.from(document.querySelectorAll('.mat-mdc-option,[role=option]')).map(o=>o.innerText.trim()).filter(Boolean)")
            print("TERM:",term,"->",len(opts))
            for o in opts[:6]: print("   *",o[:80])
            page.keyboard.press("Escape"); time.sleep(0.4)
        except Exception as e:
            print("ERR",term,repr(e)[:80])
