/**
 * Table-driven checks for frontend/session-rules.js (run: npm run test:session-rules).
 */
'use strict';

const assert = require('assert');
const path = require('path');

const rules = require(path.join(__dirname, '..', 'frontend', 'session-rules.js'));

const cases = [
  {
    raw: 'Please export PDF now.',
    writeIntent: false,
    answerStated: false,
    exportIntent: true,
    questionNum: null,
  },
  {
    raw: 'Export the PDF please.',
    writeIntent: false,
    answerStated: false,
    exportIntent: true,
    questionNum: null,
  },
  {
    raw: 'Save this as PDF please.',
    writeIntent: false,
    answerStated: false,
    exportIntent: true,
    questionNum: null,
  },
  {
    raw: 'Write my answer for question 2.',
    writeIntent: true,
    answerStated: false,
    exportIntent: false,
    questionNum: 2,
  },
  {
    raw: 'Write my answer for question two.',
    writeIntent: true,
    answerStated: false,
    exportIntent: false,
    questionNum: 2,
  },
  {
    raw: 'My answer is 42 for question 3.',
    writeIntent: false,
    answerStated: true,
    exportIntent: false,
    questionNum: 3,
  },
  {
    raw: 'My answer for question 2 is 12.',
    writeIntent: false,
    answerStated: true,
    exportIntent: false,
    questionNum: 2,
  },
  {
    raw: 'My answer for question two is 12.',
    writeIntent: false,
    answerStated: true,
    exportIntent: false,
    questionNum: 2,
  },
  {
    raw: 'I think it is the Civil War.',
    writeIntent: false,
    answerStated: true,
    exportIntent: false,
    questionNum: null,
  },
  {
    raw: "That's my answer.",
    writeIntent: false,
    answerStated: true,
    exportIntent: false,
    questionNum: null,
  },
  {
    raw: 'That\u2019s my answer.',
    writeIntent: false,
    answerStated: true,
    exportIntent: false,
    questionNum: null,
  },
  {
    raw: "I think it's 42.",
    writeIntent: false,
    answerStated: true,
    exportIntent: false,
    questionNum: null,
  },
  {
    raw: 'I think it\u2019s 42.',
    writeIntent: false,
    answerStated: true,
    exportIntent: false,
    questionNum: null,
  },
  {
    raw: 'Let me write that for question 1',
    writeIntent: true,
    answerStated: false,
    exportIntent: false,
    questionNum: 1,
    clarosWriteQ: 1,
  },
  {
    raw: 'Let me write that for question two',
    writeIntent: true,
    answerStated: false,
    exportIntent: false,
    questionNum: 2,
    clarosWriteQ: 2,
  },
];

for (const c of cases) {
  const norm = rules.normalizeTranscript(c.raw);
  assert.strictEqual(rules.WRITE_INTENT_RE.test(norm), c.writeIntent, `writeIntent ${c.raw}`);
  assert.strictEqual(rules.ANSWER_STATED_RE.test(norm), c.answerStated, `answerStated ${c.raw}`);
  assert.strictEqual(rules.hasExportIntent(norm), c.exportIntent, `exportIntent ${c.raw}`);
  assert.strictEqual(rules.parseQuestionNum(norm), c.questionNum, `questionNum ${c.raw}`);
  if (c.clarosWriteQ != null) {
    const m = rules.CLAROS_WRITE_PHRASE_RE.exec(norm);
    assert.ok(m, `claros phrase should match: ${c.raw}`);
    assert.strictEqual(rules.parseClarosWriteQuestionNum(norm), c.clarosWriteQ);
  }
}

console.log('session-rules.test.cjs: all', cases.length, 'cases passed.');
