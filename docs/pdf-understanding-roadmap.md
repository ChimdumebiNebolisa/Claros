# Claros PDF understanding roadmap

> **Historical roadmap (status date 2026-07-15).** Not the present-tense
> Claros product roadmap. Current defaults and authority:
> [`ARCHITECTURE.md`](ARCHITECTURE.md), [`CLAROS_REVAMP_ROADMAP.md`](CLAROS_REVAMP_ROADMAP.md).
> Normal use does not require teacher review.

**Status date:** 2026-07-15
**Purpose:** durable execution plan grounded in the completed repository investigation, 20-PDF benchmark, and 17-page pilot
**Current authorization (at writing):** documentation and evaluation planning only; no production promotion or deployment

Claros remains an AI learning agent for students with typing difficulties. Its target workflow is direct student upload of educational PDFs, accessible answering by voice or typing, answer review and confirmation, and export of the completed original PDF whenever placement is reliable. Teacher review is an optional safety support, not the product premise or a required path for direct student uploads.

## 1. Executive decision

- The corrected legacy parser remains the production default.
- PaddleOCR PP-StructureV3 remains feature-gated, unpromoted, and unsuitable for the current synchronous request service.
- Adding another generic PDF-to-text or PDF-to-Markdown parser is not currently justified. Physical scan recovery is demonstrated; the principal unknowns are semantic task segmentation, answer-region detection, and prompt-to-response linking.
- The current 20-PDF benchmark has document-level expected counts but no task-level gold spans, block membership, grouping, response rectangles, or links. Count matching cannot establish precision or recall.
- Production deployment of the candidate pipeline is not authorized.
- `https://claros-505797934944.us-central1.run.app/` and `https://claros-fnaobzrxeq-uc.a.run.app/` are URLs for the same Cloud Run service. Neither may be deleted or treated as a stray service.

The next evidence-producing step is a fixed, cost-capped 17-page comparison using **agent-adjudicated reference labels**, followed by a small optional human audit focused on disagreements and unsafe-placement risk. Those labels are directional evaluation evidence, not human gold or final production truth.

## 2. Completed evidence

### Evidence ledger

| Classification | Current state |
|---|---|
| Completed work | Corrected legacy parser; feature-gated Paddle adapter; intermediate document/page/block/task model; structured free-form Gemini classifier; conservative response candidates; safety-gated export; corpus benchmark; 17-page pilot selection; Label Studio-compatible schema; closed-world experimental schema and runner. |
| Verified findings | Paddle recovered physical text/layout from all three scans; free-form semantic classification over-produced/split tasks; most candidate tasks lacked a reliable physical response region; runtime and memory exceed the current service shape; no deployment occurred. |
| Current blockers | No task-level reference labels; no structured Paddle cache for the three selected scans; prior free-form output lacks reusable per-page task geometry/block membership; incomplete response proposals for cells, checkboxes, drawing canvases, and free space; missing model usage/cost metadata. |
| Planned work | Recover scan blocks; create blind agent annotations and adjudication; optionally audit disagreements with a human; rerun both Gemini paths with cost instrumentation; score; decide whether semantics, physical proposals, or a learned model deserves further work. |
| Unknowns requiring evidence | Task precision/recall, grouping accuracy, page-role macro-F1, response/link accuracy, unsafe-region rate, OCR CER/WER, multi-column reading order, closed-world improvement, retry behavior, per-page Gemini cost, Linux worker performance, and sufficient data volume for supervised learning. |

### Physical extraction and OCR

The [benchmark report](./pdf-understanding-benchmark-report.md) verifies that PP-StructureV3 extracted all three image-only scans and preserved useful page, block, layout, reading-order, confidence, and coordinate information. The scan physical passes returned 4, 16, and 5 blocks in approximately 35.1, 43.9, and 50.6 seconds. Across the full corpus the physical stage produced 602 Paddle blocks.

This establishes that Paddle can be a scan/layout source. It does not establish that Paddle understands educational meaning, finds all writable cells, or groups content into student tasks.

### Semantic task classification

The free-form Gemini layer did not produce acceptable task granularity. On the 17 count-labeled PDFs, the legacy parser emitted 99 records for 136 expected tasks and the staged candidate emitted 201. Across all PDFs, all 224 candidate tasks remained review-required; 44 had detected physical regions, 8 were low-confidence, and 172 used the side panel.

