# Claros PDF gold pilot annotation protocol

This pilot labels student-answerable tasks; it does not define a teacher-review product workflow. The page-selection expectations are coverage notes, not labels. Paddle/native predictions are suggestions and must be accepted, changed, or deleted by a human.

## Annotation unit

Annotate the rendered original page. Assign exactly one page role. Draw or correct physical block rectangles, then label their educational role. A `student_prompt` is content the student is genuinely expected to answer or complete, not merely a numbered line, objective, worked example, teacher direction, answer-key question, URL, standard, or reference value.

For every gold task:

1. Draw one `task_prompt_bbox` around the full prompt and give it a stable `gold_task_id`.
2. Give each member `student_prompt` block the same `gold_task_id`.
3. Record `parent_task_id`, `subpart`, `task_type`, and `accessible_task_order` on the `task_prompt_bbox`.
4. Mark whether the task is student-answerable. If it is not answerable, it is not a gold task; retain the block's non-task semantic label.
5. Draw or correct any response region, set its physical type and safety, and connect it with `prompt_to_response_region`.
6. If there is no reliable physical response region, set the prompt's `response_type` to `none`, its safety to `side_panel_only`, and record this in `task_manifest_json`. Do not draw a guessed response rectangle.
7. Draw `visual_anchor` regions only when the visual is needed to understand or answer the task, then connect them with `prompt_to_visual_anchor`.
8. Connect parent and child task prompt boxes with `parent_task_to_subpart`.

`task_manifest_json` is a cross-check and should contain one object per task with these keys: `gold_task_id`, `parent_task_id`, `subpart`, `prompt_region_ids`, `response_region_ids`, `visual_anchor_region_ids`, `task_type`, `accessible_task_order`, `student_answerable`, `response_type`, and `response_safety`.

## Response safety

- `safe_physical`: an explicit line, box, cell, checkbox, drawing canvas, or clearly bounded free-space region that can receive an answer without covering source content.
- `ambiguous`: a plausible region whose bounds or prompt link are uncertain.
- `unsafe`: a visible region that would cover content, belongs to another task, or is otherwise unsuitable for writing.
- `side_panel_only`: the original page offers no reliable writable location. Preserve the PDF and keep the answer outside the page.

## Quality control

Double-annotate at least 4 of the 17 pages (23.5%), including one scan, one teacher/answer-key page, one compound-task page, and one table/form page. Resolve disagreements before scoring. If only one annotator is available, leave adjudication status `single_annotator_unvalidated` and do not present the labels as validated gold.

Do not use any Gemini prediction as truth. Annotators should see the original page and physical suggestions, not free-form or closed-world task predictions, during the first pass.
