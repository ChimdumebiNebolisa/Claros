"""Freeze and verify local, AI-adjudicated silver benchmark metadata.

The benchmark manifest stores content hashes and structured labels only. Source
PDFs and rendered images remain local and are deliberately not copied here.
"""
from __future__ import annotations

import hashlib
import json
import argparse
from pathlib import Path
from typing import Any


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    """Return a stable SHA-256 digest for JSON-compatible metadata."""
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def build_freeze_manifest(
    *,
    pages: list[dict[str, Any]],
    adjudicator: str,
    prompt_version: str,
    schema_version: str,
) -> dict[str, Any]:
    """Build an immutable metadata manifest for AI-adjudicated silver labels."""
    if not pages:
        raise ValueError("a silver benchmark requires at least one page")
    page_ids = [str(page.get("page_id", "")) for page in pages]
    if any(not page_id for page_id in page_ids) or len(page_ids) != len(set(page_ids)):
        raise ValueError("silver benchmark page_id values must be unique and non-empty")
    for page in pages:
        if not page.get("source_sha256"):
            raise ValueError("every silver page requires a source_sha256")
        if "label" not in page:
            raise ValueError("every silver page requires an AI-adjudicated label")
    payload = {
        "label_kind": "ai_adjudicated_silver",
        "adjudicator": adjudicator,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "pages": pages,
    }
    return {**payload, "freeze_sha256": sha256_json(payload)}


def verify_freeze_manifest(manifest: dict[str, Any]) -> None:
    """Reject altered, non-silver, or incomplete benchmark manifests."""
    if manifest.get("label_kind") != "ai_adjudicated_silver":
        raise ValueError("benchmark labels must be explicitly AI-adjudicated silver")
    recorded_digest = manifest.get("freeze_sha256")
    payload = {key: value for key, value in manifest.items() if key != "freeze_sha256"}
    if not isinstance(recorded_digest, str) or recorded_digest != sha256_json(payload):
        raise ValueError("silver benchmark freeze hash did not match manifest contents")
    build_freeze_manifest(
        pages=list(manifest.get("pages", [])),
        adjudicator=str(manifest.get("adjudicator", "")),
        prompt_version=str(manifest.get("prompt_version", "")),
        schema_version=str(manifest.get("schema_version", "")),
    )


def load_and_verify(path: Path) -> dict[str, Any]:
    """Load a local manifest without reading source documents."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    verify_freeze_manifest(manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("benchmark_manifest.json"))
    args = parser.parse_args()
    if not args.verify:
        parser.error("--verify is required")
    if not args.manifest.exists():
        raise SystemExit("benchmark manifest is absent; no AI-adjudicated silver reference is frozen")
    load_and_verify(args.manifest)
    print("silver benchmark freeze verified")
