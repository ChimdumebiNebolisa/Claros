---
name: Browser speech verification
description: Separate speech-control tests from verification of actual audible and live AI replies.
---

Headless Chromium may expose browser speech synthesis while providing no installed speech voices. Successful speech-event tests are not evidence of audible playback.

**Why:** The workspace's system Chromium had no available voices during the homepage demo check, despite exposing the speech API.

**How to apply:** Verify the no-voice explanation and typed route in the real test browser. Use controlled speech events to test playback controls, timers, cancellation, and reset. Keep that verification distinct from listening to audio in a browser with an available voice.

For the real conversational demo, mocked WebRTC events verify transcript handling, permission errors, and cleanup—not an upstream AI conversation or audible replies.

**Why:** The user explicitly rejected fixed sample playback and asked for a real spoken back-and-forth.

**How to apply:** Never describe fixture-based conversation tests as verification of live AI speech. Verify the provider connection and actual reply audio separately; explain any credential or browser-audio limitation plainly.