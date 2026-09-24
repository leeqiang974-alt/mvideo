# -*- coding: utf-8 -*-
"""Search MV group for costume jewelry, list suggestions."""
import json, urllib.request, time
from playwright.sync_api import sync_playwright

info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = info["webSocketDebuggerUrl"]
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    page = [pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    # find the search input (placeholder 按组搜索 / "Искать по группе")
    inp = None
    for cand in page.query_selector_all("input"):
        ph = cand.get_attribute("placeholder") or ""
        if "руп" in ph or "搜索" in ph or "груп" in ph.lower():
            inp = cand; break
    if not inp:
        inp = page.query_selector("input")
    print("placeholder:", inp.get_attribute("placeholder"))
    inp.click()
    inp.fill("")
    inp.type("бижутерия", delay=80)
    time.sleep(3)
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_search_bijut.png")
    # dump dropdown options
    print("--- visible options ---")
    for opt in page.query_selector_all("[role=option], li, .MuiAutocomplete-option"):
        try:
            t = opt.inner_text().strip()
            if t and len(t) < 100:
                print("  OPT:", t)
        except Exception:
            pass
    print("SHOT")
