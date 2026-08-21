"""Consistency checks for the canonical supported-worksheet boundary."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "SUPPORTED_WORKSHEET_CONTRACT.md"


def test_canonical_contract_covers_implemented_boundary():
    text = CONTRACT.read_text(encoding="utf-8")

    for heading in (
        "## Question",
        "## Answer-region geometry",
        "## Association and order",
        "## Page boundaries",
        "## Rejection",
        "## Authority",
    ):
        assert heading in text
    for implemented_limit in ("eight pages", "forty questions", "120 PDF points", "180 PDF points"):
        assert implemented_limit in text
    assert "UNSUPPORTED_WORKSHEET_FORMAT" in text
    assert "canonical-short-answer-ecosystems" in text


def test_current_docs_link_to_canonical_contract():
    expected_links = {
        "README.md": "docs/SUPPORTED_WORKSHEET_CONTRACT.md",
        "docs/ARCHITECTURE.md": "SUPPORTED_WORKSHEET_CONTRACT.md",
        "docs/github-actions-deploy.md": "SUPPORTED_WORKSHEET_CONTRACT.md",
        "docs/redesign/CURRENT_PRODUCT_PRD.md": "../SUPPORTED_WORKSHEET_CONTRACT.md",
        "docs/VERIFICATION.md": "SUPPORTED_WORKSHEET_CONTRACT.md",
    }

    for relative_path, link in expected_links.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert link in text, relative_path


def test_current_product_docs_do_not_advertise_three_samples_or_unsafe_fallback():
    prd = (ROOT / "docs" / "redesign" / "CURRENT_PRODUCT_PRD.md").read_text(encoding="utf-8")
    assert "three official" not in prd
    assert "Route uncertain or unsafe placement" not in prd
