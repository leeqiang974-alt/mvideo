from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx=b.contexts[0]
    pg=ctx.new_page()
    pg.goto("https://sellers.mvideo.ru/mpa/upload-history/import/products")
    pg.wait_for_load_state("networkidle",timeout=30000)
    print(pg.url)
    print(pg.title())
