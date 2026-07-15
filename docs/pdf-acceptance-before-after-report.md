# Claros PDF acceptance: targeted-correction before/after report

**Audit date:** 2026-07-15
**Corpus:** `C:\Users\Chimdumebi\Downloads\claros-pdf-acceptance-corpus\claros-pdf-corpus`
**Scope:** all 20 supplied PDFs and all 109 pages (17 selectable-text PDFs, 3 image-only scans)
**Baseline:** `docs/pdf-acceptance-report.md`
**Deployment:** none

## Decision

**Do not deploy and do not freeze the parser.** The targeted corrections materially improve safety and failure honesty, but the separately defined student-only launch subset passes only **2/5 (40.0%)**, below the 90% freeze threshold. Continue with targeted detection/classification work; the remaining failures are still clustered and do not yet justify replacing the underlying PDF text extractor.

The strongest improvement is safety. All three scans now return `requires_ocr` with zero questions; unsupported layouts return zero questions; internal IDs are unique; compound source labels are preserved separately; and every document with unresolved layout is held in `layout_review_required`. No corpus PDF now returns `ok`, so none can silently proceed to writing. The write endpoint also rejects unresolved or absent answer regions unless a reviewed region is explicitly supplied.

## Method

Before changing parser behavior, I added seven characterization/regression tests for every baseline failure cluster and confirmed that all seven failed against the baseline implementation. The tests cover:

- image-only/textless PDFs returning `requires_ocr` with zero questions;
- unsupported selectable PDFs returning zero questions and never ID 0;
- compound labels, globally unique internal IDs, and page attribution;
- rejection of numeric-only values, scientific notation, URLs, and procedure entries;
- exclusion of educator and answer-key sections;
- suppression of low-confidence answer regions with mandatory review;
- server-side refusal to write to an unconfirmed layout.

After implementing the corrections, I ran the existing Claros parsing entry point once for every corpus PDF, timed the parser call, and recorded title, status, warnings, question count, internal IDs, source labels, page attribution, regions, and confidence. I rendered every source page at 1.5x with prompt regions in red and answer regions in blue, then visually compared all 109 overlays with the originals. Text-only extraction was not used as evidence of layout accuracy.

Raw before evidence is at `C:\Users\Chimdumebi\AppData\Local\Temp\claros-pdf-acceptance-audit`. Raw after evidence, including `results.json`, 109 page overlays, and 20 contact sheets, is at `C:\Users\Chimdumebi\AppData\Local\Temp\claros-pdf-acceptance-after`.

## Acceptance definitions

- **Strict detection:** expected student prompt/task set, without false, merged, split, duplicate, or missing questions.
- **Text fidelity:** readable prompt text, correct boundaries, and correct reading order/page.
- **Safe answer handling:** retained regions are on the question's page and visually plausible; uncertain regions are suppressed; writing cannot proceed until review confirms a region.
- **Honest failure:** scans say `requires_ocr`; unsupported inputs say `unsupported_layout`; uncertain supported inputs say `layout_review_required`; all failure states return no invented fallback question.
- **Launch-subset pass:** strict detection and text fidelity, plus safe answer handling. A review status is acceptable because Claros v1 requires confirmation for low-confidence layouts.

## Before/after metrics

Rates are document-level and intentionally retain the baseline expected counts.

