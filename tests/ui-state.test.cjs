'use strict';

const assert = require('assert');
const path = require('path');

const ui = require(path.join(__dirname, '..', 'frontend', 'ui-state.js'));

for (const state of ui.WORKSPACE_STATES) {
  const model = ui.getWorkspaceModel(state, { hasAssignment: state !== 'empty' });
  assert.strictEqual(model.state, state);
  assert.ok(model.title);
  assert.ok(model.description);
}

for (const state of ui.VOICE_STATES) {
  const model = ui.getVoiceModel(state, { hasAssignment: true, liveSession: false });
  assert.strictEqual(model.state, state);
  assert.ok(model.title);
  assert.ok(model.badge);
}

assert.strictEqual(ui.getVoiceModel('idle', { hasAssignment: true, liveSession: false }).badge, 'Offline');
assert.strictEqual(ui.getVoiceModel('connecting', { hasAssignment: true, liveSession: false }).badge, 'Connecting');
assert.strictEqual(ui.getVoiceModel('listening', { hasAssignment: true, liveSession: true }).badge, 'Live');
assert.strictEqual(ui.getVoiceModel('answer_detected', { hasAssignment: true, liveSession: true }).badge, 'Review');
assert.strictEqual(ui.getVoiceModel('speaking', { hasAssignment: true, liveSession: true }).showInterrupt, true);
assert.strictEqual(ui.getVoiceModel('answer_detected', { hasAssignment: true }).showConfirmation, true);
assert.strictEqual(ui.getVoiceModel('confirming', { hasAssignment: true }).showConfirmation, true);
assert.strictEqual(ui.getVoiceModel('writing', { hasAssignment: true }).primaryDisabled, true);
assert.strictEqual(ui.getVoiceModel('listening', { hasAssignment: true, liveSession: true }).primaryLabel, 'End session');
assert.match(ui.getVoiceModel('idle', { hasAssignment: false }).disabledReason, /worksheet/i);
assert.strictEqual(ui.getVoiceModel('error', { hasAssignment: true }).primaryLabel, 'Try voice again');

assert.strictEqual(ui.getWorkspaceModel('empty', { hasAssignment: false }).showSetup, true);
assert.strictEqual(ui.getWorkspaceModel('uploading', { hasAssignment: false }).busy, true);
assert.strictEqual(ui.getWorkspaceModel('parsing', { hasAssignment: false }).showSetup, true);
assert.strictEqual(ui.getWorkspaceModel('ready', { hasAssignment: true }).showWorkspace, true);
assert.strictEqual(ui.getWorkspaceModel('needs_layout_review', { hasAssignment: true }).showLayoutReview, true);
assert.strictEqual(ui.getWorkspaceModel('exporting', { hasAssignment: true }).canExport, false);
assert.strictEqual(ui.getWorkspaceModel('exporting', { hasAssignment: true }).exportLabel, 'Preparing PDF…');
assert.strictEqual(ui.getWorkspaceModel('complete', { hasAssignment: true }).exportLabel, 'Export again');
assert.strictEqual(ui.getWorkspaceModel('error', { hasAssignment: false }).showSetup, true);

assert.throws(() => ui.getWorkspaceModel('not-a-state', {}));
assert.throws(() => ui.getVoiceModel('not-a-state', {}));

console.log('ui-state.test.cjs: workspace and voice mappings passed.');
