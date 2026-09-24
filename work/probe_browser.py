import importlib.util, shutil, os
print("chrome_pf:", os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe"))
print("chrome_pf86:", os.path.exists(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"))
print("msedge:", os.path.exists(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"))
for mod in ("playwright", "selenium", "DrissionPage", "pyppeteer"):
    print(mod, "->", bool(importlib.util.find_spec(mod)))
# edge/chrome in user local
for p in [os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
          os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe")]:
    print("candidate:", p, os.path.exists(p))
