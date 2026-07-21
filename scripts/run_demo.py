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
    os.environ["CLAROS_DEMO_MODE"] = "true"
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
