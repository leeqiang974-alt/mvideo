# -*- coding: utf-8 -*-
import json, urllib.request, time, sys
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright
info=json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version",timeout=5))
ws=info["webSocketDebuggerUrl"]
JOBS=[("контейнер для продуктов",r"E:\mvideo\MvideoERP\work\downloads\template_container.xlsx"),
      ("калейдоскоп",r"E:\mvideo\MvideoERP\work\downloads\template_kaleidoscope.xlsx")]
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp(ws); ctx=b.contexts[0]
    page=[pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    for term,out in JOBS:
        try:
            page.goto("https://sellers.mvideo.ru/mpa/products/import",wait_until="networkidle",timeout=60000)
            time.sleep(3)
            inp=page.query_selector("input.mat-mdc-autocomplete-trigger")
            inp.click(); time.sleep(0.4); inp.fill(""); inp.type(term,delay=60); time.sleep(2.5)
            opt=page.query_selector(".mat-mdc-option"); opt.click(); time.sleep(2)
            with page.expect_download(timeout=30000) as dl:
                page.click("button:has-text('下载模板')")
            dl.value.save_as(out); print("saved",out)
        except Exception as e:
            print("FAIL",term,repr(e)[:100])
