"""Deterministic first-party PDFs for the narrow worksheet contract evaluation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Literal

import fitz

from document_model import (
    BlockSemanticRole,
    DocumentBlock,
    PageRole,
    SourceKind,
)
from semantic_classifier import (
    SemanticBlockDecision,
    SemanticPageResult,
    SemanticTaskCandidate,
)


PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0
PDF_METADATA = {
    "title": "Claros worksheet contract fixture",
    "author": "Claros",
    "subject": "Deterministic first-party contract evaluation",
    "keywords": "claros,worksheet,contract,fixture",
    "creator": "Claros deterministic fixture generator",
    "producer": "Claros deterministic fixture generator",
    "creationDate": "D:20260101000000Z",
    "modDate": "D:20260101000000Z",
}

ResponseKind = Literal["line", "line_group", "box", "field", "two_fields", "checkbox", "table", "none"]
SelectorMode = Literal["normal", "shift_responses", "fabricated_response"]


@dataclass(frozen=True)
class QuestionSpec:
    page_index: int
    label: str
    prompt: str
    prompt_bbox: tuple[float, float, float, float]
    response_bbox: tuple[float, float, float, float] | None
    response_kind: ResponseKind = "line"
    response_type: str = "short_text"
    response_page_index: int | None = None
    explicit_answer_label: bool = False
    line_count: int = 1


@dataclass(frozen=True)
class FixtureSpec:
    fixture_id: str
    tags: tuple[str, ...]
    questions: tuple[QuestionSpec, ...]
    page_count: int = 1
    page_roles: tuple[PageRole, ...] = (PageRole.student_worksheet,)
    selector_mode: SelectorMode = "normal"
    extra_layout: str | None = None
    rotated_page: int | None = None
    page_sizes: tuple[tuple[float, float], ...] = ()

    def page_role(self, page_index: int) -> PageRole:
        if page_index < len(self.page_roles):
            return self.page_roles[page_index]
        return PageRole.student_worksheet

    def page_size(self, page_index: int) -> tuple[float, float]:
        if page_index < len(self.page_sizes):
            return self.page_sizes[page_index]
        return PAGE_WIDTH, PAGE_HEIGHT


def _numbered_questions(
    count: int,
    *,
    per_page: int = 5,
    response_kind: ResponseKind = "line",
    response_type: str = "short_text",
    font_margin: bool = False,
    wrapped: bool = False,
    line_count: int = 1,
) -> tuple[QuestionSpec, ...]:
    questions: list[QuestionSpec] = []
    for index in range(count):
        page_index = index // per_page
        slot = index % per_page
        step = 138.0 if per_page <= 5 else 88.0
        top = 62.0 + slot * step
        indent = (index % 3) * 16.0 if font_margin else 0.0
        x0 = (48.0 if font_margin else 72.0) + indent
        x1 = 552.0 if font_margin else 540.0
        if wrapped:
            prompt = (
                f"{index + 1}. Explain one relationship shown in this ecosystem and "
                "support the response with one brief observation."
            )
            prompt_height = 34.0
        elif response_type == "numeric":
            prompt = f"{index + 1}. Calculate the sample value for item {index + 1}."
            prompt_height = 18.0
        else:
            prompt = f"{index + 1}. State one short observation for item {index + 1}."
            prompt_height = 18.0
        response_top = top + prompt_height + 18.0
        response_height = 6.0 if response_kind == "line" else 58.0
        if response_kind == "line_group":
            response_height = 58.0
        elif response_kind == "field":
            response_height = 34.0
        questions.append(
            QuestionSpec(
                page_index=page_index,
                label=str(index + 1),
                prompt=prompt,
                prompt_bbox=(x0, top, x1, top + prompt_height),
                response_bbox=(x0, response_top, x1, response_top + response_height),
                response_kind=response_kind,
                response_type=response_type,
                line_count=line_count,
            )
        )
    return tuple(questions)


def _command_questions() -> tuple[QuestionSpec, ...]:
    commands = (
        "Describe one role of sunlight in an ecosystem.",
        "Identify one producer in a food web.",
        "Compare a consumer with a decomposer.",
        "Explain why water availability matters.",
        "State one effect of habitat loss.",
    )
    return tuple(
        QuestionSpec(
            page_index=0,
            label=str(index + 1),
            prompt=prompt,
            prompt_bbox=(72.0, 62.0 + index * 138.0, 540.0, 82.0 + index * 138.0),
            response_bbox=(72.0, 102.0 + index * 138.0, 540.0, 150.0 + index * 138.0),
            response_kind="box",
            explicit_answer_label=True,
        )
        for index, prompt in enumerate(commands)
    )


def _text_field_questions() -> tuple[QuestionSpec, ...]:
    questions = [
        QuestionSpec(
            page_index=0,
            label="1",
            prompt="1. Explain one short result.",
            prompt_bbox=(15.0, 38.0, 315.0, 58.0),
            response_bbox=(15.0, 70.0, 315.0, 100.0),
            response_kind="field",
        )
    ]
    questions.extend(
        replace(
            question,
            page_index=1,
            label=str(index + 2),
            prompt=question.prompt.replace(f"{index + 1}.", f"{index + 2}.", 1),
        )
        for index, question in enumerate(_numbered_questions(4))
    )
    return tuple(questions)


def _local_gap_questions() -> tuple[QuestionSpec, ...]:
    gaps = (24.0, 32.0, 40.0, 48.0, 56.0, 64.0, 72.0, 80.0)
    questions = []
    for index, gap in enumerate(gaps):
        page_index = index // 4
        slot = index % 4
        top = 62.0 + slot * 180.0
        prompt_bottom = top + 18.0
        response_y = prompt_bottom + gap
        questions.append(
            QuestionSpec(
                page_index=page_index,
                label=str(index + 1),
                prompt=f"{index + 1}. Give one brief response for local gap {index + 1}.",
                prompt_bbox=(72.0, top, 540.0, prompt_bottom),
                response_bbox=(72.0, response_y - 3.0, 540.0, response_y + 3.0),
            )
        )
    return tuple(questions)


def _page_edge_questions() -> tuple[QuestionSpec, ...]:
    tops = (42.0, 190.0, 338.0, 486.0, 684.0)
    return tuple(
        QuestionSpec(
            page_index=0,
            label=str(index + 1),
            prompt=f"{index + 1}. State one concise page-edge observation.",
            prompt_bbox=(72.0, top, 540.0, top + 18.0),
            response_bbox=(72.0, top + 42.0, 540.0, top + 48.0),
        )
        for index, top in enumerate(tops)
    )


def _single_question(
    *,
    prompt: str = "1. Explain the result in one short sentence.",
    prompt_bbox: tuple[float, float, float, float] = (72.0, 82.0, 540.0, 102.0),
    response_bbox: tuple[float, float, float, float] | None = (72.0, 128.0, 540.0, 134.0),
    response_kind: ResponseKind = "line",
    response_type: str = "short_text",
    response_page_index: int | None = None,
    line_count: int = 1,
) -> tuple[QuestionSpec, ...]:
    return (
        QuestionSpec(
            page_index=0,
            label="1",
            prompt=prompt,
            prompt_bbox=prompt_bbox,
            response_bbox=response_bbox,
            response_kind=response_kind,
            response_type=response_type,
            response_page_index=response_page_index,
            line_count=line_count,
        ),
    )


def _choice_question(response_type: str) -> tuple[QuestionSpec, ...]:
    return _single_question(
        prompt="1. Choose the best answer about ecosystem energy.",
        response_bbox=(72.0, 125.0, 420.0, 230.0),
        response_kind="checkbox",
        response_type=response_type,
        line_count=3,
    )


def _end_collected_questions() -> tuple[QuestionSpec, ...]:
    return tuple(
        QuestionSpec(
            page_index=0,
            label=str(index + 1),
            prompt=f"{index + 1}. Give one brief observation.",
            prompt_bbox=(72.0, 70.0 + index * 60.0, 540.0, 90.0 + index * 60.0),
            response_bbox=(72.0, 600.0 + index * 45.0, 540.0, 606.0 + index * 45.0),
        )
        for index in range(3)
    )


def _multi_column_questions() -> tuple[QuestionSpec, ...]:
    return (
        QuestionSpec(
            page_index=0,
            label="1",
            prompt="1. Explain the first result.",
            prompt_bbox=(60.0, 82.0, 280.0, 102.0),
            response_bbox=(60.0, 128.0, 280.0, 134.0),
        ),
        QuestionSpec(
            page_index=0,
            label="2",
            prompt="2. Explain the second result.",
            prompt_bbox=(330.0, 280.0, 552.0, 300.0),
            response_bbox=(330.0, 326.0, 552.0, 332.0),
        ),
    )


def _adjacent_questions() -> tuple[QuestionSpec, ...]:
    return (
        QuestionSpec(
            page_index=0,
            label="1",
            prompt="1. Explain the first adjacent result.",
            prompt_bbox=(72.0, 82.0, 540.0, 102.0),
            response_bbox=(72.0, 128.0, 540.0, 134.0),
        ),
        QuestionSpec(
            page_index=0,
            label="2",
            prompt="2. Explain the second adjacent result.",
            prompt_bbox=(72.0, 188.0, 540.0, 208.0),
            response_bbox=(72.0, 234.0, 540.0, 240.0),
        ),
    )


FIXTURES: tuple[FixtureSpec, ...] = (
    FixtureSpec("supported-numbered-lines-5", ("supported", "numbered", "lines", "five_questions"), _numbered_questions(5)),
    FixtureSpec("supported-command-boxes-5", ("supported", "command_style", "boxes"), _command_questions()),
    FixtureSpec("supported-wrapped-prompts-6", ("supported", "wrapped_prompts"), _numbered_questions(6, per_page=3, wrapped=True), page_count=2),
    FixtureSpec("supported-aligned-line-groups-5", ("supported", "aligned_line_groups"), _numbered_questions(5, response_kind="line_group", line_count=3)),
    FixtureSpec(
        "supported-text-fields-5",
        ("supported", "text_fields", "multiple_pages"),
        _text_field_questions(),
        page_count=2,
        page_sizes=((330.0, 120.0), (PAGE_WIDTH, PAGE_HEIGHT)),
    ),
    FixtureSpec("supported-font-margin-indent-7", ("supported", "font_variation", "margin_variation", "indentation"), _numbered_questions(7, per_page=7, font_margin=True)),
    FixtureSpec("supported-local-gaps-8", ("supported", "local_vertical_gaps", "multiple_pages"), _local_gap_questions(), page_count=2),
    FixtureSpec("supported-multipage-10", ("supported", "multiple_pages", "ten_questions"), _numbered_questions(10, per_page=5), page_count=2),
    FixtureSpec("supported-page-edge-5", ("supported", "page_edge"), _page_edge_questions()),
    FixtureSpec("supported-numeric-20", ("supported", "numeric", "twenty_questions"), _numbered_questions(20, per_page=5, response_type="numeric"), page_count=4),
    FixtureSpec("rejected-multiple-choice", ("rejected", "multiple_choice", "choice_numbering"), _choice_question("choice")),
    FixtureSpec("rejected-checkboxes", ("rejected", "checkboxes"), _choice_question("checkbox")),
    FixtureSpec("rejected-table-entry", ("rejected", "table_entry"), _single_question(prompt="1. Record the observation in the table.", response_bbox=(72.0, 128.0, 540.0, 250.0), response_kind="table", response_type="table")),
    FixtureSpec("rejected-answer-key", ("rejected", "answer_key"), _single_question(), page_roles=(PageRole.answer_key,)),
    FixtureSpec("rejected-teacher-guide", ("rejected", "teacher_guide"), _single_question(), page_roles=(PageRole.teacher_guide,)),
    FixtureSpec("rejected-essay-area", ("rejected", "essay_area"), _single_question(response_bbox=(72.0, 128.0, 540.0, 380.0), response_kind="box", response_type="long_text")),
    FixtureSpec("rejected-remote-answer", ("rejected", "remote_answer"), _single_question(response_bbox=(72.0, 650.0, 540.0, 656.0))),
    FixtureSpec("rejected-end-collected-answers", ("rejected", "end_collected_answers"), _end_collected_questions()),
    FixtureSpec("rejected-multi-column", ("rejected", "multi_column", "staggered_columns"), _multi_column_questions()),
    FixtureSpec(
        "rejected-competing-spaces",
        ("rejected", "competing_spaces", "line_group_red_team"),
        _single_question(
            prompt_bbox=(15.0, 34.0, 315.0, 54.0),
            response_bbox=(15.0, 62.0, 315.0, 122.0),
            response_kind="two_fields",
        ),
        page_sizes=((330.0, 140.0),),
    ),
    FixtureSpec("rejected-unclaimed-space", ("rejected", "unclaimed_space", "decorative_line"), _single_question(), extra_layout="unclaimed_line"),
    FixtureSpec("rejected-cross-page", ("rejected", "cross_page"), _single_question(response_bbox=(72.0, 92.0, 540.0, 98.0), response_page_index=1), page_count=2),
    FixtureSpec("rejected-transformed-page", ("rejected", "unsupported_transform"), _single_question(), rotated_page=0),
    FixtureSpec("rejected-image-only-scan", ("rejected", "image_only_scan"), (), extra_layout="image_only"),
    FixtureSpec("rejected-questionless-page", ("rejected", "questionless_page"), _single_question(), page_count=2, extra_layout="questionless_page"),
    FixtureSpec("rejected-unmappable-diagram", ("rejected", "unmappable_diagram"), _single_question(prompt="1. Draw and label the energy flow.", response_bbox=None, response_kind="none", response_type="drawing"), extra_layout="diagram"),
    FixtureSpec("rejected-overlapping-graphic", ("rejected", "overlapping_graphic"), _single_question(), extra_layout="overlapping_graphic"),
    FixtureSpec("rejected-shifted-association", ("rejected", "adjacent_association"), _adjacent_questions(), selector_mode="shift_responses"),
    FixtureSpec("rejected-semantic-promotion", ("rejected", "unauthorized_semantic_promotion"), _single_question(), selector_mode="fabricated_response"),
)

FIXTURE_BY_ID = {fixture.fixture_id: fixture for fixture in FIXTURES}


def _add_text_field(page: fitz.Page, rect: fitz.Rect, field_name: str) -> None:
    widget = fitz.Widget()
    widget.field_name = field_name
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.rect = rect
    widget.field_value = ""
    widget.text_font = "Helv"
    widget.text_fontsize = 10
    widget.field_flags = 0
    widget.border_color = (0, 0, 0)
    widget.border_width = 1
    page.add_widget(widget)


def _draw_question(page: fitz.Page, question: QuestionSpec) -> None:
    prompt_rect = fitz.Rect(question.prompt_bbox)
    if prompt_rect.height > 22:
        page.insert_textbox(prompt_rect, question.prompt, fontsize=10.5, fontname="helv")
    else:
        page.insert_text((prompt_rect.x0, prompt_rect.y1 - 4.0), question.prompt, fontsize=10.5, fontname="helv")

    if question.response_bbox is None:
        return
    response_page_index = question.response_page_index
    if response_page_index is not None and response_page_index != question.page_index:
        return
    rect = fitz.Rect(question.response_bbox)
    if question.explicit_answer_label:
        page.insert_text((rect.x0, rect.y0 - 7.0), "Answer:", fontsize=8.5, fontname="helv")
    if question.response_kind == "line":
        y = (rect.y0 + rect.y1) / 2.0
        page.draw_line((rect.x0, y), (rect.x1, y), width=1.0, color=(0, 0, 0))
    elif question.response_kind == "line_group":
        if question.line_count <= 1:
            positions = [(rect.y0 + rect.y1) / 2.0]
        else:
            spacing = (rect.y1 - rect.y0) / max(question.line_count - 1, 1)
            positions = [rect.y0 + spacing * index for index in range(question.line_count)]
        for y in positions:
            page.draw_line((rect.x0, y), (rect.x1, y), width=1.0, color=(0, 0, 0))
    elif question.response_kind == "box":
        page.draw_rect(rect, width=1.0, color=(0, 0, 0))
    elif question.response_kind == "field":
        _add_text_field(page, rect, f"answer-{question.label}")
    elif question.response_kind == "two_fields":
        _add_text_field(page, fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + 24), "answer-a")
        _add_text_field(page, fitz.Rect(rect.x0, rect.y0 + 34, rect.x1, rect.y0 + 58), "answer-b")
    elif question.response_kind == "checkbox":
        choice_height = (rect.y1 - rect.y0) / max(question.line_count, 1)
        for index in range(question.line_count):
            y0 = rect.y0 + index * choice_height
            box = fitz.Rect(rect.x0, y0 + 3.0, rect.x0 + 14.0, y0 + 17.0)
            page.draw_rect(box, width=1.0, color=(0, 0, 0))
            page.insert_text((rect.x0 + 24.0, y0 + 15.0), f"{index + 1}) Option {index + 1}", fontsize=9.5)
    elif question.response_kind == "table":
        for fraction in (0.0, 0.5, 1.0):
            x = rect.x0 + rect.width * fraction
            page.draw_line((x, rect.y0), (x, rect.y1), width=1.0)
        for fraction in (0.0, 0.33, 0.66, 1.0):
            y = rect.y0 + rect.height * fraction
            page.draw_line((rect.x0, y), (rect.x1, y), width=1.0)


def _image_only_pdf(fixture_id: str) -> bytes:
    source = fitz.open()
    source_page = source.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    source_page.insert_text((72, 110), "1. Explain the image-only worksheet.", fontsize=12)
    source_page.draw_line((72, 150), (540, 150), width=1)
    png = source_page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False).tobytes("png")
    source.close()

    document = fitz.open()
    page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_image(page.rect, stream=png)
    document.set_metadata({**PDF_METADATA, "title": fixture_id})
    result = document.tobytes(garbage=4, deflate=True, no_new_id=True)
    document.close()
    return result


def generate_fixture_pdf(fixture: FixtureSpec) -> bytes:
    """Generate one stable PDF solely from the checked-in fixture definition."""
    if fixture.extra_layout == "image_only":
        return _image_only_pdf(fixture.fixture_id)

    document = fitz.open()
    for page_index in range(fixture.page_count):
        page_width, page_height = fixture.page_size(page_index)
        page = document.new_page(width=page_width, height=page_height)
        role = fixture.page_role(page_index)
        title = {
            PageRole.answer_key: "Answer Key",
            PageRole.teacher_guide: "Teacher Guide - Do Not Write",
        }.get(role, "Student Worksheet")
        if fixture.extra_layout == "questionless_page" and page_index == 1:
            title = "Student Worksheet - Reference Page"
        page.insert_text((15 if page_width < 400 else 48, 24), title, fontsize=11, fontname="helv")
        for question in fixture.questions:
            if question.page_index == page_index:
                _draw_question(page, question)
            elif question.response_page_index == page_index and question.response_bbox is not None:
                rect = fitz.Rect(question.response_bbox)
                y = (rect.y0 + rect.y1) / 2.0
                page.draw_line((rect.x0, y), (rect.x1, y), width=1.0)

        if fixture.extra_layout == "unclaimed_line" and page_index == 0:
            page.draw_line((120, 190), (470, 190), width=1.0)
        elif fixture.extra_layout == "diagram" and page_index == 0:
            page.draw_circle((300, 240), 65, width=2.0)
            page.draw_line((180, 240), (235, 240), width=2.0)
            page.draw_line((365, 240), (430, 240), width=2.0)
        elif fixture.extra_layout == "overlapping_graphic" and page_index == 0:
            page.draw_rect(fitz.Rect(230, 118, 380, 145), width=2.0)

        if fixture.rotated_page == page_index:
            page.set_rotation(90)

    document.set_metadata({**PDF_METADATA, "title": fixture.fixture_id})
    result = document.tobytes(garbage=4, deflate=True, no_new_id=True)
    document.close()
    return result


def fixture_hashes() -> dict[str, str]:
    return {
        fixture.fixture_id: hashlib.sha256(generate_fixture_pdf(fixture)).hexdigest()
        for fixture in FIXTURES
    }


def _intersects(first: tuple[float, float, float, float], second: list[float]) -> bool:
    return max(first[0], second[0]) <= min(first[2], second[2]) and max(first[1], second[1]) <= min(
        first[3], second[3]
    )


class FixtureEvidenceSelector:
    """Closed-world selector: it can reference only extracted fixture evidence."""

    provider_call_units = 0
    parser_name = "worksheet-contract-fixture-selector-v2"

    def __init__(self, fixture: FixtureSpec):
        self.fixture = fixture

    def classify_page(
        self,
        page,
        blocks: list[DocumentBlock],
        *,
        page_context: str = "",
        page_image: bytes | None = None,
    ) -> SemanticPageResult:
        del page_context, page_image
        questions = [question for question in self.fixture.questions if question.page_index == page.page_index]
        native_blocks = [
            block
            for block in blocks
            if block.source == SourceKind.native_pdf and block.bbox is not None and block.text.strip()
        ]
        response_blocks = [
            block
            for block in blocks
            if block.source == SourceKind.pdf_geometry
            and block.bbox is not None
            and block.block_label in {"answer_line", "bounded_box", "checkbox", "form_field", "writable_area"}
        ]
        selected_prompt_ids: set[str] = set()
        tasks: list[SemanticTaskCandidate] = []

        response_boxes = [question.response_bbox for question in questions]
        if self.fixture.selector_mode == "shift_responses" and len(response_boxes) > 1:
            response_boxes = response_boxes[1:] + response_boxes[:1]

        for index, question in enumerate(questions):
            prompts = sorted(
                [
                    block
                    for block in native_blocks
                    if block.bbox is not None and _intersects(question.prompt_bbox, block.bbox)
                ],
                key=lambda block: (block.bbox[1], block.bbox[0], block.id),
            )
            if not prompts:
                continue
            selected_prompt_ids.update(block.id for block in prompts)
            target = response_boxes[index]
            response_ids = []
            if target is not None:
                response_ids = [
                    block.id
                    for block in sorted(response_blocks, key=lambda item: (item.bbox[1], item.bbox[0], item.id))
                    if block.bbox is not None and _intersects(target, block.bbox)
                ]
            if self.fixture.selector_mode == "fabricated_response":
                response_ids.append("fixture-fabricated-response-id")
            tasks.append(
                SemanticTaskCandidate(
                    label=question.label,
                    prompt_text=question.prompt,
                    prompt_block_ids=[block.id for block in prompts],
                    response_block_ids=response_ids,
                    response_type=question.response_type,
                    confidence=0.99,
                )
            )

        return SemanticPageResult(
            page_index=page.page_index,
            page_role=self.fixture.page_role(page.page_index),
            confidence=0.99,
            blocks=[
                SemanticBlockDecision(
                    block_id=block.id,
                    role=(
                        BlockSemanticRole.student_prompt
                        if block.id in selected_prompt_ids
                        else block.semantic_role
                    ),
                    confidence=0.99,
                )
                for block in blocks
            ],
            tasks=tasks,
            warnings=["deterministic_fixture_evidence_selector"],
        )


def fixture_manifest() -> dict[str, object]:
    hashes = fixture_hashes()
    return {
        "schema_version": "worksheet-contract-fixtures-v2",
        "fixture_count": len(FIXTURES),
        "fixtures": [
            {
                "fixture_id": fixture.fixture_id,
                "tags": list(fixture.tags),
                "page_count": fixture.page_count,
                "question_count": len(fixture.questions),
                "sha256": hashes[fixture.fixture_id],
            }
            for fixture in FIXTURES
        ],
    }
