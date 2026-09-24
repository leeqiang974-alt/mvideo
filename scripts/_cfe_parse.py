# -*- coding: utf-8 -*-
"""Parse mvideo.cfe container structure. Read-only analysis, prints nothing sensitive."""
import struct, sys, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATH = r"D:\Desktop\mvideo\mvideo.cfe"
data = open(PATH, "rb").read()
print("size:", len(data))

def ascii_at(off, n=64):
    chunk = data[off:off+n]
    s = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
    return s

# --- Header block ---
print("\n=== header 256 bytes (hex + ascii) ===")
for row in range(0, 256, 16):
    hexs = " ".join(f"{b:02X}" for b in data[row:row+16])
    asc = "".join(chr(b) if 32 <= b <= 126 else "." for b in data[row:row+16])
    print(f"{row:06X}  {hexs}  {asc}")

# --- Collect all ascii runs >= 6 chars anywhere in file ---
print("\n=== notable ascii runs (>=6, dedup, first 200) ===")
runs = re.findall(rb"[ -~]{6,}", data)
seen = {}
for r in runs:
    s = r.decode("ascii", "replace")
    if re.fullmatch(r"[0-9a-f]{8,}", s) and len(s) > 12:
        continue  # hex offsets
    if s.strip("0 ").strip() == "":
        continue
    seen[s] = seen.get(s, 0) + 1
for s, c in list(seen.items())[:200]:
    print(f"x{c:3d}  {s[:120]}")
