import json, traceback, urllib.request
from playwright.sync_api import sync_playwright

try:
    info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
    ws_url = info["webSocketDebuggerUrl"]
    print("ws:", ws_url)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(ws_url, timeout=30000)
        print("CONNECTED via ws")
        ctx = browser.contexts[0]
        print("pages:", len(ctx.pages))
        for pg in ctx.pages:
            print("  -", pg.url, "|", pg.title()[:60])
        browser.close()
except Exception:
    traceback.print_exc()