The six-task split of PDF 01's single form activity is direct evidence of semantic over-splitting. The recovery of four visible prompts on scan PDF 18 is evidence of useful OCR plus semantic recovery. Neither observation yields precision or recall because the corpus lacks task-level labels. Expected-count matches can hide simultaneous splits, merges, misses, and false positives.

### Runtime and memory

The measured Paddle physical-stage total was about 4,510.6 seconds; the semantic-stage total was about 1,836.2 seconds. Paddle's document median was approximately 115.9 seconds and the maximum was approximately 895.3 seconds. The isolated Paddle environment was about 1.10 GiB, with roughly 159 MiB of configured model files, peak RSS growth around 679 MiB, and an observed working set approaching 1 GiB.

The current Cloud Run service has approximately 512 MiB memory, 1 vCPU, concurrency 80, and a 3,600-second timeout. Synchronous Paddle execution in that service is unsafe because one process can exceed available memory and long CPU-bound parsing would contend across high concurrency. Linux container inference remains unverified. See the [architecture record](./pdf-understanding-architecture.md).

### Safety and product invariants already present

- Students can answer by voice or typing and confirm before writing.
- PyMuPDF preserves and writes against the original PDF; Claros does not regenerate a blank worksheet from extracted text.
- Only explicit, sufficiently confident physical evidence or an explicitly confirmed valid region can authorize placement.
- Missing or uncertain placement uses a side-panel/export fallback rather than guessed coordinates.
- Invalid or unresolved regions do not silently become writable.
- Overflow or missing regions preserve the full confirmed answer instead of silently truncating it.

The [targeted-correction report](./pdf-acceptance-before-after-report.md) documents the legacy safety improvements, and the [initial acceptance report](./pdf-acceptance-report.md) preserves the pre-correction failure evidence.

### Seventeen-page pilot

The [pilot report](./pdf-gold-pilot-report.md) records 17 selected pages from 13 PDFs, including all three scans, dense forms, compound subparts, unnumbered prompts, visual activities, teacher-guide pages, an answer key, multi-column material, and pages without explicit response regions.

The local evaluation package contains 17 rendered pages, 17 physical overlays, a neutral annotation schema, 17 suggestion records, 67 response candidates, and a closed-world contract. Fourteen pages have native/PDF-geometry blocks. The three scans (`pdf03-p01`, `pdf10-p01`, and `pdf18-p01`) lack structured cached Paddle blocks because only prior overlays were retained. There are zero human annotation sets. Selection expectations and prior suggestions must not be represented as human gold.

Local working-tree artifacts currently live under `evaluation/pdf_gold_pilot/` and `output/pdf-gold-pilot/`. They are evidence inputs, not production dependencies, and are intentionally outside this documentation-only commit.

## 3. Future roadmap phases

Phases are sequential unless a phase explicitly says otherwise. A stop condition ends that phase without forcing a pass.

### Phase 1: Documentation and cost instrumentation

- **Objective:** Freeze this roadmap and add evaluation-only usage/cost capture before any future Gemini request.
- **Prerequisites:** This roadmap; current `semantic_classifier.py`; local pilot inputs; a documented price snapshot supplied by the operator when the experiment runs.
- **Exact inputs:** `docs/pdf-understanding-roadmap.md`; `output/pdf-gold-pilot/physical-inputs.json`; current model configuration; the Google GenAI response metadata available to the installed SDK.
- **Exact deliverables:** An evaluation-only request ledger schema; code that records model name, request ID, token/image usage, retries, page ID, elapsed time, and cost estimate; a pre-request budget projection; unit tests using fake responses; a local per-run cost report.
- **Actor:** Main Codex.
- **May change:** Evaluation scripts/tests and local evaluation report schemas only.
- **Must not change:** Production Gemini services, upload behavior, parser flags/defaults, credentials, or deployment configuration.
- **Cost risk:** None if verified with fake responses; no model call is part of this phase.
- **Exit criteria:** Tests prove every request is blocked when metadata capture or a price snapshot is unavailable and when projected spend exceeds the cap.
- **Stop conditions:** Stop if instrumentation would require modifying the production request path, if pricing cannot be pinned locally, or if the SDK exposes insufficient metadata without a documented fallback.
- **Decision produced:** Whether future Gemini evaluation can run with auditable spend and complete structured outputs.

### Phase 2: Recover structured Paddle blocks for the three scans

