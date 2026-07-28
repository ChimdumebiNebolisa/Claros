const assert = require('node:assert/strict');

class FakeElement {
  constructor() {
    this.children = [];
    this.dataset = {};
    this.styleProps = {};
    this.style = {
      setProperty: (name, value) => {
        this.styleProps[name] = value;
      },
    };
    this.attributes = {};
    this.classList = { add() {}, toggle() {} };
    this.textContent = '';
    this.handlers = {};
    this.clientWidth = 800;
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  replaceChildren(...children) {
    this.children = children;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  addEventListener(name, handler) {
    this.handlers[name] = handler;
  }

  querySelector() {
    return null;
  }

  scrollIntoView() {}
}

global.document = { createElement: () => new FakeElement() };
global.fetch = async () => ({ ok: false });

const WorksheetView = require('../frontend/worksheet-view.js');
const canonicalDocument = {
  schema_version: 2,
  pages: [{ page_index: 0, width_points: 600, height_points: 800 }],
  response_regions: [
    {
      id: 'region-answer-opaque',
      page_index: 0,
      bbox: [60, 160, 420, 220],
      safety: 'approved',
      response_type: 'short_text',
      region_type: 'answer_line',
    },
    {
      id: 'region-explanation-opaque',
      page_index: 0,
      bbox: [60, 280, 480, 420],
      safety: 'approved',
      response_type: 'long_text',
      region_type: 'bounded_box',
    },
  ],
  tasks: [
    {
      id: 'task-river-opaque',
      legacy_question_id: 7,
      order: 3,
      label: '7',
      prompt_text: 'Choose a habitat and explain your reasoning.',
      anchor_page_index: 0,
      response_type: 'short_text',
      response_links: [
        { response_region_id: 'region-answer-opaque', role: 'answer', order: 0 },
        { response_region_id: 'region-explanation-opaque', role: 'explanation', order: 1 },
      ],
    },
  ],
};

const normalized = WorksheetView.normalizeDocument({ document: canonicalDocument });
assert.equal(normalized.tasks[0].id, 'task-river-opaque');
assert.deepEqual(normalized.tasks[0].responseTargetIds, [
  'region-answer-opaque',
  'region-explanation-opaque',
]);
assert.equal(normalized.responseTargetsById['region-answer-opaque'].region.width, 0.6);
assert.equal(normalized.responseTargetsById['region-explanation-opaque'].role, 'explanation');

const clientSafeDocument = {
  schema_version: 2,
  pages: [{ page_index: 0, width_points: 600, height_points: 800 }],
  tasks: [
    {
      id: 'task-client-safe',
      legacy_question_id: 11,
      order: 0,
      prompt_text: 'Select and explain.',
      anchor_page_index: 0,
      side_panel_fallback: true,
      response_target_id: 'client-choice',
      response_regions: [
        {
          id: 'client-choice',
          role: 'choice',
          order: 0,
          page_index: 0,
          safe_for_write: true,
          safety: 'approved',
          region: { x: 0.1, y: 0.2, width: 0.2, height: 0.1 },
        },
        {
          id: 'client-explanation',
          role: 'explanation',
          order: 1,
          page_index: 0,
          safe_for_write: false,
          safety: 'needs_review',
        },
      ],
    },
  ],
};
const clientNormalized = WorksheetView.normalizeDocument({ document: clientSafeDocument });
assert.deepEqual(clientNormalized.tasks[0].responseTargetIds, ['client-choice', 'client-explanation']);
assert.equal(clientNormalized.responseTargetsById['client-choice'].safeForWrite, true);
assert.equal(clientNormalized.responseTargetsById['client-explanation'].useSidePanel, true);

const defaultTargetDocument = {
  schema_version: 2,
  pages: [{ page_index: 0, width_points: 600, height_points: 800 }],
  tasks: [
    {
      id: 'task-answer-show-work',
      legacy_question_id: 12,
      order: 0,
      prompt_text: 'Give the answer and show your work.',
      anchor_page_index: 0,
      response_target_id: 'show-work-target',
      response_regions: [
        {
          id: 'answer-target',
          role: 'answer',
          order: 0,
          page_index: 0,
          safe_for_write: true,
          safety: 'approved',
          region: { x: 0.1, y: 0.1, width: 0.3, height: 0.06 },
        },
        {
          id: 'show-work-target',
          role: 'show_work',
          order: 1,
          page_index: 0,
          safe_for_write: true,
          safety: 'approved',
          region: { x: 0.1, y: 0.2, width: 0.5, height: 0.2 },
        },
      ],
    },
    {
      id: 'task-mixed-targets',
      legacy_question_id: 13,
      order: 1,
      prompt_text: 'Use the safe destination selected by the server.',
      anchor_page_index: 0,
      side_panel_fallback: true,
      response_target_id: 'safe-target',
      response_regions: [
        {
          id: 'unsafe-target',
          role: 'answer',
          order: 0,
          page_index: 0,
          safe_for_write: false,
          safety: 'needs_review',
        },
        {
          id: 'safe-target',
          role: 'answer',
          order: 1,
          page_index: 0,
          safe_for_write: true,
          safety: 'approved',
          region: { x: 0.1, y: 0.46, width: 0.4, height: 0.07 },
        },
      ],
    },
    {
      id: 'task-choice-only',
      legacy_question_id: 14,
      order: 2,
      prompt_text: 'Select the correct option.',
      anchor_page_index: 0,
      side_panel_fallback: true,
      response_target_id: 'task-choice-only:side-panel',
      choices: [
        { id: 'choice-second', label: 'Invented second label', text: 'Second option', order: 1 },
        { id: 'choice-first', label: 'Invented first label', text: 'First option', order: 0 },
      ],
      // These targets deliberately use a different order than the choice
      // list. The explicit choice_id, never array position, owns the label.
      response_regions: [
        {
          id: 'choice-first-target',
          role: 'choice',
          choice_id: 'choice-first',
          order: 0,
          page_index: 0,
          safe_for_write: true,
          safety: 'approved',
          region: { x: 0.12, y: 0.6, width: 0.04, height: 0.04 },
        },
        {
          id: 'choice-second-target',
          role: 'choice',
          choice_id: 'choice-second',
          order: 1,
          page_index: 0,
          safe_for_write: true,
          safety: 'approved',
          region: { x: 0.12, y: 0.68, width: 0.04, height: 0.04 },
        },
      ],
    },
  ],
};

const defaultTargetsNormalized = WorksheetView.normalizeDocument({ document: defaultTargetDocument });
const answerShowWorkTask = defaultTargetsNormalized.tasks[0];
const mixedTargetsTask = defaultTargetsNormalized.tasks[1];
const choiceOnlyTask = defaultTargetsNormalized.tasks[2];
assert.equal(answerShowWorkTask.defaultResponseTargetId, 'show-work-target');
assert.equal(
  WorksheetView.defaultResponseTarget(defaultTargetsNormalized, answerShowWorkTask).id,
  'show-work-target',
  'the server default chooses show-work instead of the first answer target',
);
assert.equal(
  WorksheetView.defaultResponseTarget(defaultTargetsNormalized, mixedTargetsTask).id,
  'safe-target',
  'the server default chooses the safe target even when an unsafe target sorts first',
);
assert.equal(choiceOnlyTask.defaultResponseTargetId, 'task-choice-only:side-panel');
assert.equal(
  WorksheetView.defaultResponseTarget(defaultTargetsNormalized, choiceOnlyTask).id,
  'task-choice-only:side-panel',
  'a choice-only task stays on its server-selected virtual side panel by default',
);
assert.equal(
  defaultTargetsNormalized.responseTargetsById['task-choice-only:side-panel'].virtual,
  true,
  'the absent server side-panel target is materialized for independent response state',
);
assert.equal(
  defaultTargetsNormalized.responseTargetsById['task-choice-only:side-panel'].useSidePanel,
  true,
);
assert.equal(
  WorksheetView.displayTargetLabel(defaultTargetsNormalized.responseTargetsById['choice-first-target'], choiceOnlyTask),
  'Choice First option',
  'choice targets resolve labels through choice_id, not array position',
);
assert.equal(
  WorksheetView.displayTargetLabel(defaultTargetsNormalized.responseTargetsById['choice-second-target'], choiceOnlyTask),
  'Choice Second option',
);

const legacyProjection = WorksheetView.normalizeDocument({
  questions: [{
    id: 11,
    task_id: 'task-projection-opaque',
    label: '11',
    text: 'Use the compatibility projection.',
    page_index: 0,
    response_target_id: 'projection-answer',
    response_regions: [{
      id: 'projection-answer',
      role: 'answer',
      order: 0,
      page_index: 0,
      safe_for_write: true,
      safety: 'approved',
      region: { x: 0.2, y: 0.2, width: 0.4, height: 0.1 },
    }],
  }],
});
assert.equal(legacyProjection.tasks[0].id, 'task-projection-opaque');
assert.equal(legacyProjection.tasks[0].legacyQuestionId, 11);

const overlayLayer = new FakeElement();
let selected = null;
const view = WorksheetView.create({
  container: new FakeElement(),
  pageImage: new FakeElement(),
  overlayLayer,
  pageLabel: new FakeElement(),
  zoomLabel: new FakeElement(),
  onSelectTarget(taskId, responseRegionId) {
    selected = { taskId, responseRegionId };
  },
});

view.load({
  assignmentId: 'assignment-opaque',
  document: canonicalDocument,
  responseStates: {
    'region-answer-opaque': { written: 'Wetland' },
    'region-explanation-opaque': { written: 'It retains water.' },
  },
  activeTaskId: 'task-river-opaque',
  activeResponseRegionId: 'region-answer-opaque',
});

assert.equal(overlayLayer.children.length, 2, 'all safe response regions are rendered');
assert.equal(overlayLayer.children[0].dataset.responseRegionId, 'region-answer-opaque');
assert.equal(overlayLayer.children[1].dataset.responseRegionId, 'region-explanation-opaque');
assert.equal(overlayLayer.children[1].children[1].textContent, 'It retains water.');
overlayLayer.children[1].handlers.click();
assert.deepEqual(selected, {
  taskId: 'task-river-opaque',
  responseRegionId: 'region-explanation-opaque',
});
view.setActiveTarget('task-river-opaque', 'region-explanation-opaque');
assert.equal(view.getState().activeResponseRegionId, 'region-explanation-opaque');

const defaultView = WorksheetView.create({
  container: new FakeElement(),
  pageImage: new FakeElement(),
  overlayLayer: new FakeElement(),
  pageLabel: new FakeElement(),
  zoomLabel: new FakeElement(),
});
defaultView.load({
  assignmentId: 'assignment-defaults',
  document: defaultTargetDocument,
  activeTaskId: 'task-choice-only',
});
assert.equal(
  defaultView.getState().activeResponseRegionId,
  'task-choice-only:side-panel',
  'initial selection honors the virtual side-panel default',
);
defaultView.setActiveTarget('task-choice-only', 'choice-first-target');
assert.equal(
  defaultView.getState().activeResponseRegionId,
  'choice-first-target',
  'an explicit choice target replaces the virtual default only after selection',
);
defaultView.setActiveQuestion(12);
assert.equal(
  defaultView.getState().activeResponseRegionId,
  'show-work-target',
  'legacy task selection also resolves through the server default target',
);

const fitContainer = new FakeElement();
fitContainer.clientWidth = 390;
const fitZoomLabel = new FakeElement();
const fitWidthBtn = new FakeElement();
const fitView = WorksheetView.create({
  container: fitContainer,
  pageImage: new FakeElement(),
  overlayLayer: new FakeElement(),
  pageLabel: new FakeElement(),
  zoomLabel: fitZoomLabel,
  fitWidthBtn,
});
fitView.load({
  assignmentId: 'fit-test',
  document: canonicalDocument,
  pageCount: 1,
  activeTaskId: 'task-river-opaque',
});
fitView.setZoom(150);
assert.equal(fitView.getState().zoom, 150);
assert.equal(fitView.getState().fitWidthMode, false, 'manual zoom clears fit-width mode');
assert.equal(fitWidthBtn.attributes['aria-pressed'], 'false');
fitView.fitWidth();
assert.equal(fitView.getState().zoom, 100, 'fit width scales to the container percent contract');
assert.equal(fitView.getState().fitWidthMode, true);
assert.equal(fitWidthBtn.attributes['aria-pressed'], 'true');
assert.equal(fitContainer.styleProps['--document-zoom'], '100%');

console.log('worksheet-view-targets.test.cjs: opaque task IDs, canonical defaults, and multiple response targets passed.');
