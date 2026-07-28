# Stage 1 test rationalization

This ledger records the tests retired while removing the inactive OpenAI and
model-written-answer runtime paths. It is scoped to Stage 1; Stage 10 will
maintain the broader product-risk inventory.

| Removed test coverage | Product risk it covered | Retained active coverage | Why the replacement is at least as strong for the active system |
| --- | --- | --- | --- |
| `tests/test_openai_semantic_compiler.py` | An OpenAI adapter could send the wrong extracted evidence or materialize untrusted model output. | `tests/test_document_pipeline.py::test_gemini_semantic_tasks_reconstruct_prompt_text_from_selected_source_blocks` and `::test_invalid_semantic_output_is_rejected_without_tasks_or_content_logs` | The OpenAI adapter no longer ships or has a production import path. The active Gemini boundary now proves that model-authored prompt text is discarded in favor of selected physical source blocks and that invalid evidence is rejected without content logging. |
| Legacy `gemini_service` streaming/write-prompt tests | A confirmed answer might be reformatted by a model or changed while being streamed. | `tests/test_gemini_service.py::test_stamp_confirmed_answer_preserves_every_character` and `tests/test_write_api.py` exact-answer and single-use-token cases | The write route no longer invokes a model. The retained tests exercise the active exact-byte stamping path and the endpoint authorization contract, including case, whitespace, and Unicode distinctions. |
| Legacy write-payload tests that supplied conversation history to a model write request | Untrusted conversation/context could influence the finalized answer. | `tests/test_write_invariant_characterization.py` endpoint contract cases and `tests/test_write_api.py` | The active route has no conversation or model-write input. Endpoint tests establish that only a server-confirmed answer with a valid, answer-bound write token can be written. |
