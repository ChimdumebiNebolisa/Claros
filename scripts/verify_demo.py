"""Verify the synthetic hero artifact without provider access."""
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
    questions = manifest_questions(pdf)
    if questions is None or len(questions) != 4:
        raise SystemExit("hero task graph was not materialized")
    if sum(item["answer_region_status"] == "side_panel" for item in questions) < 2:
        raise SystemExit("hero worksheet lacks intentional side-panel routing")
    print("hero demo fixture verified")


if __name__ == "__main__":
    main()
