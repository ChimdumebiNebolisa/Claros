"""Issue exactly one sanitized provider diagnostic request for a pending unit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.pdf_silver_benchmark.execution import classify_provider_error, safe_error_metadata
from evaluation.pdf_silver_benchmark.run import _annotation_prompt, _call_structured, _image_bytes, _load_pages
from evaluation.pdf_gold_pilot.closed_world import ClosedWorldPageResult


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()
    page = next(item for item in _load_pages() if item.pilot_id == args.page)
    try:
        _call_structured(
            instructions="Return strict closed-world page classification only.",
            text=_annotation_prompt(page, args.role),
            image=_image_bytes(page),
            schema=ClosedWorldPageResult,
        )
        record = {"page_id": args.page, "role": args.role, "outcome": "succeeded"}
    except Exception as exc:
        record = safe_error_metadata(exc)
        record.update({"page_id": args.page, "role": args.role, "model": "gpt-5.6", "requested_max_output_tokens": 4096, "attempt": 1})
        record["classification"] = classify_provider_error(
            status=record["http_status"],
            error_type=record["provider_error_type"],
            code=record["provider_error_code"],
            message=record["provider_message"],
        )
    destination = Path(__file__).resolve().parent / "local_runs" / "rate_limit_diagnostics" / f"{args.page}-{args.role}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record.get(key) for key in ("outcome", "classification", "http_status", "provider_error_type", "provider_error_code")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