- **Objective:** Produce reusable physical block JSON for `pdf03-p01`, `pdf10-p01`, and `pdf18-p01` without rerunning the 20-PDF corpus.
- **Prerequisites:** The three source PDFs/pages, clean rendered images, current Paddle adapter, isolated Paddle environment, and the pilot cache schema.
- **Exact inputs:** The three corpus PDFs; pilot page numbers; page dimensions/rotation; existing clean renders; `evaluation/pdf_gold_pilot/build_annotation_project.py` cache contract.
- **Exact deliverables:** One immutable JSON record per page containing block ID, OCR text, layout label, polygon/bbox in image pixels and PDF points, confidence, reading order, page index, rotation, model/version, processing time, and source checksum; updated neutral physical overlays; a cache manifest.
- **Actor:** Main Codex.
- **May change:** Isolated cache/export scripts and output artifacts.
- **Must not change:** Paddle production flags, the production image, source PDFs, semantic labels, tasks, or response placement.
- **Cost risk:** Local CPU time, memory, and possible model download; no Gemini spend.
- **Exit criteria:** All three page caches validate, overlay back-projection aligns with the source page, IDs are unique, and provenance/checksums are recorded.
- **Stop conditions:** Stop after one failed retry per page, on memory exhaustion, on an unexpected model download requiring approval, or if coordinate normalization cannot be verified.
- **Decision produced:** Whether the frozen 17-page physical input is complete enough for blind annotation and identical-model comparison.

### Phase 3: Agent-adjudicated reference labels

- **Objective:** Create directional task/page/response reference labels without exposing annotators to parser predictions.
- **Prerequisites:** Complete neutral blocks for all 17 pages; clean page images; frozen annotation schema and instructions.
- **Exact inputs:** Source page images; neutral physical block IDs/text/layout labels/coordinates/reading order; neutral page metadata; no legacy, Paddle semantic, free-form Gemini, or closed-world task predictions.
- **Exact deliverables:** `annotator-a.json`; `annotator-b.json`; schema-validation results; field-level and region-level disagreement records; `agent-adjudicated-reference-labels.json`; adjudication notes and source citations by page/region; dataset version/checksums.
- **Actor:** Two independent annotation subagents, then a separate adjudicator subagent. The main Codex orchestrates inputs and validates outputs but does not silently decide labels.
- **May change:** Evaluation annotation JSON and disagreement/adjudication reports.
- **Must not change:** Physical inputs after annotation starts, source pages, production code, or the annotation schema without restarting both blind passes.
- **Cost risk:** Codex/subagent execution time and context volume; no Gemini API call.
- **Exit criteria:** Two complete blind records exist for every page; all disagreements are explicitly retained and adjudicated; schema/provenance checks pass; the dataset is named exactly `agent-adjudicated reference labels`.
- **Stop conditions:** Stop if either annotator sees model/parser predictions, if inputs differ between annotators, if one pass is incomplete, or if adjudication lacks source evidence.
- **Decision produced:** A directional reference set suitable for pilot comparison and a disagreement map for human audit.

### Phase 4: Optional human disagreement audit

- **Objective:** Test the highest-risk agent decisions without requiring teacher review as the product workflow.
- **Prerequisites:** Completed agent-adjudicated labels and disagreement ranking.
- **Exact inputs:** High-disagreement pages; high-impact safe/unsafe region decisions; mixed teacher/student and answer-key pages; compound tasks; scans; agent disagreement/adjudication notes; clean source evidence.
- **Exact deliverables:** Human audit decisions, rationale, unresolved cases, and a versioned delta from the agent-adjudicated set.
- **Actor:** Human reviewer.
- **May change:** Audit annotations and an audited derivative evaluation set.
- **Must not change:** Original agent records or disagreement history; production behavior.
- **Cost risk:** Human review time.
- **Exit criteria:** The selected audit subset is complete and every change references the source page/region.
- **Stop conditions:** Stop if a reviewer is unavailable; proceed with agent-adjudicated labels only, marked directional and unaudited.
- **Decision produced:** Whether disagreement-focused human review materially changes conclusions or exposes annotation-schema ambiguity.

### Phase 5: Structured free-form Gemini rerun

