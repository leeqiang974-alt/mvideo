# -*- coding: utf-8 -*-
"""OMNI API connectivity + auth probe (read-only). Never prints the key."""
import sys, json, urllib.request, urllib.error, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://omni-net.sellers.mvideo.ru"
LEGACY_BASE = "https://api.sellers.mvideo.ru"

def load_key():
    env_path = r"C:\MvideoERP\.env"
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("MVIDEO_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

def post(url, body, key, timeout=20):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("api-key", key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            return r.status, raw[:500]
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return e.code, raw[:500]
    except Exception as e:
        return "ERR", repr(e)[:500]

key = load_key()
print("key loaded:", bool(key), "len:", len(key) if key else 0)

# 1) TLS / connectivity to omni-net root
try:
    req = urllib.request.Request(BASE + "/", method="GET")
    req.add_header("User-Agent", "Mozilla/5.0")
    with urllib.request.urlopen(req, timeout=20) as r:
        print("omni-net root:", r.status, r.headers.get("Server", ""))
except Exception as e:
    print("omni-net root ERR:", repr(e)[:300])

# 2) Read-only probe: mapping/list (query identity mapping; safe, no writes)
print("--- /v1/product/mapping/list ---")
st, body = post(BASE + "/v1/product/mapping/list", {"filter": {}, "limit": 3}, key)
print("status:", st)
print("body:", body)

# 3) Read-only probe: price/info
print("--- /v1/product/price/info ---")
st, body = post(BASE + "/v1/product/price/info", {"filter": {}}, key)
print("status:", st)
print("body:", body)

# 4) Read-only probe: stock/info
print("--- /v1/product/stock/info ---")
st, body = post(BASE + "/v1/product/stock/info", {"filter": {}}, key)
print("status:", st)
print("body:", body)

# 5) market location list (FBS warehouses, read-only)
print("--- /v1/market/location/list ---")
st, body = post(BASE + "/v1/market/location/list", {}, key)
print("status:", st)
print("body:", body)

# 6) Legacy checking-connection for comparison
print("--- legacy /v2/checking-connection ---")
req = urllib.request.Request(LEGACY_BASE + "/v2/checking-connection", method="GET")
req.add_header("Api-Key", key)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        print("status:", r.status)
        print("body:", r.read().decode("utf-8", errors="replace")[:300])
except urllib.error.HTTPError as e:
    print("status:", e.code, e.read().decode("utf-8", errors="replace")[:300])
except Exception as e:
    print("ERR:", repr(e)[:300])
