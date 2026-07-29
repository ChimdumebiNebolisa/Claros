# Claros closed-world PDF gold pilot

## Historical stress-pilot status

This preserved 17-page package is a broad later-stage stress pilot, not the
initial parser milestone or its critical path. Its historical directory name
does not imply that human or otherwise validated gold labels exist. The
controlled first-party milestone is `evaluation/canonical_v1`.

This directory is an offline evaluation package. Nothing here is imported by the Claros upload, assignment, answer-confirmation, PDF-writing, or export paths. Production parser mode is configured separately (`PDF_PARSER_MODE` defaults to `hybrid` in current Claros); this package does not define runtime defaults.

## Current stopping point

The selected corpus has no human task-level gold export. The existing benchmark saved rendered Paddle/Gemini overlays and document summaries, but not reusable raw Paddle blocks or free-form per-page task geometry. The builder therefore creates native/PDF-geometry suggestions where machine-readable data exists and leaves scan pages without fabricated block preannotations. It never treats overlay pixels or Gemini output as truth.

## Build the annotation package

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m evaluation.pdf_gold_pilot.build_annotation_project
```

Generated assets are written to `output/pdf-gold-pilot`:

- `rendered`: clean 144-DPI page images.
- `physical-overlays`: native/PDF-geometry suggestions and response candidates.
- `physical-inputs.json`: closed-world input contract.
- `label-studio-tasks.json`: Label Studio import with suggestions in `predictions`, not `annotations`.
- `baselines.json`: fresh legacy page tasks plus references to stored free-form overlays.
- `status.json`: gold/cache/tool availability and scoring gate.

If a structured Paddle cache is later exported, pass `--paddle-cache PATH`. Its format is:

```json
{
  "pages": [
    {
      "source_pdf": "18_scan_numbered_questions.pdf",
      "page_number": 1,
      "blocks": ["DocumentBlock JSON objects whose source is paddleocr"]
    }
  ]
}
```

The builder does not rerun PaddleOCR and does not install it.

## Label Studio setup

Label Studio is intentionally not a Claros dependency. In a separate virtual environment outside the production image:

```powershell
py -3.11 -m venv C:\Users\Chimdumebi\label-studio-claros-pilot
& C:\Users\Chimdumebi\label-studio-claros-pilot\Scripts\Activate.ps1
python -m pip install label-studio
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED='true'
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT='C:\Users\Chimdumebi\Claros\output\pdf-gold-pilot'
label-studio start --data-dir C:\Users\Chimdumebi\label-studio-claros-pilot-data
```

Create a project, paste `output/pdf-gold-pilot/label_studio_config.xml` into the labeling interface, then import `output/pdf-gold-pilot/label-studio-tasks.json`. Follow `annotation-protocol.md`. Export completed annotations as JSON to `output/pdf-gold-pilot/gold/annotations.json` without editing the suggestion file.

Double-annotate at least four pages. If only one annotator is available, record that limitation and do not describe the export as validated gold.

## Closed-world experiment gate

`run_closed_world.py` refuses network execution unless a non-empty human export exists, the isolated `CLAROS_PDF_GOLD_PILOT=1` flag is set, and `--execute` is supplied. A validation-only run does not call Gemini:

```powershell
.\.venv\Scripts\python.exe -m evaluation.pdf_gold_pilot.run_closed_world --validate-only
```

After gold and a complete physical cache exist:

```powershell
$env:CLAROS_PDF_GOLD_PILOT='1'
.\.venv\Scripts\python.exe -m evaluation.pdf_gold_pilot.run_closed_world `
  --execute `
  --gold output\pdf-gold-pilot\gold\annotations.json
```

Before scoring the three-way comparison, also retain a structured rerun of the existing free-form classifier; the stored overlays alone cannot support task/block matching. The matching and metric definitions are in `evaluation-protocol.md`.
