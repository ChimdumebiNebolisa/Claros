# PDF silver benchmark

This directory holds only structured, AI-adjudicated silver labels and their
hashes. It is not human gold, ground truth, expert-verified data, or a measure
of correctness.

Each frozen page needs a stable `page_id`, a `source_sha256`, and an
AI-adjudicated closed-world label. Keep source PDFs, page renders, raw provider
payloads, and document text out of version control unless rights and privacy
are explicitly confirmed. The freeze hash detects any post-freeze changes.

Before a live evaluation run, record the adjudicator/model, prompt version,
schema version, validation output, abstentions, validator catches, and cost in
the run evidence. Report agreement and unsafe-placement rates only as
silver-relative/provisional measures.
