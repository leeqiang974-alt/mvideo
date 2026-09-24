from pathlib import Path
L=[x.strip() for x in Path(r"C:\Users\Administrator\Desktop\api\ozonapi.txt").read_text(encoding="utf-8",errors="replace").splitlines() if x.strip()]
for i,x in enumerate(L): print(i,repr(x[:50]))
