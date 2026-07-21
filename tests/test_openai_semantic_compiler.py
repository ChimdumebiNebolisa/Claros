from types import SimpleNamespace

from document_compiler import build_closed_world_page_input, compile_and_materialize
from document_model import BlockSemanticRole, DocumentBlock, DocumentPage, SourceKind
from evaluation.pdf_gold_pilot.closed_world import ClosedWorldPageResult
from providers.openai_semantic_compiler import OpenAISemanticCompiler
from providers.openai_semantic_classifier import OpenAIClosedWorldSemanticClassifier
from semantic_classifier import SemanticPageResult


def _page():
    from tests.test_pdf_gold_pilot import _page as pilot_page

    return pilot_page()


def _result():
    from tests.test_pdf_gold_pilot import _result as pilot_result

    return pilot_result()


def test_openai_adapter_sends_image_and_validates_closed_world_result():
    calls = []

    class FakeResponses:
        def parse(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_parsed=_result())

    compiler = OpenAISemanticCompiler(client=SimpleNamespace(responses=FakeResponses()), model="gpt-5.6")
    result = compiler.compile_page(_page(), b"png-bytes")

    assert isinstance(result, ClosedWorldPageResult)
    assert calls[0]["model"] == "gpt-5.6"
    assert calls[0]["store"] is False
    assert calls[0]["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")


def test_materializer_never_uses_model_authored_text_or_coordinates():
    class FakeCompiler:
        def compile_page(self, _page, _image):
            return _result()

    tasks = compile_and_materialize(FakeCompiler(), _page(), b"png-bytes")
    assert tasks[0]["prompt_text"] == "3a. Explain the result.\nUse evidence from the table."
    assert tasks[0]["response_bbox"] == [20.0, 100.0, 400.0, 130.0]
    assert tasks[0]["write_authorized"] is False


def test_document_ir_conversion_preserves_evidence_and_candidate_safety():
    page = DocumentPage(page_index=0, width_points=612, height_points=792, block_ids=["p0-b1", "p0-r1"])
    blocks = [
        DocumentBlock(
            id="p0-b1", page_index=0, reading_order=0, text="1. Explain.", block_label="native_text",
            bbox=[10, 10, 100, 25], confidence=1.0, source=SourceKind.native_pdf,
        ),
        DocumentBlock(
            id="p0-r1", page_index=0, reading_order=1, text="", block_label="answer_line",
            bbox=[20, 30, 100, 50], confidence=0.97, source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.response_area,
        ),
    ]

    compiler_input = build_closed_world_page_input(
        document_id="doc-hash", source_reference="sha256:abc", page=page, blocks=blocks, image_reference="local-render",
    )

    assert [block.id for block in compiler_input.blocks] == ["p0-b1"]
    assert compiler_input.response_candidates[0].id == "p0-r1"
    assert compiler_input.response_candidates[0].safe_for_writing is True


def test_runtime_adapter_materializes_only_closed_world_evidence():
    class FakeCompiler:
        def compile_page(self, _page, _image):
            return _result()

    page = DocumentPage(page_index=0, width_points=600, height_points=800, block_ids=["block-1", "block-2", "line-1"])
    blocks = [
        DocumentBlock(
            id="block-1", page_index=0, reading_order=1, text="3a. Explain the result.",
            block_label="native_text", bbox=[20, 30, 300, 60], confidence=1.0, source=SourceKind.native_pdf,
        ),
        DocumentBlock(
            id="block-2", page_index=0, reading_order=2, text="Use evidence from the table.",
            block_label="native_text", bbox=[20, 62, 320, 86], confidence=1.0, source=SourceKind.native_pdf,
        ),
        DocumentBlock(
            id="line-1", page_index=0, reading_order=3, text="", block_label="answer_line",
            bbox=[20, 100, 400, 130], confidence=0.92, source=SourceKind.pdf_geometry,
            semantic_role=BlockSemanticRole.response_area,
        ),
    ]

    result = OpenAIClosedWorldSemanticClassifier(compiler=FakeCompiler()).classify_page(
        page, blocks, page_image=b"png-bytes"
    )

    assert isinstance(result, SemanticPageResult)
    assert result.page_role.value == "student_worksheet"
    assert result.tasks[0].prompt_text == "3a. Explain the result.\nUse evidence from the table."
    assert result.tasks[0].response_block_ids == ["line-1"]


def test_runtime_adapter_rejects_missing_page_image_without_tasks():
    page = DocumentPage(page_index=0, width_points=600, height_points=800, block_ids=["block-1"])
    block = DocumentBlock(
        id="block-1", page_index=0, reading_order=1, text="Explain.",
        block_label="native_text", bbox=[20, 30, 300, 60], confidence=1.0, source=SourceKind.native_pdf,
    )

    result = OpenAIClosedWorldSemanticClassifier().classify_page(page, [block])

    assert result.tasks == []
    assert result.warnings == ["openai_semantic_result_rejected", "page_image_required"]
