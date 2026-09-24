# -*- coding: utf-8 -*-
import json, urllib.request, time
from playwright.sync_api import sync_playwright
info=json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/version",timeout=5))
ws=info["webSocketDebuggerUrl"]
with sync_playwright() as p:
    b=p.chromium.connect_over_cdp(ws); ctx=b.contexts[0]
    page=[pg for pg in ctx.pages if "upload-history" in pg.url or "import" in pg.url]
    page=page[0]; page.bring_to_front()
    page.goto("https://sellers.mvideo.ru/mpa/upload-history/import/products",wait_until="networkidle",timeout=60000)
    time.sleep(4)
    # click "错误详情" link for b2 row (first row)
    txt=page.evaluate("""()=>{
      const rows=[...document.querySelectorAll('tr,mat-row')];
      const out=[];
      for(const r of rows){const t=r.innerText; if(t.includes('b2')) out.push(t);}
      return out;
    }""")
    print("ROW:",txt)
    # click error detail
    try:
        link=page.query_selector("a:has-text('错误详情'), span:has-text('错误详情')")
        if link:
            link.click(); time.sleep(4)
            body=page.evaluate("()=>document.body.innerText")
            import re
            idx=body.find("b2")
            print("DETAIL around b2:\n", body[idx:idx+2000] if idx>=0 else body[:2000])
    except Exception as e:
        print("click err",e)
    page.screenshot(path=r"E:\mvideo\MvideoERP\work\mv_b2_error.png",full_page=True)
