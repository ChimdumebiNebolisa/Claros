"""Current frontend documentation must match the shipped presentation contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_design_contract_matches_simplified_frontend():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for phrase in (
        "Instrument Sans",
        "Shadcn",
        "Geist",
        "approximately",
        "two-thirds",
        "Confirmed",
        "Failed write",
        "700px",
        "interactive Shadcn product composition",
    ):
        assert phrase in design


def test_verification_points_to_current_dated_evidence():
    verification = (ROOT / "docs" / "VERIFICATION.md").read_text(encoding="utf-8")
    evidence_paths = (
        ROOT / "docs" / "evidence" / "LANDING_SHADCN_2026-07-30.md",
        ROOT / "docs" / "evidence" / "FRONTEND_SIMPLIFICATION_2026-07-29.md",
    )
    for evidence_path in evidence_paths:
        assert evidence_path.name in verification
        assert evidence_path.exists()


def test_build_week_delta_records_frontend_release_scope():
    delta = (ROOT / "docs" / "BUILD_WEEK_DELTA.md").read_text(encoding="utf-8")
    assert "Frontend simplification release" in delta
    assert "Shadcn landing refinement" in delta
    assert "confirmation produced `/confirm` without `/api/write/`" in delta


def test_cloud_run_workflow_is_the_single_bounded_deployment_contract():
    workflow = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    deploy_notes = (ROOT / "DEPLOY.md").read_text(encoding="utf-8")
    manual_script = (ROOT / "deploy.sh").read_text(encoding="utf-8")

    for phrase in (
        "APP_ENV=production",
        "CLAROS_STORAGE_BACKEND=gcs",
        "MAX_PDF_PAGES=8",
        "MAX_WORKSHEET_QUESTIONS=40",
        "MAX_SEMANTIC_PROVIDER_CALLS=8",
        "--max-instances 2",
        "--concurrency 1",
        "--startup-probe",
        "--liveness-probe",
        "GEMINI_API_KEY=claros-gemini-api-key:latest",
    ):
        assert phrase in workflow
    assert "${{ secrets.GEMINI_API_KEY }}" not in workflow
    assert "only supported production deployment path" in deploy_notes
    assert "gcloud run deploy" not in manual_script


def test_production_image_and_landing_build_are_hygienic():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    package = (ROOT / "marketing" / "package.json").read_text(encoding="utf-8")
    prerender = (ROOT / "marketing" / "scripts" / "prerender.mjs").read_text(encoding="utf-8")
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "USER claros" in dockerfile
    assert "worksheet_contract.py" in dockerfile
    assert package.index('"devDependencies"') < package.index('"shadcn"')
    assert 'replace(/\\r\\n?/g, "\\n")' in prerender
    assert "frontend/landing.html text eol=lf" in attributes
