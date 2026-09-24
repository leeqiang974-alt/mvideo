# -*- coding: utf-8 -*-
"""Connect to the existing chromex via CDP, verify M.Video session, screenshot."""
import time
from playwright.sync_api import sync_playwright

OUT = r"C:\MvideoERP\work\mv_login_check.png"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    pages = ctx.pages
    print("open pages:", len(pages))
    page = pages[0] if pages else ctx.new_page()
    page.bring_to_front()
    # try the import page
    try:
        page.goto("https://seller.mvideo.ru/mpa/products/import", wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        print("goto err:", repr(e)[:200])
    time.sleep(5)
    print("URL:", page.url)
    print("TITLE:", page.title())
    # detect login form vs logged-in dashboard
    body = page.inner_text("body")[:800]
    print("BODY_HEAD:", body[:500].replace("\n", " | "))
    page.screenshot(path=OUT, full_page=False)
    print("SHOT:", OUT)
    browser.close()