- **Objective:** Reproduce the existing semantic approach on frozen inputs while retaining everything needed for scoring and cost audit.
- **Prerequisites:** Phases 1-3 complete; optional Phase 4 does not block; fixed 17-page physical inputs; current free-form schema/configuration preserved.
- **Exact inputs:** Frozen page images; frozen blocks and response candidates; page context; pinned model name; pinned price snapshot; $5 run cap; reference labels hidden from the model.
- **Exact deliverables:** One strict structured result per page, raw validated response object, selected prompt/response block references, derived task geometry, warnings/rejections, request/usage ledger, retry record, elapsed time, memory snapshot, and per-run cost report.
- **Actor:** Main Codex.
- **May change:** Evaluation-only rerun and serialization code necessary to retain structured output.
- **Must not change:** Free-form task prompt/schema semantics beyond serialization/instrumentation, production flags/defaults, reference labels, or physical inputs.
- **Cost risk:** Gemini API spend up to the default $5 cap.
- **Exit criteria:** Every attempted page has a structured success or explicit rejected/failed record; no request lacks usage/cost metadata; outputs are immutable and checksummed.
- **Stop conditions:** Stop before a request that would exceed the cap; stop after one retry; stop on missing usage metadata, invalid model identity, changed inputs, or inability to preserve structured output.
- **Decision produced:** A reproducible free-form baseline for task-level scoring.

### Phase 6: Closed-world Gemini block-selection and grouping experiment

- **Objective:** Test whether constrained selection/grouping improves semantics without invented text or coordinates.
- **Prerequisites:** Phases 1-3 and 5 complete; validated closed-world input for all pages; reference labels hidden from the model.
- **Exact inputs:** The identical frozen images, physical blocks, reading order, layout labels, response candidates, model/version, price snapshot, and budget ledger used in Phase 5.
- **Exact deliverables:** Selected and rejected block IDs; task groups; parent/subpart relations; selected response-candidate IDs; page role; review/uncertainty reasons; deterministically derived task text/boxes; rejected invalid-output records; usage/cost/runtime/memory report.
- **Actor:** Main Codex.
- **May change:** Evaluation-only closed-world scripts/tests if required to fix schema validation, never to relax the closed-world contract after seeing scores.
- **Must not change:** Physical inputs, reference labels, production code, or the rule forbidding invented IDs/text/coordinates.
- **Cost risk:** Gemini API spend; share the same $5 default experiment cap unless an operator explicitly supplies a separate cap.
- **Exit criteria:** Complete structured results or explicit failures for all 17 pages, with zero unknown IDs and `write_authorized=false` on every derived task.
- **Stop conditions:** Stop before exceeding budget, after one retry, on any invented reference, on missing metadata, or if the run cannot use inputs identical to Phase 5.
- **Decision produced:** Whether closed-world constraints improve task selection/grouping enough to warrant continued semantic work.

### Phase 7: Three-way scoring

- **Objective:** Compare legacy, structured free-form Gemini, and closed-world Gemini without relying on counts.
- **Prerequisites:** Agent-adjudicated labels; complete outputs from Phases 5-6; frozen legacy output regenerated or preserved for the selected pages.
- **Exact inputs:** Reference labels and disagreements; legacy page tasks/regions; free-form structured outputs; closed-world structured outputs; page images; physical blocks.
- **Exact deliverables:** Per-method metric tables; confidence intervals or exact page counts where appropriate; per-page match records; split/merge/false-positive/miss taxonomy; grouping errors; visual overlays; a machine-readable comparison JSON and concise Markdown decision report.
- **Actor:** Main Codex; human reviewer resolves only evaluation-rule ambiguities, not method outcomes.
- **May change:** Scoring and overlay scripts.
- **Must not change:** Predictions, reference labels, eligibility thresholds, or matching weights after scores are viewed without versioning a new evaluation.
- **Cost risk:** Local CPU/memory only; no model calls.
- **Exit criteria:** Every metric is traceable to matched IDs/regions; unmatched tasks are classified; unavailable metrics remain explicitly unavailable.
- **Stop conditions:** Stop if any method lacks structured per-page output, if reference provenance fails, or if the matcher cannot uniquely represent a material class of tasks.
- **Decision produced:** Whether constrained Gemini materially improves semantic task identification and grouping over both baselines.

### Phase 8: Response-region proposal and prompt-to-response-link evaluation

