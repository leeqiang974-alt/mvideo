# -*- coding: utf-8 -*-
"""Connect to running CDP chrome, open MV import page, dump structure + screenshot."""
import json, urllib.request, time
from playwright.sync_api import sync_playwright

info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = info["webSocketDebuggerUrl"]
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    page = None
    for pg in ctx.pages:
        if "sellers.mvideo.ru" in pg.url:
            page = pg; break
    if not page:
        page = ctx.new_page()
    page.bring_to_front()
    page.goto("https://sellers.mvideo.ru/mpa/products/import", wait_until="networkidle", timeout=60000)
    time.sleep(4)
    print("URL:", page.url)
    print("TITLE:", page.title())
    # dump visible buttons/links/inputs
    print("--- INPUTS ---")
    for el in page.query_selector_all("input, button, a, select, [role=button]"):
        try:
            t = (el.inner_text() or el.get_attribute("placeholder") or el.get_attribute("aria-label") or "").strip()
            if t:
                print("  ", el.evaluate("e=>e.tagName"), "|", t[:60])
        except Exception:
            pass
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_import2.png", full_page=True)
    print("SHOT2")
