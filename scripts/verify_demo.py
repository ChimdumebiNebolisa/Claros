"""Verify the historical hero artifact remains isolated from production."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from demo.hero_fixture import load_hero, manifest_questions


def main() -> None:
    pdf = Path("demo/hero_worksheet.pdf").read_bytes()
    loaded = load_hero(pdf)
    if loaded is None:
        raise SystemExit("hero worksheet hash did not match its replay fixture")
    manifest = __import__("json").loads(Path("demo/hero_worksheet_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("semantic_source") != "synthetic_fixture" or manifest.get("generated_by_model") is not False:
        raise SystemExit("hero semantic fixture provenance is invalid")
    questions = manifest_questions(pdf)
    if questions is None or len(questions) != 4:
        raise SystemExit("hero task graph was not materialized")
    assignment_source = Path("assignment_service.py").read_text(encoding="utf-8")
    if "manifest_questions" in assignment_source or "offline-synthetic-fixture" in assignment_source:
        raise SystemExit("historical hero replay still bypasses the production worksheet gate")
    print("historical hero fixture verified and isolated from production")


if __name__ == "__main__":
    main()