- **Objective:** Measure the separate physical-region/linking blocker and identify which document classes require side-panel fallback.
- **Prerequisites:** Reference response regions/safety/link labels and three-way task matches.
- **Exact inputs:** Gold/reference response types and boxes; current 67 pilot candidates; recovered scan layout; predicted task-response links; protected source-content regions; page geometry/rotation.
- **Exact deliverables:** Response coverage/IoU, link precision/recall, unsafe-region rate, side-panel correctness, error taxonomy by line/box/cell/checkbox/canvas/free-space/none, and overlays showing wrong/missing links.
- **Actor:** Main Codex; adjudicator subagent revisits only disputed reference links; optional human reviewer audits unsafe/high-impact cases.
- **May change:** Evaluation-only candidate-generation experiments after the frozen baseline is scored, each under a new version.
- **Must not change:** Production writer/export, confirm-before-write, or the rule that ambiguous/unsafe regions are never automatically writable.
- **Cost risk:** Local geometry/image processing; no Gemini call unless a later separately approved link experiment is proposed.
- **Exit criteria:** All matched tasks receive a scored response disposition; unsafe selections are individually inspectable; proposal and linking errors are separated.
- **Stop conditions:** Stop if response labels are incomplete, coordinate systems disagree, or evaluation would require writing into source PDFs.
- **Decision produced:** Whether the next improvement belongs in physical proposal generation, semantic linking, or side-panel policy.

### Phase 9: Evidence decision gate

- **Objective:** Choose one next direction without forcing promotion.
- **Prerequisites:** Phase 7 and Phase 8 reports, cost/runtime data, annotation disagreement report, and optional human audit.
- **Exact inputs:** All scored metrics, error examples, cost ledger, runtime/memory, unsafe-region evidence, and document-class breakdowns.
- **Exact deliverables:** A signed decision record selecting one or more of: improve semantic approach; improve physical proposals; investigate supervised layout-aware classifier; retain scan-only Paddle fallback; stop the candidate; or gather a larger reference set.
- **Actor:** Main Codex prepares evidence; human reviewer approves direction.
- **May change:** Documentation and future experiment plan.
- **Must not change:** Production defaults, deployment, or safety invariants.
- **Cost risk:** None.
- **Exit criteria:** Decision cites quantitative metrics and page-level evidence, states uncertainty, defines a budget, and names a stop condition.
- **Stop conditions:** Stop with `insufficient evidence` if labels, costs, or safety metrics are incomplete or if results are mixed without a document-class boundary.
- **Decision produced:** Proceed, gather more evidence, change direction, or stop.

### Phase 10: Only after evidence, asynchronous worker design and deployment benchmark

- **Objective:** Design and benchmark an isolated low-concurrency parser job only if Phase 9 retains Paddle or model inference.
- **Prerequisites:** Positive Phase 9 decision; explicit infrastructure and deployment-benchmark authorization; Linux-compatible dependency lock; measured workload and retry requirements.
- **Exact inputs:** Pilot/corpus latency and peak-memory distributions; cached-model sizes; job payload/output schemas; security/retention requirements; Cloud Run limits; cost assumptions.
- **Exact deliverables:** Architecture decision record; queue/job lifecycle; idempotency and retry rules; privacy-safe logging; cancellation/timeout behavior; resource/concurrency sizing; Linux container benchmark; compute cost estimate; rollback plan. Deployment, if later authorized, must target a separate evaluation worker/revision.
- **Actor:** Main Codex designs/benchmarks; human reviewer authorizes infrastructure and any deployment.
- **May change:** Isolated worker prototype, benchmark container, and infrastructure documentation after approval.
- **Must not change:** Current synchronous service, production parser default, direct student workflow, or either existing Cloud Run URL.
- **Cost risk:** Container build/storage and worker compute; track separately from Gemini API spend.
- **Exit criteria:** Representative pages finish within explicit latency/memory/retry targets at low concurrency, with costs and failure recovery measured on Linux.
- **Stop conditions:** Stop without explicit authorization, if memory remains near/above the selected instance limit, if cold-start/latency is unacceptable, or if job safety/idempotency is unproven.
- **Decision produced:** Whether an asynchronous worker is operationally viable and what resource envelope it requires.

### Phase 11: Only after evidence, decide whether a supervised layout-aware classifier is warranted

