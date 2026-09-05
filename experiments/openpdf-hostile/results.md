# OpenPDF hostile-PDF results

## Decision

**Recommendation: B — OpenPDF looks promising, but requires more testing before replacing the current engine.**

OpenPDF 3.0.5 preserved every machine-checked source property and hit every physical-coordinate probe in this synthetic corpus when structurally sound files were stamped incrementally. It is not yet safe enough for Claros's production export contract because one ordinary Latin string rendered visibly but failed exact extraction (`office` became `ofce` in both PDFBox and PDF.js), RTL correctness remains only partially established, and damaged PDFs require a materially different full-rewrite path. No production integration was made.

## Run context

- Evidence generated: 2026-09-05T21:16:07Z.
- Checkout: `codex/claros-v2-nerdy` at `0a674d6a40f20cb02efbc2773f2378e3b7676b8b`.
- Main baseline inspected read-only: `origin/main` at `5fb217715e4b3278f21a882b2652d928f2cca628` (2026-08-23).
- OpenPDF 3.0.5, Apache PDFBox 3.0.8, qpdf 12.3.2, PDF.js 4.8.69, Playwright 1.58.2, Microsoft OpenJDK 21.0.10, Windows 11 amd64.
- 33 source PDFs, 122 source pages, 33 derivatives, and 125 derivative pages.
- 176,639 source bytes and 626,164 derivative bytes in this synthetic run.
- 32 inputs used incremental stamping. The malformed-xref input was visibly classified and processed through the full-rewrite fallback.

The complete machine-readable evidence is generated at `target/evidence/results.json`; its condensed table is `target/evidence/results-table.md`.

## Findings by core question

1. **Preserve the original document:** PASS for all 33 cases within the properties measured. Source SHA-256 values were unchanged. Source page boxes, rotations, UserUnit, text runs, annotations, links, AcroForm values, outlines, metadata, XMP, encryption permissions, raster images, and embedded font programs were retained. Every source-page raster comparison reported zero pixels changed outside approved overlay masks.
2. **Place at exact approved physical coordinates:** PASS for all 33 cases. Magenta coordinate markers were independently observed within 1.75 physical points of the requested crop-relative top-left point at 288 DPI. Forward/inverse transforms cover 0/90/180/270 degrees, offset CropBoxes, and `/UserUnit 2`.
3. **Handle rotation and page boxes:** PASS for 90/180/270-degree pages, mixed rotations, offset CropBox, distinct TrimBox/BleedBox, mixed page sizes, and non-default UserUnit. Representative Poppler renders showed upright overlays in physical display space.
4. **Embed/render Unicode safely:** PASS for accented Latin, curly punctuation, Greek/math, CJK, Hebrew logical extraction, and a monochrome emoji probe. PARTIAL for Arabic and Hebrew overall because linguistic shaping order was not machine-proven. PDF.js returned Arabic presentation-form characters rather than the exact logical string. FAIL for exact extraction of the Latin word `office`: both PDFBox and PDF.js recovered `ofce` even though the page rendered visibly as `office`.
5. **Append continuation pages:** PASS. The one-page source remained page 1 and OpenPDF appended three numbered Letter pages. Independent extraction recovered the worksheet title, source page number, stable question ID, exact source question, and the complete long approved answer in order.
6. **Reopen and validate:** PASS for all 33 derivatives in OpenPDF, qpdf, PDFBox, and PDF.js canvas rendering. PDF.js rendered all 125 derivative pages. The encrypted derivative reopened with the known user password and retained the source AES-128 permission signature.
7. **Detect unrelated change or disappearance:** No checked source loss was observed. The metadata fixture retained an identical information dictionary and identical XMP SHA-256. Existing images and embedded font streams retained their decoded-content hashes. This is strong evidence for the covered objects, not proof for every object type allowed by the PDF specification.

## Unsafe, failed, or partial cases

- `office-style` is FAIL. The overlay is visible and correctly placed, but two independent extractors recover `CLAROS ofce overlay`. That violates Claros's exact-Unicode output requirement even though qpdf and render validation pass.
- `arabic-rtl` is PARTIAL. PDFBox recovered the logical string and the page rendered, but PDF.js exposed Arabic presentation forms and exact logical-string comparison failed. Shaping correctness needs expert-reviewed golden images and extraction policy.
- `hebrew-rtl` is PARTIAL. PDFBox and PDF.js recovered the logical string and the page rendered, but shaping/order has not been certified by a fluent reviewer or renderer-specific goldens.
- `malformed-readable` passed the checked output assertions only after OpenPDF rebuilt its xref and the harness used a full rewrite. One deterministic corruption is not representative of arbitrary damaged PDFs.
- Default non-incremental `PdfStamper` behavior is unsafe for preservation without additional controls: `PdfStamperMetadataModeTest` proves it changes the Producer metadata. Incremental mode retained metadata/XMP, but OpenPDF refuses that mode for a rebuilt xref.

## Maturity, maintenance, licensing, and security

