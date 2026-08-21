# Contract corpus triage

The first expanded-corpus pass produced three review findings. Each was
resolved against the unchanged `sequential-short-answer-v1` boundary.

| Fixture | Initial observation | Disposition | Resolution |
| --- | --- | --- | --- |
| `supported-local-gaps-8` | Two answer-line interiors reached into the next prompt interval. | Fixture expectation error | Moved the eight questions across two pages so every varied gap remains local and ends before the next prompt. No parser rule changed. |
| `rejected-competing-spaces` | Only one drawn line qualified as deterministic response evidence, so the document had one valid destination. | Fixture expectation error | Replaced the drawing with two visible form fields that create genuine competing writable spaces. No parser rule changed. |
| `rejected-semantic-promotion` | A fabricated response ID escaped as `KeyError` instead of a controlled rejection. | In-contract parser defect | Validate selected IDs before lookup, route the existing materialization failure path, and retain the source-backed region as unclaimed evidence. Added a focused regression test. |

The final report has no decision disagreements, no supported-fixture
rejections, and no unsafe acceptances. Rejected fixtures retain their individual
stable reason-code lists in `generated/report.json`.