- **Objective:** Decide whether Claros-specific training is justified; do not train merely because generic semantics failed.
- **Prerequisites:** Phase 9 identifies persistent block-selection/grouping errors; a larger labeled-data plan; licensing/model-weight review; compute budget; baseline metrics.
- **Exact inputs:** Agent-adjudicated and human-audited labels; error taxonomy; document-level train/validation/test split plan; candidate model cards/licenses; hardware/runtime requirements; minimum detectable improvement target.
- **Exact deliverables:** Data requirement estimate; label taxonomy stability assessment; leakage-safe split; model options such as token classification, relation extraction, or layout graph selection; license/weight constraints; training/inference cost estimate; go/no-go experiment proposal.
- **Actor:** Main Codex researches and drafts; human reviewer approves data collection/training. Independent annotation and adjudication actors expand labels only under the frozen protocol.
- **May change:** Documentation, dataset plan, and a separately approved offline training branch after go-ahead.
- **Must not change:** Production code or models; no training occurs during the decision phase.
- **Cost risk:** Potentially high annotation, GPU, storage, and maintenance cost.
- **Exit criteria:** The proposal states required labeled pages/PDFs, target metrics over closed-world Gemini, runtime envelope, licenses, budget, and stop criteria.
- **Stop conditions:** Stop if the label set is unstable, data is insufficient, licensing is incompatible, projected inference cannot fit the worker envelope, or simpler semantic/physical fixes address the measured errors.
- **Decision produced:** Train a Claros-specific model, collect more data, use closed-world Gemini, or stop supervised investigation.

## 4. Agent-adjudicated labeling protocol

Future Codex execution must use this protocol exactly unless a versioned protocol amendment is approved before annotation begins.

1. The main Codex freezes page images, neutral physical blocks, neutral metadata, schema version, and checksums.
2. It starts two independent annotation subagents. They work blind and may not communicate or inspect one another's outputs.
3. Neither annotator may see legacy tasks, Paddle semantic/page-role predictions, free-form Gemini tasks, closed-world tasks, overlays containing task predictions, expected question counts, or prior agent selection expectations.
4. Both annotators inspect only the source page image, neutral physical block IDs/text/layout labels/coordinates/reading order, page geometry/rotation, and neutral document position metadata.
5. Each independently labels page role; block role; student-answerable tasks; task boundaries; prompt membership/box; parent/subparts; accessible order; visual anchors; response type/box/safety; prompt-response and prompt-visual relations; and side-panel-only cases.
6. The main Codex validates schemas but does not merge disagreements.
7. A third, separate adjudicator subagent receives both records, the disagreement list, and source evidence. The adjudicator must decide each disagreement explicitly or mark it unresolved; it may not consult parser/model predictions.
8. Preserve both original annotations, all disagreement records, adjudication rationale, unresolved items, timestamps, actor IDs, schema version, and input checksums.
9. Name the final dataset **agent-adjudicated reference labels**. Never call it human gold.
10. A later human audit should prioritize high-disagreement pages and high-impact decisions: unsafe versus safe placement, mixed/answer-key roles, parent/subpart grouping, visual tasks, scans, and side-panel-only cases.
11. Metrics based on this set are directional. Production promotion still requires broader evidence and, for high-risk placement decisions, targeted human review.

Recommended agreement statistics include page-role Cohen's kappa, task-level matched F1 between annotators, prompt-block F1, grouping agreement, response-disposition agreement, link agreement, and box IoU distributions. These describe annotation reliability; they are not parser scores.

## 5. Evaluation contract

### Matching rule

For block-aware predictions, match tasks on the same page using maximum-weight one-to-one bipartite matching:

`match_weight = 0.7 * prompt_block_F1 + 0.3 * prompt_region_IoU`

A pair is eligible when prompt-block F1 is at least 0.5 **or** prompt-region IoU is at least 0.5. A split yields at most one true-positive match plus extra false positives. A merge yields at most one match plus missed reference tasks. Score parent/subpart relations only after task matching.

Legacy tasks do not have physical block membership. Match them using same-page prompt IoU plus normalized text overlap and report that different evidence separately; do not imply direct equivalence with block-aware matching.

Freeze thresholds and weights before viewing method scores. Any changed matcher is a new version and must rescore every method.

### Required metrics

