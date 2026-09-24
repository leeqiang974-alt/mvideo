# -*- coding: utf-8 -*-
"""Select the jewelry/brooch group, list info models, download template."""
import json, urllib.request, time, os
from playwright.sync_api import sync_playwright
info = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5))
ws = info["webSocketDebuggerUrl"]
DL_DIR = r"E:\mvideo\MvideoERP\work\downloads"
os.makedirs(DL_DIR, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp(ws)
    ctx = b.contexts[0]
    page = [pg for pg in ctx.pages if "sellers.mvideo.ru" in pg.url][0]
    page.bring_to_front()
    inp = page.query_selector("input.mat-mdc-autocomplete-trigger")
    inp.click(); time.sleep(0.4); inp.fill(""); inp.type("брошь", delay=70); time.sleep(2.5)
    # click the option containing '胸针' (brooch)
    opts = page.query_selector_all(".mat-mdc-option")
    chosen = None
    for o in opts:
        if "胸针" in o.inner_text():
            chosen = o; break
    chosen.click(); time.sleep(2)
    print("selected group. Now info model options:")
    # info model is a second autocomplete; dump visible inputs
    els = page.evaluate("""() => Array.from(document.querySelectorAll('input')).map(e=>({ph:e.placeholder, vis:e.offsetParent!==null, x:e.getBoundingClientRect().x, y:e.getBoundingClientRect().y}))""")
    for e in els:
        if e["vis"]: print("   input:", e)
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_group_selected.png")
    # click the info-model autocomplete (2nd visible)
    vis_inputs = [e for e in page.query_selector_all("input") if e.is_visible()]
    print("visible inputs:", len(vis_inputs))
    if len(vis_inputs) >= 2:
        vis_inputs[1].click(); time.sleep(1.5)
        imgs = page.evaluate("""() => Array.from(document.querySelectorAll('.mat-mdc-option')).map(o=>o.innerText.trim())""")
        print("INFO MODELS:")
        for im in imgs[:15]:
            print("   *", im[:90])
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_models.png")
    print("done")
