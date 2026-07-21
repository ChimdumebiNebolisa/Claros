"""PaddleOCR PP-StructureV3 adapter with PDF-point coordinate normalization."""
from __future__ import annotations

import logging
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol

import fitz

import config

logger = logging.getLogger(__name__)


def _right_angle_rotation(rotation: int) -> int:
    normalized = int(rotation) % 360
    if normalized not in {0, 90, 180, 270}:
        raise ValueError("rotation must be 0, 90, 180, or 270 degrees")
    return normalized


@dataclass(frozen=True)
class OCRTextBlock:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float = 0.0
    label: str = "text"
    polygon: tuple[tuple[float, float], ...] | None = None
    reading_order: int = 0
    source_id: str | None = None


@dataclass(frozen=True)
class OCRPageResult:
    page_index: int
    blocks: list[OCRTextBlock]
    engine: str
    warnings: list[str]
    status: str = "parsed"
    width_points: float = 0.0
    height_points: float = 0.0
    rotation: int = 0
    processing_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class OCRAdapter(Protocol):
    def extract_page(self, pdf_bytes: bytes, page_index: int) -> OCRPageResult:
        """Extract structured text/layout for one page without mutating the PDF."""

    def extract_page_text(self, pdf_bytes: bytes, page_index: int) -> OCRPageResult:
        """Backward-compatible alias for extract_page."""

    def extract_image(
        self,
        image_bytes: bytes,
        *,
        page_index: int = 0,
        width_points: float | None = None,
        height_points: float | None = None,
        rotation: int = 0,
    ) -> OCRPageResult:
        """Extract a standalone page image in caller-supplied PDF geometry."""


class NullOCRAdapter:
    """Default adapter: OCR is intentionally unavailable."""

    def extract_page(self, pdf_bytes: bytes, page_index: int) -> OCRPageResult:
        try:
            geometry = _pdf_page_geometry(pdf_bytes, page_index)
        except (fitz.FileDataError, RuntimeError, IndexError):
            geometry = {"width_points": 0.0, "height_points": 0.0, "rotation": 0}
        return OCRPageResult(
            page_index=page_index,
            blocks=[],
            engine="null",
            warnings=["ocr_not_configured"],
            status="requires_ocr",
            **geometry,
        )

    def extract_page_text(self, pdf_bytes: bytes, page_index: int) -> OCRPageResult:
        return self.extract_page(pdf_bytes, page_index)

    def extract_image(
        self,
        image_bytes: bytes,
        *,
        page_index: int = 0,
        width_points: float | None = None,
        height_points: float | None = None,
        rotation: int = 0,
    ) -> OCRPageResult:
        pixmap = fitz.Pixmap(image_bytes)
        return OCRPageResult(
            page_index=page_index,
            blocks=[],
            engine="null",
            warnings=["ocr_not_configured"],
            status="requires_ocr",
            width_points=width_points or float(pixmap.width),
            height_points=height_points or float(pixmap.height),
            rotation=_right_angle_rotation(rotation),
        )


def _pdf_page_geometry(pdf_bytes: bytes, page_index: int) -> dict[str, float | int]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_index < 0 or page_index >= document.page_count:
            raise IndexError("page_index is outside the PDF")
        page = document[page_index]
        return {
            "width_points": float(page.rect.width),
            "height_points": float(page.rect.height),
            "rotation": int(page.rotation) % 360,
        }
    finally:
        document.close()


def _as_plain_dict(result: Any) -> dict[str, Any]:
    payload = getattr(result, "json", result)
    if callable(payload):
        payload = payload()
    if not isinstance(payload, dict):
        raise ValueError("PP-StructureV3 returned a non-object result")
    nested = payload.get("res")
    return nested if isinstance(nested, dict) else payload


def _bbox_from_polygon(raw: Any) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    try:
        points = [[float(point[0]), float(point[1])] for point in raw]
    except (TypeError, ValueError, IndexError):
        return None
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_from_raw(raw: Any) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    try:
        values = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None
    if len(values) == 4:
        x0, y0, x1, y1 = values
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None
    return _bbox_from_polygon(raw)


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    if intersection <= 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / max(area_a + area_b - intersection, 1.0)


def _layout_confidence(payload: dict[str, Any], label: str, bbox: tuple[float, float, float, float]) -> float:
    layout = payload.get("layout_det_res") or {}
    best = 0.0
    for item in layout.get("boxes") or []:
        candidate = _bbox_from_raw(item.get("coordinate"))
        if candidate is None:
            continue
        label_bonus = 1.0 if str(item.get("label", "")) == label else 0.8
        score = float(item.get("score") or 0.0) * label_bonus * _iou(candidate, bbox)
        best = max(best, score)
    return min(1.0, best)