| Metric | Baseline | After corrections | Interpretation |
|---|---:|---:|---|
| Open/process without crash | 20/20 (100%) | 20/20 (100%) | No upload or parser crashes in either run. |
| Strict question detection, selectable | 3/17 (17.6%) | 2/17 (11.8%): 04, 17 | Safety became more conservative: ambiguous forms previously counted as detected are now honestly rejected. |
| Strict text fidelity, selectable | 2/17 (11.8%) | 2/17 (11.8%): 04, 17 | U+0007 corruption in 04 is fixed; 20 is no longer treated as a supported question layout. |
| Exact-set, safe answer handling | 2/17 (11.8%) | 2/17 (11.8%): 04, 17 | Uncertain regions in these documents are now suppressed and review-gated instead of invented. |
| Cross-page or low-confidence writing can silently proceed | 15/17 selectable failures | 0/20 (0%) | Every uncertain parse/region is blocked by status, UI state, and server validation. |
| Honest handling of unusable/uncertain inputs | 3/18 (16.7%) | 18/18 (100%) | Every non-pass corpus input now has a non-`ok` status. |
| Image-only OCR handling | 0/3 (0%) | 3/3 (100%) | Each scan returns `requires_ocr`, zero questions, no ID 0. |
| Unique internal IDs | duplicate-ID warning on 9/17 selectable PDFs | 20/20 (100%) unique | Source labels are separate from sequential internal IDs. |
| Selectable question records emitted | 277 | 99 | The reduction is mainly the removal of table/procedure/educator and fallback records; incomplete detection remains documented below. |
| Automatically ready without review | 1/17 (5.9%) | 0/17 (0%) | Deliberately conservative: the two usable student worksheets require review because some regions were suppressed. |

Processing time improved from 22.197 s to **12.167 s total**. After-correction selectable parsing used 12.153 s total (0.715 s average, 0.137 s median, 7.603 s maximum); scans used 0.014 s total.

## Student-only launch subset

The subset was selected by v1 product scope, not by the after result: student-facing worksheet pages, clearly numbered/lettered prompts, no teacher/answer-key section, and no primary dependence on free-form tables, diagrams, matching, `Step` procedures, or OCR. That yields PDFs **02, 04, 05, 13, and 17**.

| PDF | Expected | After | Launch result |
|---|---:|---|---|
| 02 mixed numbering | 12 | 10; labels `3a,3b,4,5,6,7a,7b,8,9,10` | **FAIL**: compound labels/pages are fixed, but tasks 1 and 2 are missed. |
| 04 data table | 3 | 3; labels `1,2,3` | **PASS after review**: text/pages are faithful; Q2's off-page work instruction has no invented region. |
| 05 image questions | 4 | 0, `unsupported_layout` | **FAIL**: honest rejection, but a clearly numbered in-scope worksheet is not detected. |
| 13 history layout | 25 | 22 | **FAIL**: false 10/19/28/29 are removed, but questions 5, 6, and 8 are also missed. |
| 17 map questions | 6 | 6; labels `1` through `6` | **PASS after review**: all prompts/pages are correct; four explicit spaces are retained and two uncertain spaces are suppressed. |

**Launch-subset pass rate: 2/5 (40.0%).** This is not launch-ready and is far below the 90% freeze rule.

## Per-PDF evidence

`IDs` below are stable internal IDs. `Labels` retain the source identity visible to the student. “Honest reject” is a safety pass, not a successful parse.

