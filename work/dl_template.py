# -*- coding: utf-8 -*-
import json, urllib.request, time, os
from playwright.sync_api import sync_playwright
info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = info["webSocketDebuggerUrl"]
DL = r"E:\mvideo\MvideoERP\work\downloads"
os.makedirs(DL, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    page = [pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    with page.expect_download(timeout=60000) as dl_info:
        page.click("button:has-text('下载模板')")
    dl = dl_info.value
    target = os.path.join(DL, "template_brosh.xlsx")
    dl.save_as(target)
    print("DOWNLOADED:", target, os.path.getsize(target), "bytes")
