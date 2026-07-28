const assert = require('node:assert/strict');

class FakeElement {
  constructor() {
    this.children = [];
    this.dataset = {};
    this.style = { setProperty() {} };
    this.attributes = {};
    this.classList = { add() {}, toggle() {} };
    this.textContent = '';
  }

  set innerHTML(_value) {
    throw new Error('Worksheet overlays must not parse HTML strings.');
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

  addEventListener() {}
  scrollIntoView() {}
}

global.document = { createElement: () => new FakeElement() };
global.fetch = async () => ({ ok: false });

const WorksheetView = require('../frontend/worksheet-view.js');
const overlayLayer = new FakeElement();
const view = WorksheetView.create({
  container: new FakeElement(),
  pageImage: new FakeElement(),
  overlayLayer,
  pageLabel: new FakeElement(),
  zoomLabel: new FakeElement(),
});
const maliciousLabel = '</span><img src=x onerror=globalThis.__xss=1>';

view.load({
  assignmentId: 'assignment-1',
  questions: [
    {
      id: 1,
      label: maliciousLabel,
      answer_region: { x: 0.1, y: 0.2, width: 0.5, height: 0.1 },
      answer_region_status: 'safe',
    },
  ],
});

assert.equal(overlayLayer.children.length, 1);
const [number, answer] = overlayLayer.children[0].children;
assert.equal(number.textContent, 'Q1');
assert.equal(answer.textContent, '');
assert.equal(globalThis.__xss, undefined);

console.log('worksheet-view-security.test.cjs: malicious labels remain text.');
