from pathlib import Path

from demo.hero_fixture import load_hero, manifest_questions


def test_hero_replay_is_hash_bound_and_validated():
    pdf = Path("demo/hero_worksheet.pdf").read_bytes()
    loaded = load_hero(pdf)

    assert loaded is not None
    assert len(loaded[2]) == 4
    assert load_hero(pdf + b"changed") is None
    assert manifest_questions(pdf)[1]["answer_region_status"] == "approved"
    assert manifest_questions(pdf)[3]["answer_region_status"] == "side_panel"
