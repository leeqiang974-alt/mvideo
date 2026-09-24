# -*- coding: utf-8 -*-
import json, urllib.request, time
from playwright.sync_api import sync_playwright
info=json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version",timeout=5))
ws=info["webSocketDebuggerUrl"]
TERM="резинка для волос"
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp(ws); ctx=b.contexts[0]
    page=[pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    page.goto("https://sellers.mvideo.ru/mpa/products/import",wait_until="networkidle",timeout=60000)
    time.sleep(3)
    inp=page.query_selector("input.mat-mdc-autocomplete-trigger")
    inp.click(); time.sleep(0.4); inp.fill(""); inp.type(TERM,delay=60); time.sleep(2.5)
    opt=page.query_selector(".mat-mdc-option"); opt.click(); time.sleep(2)
    btns=page.evaluate("()=>Array.from(document.querySelectorAll('button,a')).map(b=>b.innerText.trim()).filter(t=>t && t.length<40)")
    print("BTNS:",btns)
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_scrunchie_sel.png",full_page=False)
