# -*- coding: utf-8 -*-
"""Relaunch LOCAL chrome with CDP (restore session), connect, verify M.Video login."""
import subprocess, time, json, urllib.request, sys, traceback
from playwright.sync_api import sync_playwright

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
UDD = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data"

subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
import time as _t
for _ in range(15):
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"], capture_output=True, text=True)
    if "chrome.exe" not in out.stdout:
        break
    _t.sleep(1)
print("chrome cleared:", "chrome.exe" not in out.stdout, flush=True)

proc = subprocess.Popen([
    CHROME,
    "--remote-debugging-port=9222",
    f"--user-data-dir={UDD}",
    "--no-first-run",
    "--no-default-browser-check",
    "https://sellers.mvideo.ru/mpa/products/import",
])
print("launched", proc.pid, flush=True)

ws_url = None
for i in range(30):
    time.sleep(1)
    try:
        info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3))
        ws_url = info["webSocketDebuggerUrl"]; print("CDP up", i, flush=True); break
    except Exception:
        pass
if not ws_url:
    print("NO CDP"); sys.exit(1)

try:
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(ws_url, timeout=30000)
        ctx = b.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.bring_to_front()
        time.sleep(6)
        print("URL:", page.url, flush=True)
        print("TITLE:", page.title(), flush=True)
        body = page.inner_text("body")[:600]
        print("BODY:", body.replace("\n", " | "), flush=True)
        page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_local_import.png")
        print("SHOT", flush=True)
except Exception:
    traceback.print_exc()