| PDF | Baseline -> after | After labels / regions | Visual evidence and disposition |
|---|---|---|---|
| 01 dense single page | 0.108 s, fallback + ID 0 -> 0.035 s, `unsupported_layout`, 0 | none / 0 | Robot-selection table remains outside clearly labeled v1 scope. **HONEST REJECT**; no silent document-wide fallback. |
| 02 mixed numbering | 0.236 s, `ok`, 12 duplicate IDs -> 0.261 s, `layout_review_required`, 10 IDs `1..10` | `3a,3b,4,5,6,7a,7b,8,9,10` / 8 | Compound labels and page attribution are correct. Visible tasks 1 and 2 are still missed; Q4 and Q9 have no invented region. **FAIL** detection, safely gated. |
| 03 scan table | 0.007 s, `empty_extraction` + ID 0 -> 0.004 s, `requires_ocr`, 0 | none / 0 | Visible three-column scan has no text layer. **PASS** honest OCR handling. |
| 04 data table | 0.800 s, `ok`, 3 -> 0.449 s, `layout_review_required`, 3 IDs `1..3` | `1,2,3` / 2 | All prompts remain on page 3; U+0007 prefixes are gone. Q1 and Q3 regions match visible spaces; Q2 directs work to a dry-erase board/chart paper and is suppressed. **PASS after review**. |
| 05 image questions | 0.039 s, `ok`, 4 -> 0.042 s, `unsupported_layout`, 0 | none / 0 | The prior merged Q4/Reading Extension region is gone, but the four numbered questions are not detected. Title still begins with a corrupt glyph. **FAIL** in-scope detection, honest status. |
| 06 diagram table | 0.104 s, fallback + ID 0 -> 0.096 s, `unsupported_layout`, 0 | none / 0 | Driving-question/diagram-key task is not clearly numbered. **HONEST REJECT** for v1; no fallback or generic strip. |
| 07 five-page packet | 0.208 s, `ok`, 27 -> 0.116 s, `unsupported_layout`, 0 | none / 0 | URLs, headings, and source-list items are no longer questions. Mixed packet is not confidently classified as a student worksheet. **HONEST REJECT**. |
| 08 engineering forms | 0.120 s, `ok`, 5 including four ID 0 records -> 0.069 s, `unsupported_layout`, 0 | none / 0 | Numeric table rows and blank form lines are no longer questions. Forms are outside clearly labeled v1 scope. **HONEST REJECT**. |
| 09 complex science packet | 0.839 s, `ok`, 88 -> 0.523 s, `layout_review_required`, 19 IDs `1..19` | `2,3,1,4,5,1,2,3,4,5,6,4,8,10,4,1,2,3,25` / 0 | Scientific notation/table values are removed, and no answer strips are invented. Some procedure entries remain while true prompts are missing. **FAIL/REVIEW**; cannot write. |
| 10 scan matching | 0.009 s, `empty_extraction` + ID 0 -> 0.006 s, `requires_ocr`, 0 | none / 0 | Visible graph/checkbox matching page has no text layer. **PASS** honest OCR handling. |
| 11 image-heavy packet | 1.423 s, `ok`, 12 -> 0.854 s, `layout_review_required`, 4 IDs `1..4` | `1,2,4,7` / 3 | Teacher/reference pages are excluded. Student pages are correctly attributed, but questions 3, 5, and 6 are missed. **FAIL/REVIEW**. |
| 12 long mixed packet | 15.005 s, `ok`, 58 -> 7.603 s, `layout_review_required`, 33 IDs `1..33` | repeated worksheet labels / 11 | Most early teacher pages are excluded, but an educator discussion item and answer-key/student duplicate sequences remain visible in overlays. **FAIL/REVIEW**; repeated/nonsequential labels and mixed packet are surfaced. |
| 13 history layout | 0.083 s, `ok`, 29 -> 0.137 s, `layout_review_required`, 22 IDs `1..22` | `1,2,3,4,7,9,11..18,20..27` / 0 | Obvious “Include a picture”/“Your sources” false entries 10, 19, 28, 29 are removed. Expected 5, 6, and 8 are also absent. **FAIL/REVIEW**; no generic regions. |
| 14 math word problems | 0.584 s, `ok`, 13 -> 0.316 s, `layout_review_required`, 2 IDs `1..2` | `4,3` / 2 | Most procedure steps are removed. The remaining labels are nonsequential and only 2/7 expected tasks are found; visible regions stay on their pages. **FAIL/REVIEW**. |
| 15 calculation tables | 2.003 s, `ok`, 10 -> 1.214 s, `unsupported_layout`, 0 | none / 0 | Values 452 and 577 are no longer question IDs. The table/form layout is outside v1. **HONEST REJECT**. |
| 16 unusual numbering | 0.017 s, fallback + ID 0 -> 0.011 s, `unsupported_layout`, 0 | none / 0 | Step One-Four procedure text no longer becomes a full-page fallback question. `Step` labels are outside clearly labeled v1 question scope. **HONEST REJECT**. |
| 17 map questions | 0.369 s, `ok`, 6 -> 0.271 s, `layout_review_required`, 6 IDs `1..6` | `1,2,3,4,5,6` / 4 | All six prompts are faithful and page-correct. Four blue regions cover visible blank response areas; two uncertain regions are suppressed. **PASS after review**. |
| 18 scan numbered questions | 0.007 s, `empty_extraction` + ID 0 -> 0.004 s, `requires_ocr`, 0 | none / 0 | Four questions are visible but image-only. **PASS** honest OCR handling. |
| 19 ten-page packet | 0.109 s, `ok`, 5 false standards -> 0.065 s, `unsupported_layout`, 0 | none / 0 | Virginia standards and teacher answers are no longer questions. The mixed unnumbered student packet is outside v1. **HONEST REJECT**. |
| 20 form tables | 0.127 s, `ok`, 2 with cross-page regions -> 0.091 s, `unsupported_layout`, 0 | none / 0 | Table-completion prompts no longer receive page-1 strips for tables on pages 2/3. Business-style forms are outside v1. **HONEST REJECT**. |

