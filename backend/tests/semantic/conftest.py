from __future__ import annotations

import pytest

from backend.document.models import PhysicalDocumentIR
from backend.semantic.models import SemanticMappingOutput, SemanticQuestionOutput
from backend.tests.document.factories import BlockSpec, make_document


@pytest.fixture
def semantic_document():
    document, blocks = make_document(
        (
            BlockSpec(
                "instruction",
                "text",
                (20_000, 20_000, 500_000, 40_000),
                text="Answer each question in one sentence.",
                join_after="newline",
            ),
            BlockSpec(
                "q1_label",
                "text",
                (20_000, 60_000, 35_000, 80_000),
                text="1.",
                join_after="space",
            ),
            BlockSpec(
                "q1_text",
                "text",
                (40_000, 60_000, 420_000, 80_000),
                text="Why do plants need sunlight?",
                join_after="newline",
            ),
            BlockSpec(
                "q1_line",
                "line",
                (20_000, 100_000, 500_000, 101_000),
            ),
            BlockSpec(
                "q2_label",
                "text",
                (20_000, 140_000, 35_000, 160_000),
                text="2.",
                join_after="space",
            ),
            BlockSpec(
                "q2_text",
                "text",
                (40_000, 140_000, 480_000, 160_000),
                text="How does sunlight help a plant make food?",
                join_after="newline",
            ),
            BlockSpec(
                "diagram",
                "image",
                (20_000, 180_000, 180_000, 300_000),
            ),
        )
    )
    return document, blocks


@pytest.fixture
def valid_mapping(semantic_document) -> SemanticMappingOutput:
    document, blocks = semantic_document
    return SemanticMappingOutput(
        document_id=document.document_id,
        complete=True,
        questions=(
            SemanticQuestionOutput(
                question_key="q_001",
                prompt_block_ids=(blocks["q1_label"].id, blocks["q1_text"].id),
                context_block_ids=(blocks["instruction"].id,),
                question_type="short_answer",
                grounding="grounded",
                visual_context_dependency=False,
                warnings=("shared_instruction",),
            ),
            SemanticQuestionOutput(
                question_key="q_002",
                prompt_block_ids=(blocks["q2_label"].id, blocks["q2_text"].id),
                context_block_ids=(blocks["instruction"].id,),
                question_type="short_answer",
                grounding="grounded",
                visual_context_dependency=False,
                warnings=("shared_instruction",),
            ),
        ),
    )


@pytest.fixture
def semantic_ir(semantic_document) -> PhysicalDocumentIR:
    return semantic_document[0]
