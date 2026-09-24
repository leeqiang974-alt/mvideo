# -*- coding: utf-8 -*-
"""Copy logged-in Chrome profile to a fresh dir, launch with CDP, verify MV."""
import subprocess, time, json, urllib.request, os, shutil, sys, traceback

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SRC_UDD = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data"
NEW_UDD = r"C:\Users\Administrator\mvauto\User Data"

# 1) kill
subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
for _ in range(15):
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"], capture_output=True, text=True)
    if "chrome.exe" not in out.stdout: break
    time.sleep(1)
print("chrome killed", flush=True)

# 2) copy profile (skip caches)
os.makedirs(NEW_UDD, exist_ok=True)
ls_src = os.path.join(SRC_UDD, "Local State")
if os.path.exists(ls_src):
    shutil.copy2(ls_src, os.path.join(NEW_UDD, "Local State"))
excl_dirs = ["Cache", "Code Cache", "GPUCache", "ShaderCache", "GrpCache",
             "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache",
             "Service Worker", "CacheStorage", "GraphiteDawnCache", "component_crx_cache"]
src_def = os.path.join(SRC_UDD, "Default")
dst_def = os.path.join(NEW_UDD, "Default")
args = ["robocopy", src_def, dst_def, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NS", "/NC"]
for d in excl_dirs:
    args += ["/XD", os.path.join(src_def, d)]
r = subprocess.run(args, capture_output=True, text=True)
print("robocopy rc:", r.returncode, flush=True)

# 3) launch with NEW user-data-dir
proc = subprocess.Popen([
    CHROME,
    "--remote-debugging-port=9222",
    f"--user-data-dir={NEW_UDD}",
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

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws_url, timeout=30000)
    ctx = b.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.bring_to_front(); time.sleep(6)
    print("URL:", page.url, flush=True)
    print("TITLE:", page.title(), flush=True)
    print("BODY:", page.inner_text("body")[:500].replace("\n", " | "), flush=True)
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_local_import.png")
    print("SHOT", flush=True)
