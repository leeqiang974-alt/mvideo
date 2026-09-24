# -*- coding: utf-8 -*-
"""Upload xlsx: select infomodel, fill file, click upload button, verify via history."""
import sys, json, urllib.request
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding="utf-8")
XLSX = sys.argv[1]
ver = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = ver["webSocketDebuggerUrl"]
try:
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(ws)
        ctx = b.contexts[0]
        pages = [pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url]
        page = pages[0] if pages else ctx.new_page()
        page.goto("https://sellers.mvideo.ru/mpa/products/import", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        # close popup
        for sel in ["button:has-text('Закрыть')", "button:has-text('关闭')", "[aria-label='Close']"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click(); print("dismissed popup"); page.wait_for_timeout(1000); break
            except: pass
        # step 1: select infomodel
        cmb = page.locator("input[aria-autocomplete]").first
        cmb.click(); page.wait_for_timeout(500)
        cmb.fill("брошь"); page.wait_for_timeout(2000)
        page.locator("mat-option, [role=option]").first.click(timeout=3000)
        print("infomodel selected")
        page.wait_for_timeout(3000)
        # step 2: fill file
        page.query_selector("input[type=file]").set_input_files(XLSX)
        print("file set")
        # wait for button to enable (up to 20s, poll every 2s)
        clicked = False
        for attempt in range(10):
            page.wait_for_timeout(2000)
            for btn in page.query_selector_all("button"):
                try:
                    t = btn.inner_text().strip()
                    if t == "Загрузить" and btn.is_visible() and not btn.get_attribute("disabled"):
                        btn.click(force=True); print("clicked upload button"); clicked = True; break
                except: pass
            if clicked: break
        if not clicked:
            print("UPLOAD_FAIL: upload button not found or disabled after 20s"); sys.exit(1)
        page.wait_for_timeout(8000)
        # verify via history
        page.goto("https://sellers.mvideo.ru/mpa/upload-history/import/products", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        rows = page.query_selector_all("table tbody tr")
        first = ""
        if rows:
            cells = rows[0].query_selector_all("td")
            first = " | ".join(c.inner_text().strip().replace("\n"," ") for c in cells[:5])
        print("FIRST_HISTORY:", first)
        sys.exit(0)
except Exception as e:
    print("UPLOAD_FAIL", repr(e)); sys.exit(1)
