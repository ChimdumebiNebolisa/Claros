# Build Week roadmap

This is the current execution order. The full acceptance criteria and detailed
implementation instructions live in `BUILD_WEEK_EXECUTION_PLAN.md`.

1. Preserve the worktree and establish provenance -> verify branch, inventory,
   ignore policy, and intentional commits.
2. Repair assignment-scoped reset, capability authorization, export bypass,
   production HMAC policy, retention documentation, abuse controls, and export
   overflow -> verify focused API/frontend/PDF regression tests.
3. Establish one canonical physical IR, parser orchestration, review model, and
   exporter -> verify migration and unit tests on one pilot page first.
4. Create and freeze the 17-page AI-adjudicated silver benchmark -> verify all
   labels, hashes, schemas, prompts, and freeze behavior without committing
   external PDFs.
5. Add the provider-neutral GPT-5.6 closed-world compiler -> verify unknown IDs,
   text invention, parent graph, candidate safety, safe fallback, cost, and
   silver-relative comparison.
6. Replace regex tutoring decisions with structured GPT-5.6 decisions while
   retaining deterministic confirmation -> verify scripted adversarial cases.
7. Migrate voice only after the compiler path is stable -> verify provider
   mocks and three live OpenAI Realtime sessions before removing Gemini.
8. Run browser, security, PDF, accessibility, benchmark, and provider suites ->
   verify repeatability and visual exports.
9. Align deployment only to the verified provider path -> verify Docker/CI and
   record production checks separately from local tests.
10. Reconcile public documentation and prepare the Build Week/Era submission ->
    verify every claim links to evidence.

MVP cut line: phases 1-5, an AI-adjudicated silver evaluation of the
17-page pilot, and an honest demo of the strongest verified path. If Realtime
is not stable, do not claim a completed voice migration.
