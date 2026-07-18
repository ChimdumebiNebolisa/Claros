import pytest

from evaluation.pdf_silver_benchmark.execution import (
    RunLedger,
    classify_provider_error,
    cost_ceiling_usd,
    estimate_cost,
    retry_delay_seconds,
    unit_id,
    worst_case_cost,
)
from evaluation.pdf_silver_benchmark.freeze import build_freeze_manifest, verify_freeze_manifest


def _pages():
    return [
        {
            "page_id": "sample-page-1",
            "source_sha256": "a" * 64,
            "label": {"page_role": "student_worksheet", "selected_block_ids": ["b1"]},
        }
    ]


def test_silver_freeze_verifies_unchanged_metadata():
    manifest = build_freeze_manifest(
        pages=_pages(),
        adjudicator="openai:gpt-5.6",
        prompt_version="closed-world-v1",
        schema_version="closed-world-v1",
    )

    verify_freeze_manifest(manifest)


def test_silver_freeze_rejects_post_freeze_label_change():
    manifest = build_freeze_manifest(
        pages=_pages(),
        adjudicator="openai:gpt-5.6",
        prompt_version="closed-world-v1",
        schema_version="closed-world-v1",
    )
    manifest["pages"][0]["label"]["page_role"] = "answer_key"

    with pytest.raises(ValueError, match="freeze hash"):
        verify_freeze_manifest(manifest)


def test_rate_limit_and_quota_classification_are_distinct():
    assert classify_provider_error(status=429, error_type="insufficient_quota", code="insufficient_quota", message="") == "quota_blocked"
    assert classify_provider_error(status=429, error_type="rate_limit_exceeded", code=None, message="") == "rate_limited"


def test_retry_prefers_provider_retry_after_without_sleeping():
    assert retry_delay_seconds(attempt=3, retry_after=17.0, jitter=0) == 17.0
    assert retry_delay_seconds(attempt=2, jitter=0) == 10.0


def test_cost_and_ceiling_estimate_are_deterministic():
    pricing = {"models": {"gpt-5.6": {"input_per_million_usd": 5, "cached_input_per_million_usd": 0.5, "output_per_million_usd": 30}}}
    assert estimate_cost(pricing, "gpt-5.6", input_tokens=6151, output_tokens=1981) == 0.090185
    assert worst_case_cost(pricing, "gpt-5.6", input_token_estimate=6151, max_output_tokens=3000) > 0.12


def test_default_cost_ceiling_is_five_dollars(monkeypatch):
    monkeypatch.delenv("SILVER_BENCHMARK_MAX_COST_USD", raising=False)
    assert cost_ceiling_usd() == 5.0


def test_successful_checkpoint_is_not_overwritten(tmp_path):
    ledger = RunLedger(tmp_path / "run.json")
    key = unit_id(page_id="p1", role="task", prompt_version="v1", schema_version="s1", model="m1", input_hash="h1")
    ledger.checkpoint(key, {"state": "succeeded"})
    ledger.checkpoint(key, {"state": "rate_limited"})

    assert ledger.get(key)["state"] == "succeeded"
