# -*- coding: utf-8 -*-
"""Launch chromex with CDP in THIS process, wait, then connect immediately."""
import subprocess, time, json, urllib.request, sys, traceback
from playwright.sync_api import sync_playwright

CHROME = r"C:\Users\Administrator\AppData\Local\Google\Chrome\Bin\chromex.exe"
UDD = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data"

# kill
subprocess.run(["taskkill", "/F", "/IM", "chromex.exe"],
               capture_output=True)
time.sleep(4)

proc = subprocess.Popen([
    CHROME,
    "--remote-debugging-port=9222",
    "--remote-debugging-address=127.0.0.1",
    f"--user-data-dir={UDD}",
    "--no-first-run",
    "--no-default-browser-check",
    "https://seller.mvideo.ru/mpa/products/import",
])
print("launched pid", proc.pid, flush=True)

ws_url = None
for i in range(30):
    time.sleep(1)
    try:
        info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3))
        ws_url = info["webSocketDebuggerUrl"]
        print("CDP up after", i, "s", flush=True)
        break
    except Exception:
        print("  wait", i, flush=True)
if not ws_url:
    print("FAILED to bring CDP up"); sys.exit(1)

try:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(ws_url, timeout=30000)
        print("CONNECTED", flush=True)
        ctx = browser.contexts[0]
        print("pages:", len(ctx.pages), flush=True)
        for pg in ctx.pages:
            print("  -", pg.url, "|", pg.title()[:70], flush=True)
        page = ctx.pages[0]
        time.sleep(4)
        print("NOW URL:", page.url, flush=True)
        print("NOW TITLE:", page.title(), flush=True)
        body = page.inner_text("body")[:400]
        print("BODY:", body.replace("\n", " | "), flush=True)
        page.screenshot(path=r"C:\MvideoERP\work\mv_import_page.png")
        print("SHOT saved", flush=True)
except Exception:
    traceback.print_exc()
