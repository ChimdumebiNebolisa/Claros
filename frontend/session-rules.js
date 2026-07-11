/**
 * Pure string helpers for voice/write/export intent (browser + Node tests).
 * Loaded in app.html before the main app script; also require()'d from tests/session-rules.test.cjs.
 */
'use strict';

function normalizeTranscript(text) {
  if (!text) return '';
  var s = String(text)
    .toLowerCase()
    .trim()
    .replace(/['\u2018\u2019]/g, '')
    .replace(/[.,!?;:"]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return s;
}

var WRITE_INTENT_RE = /\b(write|put\s+that\s+down|answer\s+question|write\s+my\s+answer|write\s+it\s+down|write\s+that)\b/;
var QUESTION_NUM_TOKEN_RE = /\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty/;
var QUESTION_NUM_RE = new RegExp('question\\s*(' + QUESTION_NUM_TOKEN_RE.source + ')\\b');
var CLAROS_WRITE_PHRASE_RE = new RegExp('let me write that for question\\s*(' + QUESTION_NUM_TOKEN_RE.source + ')\\b', 'i');
var ANSWER_STATED_RE = new RegExp(
  '(?:my|the|final)\\s+answer\\s+(?:for\\s+question\\s+(?:' + QUESTION_NUM_TOKEN_RE.source + ')\\s+)?is\\b' +
  '|i\\s+think\\s+(?:its|it\\s+is|the\\s+answer\\s+is)\\b' +
  '|(?:my|the)\\s+final\\s+answer\\b' +
  '|thats\\s+my\\s+answer\\b' +
  '|so\\s+(?:its|it\\s+is|the\\s+answer\\s+is)\\b'
);

var QUESTION_NUM_WORDS = {
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  eleven: 11,
  twelve: 12,
  thirteen: 13,
  fourteen: 14,
  fifteen: 15,
  sixteen: 16,
  seventeen: 17,
  eighteen: 18,
  nineteen: 19,
  twenty: 20,
};

function parseQuestionNumToken(token) {
  if (!token) return null;
  if (/^\d+$/.test(token)) return parseInt(token, 10);
  return QUESTION_NUM_WORDS[token.toLowerCase()] || null;
}

function parseQuestionNum(norm) {
  var m = QUESTION_NUM_RE.exec(norm || '');
  return m ? parseQuestionNumToken(m[1]) : null;
}

function parseClarosWriteQuestionNum(text) {
  var m = CLAROS_WRITE_PHRASE_RE.exec(text || '');
  return m ? parseQuestionNumToken(m[1]) : null;
}

function hasExportIntent(norm) {
  if (!norm) return false;
  return norm.indexOf('export pdf') !== -1 ||
    norm.indexOf('export the pdf') !== -1 ||
    norm.indexOf('export as pdf') !== -1 ||
    norm.indexOf('export this as pdf') !== -1 ||
    norm.indexOf('download pdf') !== -1 ||
    norm.indexOf('download the pdf') !== -1 ||
    norm.indexOf('download this as pdf') !== -1 ||
    norm.indexOf('save as pdf') !== -1 ||
    norm.indexOf('save this as pdf') !== -1 ||
    norm.indexOf('save it as pdf') !== -1;
}

function extractDraftAnswer(norm) {
  if (!norm) return '';
  var m = ANSWER_STATED_RE.exec(norm);
  if (!m) return '';
  var idx = m.index + m[0].length;
  return (norm.slice(idx) || norm).trim();
}

var ClarosSessionRules = {
  normalizeTranscript: normalizeTranscript,
  hasExportIntent: hasExportIntent,
  parseQuestionNum: parseQuestionNum,
  parseClarosWriteQuestionNum: parseClarosWriteQuestionNum,
  extractDraftAnswer: extractDraftAnswer,
  WRITE_INTENT_RE: WRITE_INTENT_RE,
  QUESTION_NUM_RE: QUESTION_NUM_RE,
  CLAROS_WRITE_PHRASE_RE: CLAROS_WRITE_PHRASE_RE,
  ANSWER_STATED_RE: ANSWER_STATED_RE,
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = ClarosSessionRules;
}
