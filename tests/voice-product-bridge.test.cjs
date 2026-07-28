/**
 * Product-event mapping for Gemini Live transcripts (Stage 9).
 */
'use strict';

const assert = require('node:assert/strict');
const path = require('path');

// session-rules must load before the bridge for ClarosSessionRules.
require(path.join(__dirname, '..', 'frontend', 'session-rules.js'));
const Bridge = require(path.join(__dirname, '..', 'frontend', 'voice-product-bridge.js'));

function types(events) {
  return events.map(function (event) { return event.type; });
}

assert.deepEqual(
  types(Bridge.interpretUserTurn('My answer for question 2 is photosynthesis.', {})),
  ['task_selected', 'answer_proposed']
);

const stated = Bridge.interpretUserTurn('My answer for question 2 is photosynthesis.', {});
assert.equal(stated[0].legacyQuestionId, 2);
assert.match(stated[1].text, /photosynthesis/i);

assert.deepEqual(
  types(Bridge.interpretUserTurn('Write my answer for question 3.', { draft: '', confirmed: false, writeToken: '' })),
  ['task_selected', 'needs_answer_before_write'],
  'write intent without a draft must not invent an answer'
);

assert.deepEqual(
  types(Bridge.interpretUserTurn('Write it down.', {
    draft: 'river habitat',
    confirmed: false,
    writeToken: '',
  })),
  ['answer_proposed']
);
assert.equal(
  Bridge.interpretUserTurn('Write it down.', { draft: 'river habitat' })[0].text,
  'river habitat'
);

assert.deepEqual(
  types(Bridge.interpretUserTurn('Write it down.', {
    draft: 'river habitat',
    confirmed: true,
    writeToken: 'tok',
  })),
  ['write_ready_notice']
);

assert.deepEqual(
  types(Bridge.interpretUserTurn('Please export the PDF.', {})),
  ['export_requested']
);

assert.deepEqual(
  types(Bridge.interpretClarosTurn('Let me write that for question 4.')),
  ['task_selected', 'write_ready_notice']
);
assert.equal(Bridge.interpretClarosTurn('Let me write that for question 4.')[0].legacyQuestionId, 4);
assert.deepEqual(Bridge.interpretClarosTurn('Here is a hint about ecosystems.'), []);

console.log('voice-product-bridge.test.cjs: structured product events passed.');
