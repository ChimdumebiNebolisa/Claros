#!/usr/bin/env python3
"""Append privacy-safe pilot counters to a local JSON file (no transcript/answer content)."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_EVENTS = {
    "ingestion_ok",
    "ingestion_fallback",
    "session_started",
    "session_completed_export",
    "write_success",
    "write_error",
    "error_recovered",
    "effort_score",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Record privacy-safe pilot metric event")
    parser.add_argument("--event", required=True, choices=sorted(ALLOWED_EVENTS))
    parser.add_argument("--value", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("pilot_metrics.jsonl"))
    args = parser.parse_args()

    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": args.event,
        "value": args.value,
    }
    with args.out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    print(f"recorded {args.event}={args.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
