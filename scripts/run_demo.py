"""Launch the local synthetic Claros hero demo in deterministic replay mode."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


if __name__ == "__main__":
    os.environ.setdefault("CLAROS_ENV", "development")
    os.environ.setdefault("CLAROS_STORAGE_BACKEND", "local")
    os.environ.setdefault("CLAROS_LOCAL_STORAGE_DIR", ".claros-data")
    os.environ.setdefault("CLAROS_DEMO_MODE", "true")
    if os.environ["CLAROS_ENV"].lower() in {"production", "prod"}:
        raise SystemExit("The offline demo launcher refuses production mode.")
    print("Claros offline demo: http://127.0.0.1:8000/app (local storage)")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
