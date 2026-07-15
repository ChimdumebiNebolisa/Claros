# Claros 17-page gold-label pilot status

**Date:** 2026-07-15
**Scope:** isolated evaluation only
**Production/deployment changes:** none
**Human gold available:** no

## Decision

Pause the three-way scoring run until humans annotate and adjudicate the selected pages. Continue with the closed-world Gemini experiment after (1) at least four pages are double-annotated, (2) all 17 pages have human task/response labels, (3) structured Paddle blocks are recovered for the three scans, and (4) a structured free-form Gemini rerun is retained. Do not promote PaddleOCR, train a supervised model, or investigate a second framework from this pilot yet.

The package is ready for annotation, but there is no evidence yet that closed-world Gemini materially improves task identification or grouping. Running it now would produce another unscored prediction set and violate the gold-first stopping rule.

## Selected pages

The selection expectations below came from manual visual inspection solely to ensure coverage. They are not gold page/task labels.

| Pilot ID | Source page | Selection rationale | Coverage expectation | Response evidence |
|---|---|---|---|---|
| pdf01-p01 | `01_selectable_dense_single_page.pdf`, p1 | Dense worksheet where the prior candidate split one form activity into six tasks | student worksheet; dense form/table | explicit lines/boxes |
| pdf02-p01 | `02_selectable_mixed_numbering.pdf`, p1 | Compound 3a/3b labels, directions, tables, and several response boxes | student worksheet; subparts/grouping | explicit |
| pdf02-p02 | same PDF, p2 | 7a/7b continuation, source thumbnails, tables, and distinct answer spaces | student worksheet; subparts/visual anchors | explicit |
| pdf03-p01 | `03_scan_table_layout.pdf`, p1 | Image-only focus question plus large writable table | scan; table/form | layout-only cells |
| pdf05-p01 | `05_selectable_image_questions.pdf`, p1 | Visual/reference-led questions without explicit answer boxes | visual student activity | none |
| pdf07-p01 | `07_selectable_five_page_packet.pdf`, p1 | Objective, numbered resource directions, URLs, and unnumbered Venn activity | mixed student content; visual/unnumbered | layout-only canvas |
| pdf07-p03 | same PDF, p3 | Numbered resources next to unnumbered summary response spaces | false-positive pressure; grouping | layout-only free space |
| pdf10-p01 | `10_scan_visual_matching.pdf`, p1 | Image-only graph matching with checkbox-like targets | scan; visual matching | layout-only checkboxes |
| pdf12-p02 | `12_selectable_long_mixed_packet.pdf`, p2 | Two-column lesson overview and numbered objectives | mixed packet; teacher guide; multi-column | none |
| pdf12-p08 | same PDF, p8 | Numbered teacher procedures/discussion prompts and instructional image | mixed packet; teacher guide | none |
| pdf12-p09 | same PDF, p9 | Questions paired with completed answers | mixed packet; answer key | none |
| pdf13-p01 | `13_selectable_history_mixed_layout.pdf`, p1 | Biography/reference text, instructions, ten prompts, images, poster activity | dense mixed-layout student page | no explicit PDF region |
| pdf14-p01 | `14_selectable_math_word_problems.pdf`, p1 | Designed worksheet with image, procedure steps, prompts, reference values, and lines | visual worksheet; numbered non-tasks | explicit |
| pdf16-p01 | `16_selectable_short_unusual_numbering.pdf`, p1 | Step labels combine procedure and answerable content over unmarked free space | unusual numbering/grouping | ambiguous free space |
| pdf18-p01 | `18_scan_numbered_questions.pdf`, p1 | Four OCR-recovered questions without explicit answer areas | scan; side-panel case | none |
| pdf19-p03 | `19_selectable_ten_page_packet.pdf`, p3 | Unnumbered prompts separated by blank space | unnumbered student prompts | ambiguous free space |
| pdf20-p02 | `20_selectable_form_tables.pdf`, p2 | Large form table mixes prompts, examples, reference values, and writable cells | table/form grouping | layout-only cells |

This is 17 pages from 13 PDFs. It includes all three image-only scans and intentionally includes pages expected to stress both false positives and missed tasks.

## Annotation setup

Label Studio is not installed in the current Claros environment and was not added to it. The isolated package contains:

- a Label Studio project configuration covering all requested page, block, task, response, safety, and relation labels;
- 17 clean 144-DPI page images;
- 17 physical-suggestion overlays;
- 17 import tasks whose preannotations live under `predictions`, never `annotations`;
- a human annotation protocol and a matching/metric protocol;
- exact separate-environment setup commands.

The protocol calls for double annotation of at least 4/17 pages (23.5%). No annotator export exists, so labels are neither available nor validated.

## Physical input and cache status

The prior benchmark preserved Paddle-rendered overlays but not reusable raw Paddle block JSON. The builder did not infer rectangles or text from overlay pixels and did not rerun PaddleOCR.

- 14/17 pages have machine-readable native/PDF-geometry blocks.
- The three scans (`pdf03-p01`, `pdf10-p01`, `pdf18-p01`) have clean images but zero structured blocks in this new input file.
- 67 PDF-geometry response candidates were proposed across the 17 pages. These remain suggestions.
- Visual inspection confirms that proposal coverage is incomplete: the dense line worksheet produces many line candidates, while the main writable cells on the large form table are not proposed; a long rule on the teacher-guide page is correctly only an ambiguous suggestion.

