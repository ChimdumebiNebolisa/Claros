from __future__ import annotations

import hashlib
import re
from pathlib import Path

import fitz

from evaluation.canonical_v1.evaluate import evaluate
from evaluation.canonical_v1.generate import DEFAULT_SPEC, generate_all
from evaluation.canonical_v1.schema import CanonicalSource


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _intersection_area(first: list[float], second: list[float]) -> float:
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    return width * height


def test_source_pdf_and_manifest_remain_consistent(tmp_path: Path):
    source = CanonicalSource.model_validate_json(DEFAULT_SPEC.read_text(encoding="utf-8"))
    output = tmp_path / "generated"
    manifest = generate_all(DEFAULT_SPEC, output)

    assert len(source.documents) == len(manifest.documents) == 3
    assert manifest.expected_labels_kind == "deterministic_first_party"
    assert manifest.machine_predictions_are_expected_labels is False

    for source_document, generated_document in zip(
        source.documents,
        manifest.documents,
        strict=True,
    ):
        assert generated_document.canonical_id == source_document.canonical_id
        assert 1 <= len(generated_document.pages) <= 2
        generated_tasks = sorted(
            (
                task
                for page in generated_document.pages
                for task in page.tasks
            ),
            key=lambda task: task.order,
        )
        assert len(generated_tasks) == len(source_document.tasks) == 5

        pdf_path = output / generated_document.pdf
        assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == generated_document.pdf_sha256
        pdf = fitz.open(pdf_path)
        try:
            assert pdf.page_count == len(generated_document.pages)
            selectable_text = _normalized_text(
                " ".join(page.get_text("text", sort=True) for page in pdf)
            )
            assert source_document.title in selectable_text
            for source_task in source_document.tasks:
                assert _normalized_text(source_task.prompt) in selectable_text
        finally:
            pdf.close()

        for source_task, generated_task in zip(
            source_document.tasks,
            generated_tasks,
            strict=True,
        ):
            assert generated_task.task_id == source_task.task_id
            assert generated_task.order == source_task.order
            assert generated_task.task_type == source_task.task_type
            assert generated_task.prompt_text == source_task.prompt
            assert [region.region_id for region in generated_task.response_regions] == [
                response.response_id for response in source_task.responses
            ]
            assert [
                region.response_type for region in generated_task.response_regions
            ] == [response.response_type for response in source_task.responses]
            assert [
                region.response_safety for region in generated_task.response_regions
            ] == [response.response_safety for response in source_task.responses]
            assert len(generated_task.relations) == len(generated_task.response_regions)
            assert {
                relation.to_region_id for relation in generated_task.relations
            } == {
                region.region_id for region in generated_task.response_regions
            }
            assert all(
                relation.relation_type == "prompt_to_response_region"
                and relation.from_region_id == generated_task.prompt_region.region_id
                for relation in generated_task.relations
            )


def test_generated_geometry_is_in_page_and_separates_prompts_from_responses(tmp_path: Path):
    manifest = generate_all(DEFAULT_SPEC, tmp_path / "generated")

    for document in manifest.documents:
        for page in document.pages:
            page_regions: list[list[float]] = []
            for task in page.tasks:
                prompt_bbox = task.prompt_region.bbox_points
                regions = [task.prompt_region, *task.response_regions]
                for region in regions:
                    x0, y0, x1, y1 = region.bbox_points
                    assert 0 <= x0 < x1 <= page.width_points
                    assert 0 <= y0 < y1 <= page.height_points
                    assert region.page_index == page.page_index
                    page_regions.append(region.bbox_points)
                for response in task.response_regions:
                    assert _intersection_area(prompt_bbox, response.bbox_points) == 0
            for index, region in enumerate(page_regions):
                for other in page_regions[index + 1 :]:
                    assert _intersection_area(region, other) == 0


def test_generation_is_byte_deterministic(tmp_path: Path):
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    first = generate_all(DEFAULT_SPEC, first_output)
    second = generate_all(DEFAULT_SPEC, second_output)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    for document in first.documents:
        first_bytes = (first_output / document.pdf).read_bytes()
        second_bytes = (second_output / document.pdf).read_bytes()
        assert first_bytes == second_bytes


def test_canonical_baseline_reports_required_metrics(tmp_path: Path):
    output = tmp_path / "generated"
    generate_all(DEFAULT_SPEC, output)
    report = evaluate(output / "manifest.json", output / "baseline.json")

    assert report["counts"]["documents"] == 3
    assert report["counts"]["expected_tasks"] == 15
    assert len(report["documents"]) == 3
    assert (output / "baseline.json").is_file()
    assert "parse_document" in report["parser"]
    required_metrics = {
        "task_count_accuracy",
        "prompt_text_fidelity",
        "task_order_accuracy",
        "response_region_detection",
        "response_type_accuracy",
        "task_to_response_association_accuracy",
        "physical_response_detection",
        "physical_response_type_accuracy",
        "false_positive_tasks",
        "false_positive_writable_regions",
    }
    assert required_metrics <= report["metrics"].keys()
    for document in report["documents"]:
        for task in document["tasks"]:
            # Stage 3 may materialize multiple typed regions per task; one
            # predicted region still cannot satisfy multiple expected ones.
            predicted_ids = [
                response["predicted_region_id"]
                for response in task["responses"]
                if response["detected"] and response["predicted_region_id"]
            ]
            assert len(predicted_ids) == len(set(predicted_ids))
