# -*- coding: utf-8 -*-
"""Full read-only inventory: category tree + per-store counts + top-category breakdown.
Writes work/store_inventory.json incrementally. No keys printed.
"""
import json, re, time, collections
from pathlib import Path
import httpx

CRED = Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt")
OUT = Path(r"C:\MvideoERP\work\store_inventory.json")
BASE = "https://api-seller.ozon.ru"


def parse_stores():
    raw = CRED.read_text(encoding="utf-8", errors="replace").splitlines()
    items = [x.strip() for x in raw if x.strip()]
    by = {}
    order = []
    for i, s in enumerate(items):
        m = re.fullmatch(r"(\d{7})", s) or re.search(r"id[：:]\s*(\d{7})", s, re.I)
        if not m:
            continue
        cid = m.group(1)
        key = ""
        if i + 1 < len(items):
            nxt = items[i + 1]
            km = re.search(r"key[：:]\s*([A-Za-z0-9_\-]{8,})", nxt, re.I)
            key = km.group(1) if km else re.sub(r"^key[：:]\s*", "", nxt, flags=re.I)
        label = ""
        if i - 1 >= 0 and "newapi" not in items[i - 1].lower() and not re.fullmatch(r"\d{7}", items[i - 1]):
            label = items[i - 1]
        if cid not in order:
            order.append(cid)
        by[cid] = (label or cid, key)
    return [(c, by[c][0], by[c][1]) for c in order]


def make_client(cid, key):
    return httpx.Client(base_url=BASE,
                        headers={"Client-Id": cid, "Api-Key": key, "Content-Type": "application/json"},
                        timeout=40)


def get_cat_tree(cli):
    """id -> name for description categories (and type ids)."""
    r = cli.post("/v1/description-category/tree", json={})
    names = {}
    def walk(nodes, depth=0):
        for n in nodes or []:
            names[str(n.get("description_category_id"))] = n.get("category_name", "?")
            walk(n.get("type", []), depth + 1)
    walk(r.json().get("result", []))
    return names


def list_pids(cli):
    pids, last = [], ""
    while True:
        r = cli.post("/v3/product/list",
                     json={"filter": {"visibility": "ALL"}, "limit": 100, "last_id": last})
        r.raise_for_status()
        res = r.json().get("result", {})
        for it in res.get("items", []):
            pids.append(it.get("product_id"))
        last = res.get("last_id", "")
        if not last or not res.get("items"):
            break
    return pids


def cat_counts(cli, pids):
    cc = collections.Counter()
    for i in range(0, len(pids), 100):
        chunk = pids[i:i + 100]
        r = cli.post("/v4/product/info/attributes",
                     json={"filter": {"product_id": chunk, "visibility": "ALL"}, "limit": 1000})
        if r.status_code != 200:
            continue
        for it in r.json().get("result", []):
            cc[str(it.get("description_category_id"))] += 1
        time.sleep(0.15)
    return cc


def main():
    stores = parse_stores()
    report = {}
    if OUT.exists():
        try:
            report = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            report = {}
    catnames = {}
    for cid, label, key in stores:
        print("== %s (%s) ==" % (label, cid), flush=True)
        try:
            cli = make_client(cid, key)
            if not catnames:
                catnames = get_cat_tree(cli)
                print("  tree nodes:", len(catnames), flush=True)
            pids = list_pids(cli)
            cc = cat_counts(cli, pids)
            cli.close()
        except Exception as e:
            print("  FAIL:", repr(e)[:200], flush=True)
            report[cid] = {"label": label, "error": repr(e)[:200]}
            continue
        rows = [{"ozon_category_id": c, "ozon_category_name": catnames.get(c, "?"), "count": n}
                for c, n in cc.most_common()]
        report[cid] = {"label": label, "product_count": len(pids), "categories": rows}
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("  total=%d cats=%d" % (len(pids), len(cc)), flush=True)
    # totals
    tot = sum(v.get("product_count", 0) for v in report.values())
    print("TOTAL PRODUCTS ALL STORES:", tot, flush=True)
    print("WROTE", OUT, flush=True)


if __name__ == "__main__":
    main()
