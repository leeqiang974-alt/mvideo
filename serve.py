"""uvicorn launcher for the M.Video ERP API.

Run: .venv\\Scripts\\python.exe serve.py
Listens on http://127.0.0.1:8077
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.normpath(os.path.join(_HERE, "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import uvicorn  # noqa: E402


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8077")),
        reload=False,
    )


if __name__ == "__main__":
    main()
