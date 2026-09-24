# -*- coding: utf-8 -*-
"""Upload the brooch pilot xlsx via the MV import page file input."""
import json, urllib.request, time
from playwright.sync_api import sync_playwright
info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = info["webSocketDebuggerUrl"]
XLSX = r"E:\mvideo\MvideoERP\work\downloads\mv_upload_brooch_pilot.xlsx"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    page = [pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    page.goto("https://sellers.mvideo.ru/mpa/products/import", wait_until="networkidle", timeout=60000)
    time.sleep(3)
    fi = page.query_selector("input[type=file]")
    fi.set_input_files(XLSX)
    print("file set, waiting for parse...")
    time.sleep(8)
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_after_upload_set.png")
    # find upload submit button
    btns = page.query_selector_all("button")
    for btn in btns:
        t = (btn.inner_text() or "").strip()
        print("BTN:", t[:40], "| disabled:", btn.is_disabled())
    # click the enabled upload (Загрузить) button
    target = None
    for btn in btns:
        t = (btn.inner_text() or "").strip()
        if t in ("Загрузить", "下载", "Загрузить файл") and not btn.is_disabled():
            target = btn; break
    if target:
        print("clicking:", target.inner_text())
        target.click()
        time.sleep(8)
    else:
        print("no upload button found")
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_after_upload_submit.png")
    print("URL now:", page.url)
