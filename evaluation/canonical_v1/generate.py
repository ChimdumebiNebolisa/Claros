"""Generate canonical_v1 PDFs, exact geometry, and rendered previews."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .schema import CanonicalDocumentSpec, CanonicalManifest, CanonicalSource, Region

DEFAULT_SPEC = Path(__file__).with_name("source.json")
DEFAULT_OUTPUT = Path(__file__).with_name("generated")

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 54.0
CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN)
BOTTOM_LIMIT = PAGE_HEIGHT - 42.0

NAVY = HexColor("#17324D")
TEAL = HexColor("#0D9488")
INK = HexColor("#17212B")
MUTED = HexColor("#526273")
PALE = HexColor("#F2F8F7")
LINE = HexColor("#A9BBC5")
SOFT = HexColor("#E5EDF1")


def _normalized_bbox(bbox: list[float]) -> dict[str, float]:
    x0, y0, x1, y1 = bbox
    return {
        "x": round(x0 / PAGE_WIDTH, 6),
        "y": round(y0 / PAGE_HEIGHT, 6),
        "width": round((x1 - x0) / PAGE_WIDTH, 6),
        "height": round((y1 - y0) / PAGE_HEIGHT, 6),
    }


def _region(region_id: str, page_index: int, bbox: list[float]) -> dict:
    return Region(
        region_id=region_id,
        page_index=page_index,
        bbox_points=[round(value, 3) for value in bbox],
        bbox_normalized=_normalized_bbox(bbox),
    ).model_dump(mode="json")


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and stringWidth(candidate, font, size) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _draw_text(
    pdf: canvas.Canvas,
    text: str,
    *,
    x: float,
    y_top: float,
    width: float,
    font: str = "Helvetica",
    size: float = 10,
    leading: float = 14,
    color: Color = INK,
) -> tuple[list[float], float]:
    lines = _wrap(text, font, size, width)
    pdf.setFont(font, size)
    pdf.setFillColor(color)
    for index, line in enumerate(lines):
        pdf.drawString(x, PAGE_HEIGHT - y_top - size - (index * leading), line)
    bottom = y_top + (len(lines) * leading)
    return [x, y_top, x + width, bottom], bottom


def _draw_page_header(pdf: canvas.Canvas, doc: CanonicalDocumentSpec, page_number: int) -> float:
    pdf.setFillColor(NAVY)
    pdf.rect(0, PAGE_HEIGHT - 82, PAGE_WIDTH, 82, stroke=0, fill=1)
    pdf.setFillColor(TEAL)
    pdf.rect(0, PAGE_HEIGHT - 86, PAGE_WIDTH, 4, stroke=0, fill=1)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 19)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 39, doc.title)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(MARGIN, PAGE_HEIGHT - 59, doc.topic_label)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 59, f"PAGE {page_number}")
    return 105.0


def _draw_footer(pdf: canvas.Canvas, canonical_id: str) -> None:
    pdf.setStrokeColor(SOFT)
    pdf.line(MARGIN, 29, PAGE_WIDTH - MARGIN, 29)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(MARGIN, 18, "Claros sample worksheet")
    pdf.drawRightString(PAGE_WIDTH - MARGIN, 18, canonical_id)


def _draw_context(pdf: canvas.Canvas, doc: CanonicalDocumentSpec, y: float) -> float:
    if not doc.context:
        return y
    panel_height = 28 + sum(len(_wrap(item, "Helvetica", 9, CONTENT_WIDTH - 34)) * 12 for item in doc.context)
    panel_height += 8 * (len(doc.context) - 1)
    pdf.setFillColor(PALE)
    pdf.setStrokeColor(HexColor("#B9D9D5"))
    pdf.roundRect(MARGIN, PAGE_HEIGHT - y - panel_height, CONTENT_WIDTH, panel_height, 8, stroke=1, fill=1)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN + 14, PAGE_HEIGHT - y - 17, doc.context_title or "Read first")
    cursor = y + 28
    for item in doc.context:
        pdf.setFillColor(TEAL)
        pdf.circle(MARGIN + 17, PAGE_HEIGHT - cursor - 5, 2.2, stroke=0, fill=1)
        _, cursor = _draw_text(
            pdf,
            item,
            x=MARGIN + 26,
            y_top=cursor,
            width=CONTENT_WIDTH - 40,
            size=9,
            leading=12,
        )
        cursor += 8
    return y + panel_height + 14


def _draw_response(pdf: canvas.Canvas, response, page_index: int, y: float) -> tuple[dict, float]:
    label = response.label
    if response.response_type == "line":
        pdf.setFont("Helvetica-Bold", 9)
        pdf.setFillColor(MUTED)
        pdf.drawString(MARGIN + 18, PAGE_HEIGHT - y - 9, label)
        label_width = stringWidth(label, "Helvetica-Bold", 9)
        x0 = MARGIN + 26 + label_width
        line_y = y + 10
        pdf.setStrokeColor(LINE)
        pdf.setLineWidth(1)
        pdf.line(x0, PAGE_HEIGHT - line_y, PAGE_WIDTH - MARGIN - 10, PAGE_HEIGHT - line_y)
        bbox = [x0, line_y - 8, PAGE_WIDTH - MARGIN - 10, line_y + 12]
        return {
            **_region(response.response_id, page_index, bbox),
            "response_type": "line",
            "response_safety": response.response_safety,
            "choice_value": None,
        }, y + 28

    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColor(MUTED)
    pdf.drawString(MARGIN + 18, PAGE_HEIGHT - y - 9, label)
    box_top = y + 16
    box_height = response.height
    x0 = MARGIN + 18
    x1 = PAGE_WIDTH - MARGIN - 10
    pdf.setFillColor(white)
    pdf.setStrokeColor(LINE)
    pdf.roundRect(x0, PAGE_HEIGHT - box_top - box_height, x1 - x0, box_height, 5, stroke=1, fill=1)
    bbox = [x0, box_top, x1, box_top + box_height]
    return {
        **_region(response.response_id, page_index, bbox),
        "response_type": "box",
        "response_safety": response.response_safety,
        "choice_value": None,
    }, box_top + box_height + 12


def _draw_task(pdf: canvas.Canvas, task, page_index: int, y: float) -> tuple[dict, float]:
    card_top = y
    prompt_lines = _wrap(task.prompt, "Helvetica-Bold", 10, CONTENT_WIDTH - 48)
    card_height = max(32.0, 14.0 + (len(prompt_lines) * 13.0))
    pdf.setFillColor(HexColor("#F8FAFB"))
    pdf.setStrokeColor(SOFT)
    pdf.roundRect(
        MARGIN,
        PAGE_HEIGHT - y - card_height,
        CONTENT_WIDTH,
        card_height,
        6,
        stroke=1,
        fill=1,
    )
    pdf.setFillColor(TEAL)
    pdf.circle(MARGIN + 17, PAGE_HEIGHT - y - 16, 10, stroke=0, fill=1)
    pdf.setFillColor(white)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(MARGIN + 17, PAGE_HEIGHT - y - 17, f"{task.order}.")
    prompt_bbox, prompt_bottom = _draw_text(
        pdf,
        task.prompt,
        x=MARGIN + 36,
        y_top=y + 7,
        width=CONTENT_WIDTH - 48,
        font="Helvetica-Bold",
        size=10,
        leading=13,
    )
    prompt_bbox[0] = MARGIN + 6
    prompt_bbox[1] = card_top
    prompt_bbox[3] = max(prompt_bbox[3], card_top + card_height)
    y = max(prompt_bottom + 8, card_top + card_height + 8)

    responses: list[dict] = []
    if task.task_type == "choice":
        checkbox_specs = [item for item in task.responses if item.response_type == "checkbox"]
        for choice, response in zip(task.choices, checkbox_specs, strict=True):
            x0 = MARGIN + 22
            box_top = y + 1
            pdf.setFillColor(white)
            pdf.setStrokeColor(TEAL)
            pdf.rect(x0, PAGE_HEIGHT - box_top - 12, 12, 12, stroke=1, fill=1)
            pdf.setFillColor(INK)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(x0 + 20, PAGE_HEIGHT - y - 10, f"{choice.value}.")
            _draw_text(
                pdf,
                choice.text,
                x=x0 + 36,
                y_top=y,
                width=CONTENT_WIDTH - 64,
                size=9,
                leading=12,
            )
            responses.append(
                {
                    **_region(response.response_id, page_index, [x0, box_top, x0 + 12, box_top + 12]),
                    "response_type": "checkbox",
                    "response_safety": response.response_safety,
                    "choice_value": choice.value,
                }
            )
            y += 19
        non_choice = [item for item in task.responses if item.response_type != "checkbox"]
    else:
        non_choice = list(task.responses)

    for response in non_choice:
        rendered, y = _draw_response(pdf, response, page_index, y)
        responses.append(rendered)

    task_payload = {
        "task_id": task.task_id,
        "order": task.order,
        "task_type": task.task_type,
        "prompt_text": task.prompt,
        "prompt_region": _region(f"{task.task_id}-prompt", page_index, prompt_bbox),
        "response_regions": responses,
        "relations": [
            {
                "relation_type": "prompt_to_response_region",
                "from_region_id": f"{task.task_id}-prompt",
                "to_region_id": response["region_id"],
            }
            for response in responses
        ],
    }
    return task_payload, y + 10


def _render_document(doc: CanonicalDocumentSpec, output: Path) -> dict:
    pdf_dir = output / "pdfs"
    preview_dir = output / "rendered"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{doc.canonical_id}.pdf"
    pdf = canvas.Canvas(
        str(pdf_path),
        pagesize=letter,
        pageCompression=1,
        invariant=1,
        title=doc.title,
        author="Claros",
        subject="First-party canonical worksheet sample",
    )

    pages: list[dict] = []
    page_index = 0
    page_tasks: list[dict] = []
    y = _draw_page_header(pdf, doc, 1)
    _, y = _draw_text(
        pdf,
        doc.instructions,
        x=MARGIN,
        y_top=y,
        width=CONTENT_WIDTH,
        size=9,
        leading=12,
        color=MUTED,
    )
    y += 10
    y = _draw_context(pdf, doc, y)

    def finish_page() -> None:
        _draw_footer(pdf, doc.canonical_id)
        pages.append(
            {
                "page_index": page_index,
                "width_points": PAGE_WIDTH,
                "height_points": PAGE_HEIGHT,
                "page_role": "student_worksheet",
                "tasks": list(page_tasks),
            }
        )

    for task in doc.tasks:
        if task.page_break_before:
            finish_page()
            pdf.showPage()
            page_index += 1
            page_tasks = []
            y = _draw_page_header(pdf, doc, page_index + 1)
            _, y = _draw_text(
                pdf,
                "Continue with the remaining questions.",
                x=MARGIN,
                y_top=y,
                width=CONTENT_WIDTH,
                size=9,
                leading=12,
                color=MUTED,
            )
            y += 12
        task_payload, y = _draw_task(pdf, task, page_index, y)
        if y > BOTTOM_LIMIT:
            raise ValueError(f"{doc.canonical_id} task {task.task_id} clips the page")
        page_tasks.append(task_payload)

    finish_page()
    pdf.save()
    pdf_bytes = pdf_path.read_bytes()

    rendered = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for index, page in enumerate(rendered):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            pix.save(str(preview_dir / f"{doc.canonical_id}-p{index + 1}.png"))
    finally:
        rendered.close()

    return {
        "canonical_id": doc.canonical_id,
        "sample_name": doc.sample_name,
        "title": doc.title,
        "pdf": f"pdfs/{pdf_path.name}",
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "pages": pages,
    }


def generate_all(spec_path: Path = DEFAULT_SPEC, output: Path = DEFAULT_OUTPUT) -> CanonicalManifest:
    source = CanonicalSource.model_validate_json(spec_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    documents = [_render_document(document, output) for document in source.documents]
    manifest = CanonicalManifest.model_validate(
        {
            "version": 1,
            "suite": "canonical_v1",
            "coordinate_system": "PDF points, top-left origin, [x0, y0, x1, y1]",
            "expected_labels_kind": "deterministic_first_party",
            "machine_predictions_are_expected_labels": False,
            "documents": documents,
        }
    )
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = generate_all(args.spec, args.output)
    print(f"Generated {len(manifest.documents)} canonical_v1 documents in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
