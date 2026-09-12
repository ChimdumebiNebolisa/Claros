"""Run the bounded Gate 4 live semantic-model selection benchmark."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import Settings  # noqa: E402
from backend.document import extract_physical_ir  # noqa: E402
from backend.semantic import (  # noqa: E402
    MODEL_ORDER,
    GoldSemanticCase,
    MappingExpectations,
    OpenAIResponsesSemanticProvider,
    RecordedSemanticRun,
    SemanticFailure,
    SemanticMapper,
    SemanticReplayCase,
    build_evaluation_fingerprint,
    replay_semantic_model,
    select_semantic_model,
)

CORPUS_DIR = ROOT / "backend" / "tests" / "corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "v2" / "gate4" / "live-model-benchmark.json"
DEFAULT_LATENCY_THRESHOLD_MS = 30_000
PRICE_USD_PER_MILLION_TOKENS = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (4.00, 20.00),
}


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to record the benchmark checkpoint")
    return subprocess.run(  # noqa: S603
        [git, *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _source_checkpoint() -> dict[str, object]:
    tracked_runner = _git(
        "ls-files", "--error-unmatch", "--", "scripts/run-gate4-live-benchmark.py", check=False
    )
    if tracked_runner.returncode != 0:
        raise RuntimeError("commit the benchmark runner before collecting live evidence")
    dirty = _git("diff", "--quiet", "HEAD", "--", check=False)
    if dirty.returncode != 0:
        raise RuntimeError("commit tracked source changes before collecting live evidence")
    return {
        "commit_sha": _git("rev-parse", "HEAD").stdout.strip(),
        "tree_sha": _git("rev-parse", "HEAD^{tree}").stdout.strip(),
        "tracked_source_clean": True,
    }


def _cost_estimator(model: str, input_tokens: int, output_tokens: int) -> int:
    input_price, output_price = PRICE_USD_PER_MILLION_TOKENS[model]
    dollars = input_tokens * input_price / 1_000_000 + output_tokens * output_price / 1_000_000
    return round(dollars * 1_000_000)


def _load_cases() -> tuple[bytes, tuple[SemanticReplayCase, ...], list[dict[str, str]]]:
    manifest_payload = MANIFEST_PATH.read_bytes()
    manifest = json.loads(manifest_payload)
    corpus_bundle = bytearray(manifest_payload)
    cases: list[SemanticReplayCase] = []
    exclusions: list[dict[str, str]] = []
    for fixture in manifest["fixtures"]:
        payload = (CORPUS_DIR / fixture["file"]).read_bytes()
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != fixture["sha256"] or len(payload) != fixture["size_bytes"]:
            raise RuntimeError(f"corpus fixture digest mismatch: {fixture['fixture_id']}")
        corpus_bundle.extend(b"\0")
        corpus_bundle.extend(fixture["fixture_id"].encode("utf-8"))
        corpus_bundle.extend(b"\0")
        corpus_bundle.extend(payload)
        expected = fixture["expected"]
        if fixture["fixture_id"] == "controlled-scan-rejection":
            exclusions.append(
                {
                    "case_id": fixture["fixture_id"],
                    "reason": "deterministic preflight rejection; no model call is permitted",
                    "expected_error_code": expected["error_code"],
                }
            )
            continue

        physical_ir = extract_physical_ir(payload)
        if expected["outcome"] == "reject":
            cases.append(
                SemanticReplayCase(
                    gold=GoldSemanticCase(
                        case_id=fixture["fixture_id"],
                        expected_failure_code="semantic_incomplete",
                    ),
                    ir=physical_ir,
                )
            )
            continue

        exact_questions = tuple(expected["question_text"])
        text_blocks = tuple(
            block for page in physical_ir.pages for block in page.blocks if block.kind == "text"
        )
        required_ids: list[str] = []
        for exact_question in exact_questions:
            matches = [block.id for block in text_blocks if block.text == exact_question]
            if len(matches) != 1:
                raise RuntimeError(
                    f"{fixture['fixture_id']} does not have one exact prompt block "
                    "for its gold text"
                )
            required_ids.append(matches[0])
        cases.append(
            SemanticReplayCase(
                gold=GoldSemanticCase(
                    case_id=fixture["fixture_id"],
                    exact_questions=exact_questions,
                ),
                ir=physical_ir,
                expectations=MappingExpectations(
                    expected_question_count=len(exact_questions),
                    required_prompt_block_ids=tuple(required_ids),
                ),
            )
        )
    return bytes(corpus_bundle), tuple(cases), exclusions


async def _run_live_rephrase(
    *, model: str, provider: OpenAIResponsesSemanticProvider, cases: tuple[SemanticReplayCase, ...]
) -> dict[str, object]:
    case = next(item for item in cases if item.gold.exact_questions)
    started_ns = time.monotonic_ns()
    try:
        await SemanticMapper(provider, model).rephrase(
            ir=case.ir,
            question_key="q_001",
            exact_question=case.gold.exact_questions[0],
            exact_candidate="Mitochondria release usable energy from food for the cell.",
        )
    except SemanticFailure as error:
        return {
            "accepted": False,
            "failure_code": error.code,
            "latency_ms": (time.monotonic_ns() - started_ns) // 1_000_000,
            "model": model,
            "output_redacted": True,
        }
    return {
        "accepted": True,
        "failure_code": None,
        "latency_ms": (time.monotonic_ns() - started_ns) // 1_000_000,
        "model": model,
        "output_redacted": True,
    }


def _run_is_correct(run: RecordedSemanticRun, case: GoldSemanticCase) -> bool:
    if case.expected_failure_code is not None:
        return run.failure_code == case.expected_failure_code and not run.exact_questions
    return run.failure_code is None and run.exact_questions == case.exact_questions


def _record_payload(run: RecordedSemanticRun, gold: GoldSemanticCase) -> dict[str, Any]:
    payload = asdict(run)
    payload["correct"] = _run_is_correct(run, gold)
    payload["expected_question_count"] = len(gold.exact_questions)
    payload["actual_question_count"] = len(run.exact_questions)
    payload.pop("exact_questions")
    return payload


async def _run(args: argparse.Namespace) -> int:
    source_checkpoint = _source_checkpoint()
    settings = Settings()
    if settings.semantic_engine != "openai" or settings.openai_api_key is None:
        raise RuntimeError(
            "Set CLAROS_SEMANTIC_ENGINE=openai and CLAROS_OPENAI_API_KEY before running"
        )

    corpus_payload, cases, exclusions = _load_cases()
    fingerprint = build_evaluation_fingerprint(corpus_payload)
    gold_by_id = {case.gold.case_id: case.gold for case in cases}
    provider = OpenAIResponsesSemanticProvider.from_api_key(
        settings.openai_api_key.get_secret_value(),
        max_output_tokens=settings.semantic_max_output_tokens,
    )
    all_runs: list[RecordedSemanticRun] = []
    decision = None

    for model in MODEL_ORDER:
        print(f"Evaluating {model}", flush=True)
        for run_number in (1, 2, 3):
            records = await replay_semantic_model(
                model=model,
                run=run_number,
                mode="live",
                fingerprint=fingerprint,
                cases=cases,
                provider=provider,
                timeout_seconds=settings.semantic_timeout_seconds,
                cost_estimator=_cost_estimator,
            )
            all_runs.extend(records)
            passed = sum(_run_is_correct(record, gold_by_id[record.case_id]) for record in records)
            print(
                f"  run {run_number}: {passed}/{len(records)} cases correct",
                flush=True,
            )
        try:
            decision = select_semantic_model(
                cases=tuple(case.gold for case in cases),
                runs=tuple(all_runs),
                mode="live",
                fingerprint=fingerprint,
                latency_threshold_ms=args.latency_threshold_ms,
            )
        except SemanticFailure as error:
            if error.code != "semantic_model_gate_failed":
                raise
        else:
            break

    live_rephrase = None
    if decision is not None:
        live_rephrase = await _run_live_rephrase(
            model=decision.selected_model, provider=provider, cases=cases
        )

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        **source_checkpoint,
        "mode": "live",
        "model_order": list(MODEL_ORDER),
        "required_runs": [1, 2, 3],
        "latency_threshold_ms": args.latency_threshold_ms,
        "latency_budget_source": "CLAROS_SEMANTIC_TIMEOUT_SECONDS default (30 seconds)",
        "pricing_observation_usd_per_million_tokens": {
            model: {"input": prices[0], "output": prices[1]}
            for model, prices in PRICE_USD_PER_MILLION_TOKENS.items()
        },
        "fingerprint": asdict(fingerprint),
        "non_model_corpus_cases": exclusions,
        "fixture_digests_verified": True,
        "runs": [_record_payload(run, gold_by_id[run.case_id]) for run in all_runs],
        "selected_model": decision.selected_model if decision is not None else None,
        "evidence": [asdict(item) for item in decision.evidence] if decision is not None else [],
        "live_rephrase": live_rephrase,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Sanitized report: {output}", flush=True)
    if decision is None or live_rephrase is None or not live_rephrase["accepted"]:
        print("No candidate met the Gate 4 acceptance criteria", flush=True)
        return 1
    print(f"Selected model: {decision.selected_model}", flush=True)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--latency-threshold-ms",
        type=int,
        default=DEFAULT_LATENCY_THRESHOLD_MS,
    )
    args = parser.parse_args()
    if args.latency_threshold_ms <= 0:
        parser.error("--latency-threshold-ms must be positive")
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
