# -*- coding: utf-8 -*-
import json, urllib.request, time
from playwright.sync_api import sync_playwright
info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = info["webSocketDebuggerUrl"]

def search(term, shot):
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(ws)
        ctx = b.contexts[0]
        page = [pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
        page.bring_to_front()
        inp = page.query_selector("input.mat-mdc-autocomplete-trigger")
        inp.click()
        time.sleep(0.5)
        inp.fill("")
        inp.type(term, delay=90)
        time.sleep(3)
        opts = page.evaluate("""() => Array.from(document.querySelectorAll('.mat-mdc-option, [role=option]')).map(o=>o.innerText.trim()).filter(Boolean)""")
        print("TERM:", term, "->", len(opts), "opts")
        for o in opts[:20]:
            print("   *", o[:90])
        page.screenshot(path=shot)
        b.close()

search("бижутерия", r"E:\mvideo\MvideoERP\work\mv_s1.png")