- **Page-role accuracy and macro-F1:** six roles, with confusion matrix.
- **Task precision, recall, and F1:** one-to-one matched student-answerable tasks.
- **Prompt-block selection accuracy:** precision, recall, and F1 over selected neutral block IDs.
- **Parent/subpart grouping accuracy:** correct family membership and relation direction after task matching.
- **Prompt-region overlap:** IoU distribution and thresholded coverage for matched tasks.
- **Response-region coverage and IoU:** only where reference labels identify a physical response region; separate by region type.
- **Prompt-to-response link accuracy:** precision/recall of matched task-to-region links.
- **Unsafe-region rate:** ambiguous/unsafe selections, wrong-task links, or regions overlapping protected source content divided by all selected physical regions. Also report absolute unsafe count.
- **Side-panel-only correctness:** accuracy/precision/recall for tasks whose correct disposition is no safe physical placement.
- **OCR checks:** CER/WER on a manually transcribed subset when transcription labels exist; otherwise unavailable.
- **Reading-order checks:** pairwise precedence accuracy on labeled multi-column/visual pages; otherwise unavailable.
- **Export correctness:** original page identity/geometry preserved; confirmed answer appears only in approved location or safe fallback; no clipping, occlusion, wrong-page placement, lost pages, or blank regeneration.
- **Runtime, memory, and retry behavior:** wall time per page/document, median/p90/max, peak RSS, Python allocation where useful, cold/warm distinction, failure/retry counts, and terminal status.

### Metrics currently unavailable

Task/page/grouping/block/link/region accuracy metrics are unavailable because no human gold or agent-adjudicated reference labels exist. OCR CER/WER is unavailable because no transcription subset exists. Reading-order accuracy is unavailable because no human/agent pairwise order labels exist. Three-way task scoring is unavailable because the prior free-form benchmark did not retain structured per-page task geometry/block membership and the three selected scans lack structured Paddle cache records. Closed-world runtime/cost is unavailable because the gold-gated runner has not executed. Export correctness for the candidate is unavailable because this pilot intentionally performed no writes.

Question-count deltas remain diagnostics only.

## 6. Cost-control plan

No Gemini experiment may start until evaluation code does all of the following:

- Logs the exact model name, provider request ID, input tokens, output tokens, image/video token usage when available, retry count, stable page ID, and elapsed time for every attempt.
- Preserves the structured per-page request result or explicit rejected/error record; no successful model call may exist only in console output or an overlay.
- Writes a per-request and per-run local cost estimate with the pinned pricing source/date and calculation formula.
- Uses a default **$5 total experiment budget cap**.
- Projects the next request from measured prior pages plus a conservative first-request bound and stops **before** sending it when projected total spend would exceed the cap.
- Uses cached physical extraction and existing rendered pages. It must not rerun Paddle during a Gemini comparison.
- Runs the fixed 17 pilot pages before any corpus-wide request.
- Limits retries to one per page unless an operator explicitly overrides the retry policy and budget.
- Avoids Google Search grounding and any other paid/grounded tool.
- Separates Gemini API spend from Cloud Run/parser-worker compute estimates and reports both independently.
- Redacts educational content and credentials from logs while retaining IDs, counts, timing, and provenance.

If token/image usage is unavailable from the SDK response, mark the request uncosted and stop further calls. Do not substitute elapsed time or character count as an actual billed total. A conservative preflight estimate may protect the cap, but the final report must distinguish estimate from provider-reported usage.

### Known cost versus unknown cost

Known locally:

- The current text-model configuration names `gemini-2.5-flash`.
- The benchmark records approximately 1,836.2 seconds of semantic-stage elapsed time and approximately 4,510.6 seconds of Paddle physical-stage elapsed time.
- The artifacts record processing and memory measurements, not billing usage.

Unknown:

- Historical input, output, cached, image, or video token counts.
- Historical provider request IDs, retry counts, and exact model identity per request.
- The pricing snapshot applicable at request time.
- Actual historical Gemini API spend.
- Any Cloud Run or local worker compute cost attributable specifically to the benchmark.

Therefore the historical Gemini cost is **unknown and not calculable from retained evidence**. The elapsed-time totals must not be converted into API cost.

## 7. Production invariants

Until a future evidence-backed promotion decision, all of the following remain unchanged:

- Direct student uploads remain a core Claros workflow.
- Voice answering and typed fallback remain available.
- Students review/confirm before any answer write.
- The legacy parser remains the production default.
- PaddleOCR, document semantics, synchronous execution, and auto-approval feature flags remain default-off.
- Export remains backed by the original PDF.
- Uncertain placement uses the side panel or another explicit safe fallback.
- No automatic write may target an ambiguous, unsafe, invented, or unconfirmed region.
- PaddleOCR is not deployed inside the current synchronous service.
- Neither existing Cloud Run URL may be deleted or modified on the assumption that it is a separate stray service.
- Optional teacher review must not replace or become mandatory for direct student uploads.

