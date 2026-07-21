# Pilot evaluation protocol

No metric in this document is reportable until human annotations have been exported and validated.

## Matching rule

Match predicted tasks to gold tasks on the same page with maximum-weight one-to-one bipartite matching. The match weight is `0.7 * block_F1 + 0.3 * prompt_IoU`. A pair is eligible when either block F1 is at least 0.5 or prompt IoU is at least 0.5. A split produces one true positive plus extra false positives; a merge produces one true positive plus missed gold tasks. Parent/subpart correctness is scored only after task matching.

For legacy tasks, which lack physical block membership, use prompt IoU and normalized text overlap, and report the different matching evidence. Do not make legacy and block-aware results look directly equivalent without this caveat.

## Metrics

- Page-role accuracy and macro-F1 over the six page roles.
- Task precision, recall, F1, false-positive task rate, and missed-task rate from matched tasks.
- Parent/subpart grouping accuracy over matched task families.
- Prompt-block selection precision and recall by physical block ID.
- Prompt-region IoU for matched tasks.
- Response-region coverage: fraction of gold tasks with a physical gold region for which the system selects any region.
- Response-region IoU for matched tasks with a selected and gold physical region.
- Prompt-to-response link precision and recall over matched task/region pairs.
- Unsafe-region rate: selected `ambiguous` or `unsafe` regions, wrong-task regions, or regions overlapping protected source content, divided by all selected response regions.
- Side-panel-only accuracy for tasks whose gold safety is `side_panel_only`.
- OCR CER/WER on a separately transcribed sample; unavailable until transcription exists.
- Reading-order accuracy using pairwise precedence on manually ordered blocks in multi-column pages.
- Original-PDF export correctness by rendering the exported original page and checking page identity, answer placement, clipping, occlusion, and side-panel behavior. This pilot does not authorize writing during classification.
- Wall-clock processing time per page and document; median, p90, and maximum.
- Peak process RSS and Python peak allocation, with environment and model versions recorded.

Question-count equality is diagnostic only and is never the task metric.
