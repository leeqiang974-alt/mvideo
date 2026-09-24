# -*- coding: utf-8 -*-
"""Upload xlsx via UI (proven working). Select infomodel brooch, fill file, click Загрузить."""
import sys, json, urllib.request
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding="utf-8")
XLSX = sys.argv[1]
ver = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = ver["webSocketDebuggerUrl"]
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    pages = [pg for pg in ctx.pages if "sellers.mvideo.ru/mpa" in pg.url and "/login/" not in pg.url]
    if pages:
        page = pages[0]
        print(f"using existing tab: {page.url[:60]}")
    else:
        print("no mvideo tab found, opening new")
        page = ctx.new_page()
    # retry navigation up to 3 times
    for attempt in range(3):
        try:
            page.goto("https://sellers.mvideo.ru/mpa/products/import", wait_until="domcontentloaded", timeout=60000)
            break
        except Exception as e:
            print(f"nav attempt {attempt} failed: {e}")
            page.wait_for_timeout(5000)
    else:
        print("UPLOAD_FAIL: cannot navigate")
        sys.exit(1)
    page.wait_for_timeout(8000)
    # close popups
    for sel in ["button:has-text('Закрыть')", "button:has-text('close')", "[aria-label='Close']"]:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(force=True); page.wait_for_timeout(1000); break
        except: pass
    # select infomodel brooch
    cmb = page.locator("input[aria-autocomplete]").first
    cmb.click(); page.wait_for_timeout(500)
    cmb.fill("брошь"); page.wait_for_timeout(2000)
    page.locator("mat-option, [role=option]").first.click(timeout=3000, force=True)
    print("infomodel selected")
    page.wait_for_timeout(3000)
    # upload file
    page.query_selector("input[type=file]").set_input_files(XLSX)
    print("file set")
    # wait for Загрузить button to enable (poll up to 30s)
    clicked = False
    for i in range(15):
        page.wait_for_timeout(2000)
        for btn in page.query_selector_all("button"):
            try:
                t = btn.inner_text().strip()
                if t in ("Загрузить", "下载") and btn.is_visible() and not btn.get_attribute("disabled"):
                    btn.click(force=True)
                    print(f"CLICKED upload button at attempt {i}")
                    clicked = True; break
            except: pass
        if clicked: break
    if not clicked:
        print("UPLOAD_FAIL: button not enabled")
        sys.exit(1)
    page.wait_for_timeout(10000)
    print("UPLOAD_OK")