def _scale_bbox(
    bbox: tuple[float, float, float, float],
    scale_x: float,
    scale_y: float,
) -> tuple[float, float, float, float]:
    return (
        round(bbox[0] * scale_x, 3),
        round(bbox[1] * scale_y, 3),
        round(bbox[2] * scale_x, 3),
        round(bbox[3] * scale_y, 3),
    )


def _scale_polygon(raw: Any, scale_x: float, scale_y: float) -> tuple[tuple[float, float], ...] | None:
    if raw is None:
        return None
    try:
        return tuple((round(float(p[0]) * scale_x, 3), round(float(p[1]) * scale_y, 3)) for p in raw)
    except (TypeError, ValueError, IndexError):
        return None


class PaddleOCRAdapter:
    """Lazy local PP-StructureV3 adapter intended for flagged benchmark/service use."""

    def __init__(self, *, dpi: int | None = None, pipeline: Any | None = None):
        self.dpi = dpi or config.PADDLEOCR_DPI
        self._pipeline = pipeline

    def _get_pipeline(self):
        if self._pipeline is None:
            try:
                from paddleocr import PPStructureV3
            except ImportError as exc:
                raise RuntimeError("PaddleOCR is not installed; install requirements-paddleocr.txt") from exc
            # Formula, chart, seal, and unwarping models add substantial memory and are
            # unnecessary for Claros's first-pass worksheet geometry evaluation.
            self._pipeline = PPStructureV3(
                device="cpu",
                # Paddle 3.3.1's Windows oneDNN executor cannot run this layout
                # graph; retain the optimized default for a future Linux worker.
                enable_mkldnn=sys.platform != "win32",
                layout_detection_model_name="PP-DocLayout-M",
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="en_PP-OCRv4_mobile_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                use_formula_recognition=False,
                use_chart_recognition=False,
                use_seal_recognition=False,
                # Claros needs table geometry and labels, not reconstructed HTML.
                # Layout detection still emits table regions without loading the
                # heavier table-cell recognition branch.
                use_table_recognition=False,
                cpu_threads=config.PADDLEOCR_CPU_THREADS,
            )
        return self._pipeline

    def extract_page(self, pdf_bytes: bytes, page_index: int) -> OCRPageResult:
        started = time.perf_counter()
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        image_path: Path | None = None
        try:
            if page_index < 0 or page_index >= document.page_count:
                raise IndexError("page_index is outside the PDF")
            page = document[page_index]
            scale = self.dpi / 72.0
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image_file:
                image_path = Path(image_file.name)
                image_file.write(pixmap.tobytes("png"))
            output = self._get_pipeline().predict(str(image_path))
            result = next(iter(output), None)
            if result is None:
                return OCRPageResult(
                    page_index=page_index,
                    blocks=[],
                    engine="paddleocr-ppstructurev3",
                    warnings=["paddleocr_empty_result"],
                    status="failed",
                    width_points=float(page.rect.width),
                    height_points=float(page.rect.height),
                    rotation=int(page.rotation) % 360,
                    processing_ms=(time.perf_counter() - started) * 1000,
                )
            payload = _as_plain_dict(result)
            blocks = self._parse_blocks(
                payload,
                page_index=page_index,
                image_width=float(pixmap.width),
                image_height=float(pixmap.height),
                page_width=float(page.rect.width),
                page_height=float(page.rect.height),
            )
            average = sum(block.confidence for block in blocks) / len(blocks) if blocks else 0.0
            warnings = []
            status = "parsed"
            if not blocks:
                warnings.append("paddleocr_no_blocks")
                status = "failed"
            elif average < config.PADDLEOCR_MIN_CONFIDENCE:
                warnings.append("paddleocr_low_confidence")
                status = "low_confidence"
            return OCRPageResult(
                page_index=page_index,
                blocks=blocks,
                engine="paddleocr-ppstructurev3",
                warnings=warnings,
                status=status,
                width_points=float(page.rect.width),
                height_points=float(page.rect.height),
                rotation=int(page.rotation) % 360,
                processing_ms=(time.perf_counter() - started) * 1000,
                metadata={
                    "dpi": self.dpi,
                    "model_settings": payload.get("model_settings") or {},
                },
            )
        except Exception as exc:
            logger.warning(
                "PaddleOCR page extraction failed page_index=%s error_type=%s",
                page_index,
                type(exc).__name__,
            )
            geometry = {
                "width_points": 0.0,
                "height_points": 0.0,
                "rotation": 0,
            }
            if 0 <= page_index < document.page_count:
                page = document[page_index]
                geometry = {
                    "width_points": float(page.rect.width),
                    "height_points": float(page.rect.height),
                    "rotation": int(page.rotation) % 360,
                }
            return OCRPageResult(
                page_index=page_index,
                blocks=[],
                engine="paddleocr-ppstructurev3",
                warnings=["paddleocr_failed", type(exc).__name__],
                status="failed",
                processing_ms=(time.perf_counter() - started) * 1000,
                **geometry,
            )
        finally:
            document.close()
            if image_path is not None:
                try:
                    image_path.unlink()
                except OSError:
                    pass

    def extract_page_text(self, pdf_bytes: bytes, page_index: int) -> OCRPageResult:
        return self.extract_page(pdf_bytes, page_index)

    def extract_image(
        self,
        image_bytes: bytes,
        *,
        page_index: int = 0,
        width_points: float | None = None,
        height_points: float | None = None,
        rotation: int = 0,
    ) -> OCRPageResult:
        """Run the same adapter path for an already-rendered page image."""
        pixmap = fitz.Pixmap(image_bytes)
        page_width = width_points or float(pixmap.width) * 72.0 / self.dpi
        page_height = height_points or float(pixmap.height) * 72.0 / self.dpi
        document = fitz.open()
        try:
            page = document.new_page(width=page_width, height=page_height)
            page.insert_image(page.rect, stream=image_bytes)
            result = self.extract_page(document.tobytes(), 0)
        finally:
            document.close()
        return replace(
            result,
            page_index=page_index,
            width_points=page_width,
            height_points=page_height,
            rotation=_right_angle_rotation(rotation),
            metadata={**result.metadata, "input": "page_image"},
        )

    @staticmethod
    def _parse_blocks(
        payload: dict[str, Any],
        *,
        page_index: int,
        image_width: float,
        image_height: float,
        page_width: float,
        page_height: float,
    ) -> list[OCRTextBlock]:
        scale_x = page_width / max(image_width, 1.0)
        scale_y = page_height / max(image_height, 1.0)
        blocks: list[OCRTextBlock] = []
        parsing = payload.get("parsing_res_list") or []
        for fallback_order, item in enumerate(parsing):
            raw_bbox = item.get("block_bbox")
            bbox = _bbox_from_raw(raw_bbox)
            if bbox is None:
                continue
            label = str(item.get("block_label") or "text")
            confidence = _layout_confidence(payload, label, bbox)
            if confidence <= 0:
                confidence = 0.5
            order = item.get("block_order")
            if not isinstance(order, int) or order < 0:
                order = fallback_order
            source_id = item.get("block_id")
            blocks.append(
                OCRTextBlock(
                    text=str(item.get("block_content") or ""),
                    bbox=_scale_bbox(bbox, scale_x, scale_y),
                    confidence=confidence,
                    label=label,
                    polygon=_scale_polygon(raw_bbox if len(raw_bbox or []) != 4 else None, scale_x, scale_y),
                    reading_order=order,
                    source_id=str(source_id) if source_id is not None else None,
                )
            )
        if blocks:
            return sorted(blocks, key=lambda block: (block.reading_order, block.bbox[1], block.bbox[0]))

        # Conservative fallback when the layout parser returned OCR lines but no
        # parsing blocks. These remain labeled as OCR text, never response areas.
        ocr = payload.get("overall_ocr_res") or {}
        texts = ocr.get("rec_texts") or []
        scores = ocr.get("rec_scores") or []
        polygons = ocr.get("rec_polys") or []
        for order, text in enumerate(texts):
            raw_polygon = polygons[order] if order < len(polygons) else None
            bbox = _bbox_from_polygon(raw_polygon)
            if bbox is None:
                continue
            score = float(scores[order]) if order < len(scores) else 0.0
            blocks.append(
                OCRTextBlock(
                    text=str(text),
                    bbox=_scale_bbox(bbox, scale_x, scale_y),
                    confidence=max(0.0, min(score, 1.0)),
                    label="ocr_text",
                    polygon=_scale_polygon(raw_polygon, scale_x, scale_y),
                    reading_order=order,
                )
            )
        return blocks


def get_ocr_adapter() -> OCRAdapter:
    """Return the flagged OCR adapter; legacy uploads stay dependency-light by default."""
    requested = config.ENABLE_PADDLEOCR or config.PDF_PARSER_MODE in {"paddle", "hybrid"}
    if requested and not config.ALLOW_SYNCHRONOUS_PADDLEOCR:
        logger.warning("Synchronous PaddleOCR is disabled; run the adapter in a parser worker/service")
        return NullOCRAdapter()
    if requested:
        return PaddleOCRAdapter()
    return NullOCRAdapter()