## Failure clusters after correction

| Rank | Remaining root cause | Frequency | Evidence / impact |
|---:|---|---:|---|
| 1 | Student-page/section classification is still too strict or incomplete | 6 selectable PDFs (02, 05, 11, 13, 14, 17 have missed prompts) | Causes incomplete question sets even when the document is otherwise within or near v1 scope. |
| 2 | Mixed packet boundaries remain imperfect | 3 PDFs (09, 11, 12) | Some procedures/answer-key items remain or student items are missed. All three are review-gated, so the error is visible rather than silently accepted. |
| 3 | Explicit answer-space recognition has incomplete coverage | 7 of 8 PDFs with detected questions | `unresolved_answer_regions` is surfaced; uncertain regions are suppressed. This blocks automatic readiness but prevents wrong-page/generic writing. |
| 4 | Title selection/text glyph cleanup remains incomplete | 2 PDFs (05, 17) | 05 retains an initial corrupt glyph; 17 selects a report footer/header rather than the worksheet title. Question safety is unaffected. |

The broad false-positive clusters from the baseline are substantially reduced: numeric-only/table values, URLs, scientific notation, educator headings, answer keys, and fallback question ID 0 no longer silently become writable questions. Remaining errors cluster around page/section classification and conservative answer-space recognition.

## Implementation summary

- Parsing is now page-scoped and limited to classified student worksheet sections.
- Compound source labels are preserved (`3a`, `3b`, `7a`, `7b`) while API/storage IDs remain sequential and unique across pages.
- Numeric values, scientific notation, URLs, and obvious procedure/list entries are rejected as labels.
- Scans/textless files return `requires_ocr`; unsupported files return `unsupported_layout`; neither creates a fallback question.
- Low-confidence answer regions are omitted. Mixed, nonsequential, repeated-label, or unresolved layouts return `layout_review_required` and mark questions for review.
- UI and API writing paths refuse unresolved/absent regions until the client supplies explicit layout confirmation and a validated region.

## Verification

- Characterization before behavior changes: **7/7 failed as expected**.
- Targeted regression file after changes: **7/7 passed**.
- Full Python suite: **161 passed**.
- Frontend session/state/contract checks: **all passed** (17 session-rule cases plus UI-state and contract validation).
- Ruff: **all checks passed**.
- Corpus rerun: **20/20 PDFs processed; 109/109 pages rendered and visually inspected**.
- No deployment command was run.

## Recommendation and remaining uncertainty

**Continue targeted fixes; do not deploy.** Prioritize student-section recognition for 02/05/11/13, then explicit answer-space detection for otherwise correct prompts. Re-run this exact corpus and keep the launch-subset expected counts fixed. Reconsider the extraction architecture only if those focused changes fail across unrelated document patterns; current failures remain clustered enough that an architecture replacement is not yet justified.

The corpus has no gold per-question annotation file, so expected counts remain the manual visual baseline from `docs/pdf-acceptance-report.md`. The student-only subset and its expected counts were not weakened to improve the after metrics. Temporary overlay evidence is not a durable CI artifact and may be removed by operating-system cleanup.
