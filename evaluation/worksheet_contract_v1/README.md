# worksheet_contract_v1

This suite exercises the production acceptance boundary on 29 deterministic,
first-party PDFs generated from the reviewable definitions in `fixtures.py`.
Ten worksheets cover realistic variation inside the sequential short-answer
contract. Nineteen ambiguous or unsupported worksheets exercise fail-closed
behavior, including red-team attempts to redirect or invent write evidence.

`baseline-v1.json` preserves the original three-canonical-document result from
`main` before this expansion. The canonical choice and multi-region math PDFs
remain available in `evaluation/canonical_v1` as rejection evidence; they are
not official product samples.

The semantic selector is deterministic and normally may select only IDs already
extracted from each PDF. One deliberate semantic-promotion fixture supplies a
fabricated ID and must receive a controlled whole-document rejection. The
selector is evaluation scaffolding, not a production parser shortcut and not a
human-labeled reference set.

The stable v2 report includes document decision agreement, supported acceptance,
unsupported rejection, unsafe acceptance, question count/order, response-region
detection, question-to-response association, response type, and rejection
reason counts. Labels are AI-adjudicated silver.

Run from the repository root:

```powershell
python -m evaluation.worksheet_contract_v1.evaluate
```

The command writes stable `generated/manifest.json` and
`generated/report.json` files. It performs no provider or network calls.
