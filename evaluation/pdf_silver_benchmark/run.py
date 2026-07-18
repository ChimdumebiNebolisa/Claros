"""Generate local-only AI-adjudicated silver labels from frozen pilot evidence.

This runner never sends one annotator another annotator's output. It writes
only structured, ID-only model results plus safe run metadata; rendered pages
and physical source text stay in the pre-existing ignored pilot directory.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from evaluation.pdf_gold_pilot.closed_world import (
    ClosedWorldPageResult,
    PilotPageInput,
    derive_tasks,
    validate_closed_world_result,
)
from evaluation.pdf_silver_benchmark.execution import cost_ceiling_usd, estimate_cost, worst_case_cost

PILOT_ROOT = ROOT / "output" / "pdf-gold-pilot"
BENCHMARK_ROOT = Path(__file__).resolve().parent
ROLE_CONFIG_PATH = BENCHMARK_ROOT / "model_roles.json"
PRICING_PATH = BENCHMARK_ROOT / "pricing.json"

ROLE_INSTRUCTIONS = {
    "task_annotator": "Find every supportable student task. Avoid under-splitting compound prompts.",
    "conservative_annotator": "Minimize false positives. Prefer rejecting uncertain material to creating a task.",
    "structure_annotator": "Focus on parent/subpart relationships and safe response-candidate links.",
}


class CritiqueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concern: str
    block_ids: list[str] = Field(default_factory=list)
    response_candidate_ids: list[str] = Field(default_factory=list)
    recommendation: str


class Critique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: str
    objections: list[CritiqueItem] = Field(default_factory=list)
    unresolved: bool = False
    notes: list[str] = Field(default_factory=list)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: bytes | Any) -> str:
    payload = value if isinstance(value, bytes) else _canonical(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_pages() -> list[PilotPageInput]:
    raw = json.loads((PILOT_ROOT / "physical-inputs.json").read_text(encoding="utf-8"))
    return [PilotPageInput.model_validate(item) for item in raw["pages"]]


def _image_bytes(page: PilotPageInput) -> bytes:
    return (PILOT_ROOT / page.image).read_bytes()


def _safe_usage(response: Any) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    return {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _role_settings(role: str) -> dict[str, Any]:
    return json.loads(ROLE_CONFIG_PATH.read_text(encoding="utf-8"))["roles"][role]


def _spent_cost() -> float:
    pricing = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    total = 0.0
    for path in (BENCHMARK_ROOT / "agent_outputs").glob("*/*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        usage = record.get("usage") or {}
        model = record.get("model")
        if model in pricing["models"] and usage.get("input_tokens") is not None and usage.get("output_tokens") is not None:
            total += estimate_cost(pricing, model, input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"])
    return round(total, 8)


def _enforce_cost_ceiling(*, model: str, text: str, max_output_tokens: int) -> None:
    pricing = json.loads(PRICING_PATH.read_text(encoding="utf-8"))
    # Text tokens are conservatively estimated; image tokens receive a fixed
    # reserve so the cap is applied before the request, not after it.
    projected = worst_case_cost(pricing, model, input_token_estimate=max(1, len(text) // 4) + 2000, max_output_tokens=max_output_tokens)
    if _spent_cost() + projected > cost_ceiling_usd():
        raise RuntimeError("silver benchmark cost ceiling would be exceeded")


def _call_structured(
    *,
    instructions: str,
    text: str,
    image: bytes,
    schema: type[BaseModel],
    model: str | None = None,
    max_output_tokens: int = 4096,
    reasoning_effort: str | None = None,
) -> tuple[BaseModel, dict[str, Any]]:
    from openai import OpenAI

    started = time.perf_counter()
    selected_model = model or config.get_openai_reasoning_model()
    _enforce_cost_ceiling(model=selected_model, text=text, max_output_tokens=max_output_tokens)
    request: dict[str, Any] = {
        "model": selected_model,
        "instructions": instructions,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": text},
                    {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(image).decode("ascii")},
                ],
            }
        ],
        "text_format": schema,
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}
    response = OpenAI(api_key=config.get_openai_api_key()).responses.parse(**request)
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise RuntimeError("provider returned no structured output")
    result = parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
    return result, {
        "model": selected_model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "usage": _safe_usage(response),
    }


def _annotation_prompt(page: PilotPageInput, role: str) -> str:
    payload = {
        "page_id": page.pilot_id,
        "page_index": page.page_index,
        "physical_blocks": [item.model_dump(mode="json") for item in page.blocks],
        "response_candidates": [item.model_dump(mode="json") for item in page.response_candidates],
    }
    return (
        "You are an independent AI-adjudicated silver benchmark annotator. "
        "You may select only supplied IDs; never create text, coordinates, answer content, or write permission. "
        "Your response must partition all physical blocks and use side_panel_only whenever physical placement is not safe. "
        f"Role-specific emphasis: {ROLE_INSTRUCTIONS[role]}\n\n"
        + _canonical(payload)
    )


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_annotation(page: PilotPageInput, role: str) -> dict[str, Any]:
    settings = _role_settings(role)
    try:
        result, metadata = _call_structured(
            instructions="Return strict closed-world page classification only.",
            text=_annotation_prompt(page, role),
            image=_image_bytes(page),
            schema=ClosedWorldPageResult,
            model=settings["model"],
            max_output_tokens=settings["max_output_tokens"],
            reasoning_effort=settings["reasoning_effort"],
        )
    except Exception as exc:
        record = {
            "page_id": page.pilot_id,
            "agent": role,
            "input_hash": _sha(page.model_dump(mode="json")),
            "prompt_version": "silver-annotation-v1",
            "result": None,
            "validation_error": None,
            "provider_error_type": type(exc).__name__,
        }
        _write(BENCHMARK_ROOT / "agent_outputs" / role / f"{page.pilot_id}.json", record)
        raise
    validation_error = None
    try:
        validate_closed_world_result(page, result)
    except ValueError as exc:
        validation_error = str(exc)
    record = {
        "page_id": page.pilot_id,
        "agent": role,
        "input_hash": _sha(page.model_dump(mode="json")),
        "prompt_version": "silver-annotation-v1",
        "result": result.model_dump(mode="json"),
        "validation_error": validation_error,
        **metadata,
    }
    _write(BENCHMARK_ROOT / "agent_outputs" / role / f"{page.pilot_id}.json", record)
    return record


def annotate(page_id: str | None = None, role_name: str | None = None, *, resume: bool = False) -> None:
    for page in _load_pages():
        if page_id and page.pilot_id != page_id:
            continue
        if not page.blocks:
            continue
        roles = [role_name] if role_name else ROLE_INSTRUCTIONS
        for role in roles:
            destination = BENCHMARK_ROOT / "agent_outputs" / role / f"{page.pilot_id}.json"
            if resume and destination.exists():
                try:
                    if json.loads(destination.read_text(encoding="utf-8")).get("result"):
                        continue
                except json.JSONDecodeError:
                    pass
            try:
                _run_annotation(page, role)
            except Exception:
                # Failure metadata is persisted by _run_annotation. Continue so
                # one provider/schema failure cannot hide the remaining pages.
                continue


def _annotation_records(page_id: str) -> dict[str, dict[str, Any]]:
    records = {}
    for role in ROLE_INSTRUCTIONS:
        path = BENCHMARK_ROOT / "agent_outputs" / role / f"{page_id}.json"
        records[role] = json.loads(path.read_text(encoding="utf-8"))
    return records


def _run_critique(page: PilotPageInput) -> dict[str, Any]:
    annotations = _annotation_records(page.pilot_id)
    text = _canonical(
        {
            "page_id": page.pilot_id,
            "physical_blocks": [item.model_dump(mode="json") for item in page.blocks],
            "response_candidates": [item.model_dump(mode="json") for item in page.response_candidates],
            "initial_annotations": annotations,
        }
    )
    critique, metadata = _call_structured(
        instructions=(
            "You are an isolated red-team critic for AI-adjudicated silver labels. "
            "Challenge unsupported task boundaries, false positives, parent/subpart errors, and unsafe placement. "
            "Every objection must cite supplied IDs; do not invent text or coordinates."
        ),
        text=text,
        image=_image_bytes(page),
        schema=Critique,
    )
    if critique.page_id != page.pilot_id:
        raise ValueError("critique page ID did not match")
    known_blocks = {item.id for item in page.blocks}
    known_candidates = {item.id for item in page.response_candidates}
    for item in critique.objections:
        if not set(item.block_ids) <= known_blocks or not set(item.response_candidate_ids) <= known_candidates:
            raise ValueError("critique referenced unknown evidence")
    record = {"page_id": page.pilot_id, "critique": critique.model_dump(mode="json"), **metadata}
    _write(BENCHMARK_ROOT / "critiques" / f"{page.pilot_id}.json", record)
    return record


def _run_adjudication(page: PilotPageInput) -> dict[str, Any]:
    annotations = _annotation_records(page.pilot_id)
    critique_path = BENCHMARK_ROOT / "critiques" / f"{page.pilot_id}.json"
    critique = json.loads(critique_path.read_text(encoding="utf-8"))
    text = _canonical(
        {
            "page_id": page.pilot_id,
            "physical_blocks": [item.model_dump(mode="json") for item in page.blocks],
            "response_candidates": [item.model_dump(mode="json") for item in page.response_candidates],
            "initial_annotations": annotations,
            "red_team_critique": critique,
        }
    )
    result, metadata = _call_structured(
        instructions=(
            "You are the final AI adjudicator for a silver benchmark. Resolve only from supplied physical evidence, "
            "annotations, and critique. Select only supplied IDs; never create text, coordinates, or write permission. "
            "When placement is uncertain, use side_panel_only or no grouping instead of guessing."
        ),
        text=text,
        image=_image_bytes(page),
        schema=ClosedWorldPageResult,
    )
    validate_closed_world_result(page, result)
    derived = derive_tasks(page, result)
    placement = {}
    for task in derived:
        placement[str(task["group_index"])] = (
            "automatic"
            if task["response_disposition"] == "safe_physical" and not task["needs_review"]
            else "side_panel"
        )
    record = {
        "page_id": page.pilot_id,
        "result": result.model_dump(mode="json"),
        "derived_task_count": len(derived),
        "placement_by_group": placement,
        **metadata,
    }
    _write(BENCHMARK_ROOT / "adjudications" / f"{page.pilot_id}.json", record)
    return record


def critique_and_adjudicate(page_ids: list[str] | None = None) -> None:
    for page in _load_pages():
        if not page.blocks or (page_ids and page.pilot_id not in page_ids):
            continue
        try:
            _run_critique(page)
            _run_adjudication(page)
        except Exception as exc:
            _write(
                BENCHMARK_ROOT / "adjudications" / f"{page.pilot_id}.json",
                {"page_id": page.pilot_id, "result": None, "provider_error_type": type(exc).__name__},
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["annotate", "adjudicate"])
    parser.add_argument("--page-id")
    parser.add_argument("--role", choices=list(ROLE_INSTRUCTIONS))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.command == "annotate":
        annotate(args.page_id, args.role, resume=args.resume)
    elif args.command == "adjudicate":
        critique_and_adjudicate([args.page_id] if args.page_id else None)