Before running the closed-world comparison, export/recover structured Paddle blocks for the three scans in the documented cache format. Improving table-cell, checkbox, drawing-canvas, and bounded-free-space proposals remains a separate physical-stage experiment.

## Legacy versus stored free-form Gemini

The unmodified legacy parser was freshly run while building the package. It emitted 23 records on the selected pages. That number is not precision, recall, or a gold task count.

The stored free-form benchmark provides document totals, page-role predictions, and overlays. It does not retain per-page task records, prompt boxes, or block membership for most PDFs, so it cannot be scored with the proposed task matcher. It must be rerun once on the frozen physical inputs and saved structurally; the existing configuration should remain unchanged for that comparison.

Unscored inspection candidates—not metric results—include:

- potential legacy false positives: one record on visually selected teacher-guide page `pdf12-p08` and six on visually selected answer-key page `pdf12-p09`;
- potential legacy misses: zero records on dense form page `pdf01-p01`, visual questions `pdf05-p01`, the two selected PDF 07 pages, unusual Step page `pdf16-p01`, unnumbered page `pdf19-p03`, form-table page `pdf20-p02`, and all scans;
- prior free-form over-splitting: six tasks on PDF 01's single activity and substantial document-level over-production on PDFs 07, 13, and 20, as already documented in the benchmark report.

These examples require human confirmation before being counted as false positives or misses.

## Closed-world Gemini status

The classifier and runner are implemented outside production paths. The response schema permits only:

- a page role;
- an exact selected/rejected partition of supplied physical block IDs;
- groupings of selected prompt/visual block IDs;
- parent/subpart references;
- supplied response-candidate IDs;
- response disposition, review status, and reasons.

There is no model-authored prompt-text field or coordinate field. Task text, task IDs, prompt boxes, and response boxes are derived deterministically from selected IDs. Unknown IDs, incomplete block partitions, invalid parent groups, unsafe candidates labeled `safe_physical`, and side-panel tasks with response candidates are rejected. Every derived task has `write_authorized=false`.

The validation-only run accepted the 17 input records, reported the three missing scan-block inputs, and made no Gemini call. The network runner refuses to execute without a non-empty human gold export, `CLAROS_PDF_GOLD_PILOT=1`, and an explicit `--execute` flag.

## Results and metrics

| Requested result | Status |
|---|---|
| Page-role accuracy / macro-F1 | unavailable: no human page labels |
| Task precision / recall / F1 | unavailable: no task-level gold |
| False-positive / missed-task rate | unavailable |
| Parent/subpart grouping accuracy | unavailable |
| Prompt-block precision / recall | unavailable |
| Prompt IoU | unavailable |
| Response coverage / IoU | unavailable |
| Prompt-response link precision / recall | unavailable |
| Unsafe-region rate | unavailable |
| Side-panel-only accuracy | unavailable |
| OCR CER/WER | unavailable: no transcription subset |
| Multi-column reading-order accuracy | unavailable: no human block order |
| Original-PDF export correctness | not run; classifier does not write or export |
| Closed-world processing time / peak memory | unavailable: gold gate prevented execution |

The annotation package build took approximately 24.8 seconds locally, including fresh legacy parsing and rendering. This is setup time, not classifier latency. The prior benchmark's Paddle runtime (~4,510 seconds corpus-wide) and near-1-GiB working set remain the applicable deployment evidence.

## Visual evidence and artifacts

- Selection: `evaluation/pdf_gold_pilot/selection.json`
- Annotation instructions: `evaluation/pdf_gold_pilot/README.md`
- Generated status: `output/pdf-gold-pilot/status.json`
- Clean renders: `output/pdf-gold-pilot/rendered`
- Physical overlays: `output/pdf-gold-pilot/physical-overlays`
- Label Studio import: `output/pdf-gold-pilot/label-studio-tasks.json`
- Closed-world inputs: `output/pdf-gold-pilot/physical-inputs.json`
- Legacy/stored-free-form index: `output/pdf-gold-pilot/baselines.json`
- Prior legacy overlays: `output/pdf-benchmark-current`
- Prior free-form overlays: `output/pdf-benchmark-semantic-full` and `output/pdf-benchmark-scans-combined`

Gold, three-way comparison overlays, task grouping results, answer-region accuracy results, and numeric false-positive/miss results do not exist yet.

## Recommendation and remaining uncertainty

1. Annotate all 17 pages; double-annotate and adjudicate at least four.
2. Recover structured Paddle block output for the three scans without rerunning the full corpus.
3. Save a structured free-form Gemini rerun on the identical frozen blocks.
4. Run the gold-gated closed-world path, render all four overlay layers, and apply the documented one-to-one matching rule.
5. Decide from task/block/link metrics—not counts—whether to continue closed-world Gemini.

A supervised layout-aware classifier is not yet justified because no labeled examples or closed-world baseline exist. Deepdoctection/LayoutLM should be reconsidered only if the constrained Gemini result still fails block selection/grouping after this gold set is scored. The visible response-proposal gaps may justify a separate physical-region experiment regardless of the semantic result.

No production parser, parser flag, student workflow, answer confirmation, PDF writer, exporter, dependency image, Cloud Run service, or URL was changed.
