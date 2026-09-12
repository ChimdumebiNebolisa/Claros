# Gate 5 live Realtime acceptance

- Date: 2026-09-11
- Branch: `codex/claros-v2-nerdy`
- Implementation checkpoint: `22b3d602d5b02711d0997af4fe18ce8945484cf5`
- Realtime model: `gpt-realtime-2.1`
- Semantic model configuration: `gpt-5.6-luna`
- Corpus: checked-in synthetic biology sample only
- Status: partial pass; task 5.7 remains open

No API key, ephemeral credential, owner identifier, assignment identifier, or
raw provider payload is recorded in this report. Credential presence was
checked as a boolean only. The local key remains in the ignored server-side
`.env` file and was absent from tracked files and the production bundle.

## Live results

| Check | Result | Evidence |
| --- | --- | --- |
| Server credential issuance | Pass | A live credential was issued after owner/question/mode/version validation. The provider accepted the 64-character privacy-safe identifier. |
| Guided typed turn over WebRTC | Pass | The live model returned context-specific responses not present in the fake adapter; the full final response appeared identically in the guided conversation and live caption region. |
| Text-only WebRTC transport | Pass | A locally owned silent audio track satisfied the SDK WebRTC transport without requesting microphone permission, and teardown owns track/context cleanup. |
| Mute/unmute | Pass | The visible control toggled between `Mute spoken output` and `Unmute spoken output` during a live session. |
| Interrupt | Pass | `Interrupt Claros` appeared during live streamed output; activation moved the UI to `Interrupted` and preserved the student turn. A subsequent guided turn completed normally. |
| Recoverable reconnect | Pass | With the local credential server intentionally unavailable, the UI showed `Connection lost` and preserved the draft. After server recovery, `Retry voice` obtained a fresh credential and returned to `Ready`. |
| Direct microphone connection and stop | Pass | The live direct path reached `Listening`; `Stop listening` returned it to `Ready` without losing the editor. |
| Cross-question captions | Pass | Moving from Question 2 to Question 3 showed the empty caption placeholder rather than the prior question's transcript. |
| Direct spoken transcript/candidate | **Not yet verified** | The browser environment did not route either system speech or a temporary synthetic WAV into its microphone input. The temporary fixture was deleted. No direct transcript was claimed. |
| Spoken exact-confirmation phrase | **Not yet verified** | Button confirmation and fake-adapter phrase authority pass, but a live microphone transcription of `Use this exact answer` still needs one human-spoken run. |

## Defects found and fixed during the live run

1. Realtime credential issuance failed because the hashed safety identifier was
   71 characters; OpenAI permits 64. The identifier is now a prefixed,
   truncated SHA-256 value of exactly 64 characters.
2. Text-only sessions passed an empty `MediaStream`, while the pinned SDK
   requires an audio track. They now use a zero-gain, app-owned Web Audio track
   with explicit cleanup.
3. Stopping direct capture left the state at `Listening`. The adapter now emits
   `Ready`, and both state-machine paths accept that transition.
4. WebRTC audio handled by the browser does not emit SDK audio buffers. Visible
   `Speaking` state now begins from live transcript/audio deltas, enabling the
   interrupt control.
5. Provider output can contain multiple transcript parts. Parts are accumulated
   and finalized on the SDK `agent_end` event; interrupted partial output is not
   promoted to a completed Claros turn.
6. Development navigation dropped `?runtime=api` and could silently fall back
   to fixtures. API-mode routes now preserve the query while ordinary fixture
   route tests remain fixture-backed.
7. Captions from one question remained visible on the next. Caption state is
   now question-scoped.

## Automated verification

| Command | Result |
| --- | --- |
| `npm test` | Pass — 89/89 |
| `python -m pytest backend/tests -q` with explicit test engines | Pass — 525 passed, 16 expected qpdf skips |
| `npx playwright test tests/e2e/gate2-workspace.spec.ts --workers=1` | Pass — 15/15 |
| `npm run typecheck` | Pass |
| `npm run lint` | Pass |
| `npm run format` | Pass |
| `npm run build` | Pass; accepted pinned EmbedPDF warnings only |
| `npm run check:dependencies` | Pass |
| `npm run check:bundles` | Pass; fake Realtime adapter absent from production |
| `python -m ruff check backend` | Pass |
| `openspec validate claros-reconstruction --strict` | Pass |
| tracked and production-bundle secret scans | Pass — 0 matches |
| `npm audit --omit=dev --audit-level=high` | Pass — 0 production vulnerabilities |

The full npm audit currently reports two high-severity development-tooling
findings in the Redocly `js-yaml` dependency chain. They are not shipped in the
production dependency set. Gate 6 must resolve or formally disposition them.

## Remaining acceptance action

Run one human-spoken direct answer through live transcription/candidate capture,
then enter exact review and speak the canonical phrase exactly once. After that
passes, task 5.7 can close and task 5.8 can begin independent review.
