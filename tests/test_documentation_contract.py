"""Current frontend documentation must match the shipped presentation contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_design_contract_matches_simplified_frontend():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for phrase in (
        "Instrument Sans",
        "approximately",
        "two-thirds",
        "Confirmed",
        "Failed write",
        "700px",
        "real Review-state product evidence",
    ):
        assert phrase in design


def test_verification_points_to_current_dated_evidence():
    verification = (ROOT / "docs" / "VERIFICATION.md").read_text(encoding="utf-8")
    evidence_path = ROOT / "docs" / "evidence" / "FRONTEND_SIMPLIFICATION_2026-07-29.md"
    assert evidence_path.name in verification
    assert evidence_path.exists()


def test_build_week_delta_records_frontend_release_scope():
    delta = (ROOT / "docs" / "BUILD_WEEK_DELTA.md").read_text(encoding="utf-8")
    assert "Frontend simplification release" in delta
    assert "confirmation produced `/confirm` without `/api/write/`" in delta
