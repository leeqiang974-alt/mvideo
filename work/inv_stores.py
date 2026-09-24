# -*- coding: utf-8 -*-
"""Read-only inventory across all 5 Ozon stores.

Parses C:\\Users\\Administrator\\Desktop\\api\\ozonapi.txt -> (label, client_id, api_key)
Then for each store:
  /v3/product/list (visibility=ALL)  -> product count
  /v4/product/info/attributes       -> category_id / category_name distribution
Writes work/store_inventory.json. NEVER prints API keys.
"""
import json, re, sys, time, collections
from pathlib import Path
import httpx

CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
OUT = Path(r"C:\MvideoERP\work\store_inventory.json")


def parse_stores():
    raw = CRED.read_text(encoding="utf-8", errors="replace").splitlines()
    # keep non-empty lines with index
    items = [(i, x.strip()) for i, x in enumerate(raw) if x.strip()]
    stores = {}  # client_id -> (label, key)
    order = []
    for idx, (i, s) in enumerate(items):
        # detect a pure-7-digit store id
        m = re.fullmatch(r"(\d{7})", s) or re.search(r"id[：:]\s*(\d{7})", s, re.I)
        if not m:
            continue
        cid = m.group(1)
        # next non-empty line = key (strip any key: prefix)
        key = ""
        label = ""
        if idx + 1 < len(items):
            nxt = items[idx + 1][1]
            km = re.search(r"key[：:]\s*([A-Za-z0-9_\-]{8,})", nxt, re.I)
            key = km.group(1) if km else re.sub(r"^key[：:]\s*", "", nxt, flags=re.I)
        # previous non-empty line = label (skip comment lines mentioning newapi)
        if idx - 1 >= 0:
            prev = items[idx - 1][1]
            if "newapi" not in prev.lower() and not re.fullmatch(r"\d{7}", prev):
                label = prev
        # later key in file wins (xymallc has 3; last one is the usable newapi)
        if cid not in stores:
            order.append(cid)
        stores[cid] = (label or cid, key)
    return [(c, stores[c][0], stores[c][1]) for c in order]


def list_store(cid, key):
    h = {"Client-Id": cid, "Api-Key": key, "Content-Type": "application/json"}
    ids = []
    last = ""
    with httpx.Client(base_url="https://api-seller.ozon.ru", headers=h, timeout=30) as cli:
        while True:
            r = cli.post("/v3/product/list", json={"filter": {"visibility": "ALL"}, "limit": 100, "last_id": last})
            r.raise_for_status()
            body = r.json()
            res = body.get("result", body)
            items = res.get("items", [])
            for it in items:
                ids.append(it.get("product_id"))
            last = res.get("last_id", "")
            if not last or not items:
                break
    return ids


def cats_of(cid, key, pids):
    h = {"Client-Id": cid, "Api-Key": key, "Content-Type": "application/json"}
    cat = collections.Counter()
    names = {}
    with httpx.Client(base_url="https://api-seller.ozon.ru", headers=h, timeout=60) as cli:
        for i in range(0, len(pids), 100):
            chunk = pids[i:i + 100]
            r = cli.post("/v4/product/info/attributes",
                         json={"filter": {"product_id": chunk, "visibility": "ALL"}, "limit": 1000})
            if r.status_code != 200:
                print("  attrs HTTP", r.status_code, r.text[:200]); continue
            for it in r.json().get("result", []):
                cid_cat = it.get("description_category_id")
                cname = it.get("description_category_name") or it.get("type_name") or "?"
                cat[cid_cat] += 1
                names[cid_cat] = cname
            time.sleep(0.2)
    return cat, names


def main():
    stores = parse_stores()
    print("Parsed %d stores:" % len(stores))
    report = {}
    for cid, label, key in stores:
        print("\n== store %s (client_id=%s) ==" % (label, cid))
        try:
            pids = list_store(cid, key)
        except Exception as e:
            print("  LIST FAIL:", repr(e)[:200]); report[cid] = {"label": label, "error": str(e)[:200]}
            continue
        print("  product count:", len(pids))
        cat, names = cats_of(cid, key, pids)
        print("  categories:")
        rows = []
        for c, n in cat.most_common():
            print("    %-12s %-40s x%d" % (c, str(names.get(c, "?"))[:40], n))
            rows.append({"ozon_category_id": c, "ozon_category_name": names.get(c, "?"), "count": n})
        report[cid] = {"label": label, "product_count": len(pids), "categories": rows}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nWROTE", OUT)


if __name__ == "__main__":
    main()
