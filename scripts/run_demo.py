"""Launch the local synthetic Claros hero demo in deterministic replay mode."""
from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    os.environ["CLAROS_DEMO_MODE"] = "true"
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
