# -*- coding: utf-8 -*-
import json, urllib.request, time
from playwright.sync_api import sync_playwright
info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = info["webSocketDebuggerUrl"]
TERMS = ["брошь", "значок", "брелок", "серьги", "браслет", "подвеска", "аксессуары", "украшения"]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    page = [pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    for term in TERMS:
        try:
            inp = page.query_selector("input.mat-mdc-autocomplete-trigger")
            inp.click(); time.sleep(0.4)
            inp.fill(""); inp.type(term, delay=70); time.sleep(2.5)
            opts = page.evaluate("""() => Array.from(document.querySelectorAll('.mat-mdc-option, [role=option]')).map(o=>o.innerText.trim()).filter(Boolean)""")
            print("TERM:", term, "->", len(opts))
            for o in opts[:8]:
                print("    *", o[:80])
            # press Escape to close dropdown
            page.keyboard.press("Escape"); time.sleep(0.5)
        except Exception as e:
            print("ERR", term, repr(e)[:100])