## 8. Ready-to-use future prompts

These prompts are for future, separately authorized sessions. Each includes a terminal stop condition.

### Recover the three scan block caches

> Work only on the Claros 17-page PDF pilot. Recover structured PP-StructureV3 blocks for `pdf03-p01`, `pdf10-p01`, and `pdf18-p01` in the existing cache schema. Preserve block IDs, text, labels, polygons/bboxes in image pixels and PDF points, confidence, reading order, rotation, model/version, timing, and checksums. Do not run Gemini, the full corpus, production code, or deployment. Verify coordinate overlays. **Stop when all three validated cache records exist, or stop and report the first unrecoverable dependency/memory/normalization blocker after one retry per page.**

### Create agent-adjudicated reference labels

> Freeze the 17 clean page images and neutral physical inputs. Spawn two independent blind annotation subagents; neither may see legacy, Paddle semantic, free-form Gemini, closed-world predictions, expected counts, or each other's work. Then use a separate adjudicator subagent to resolve recorded disagreements from source evidence. Preserve both originals, disagreements, adjudication notes, schema version, and checksums. Name the result `agent-adjudicated reference labels`; do not call it human gold. **Stop if blindness is breached, inputs differ, either annotation is incomplete, or every disagreement is not explicitly resolved or marked unresolved.**

### Rerun structured free-form Gemini

> Use the frozen 17-page images, blocks, response candidates, and current free-form semantic schema. First verify request/usage/cost instrumentation, a pinned model and price snapshot, structured output persistence, one-retry maximum, and the $5 cap. Hide reference labels from the model. Preserve one validated or rejected structured record per page plus request ID, model, token/image usage, retry, elapsed time, memory, and estimated cost. Do not alter production code or prompts after seeing results. **Stop before any request that would exceed the cap, and stop immediately on missing usage metadata, changed inputs, or inability to preserve structured output.**

### Run closed-world Gemini

> Run the existing closed-world experiment on exactly the same frozen 17-page inputs and pinned model used for the free-form rerun. The model may only select/reject existing block IDs, group selected IDs, declare parent/subparts, select existing response candidates, and return review reasons/page role. Derive text and coordinates deterministically; every task must remain `write_authorized=false`. Apply the instrumented $5 cap and one-retry maximum. **Stop on any invented reference, invalid partition, missing metadata, changed input, or projected budget overrun.**

### Score the three-way comparison

> Without model calls, score legacy, structured free-form Gemini, and closed-world Gemini against the frozen agent-adjudicated reference labels using the roadmap's versioned bipartite matching rule. Report page-role, task, block, grouping, prompt-region, response/link, unsafe, side-panel, OCR/order where available, runtime, memory, retries, and cost. Render traceable per-page overlays and retain unmatched/split/merged records. **Stop without scores if any method lacks structured per-page output, reference provenance fails, or the matcher cannot represent a material task class.**

### Design an asynchronous worker only if warranted

> First read the Phase 9 decision. Proceed only if it explicitly retains Paddle/model inference and grants worker-design authorization. Design an isolated low-concurrency job protocol and benchmark a Linux container on representative pilot pages, recording cold/warm latency, peak RSS, retries, idempotency, cancellation, privacy-safe logs, and separate compute cost. Do not modify the current synchronous service, parser default, or either Cloud Run URL, and do not deploy without separate approval. **Stop if Phase 9 is absent/negative, authorization is missing, memory exceeds the chosen instance envelope, or failure recovery is unproven.**

## Repository evidence map

Tracked documentation intended to survive this commit:

- [Initial acceptance baseline](./pdf-acceptance-report.md)
- [Targeted-correction before/after report](./pdf-acceptance-before-after-report.md)
- [PDF-understanding architecture](./pdf-understanding-architecture.md)
- [Full candidate benchmark report](./pdf-understanding-benchmark-report.md)
- [Seventeen-page pilot status](./pdf-gold-pilot-report.md)
- This roadmap

Local evaluation/benchmark artifacts remain useful but are intentionally not part of the documentation commit: `evaluation/pdf_gold_pilot/`, `output/pdf-gold-pilot/`, `output/pdf-benchmark-final/`, page overlays, raw PDFs, caches, virtual environments, and pilot code/tests. A future session must verify their availability before executing artifact-dependent phases and report them unavailable rather than reconstructing evidence or labels.
