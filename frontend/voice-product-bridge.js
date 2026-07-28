/**
 * Maps Gemini Live transcripts to structured Claros product events.
 * Transport-agnostic: no sockets, audio, or DOM. Browser + Node tests.
 */
'use strict';

(function (root) {
  function getRules() {
    if (typeof ClarosSessionRules !== 'undefined') return ClarosSessionRules;
    if (typeof module !== 'undefined' && module.exports) {
      try {
        return require('./session-rules.js');
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  function interpretUserTurn(rawText, context) {
    const Rules = getRules();
    if (!Rules) return [];
    context = context || {};
    const full = rawText == null ? '' : String(rawText).trim();
    if (!full) return [];
    const normalized = Rules.normalizeTranscript(full);
    const events = [];
    const questionNum = Rules.parseQuestionNum(normalized);
    if (questionNum != null) {
      events.push({ type: 'task_selected', legacyQuestionId: questionNum });
    }

    if (Rules.ANSWER_STATED_RE.test(normalized)) {
      const extracted = Rules.extractDraftAnswer(normalized);
      events.push({
        type: 'answer_proposed',
        text: extracted || full,
        source: 'answer_stated',
      });
    }

    if (Rules.WRITE_INTENT_RE.test(normalized)) {
      if (context.confirmed && context.writeToken) {
        events.push({ type: 'write_ready_notice', source: 'user_write_intent' });
      } else {
        const draft = (context.draft || '').trim();
        const extracted = Rules.extractDraftAnswer(normalized);
        const text = draft || extracted;
        if (text) {
          events.push({
            type: 'answer_proposed',
            text: text,
            source: 'write_intent',
          });
        } else {
          events.push({
            type: 'needs_answer_before_write',
            source: 'write_intent',
          });
        }
      }
    }

    if (Rules.hasExportIntent(normalized)) {
      events.push({ type: 'export_requested', normalized: normalized });
    }
    return events;
  }

  function interpretClarosTurn(rawText) {
    const Rules = getRules();
    if (!Rules) return [];
    const text = rawText == null ? '' : String(rawText).trim();
    if (!text) return [];
    const questionNum = Rules.parseClarosWriteQuestionNum(text);
    if (questionNum == null) return [];
    return [
      { type: 'task_selected', legacyQuestionId: questionNum, source: 'claros_write_phrase' },
      { type: 'write_ready_notice', source: 'claros_write_phrase' },
    ];
  }

  const ClarosVoiceProductBridge = {
    interpretUserTurn: interpretUserTurn,
    interpretClarosTurn: interpretClarosTurn,
  };

  root.ClarosVoiceProductBridge = ClarosVoiceProductBridge;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = ClarosVoiceProductBridge;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
