from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    for c in b.contexts:
        for pg in c.pages: print(pg.url)
