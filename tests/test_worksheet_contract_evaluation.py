from pathlib import Path

from evaluation.worksheet_contract_v1.evaluate import evaluate


def test_first_party_contract_evaluation_rejects_unsupported_documents(tmp_path: Path):
    report = evaluate(report_path=tmp_path / "report.json")

    assert report["report_schema_version"] == "worksheet-contract-evaluation-v1"
    assert report["counts"] == {
        "documents": 3,
        "expected_supported": 1,
        "expected_unsupported": 2,
        "unsafe_acceptances": 0,
    }
    assert report["metrics"] == {
        "decision_agreement": 1.0,
        "supported_acceptance": 1.0,
        "unsupported_rejection": 1.0,
    }
    assert (tmp_path / "report.json").is_file()


def test_active_canonical_reports_use_adjudication_safe_vocabulary():
    root = Path(__file__).resolve().parent.parent
    active_files = (
        root / "evaluation" / "canonical_v1" / "evaluate.py",
        root / "evaluation" / "canonical_v1" / "README.md",
        root / "evaluation" / "canonical_v1" / "generated" / "baseline.json",
        root / "evaluation" / "worksheet_contract_v1" / "evaluate.py",
        root / "evaluation" / "worksheet_contract_v1" / "README.md",
    )
    prohibited = ("accuracy", "correctness", "ground truth", "human gold")
    for path in active_files:
        content = path.read_text(encoding="utf-8").lower()
        for term in prohibited:
            assert term not in content, f"{term!r} is prohibited in {path}"