OpenPDF is active and mature enough to justify further evaluation: 3.0.5 was the latest release on the test date, published May 22, 2026, and the upstream repository had commits in August 2026. The project is not archived. See the [3.0.5 release](https://github.com/LibrePDF/OpenPDF/releases/tag/3.0.5) and [upstream repository](https://github.com/LibrePDF/OpenPDF).

The core is dual-licensed `MPL-2.0 OR LGPL-2.1+`. Apache FOP is Apache-2.0 and is needed here for OpenPDF's complex-script path; Bouncy Castle's MIT-style licensed provider is needed for the encrypted fixture. Those licenses appear compatible with an internal service, but production adoption still needs the project's normal legal review and notice/source-compliance process.

The upstream [security policy](https://github.com/LibrePDF/OpenPDF/blob/3.0.5/Security.md) explicitly says OpenPDF is neither sandboxed nor hardened and does not protect against memory exhaustion or denial of service from large or malformed PDFs. A point-in-time GitHub repository-advisory query and OSV queries for OpenPDF 3.0.5, FOP 2.11, and `bcprov-jdk18on` 1.84 returned no records on 2026-09-05; that is not a guarantee of absence. Arbitrary student PDFs would require byte/page/object/decompression limits, execution deadlines, memory limits, restricted filesystem/network access, and an isolated worker before production use.

OpenPDF 3.x requires Java 21+. The harness's prospective engine stack—OpenPDF, FOP, Bouncy Castle, and their runtime dependencies, excluding PDFBox/Jackson validation—contains 33 jars totaling 20.20 MiB. OpenPDF itself is 2.12 MiB, FOP core 4.26 MiB, and Bouncy Castle 8.51 MiB. The local full JDK is 326.82 MiB; a production JRE or `jlink` image could be smaller. Claros currently exports in Python, so adoption would add a JVM worker/sidecar or require a backend rewrite, plus health checks, resource isolation, telemetry, deployment images, and cross-runtime failure handling.

## Remaining coverage gaps

The corpus does not yet prove digital-signature preservation, PDF/A or PDF/UA conformance, portfolios/attachments, optional-content groups, JavaScript/actions, rich media, color profiles, incremental-update chains with signed revisions, linearization retention, multi-gigabyte/resource-exhaustion behavior, or broad real-world producer diversity. It also has not been opened in Adobe Acrobat, macOS Preview, or mobile viewers. These are unverified, not assumed safe.

Before changing production, the next investigation should isolate the `office` extraction defect at the ToUnicode/CMap or glyph-substitution layer, add extractor round trips as a hard text gate, add linguistically reviewed RTL golden renders, expand the malformed/producer corpus, and run the engine inside the same limits intended for deployment.

## Results table

| Fixture | Open/read | Preserves source | Overlay succeeds | Coordinate correct | Unicode correct | Continuation works | qpdf validation | PDF.js reopen/render | Source losses | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| normal-letter | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| a4 | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| mixed-page-sizes | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| rotated-90 | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| rotated-180 | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| rotated-270 | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| cropbox-offset | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| trim-bleed-boxes | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| mixed-rotations | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| annotations | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| acroform | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| embedded-font | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| unicode-text | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| accented-latin | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| mathematical-symbols | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| cjk | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| arabic-rtl | PASS | PASS | PASS | PASS | PARTIAL | NOT_APPLICABLE | PASS | PASS | None observed | PARTIAL |
| hebrew-rtl | PASS | PASS | PASS | PASS | PARTIAL | NOT_APPLICABLE | PASS | PASS | None observed | PARTIAL |
| long-multiline-answer | PASS | PASS | PASS | PASS | NOT_APPLICABLE | PASS | PASS | PASS | None observed | PASS |
| existing-images | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| vector-graphics | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| transparency | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| object-stream-heavy | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| office-style | PASS | PASS | FAIL | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | FAIL |
| scanned-image-only | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| large-multipage | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| encrypted | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| malformed-readable | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| outlines | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| links | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| metadata | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| user-unit-2 | PASS | PASS | PASS | PASS | NOT_APPLICABLE | NOT_APPLICABLE | PASS | PASS | None observed | PASS |
| emoji | PASS | PASS | PASS | PASS | PASS | NOT_APPLICABLE | PASS | PASS | None observed | PASS |

Overall: 30 PASS, 2 PARTIAL, and 1 FAIL. All 33 preservation, coordinate, qpdf, and PDF.js reopen/render checks passed; exact overlay extraction passed 32 of 33 cases.

## Commands and actual results

- `experiments/openpdf-hostile/scripts/run.ps1` — exit 0. Maven reported 5 tests, 0 failures; the corpus run emitted 33 derivatives; PDF.js rendered 33/33 derivatives; qpdf derivative validation passed 33/33.
- `.venv/Scripts/python.exe -m pytest backend/tests/document backend/tests/domain/test_export_workflow.py` — exit 0, 120 passed, 22 existing pypdf deprecation warnings in 17.55 seconds.
- `mvn dependency:tree` and `mvn dependency:copy-dependencies -DincludeScope=runtime -DoutputDirectory=target/runtime-deps` — exit 0; used for the deployment-size measurements above.
