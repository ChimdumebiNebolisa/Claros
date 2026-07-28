# Revamp Stage 9 verification

## Scope and provenance

- Base SHA: `2c98193` (`Merge pull request #27` — Stage 8 on `main`).
- Working branch: `codex/stage9-gemini-voice`.
- Scope: Gemini Live transport isolation, structured product events, reconnect,
  interrupt signal, capture speaker-leak fix, and typed fallback after voice
  failure. Confirm/write/export authority stays server-owned. No Stage 10 test
  suite purge and no Cloud Run changes.
- Contributor evidence: Stage 9 audit, independent red-team after
  implementation, frontend contract checks, product-bridge unit tests.

## Architecture changes

| Area | Change |
| --- | --- |
| Transport | `frontend/voice-live-transport.js` owns capture, PCM encode, playback, keepalive, provider close, and `activityEnd` interrupt. |
| Product bridge | `frontend/voice-product-bridge.js` maps user/Claros transcripts to structured events only. |
| Write intent | No longer proposes the full utterance when no draft exists; emits `needs_answer_before_write`. |
| Claros phrase | “Let me write that for question N” selects the task and shows write-ready notice; never auto-writes. |
| Reconnect | Up to 2 automatic reconnects with fresh `session-config` token; durable session/response state untouched. Generation-bound callbacks ignore stale close/error. |
| Disconnect UX | Unexpected close/error falls back to typed interaction after reconnect budget is exhausted; mic tracks released on final fallback. |
| Capture | Mic processor feeds a silent gain node (no speaker monitor path). |
| Confirmed protection | Voice `answer_proposed` does not clear an already confirmed answer/write token. |

## Verified evidence

| Check | Result |
| --- | --- |
| Frontend contract | `python scripts/validate_frontend.py` |
| Product-bridge tests | `npm run test:voice-bridge` |
| Frontend suite | `npm run test:frontend` |
| Integration module routes | `tests/test_main_integration.py` voice module markers |

Live Gemini provider verification is not claimed without a live token/run in this stage.

## Independent review / red-team findings

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| S9-P0-1 | P0 | Transport and product side effects were mixed in `app.js`. | Fixed: transport + product-bridge modules. |
| S9-P0-2 | P0 | Write intent could propose the entire utterance as draft. | Fixed: `needs_answer_before_write` / draft-only proposal. |
| S9-P0-3 | P0 | No reconnect; unexpected close left students without typed fallback banner. | Fixed: reconnect budget + typed fallback. |
| S9-RT-01 | P0 | Stale onclose/onerror could tear down a newer live session. | Fixed: generation + session identity gates. |
| S9-RT-02 | P0 | Voice answer proposals could clear confirmed/writeToken. | Fixed: ignore answer_proposed when confirmed. |
| S9-P1-1 | P1 | Interrupt was local playback only. | Fixed: `activityEnd` + suppress follow-on audio until turnComplete. |
| S9-P1-2 | P1 | Capture monitored into `audioContext.destination`. | Fixed: silent gain path. |
| S9-RT-04/05 | P1 | Intentional stop fallback / double reconnect scheduling. | Fixed: intentional stop short-circuit + reconnect in-flight lock. |
| S9-RT-06 | P1 | Confirmed+live disabled End session. | Fixed: End session remains enabled while live. |
| S9-P2-1 | P2 | `ScriptProcessorNode` remains (AudioWorklet deferred). | Accepted; owned by later audio hardening / Stage 12 if needed. |
| S9-P2-2 | P2 | Live provider E2E still manual. | Owned by Stage 14. |

No remaining valid P0/P1 findings for Stage 9 acceptance after the red-team remediation pass.

## Deployment limitation

No production Cloud Run settings, secrets, or deploy triggers are changed by
Stage 9.
