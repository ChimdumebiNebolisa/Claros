# Claros synthetic hero worksheet

`hero_worksheet.pdf` is an original synthetic fixture; it does not distribute
the external `pdf02-p02` source page. It preserves the demo's relevant
structure: a compound prompt, two safe answer lines, mixed instructions, and
an intentionally uncertain drawing task that routes to the side panel.

`hero_compiler_result.json` is a deterministic synthetic fixture, not a fresh
or historical GPT-5.6 response. `hero_fixture.py` hash-binds it to the PDF and
always runs the same closed-world validator/materializer before use.
