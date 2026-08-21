"""Official Claros samples that satisfy the active worksheet contract."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import config

DEFAULT_SAMPLE_ID = "canonical-short-answer-ecosystems"
_SAMPLES_ROOT = config.ROOT / "evaluation" / "canonical_v1"
_SOURCE_PATH = _SAMPLES_ROOT / "source.json"
_PDF_DIR = _SAMPLES_ROOT / "generated" / "pdfs"
_RENDERED_DIR = _SAMPLES_ROOT / "generated" / "rendered"
_SUPPORTED_SAMPLE_IDS = {DEFAULT_SAMPLE_ID}


@dataclass(frozen=True)
class ProductSample:
    canonical_id: str
    sample_name: str
    title: str
    topic_label: str
    description: str
    upload_filename: str
    pdf_path: Path
    preview_png_path: Path | None

    def to_public_dict(self) -> dict[str, str]:
        return {
            "id": self.canonical_id,
            "sample_name": self.sample_name,
            "title": self.title,
            "topic_label": self.topic_label,
            "description": self.description,
            "pdf_url": f"/samples/{self.canonical_id}.pdf",
            "preview_url": f"/samples/{self.canonical_id}/preview.png",
        }


_SAMPLE_DESCRIPTIONS = {
    "canonical-short-answer-ecosystems": (
        "Five short-answer science questions with answer lines and boxes."
    ),
    "canonical-choice-digital-safety": (
        "Five multiple-choice questions with checkbox choices and explanations."
    ),
    "canonical-numeric-everyday-math": (
        "Five numeric word problems with answer fields and show-your-work areas."
    ),
}


def _preview_path_for(canonical_id: str) -> Path | None:
    candidate = _RENDERED_DIR / f"{canonical_id}-p1.png"
    return candidate if candidate.exists() else None


@lru_cache(maxsize=1)
def list_product_samples() -> tuple[ProductSample, ...]:
    """Return the ordered official sample catalog from canonical_v1 source."""
    payload = json.loads(_SOURCE_PATH.read_text(encoding="utf-8"))
    samples: list[ProductSample] = []
    for document in payload["documents"]:
        canonical_id = document["canonical_id"]
        if canonical_id not in _SUPPORTED_SAMPLE_IDS:
            continue
        pdf_path = _PDF_DIR / f"{canonical_id}.pdf"
        if not pdf_path.exists():
            raise FileNotFoundError(f"Missing product sample PDF: {pdf_path}")
        sample_name = document["sample_name"]
        title = document["title"]
        samples.append(
            ProductSample(
                canonical_id=canonical_id,
                sample_name=sample_name,
                title=title,
                topic_label=document.get("topic_label", ""),
                description=_SAMPLE_DESCRIPTIONS.get(
                    canonical_id,
                    f"{sample_name}: {title}",
                ),
                upload_filename=f"Claros sample — {sample_name}.pdf",
                pdf_path=pdf_path,
                preview_png_path=_preview_path_for(canonical_id),
            )
        )
    if not samples:
        raise RuntimeError("canonical_v1 source.json defines no product samples")
    return tuple(samples)


def get_product_sample(sample_id: str | None) -> ProductSample:
    """Resolve a sample id, including legacy ``1`` / empty → default short answer."""
    samples = {sample.canonical_id: sample for sample in list_product_samples()}
    if not sample_id or sample_id in {"1", "true", "default"}:
        return samples[DEFAULT_SAMPLE_ID]
    sample = samples.get(sample_id)
    if sample is None:
        raise KeyError(sample_id)
    return sample


def resolve_sample_query(raw: str | None) -> ProductSample | None:
    """Map ``?sample=`` query values to a catalog entry, or None when absent."""
    if raw is None or raw == "":
        return None
    return get_product_sample(raw)
