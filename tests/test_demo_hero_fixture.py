from pathlib import Path

import assignment_service
import config
from demo.hero_fixture import load_hero, manifest_questions


def test_hero_replay_is_hash_bound_and_validated():
    pdf = Path("demo/hero_worksheet.pdf").read_bytes()
    loaded = load_hero(pdf)

    assert loaded is not None
    assert len(loaded[2]) == 4
    assert load_hero(pdf + b"changed") is None
    assert manifest_questions(pdf)[1]["answer_region_status"] == "approved"
    assert manifest_questions(pdf)[3]["answer_region_status"] == "side_panel"


def test_demo_mode_uses_replay_only_for_matching_hero(monkeypatch):
    monkeypatch.setattr(config, "CLAROS_DEMO_MODE", True)
    manifest = assignment_service._parse_and_build_manifest(
        "550e8400-e29b-41d4-a716-446655440000",
        "demo/hero_worksheet.pdf",
    )

    assert manifest.parser == "demo-replay-synthetic-v1"
    assert len(manifest.questions) == 4
