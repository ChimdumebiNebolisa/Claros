# worksheet_contract_v1

This suite exercises the production acceptance boundary on the three
first-party canonical PDFs. The short-answer worksheet must be accepted; the
choice worksheet and multi-region numeric worksheet must be rejected. The
report records decision agreement and treats any accepted unsupported document
as an unsafe acceptance.

The semantic selector is deterministic and may select only geometry already
extracted from each PDF. It is evaluation scaffolding, not a production parser
shortcut and not a human-labeled reference set.

Run from the repository root:

```powershell
python -m evaluation.worksheet_contract_v1.evaluate
```
