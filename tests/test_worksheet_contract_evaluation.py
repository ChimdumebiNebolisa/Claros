import json
from pathlib import Path

from evaluation.worksheet_contract_v1.evaluate import evaluate
from evaluation.worksheet_contract_v1.fixtures import FIXTURES, fixture_hashes


def test_fixture_corpus_is_deterministic_distinct_and_substantial():
    first_hashes = fixture_hashes()
    second_hashes = fixture_hashes()

    assert 20 <= len(FIXTURES) <= 30
    assert list(first_hashes) == [fixture.fixture_id for fixture in FIXTURES]
    assert first_hashes == second_hashes
    assert len(set(first_hashes.values())) == len(FIXTURES)


def test_fixture_inventory_covers_supported_and_fail_closed_dimensions():
    tags = {tag for fixture in FIXTURES for tag in fixture.tags}
    required = {
        "supported",
        "numbered",
        "command_style",
        "wrapped_prompts",
        "aligned_line_groups",
        "boxes",
        "text_fields",
        "font_variation",
        "margin_variation",
        "indentation",
        "local_vertical_gaps",
        "multiple_pages",
        "page_edge",
        "numeric",
        "five_questions",
        "ten_questions",
        "twenty_questions",
        "rejected",
        "multiple_choice",
        "checkboxes",
        "table_entry",
        "answer_key",
        "teacher_guide",
        "essay_area",
        "remote_answer",
        "end_collected_answers",
        "multi_column",
        "competing_spaces",
        "unclaimed_space",
        "cross_page",
        "unsupported_transform",
        "image_only_scan",
        "questionless_page",
        "unmappable_diagram",
        "decorative_line",
        "choice_numbering",
        "overlapping_graphic",
        "adjacent_association",
        "staggered_columns",
        "unauthorized_semantic_promotion",
    }
    assert required <= tags


def test_first_party_contract_evaluation_reports_all_agreements(tmp_path: Path):
    report_path = tmp_path / "report.json"
    manifest_path = tmp_path / "manifest.json"
    report = evaluate(report_path=report_path, manifest_path=manifest_path)

    assert report["report_schema_version"] == "worksheet-contract-evaluation-v2"
    assert report["counts"] == {
        "documents": len(FIXTURES),
        "expected_supported": 10,
        "expected_unsupported": len(FIXTURES) - 10,
        "supported_rejections": 0,
        "unsafe_acceptances": 0,
    }
    assert all(metric["value"] == 1.0 for metric in report["metrics"].values())
    assert report["disagreements"] == []
    assert report["rejection_reason_counts"]
    rejected = [item for item in report["documents"] if item["actual_decision"] == "unsupported"]
    assert rejected and all(item["reason_codes"] for item in rejected)
    assert all(item["semantic_provider_calls"] == 0 for item in report["documents"])
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["fixture_count"] == len(FIXTURES)


def test_active_contract_reports_use_adjudication_safe_vocabulary():
    root = Path(__file__).resolve().parent.parent
    active_files = (
        root / "evaluation" / "canonical_v1" / "evaluate.py",
        root / "evaluation" / "canonical_v1" / "README.md",
        root / "evaluation" / "canonical_v1" / "generated" / "baseline.json",
        root / "evaluation" / "worksheet_contract_v1" / "evaluate.py",
        root / "evaluation" / "worksheet_contract_v1" / "fixtures.py",
        root / "evaluation" / "worksheet_contract_v1" / "README.md",
    )
    prohibited = ("accuracy", "correctness", "ground truth", "human gold")
    for path in active_files:
        content = path.read_text(encoding="utf-8").lower()
        for term in prohibited:
            assert term not in content, f"{term!r} is prohibited in {path}"
