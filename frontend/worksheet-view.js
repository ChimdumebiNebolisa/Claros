(function (root) {
  'use strict';

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function copyRegion(region) {
    return region ? {
      x: Number(region.x),
      y: Number(region.y),
      width: Number(region.width),
      height: Number(region.height)
    } : null;
  }

  function create(options) {
    var container = options.container;
    var pageImage = options.pageImage;
    var overlayLayer = options.overlayLayer;
    var pageLabel = options.pageLabel;
    var zoomLabel = options.zoomLabel;
    var state = {
      assignmentId: null,
      questions: [],
      answers: {},
      currentPage: 1,
      pageCount: 1,
      activeQuestionId: null,
      zoom: 100,
      correctionMode: false,
      selectedQuestionId: null
    };

    function pageQuestions() {
      return state.questions.filter(function (question) {
        return Number(question.page || 1) === state.currentPage;
      });
    }

    function updateToolbar() {
      if (pageLabel) pageLabel.textContent = 'Page ' + state.currentPage + ' of ' + state.pageCount;
      if (zoomLabel) zoomLabel.textContent = state.zoom + '%';
      container.style.setProperty('--document-zoom', state.zoom + '%');
    }

    function renderOverlays() {
      overlayLayer.innerHTML = '';
      pageQuestions().forEach(function (question) {
        var region = question.answer_region;
        if (!region) return;
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'answer-region';
        button.dataset.questionId = question.id;
        button.style.left = (Number(region.x) * 100) + '%';
        button.style.top = (Number(region.y) * 100) + '%';
        button.style.width = (Number(region.width) * 100) + '%';
        button.style.height = (Number(region.height) * 100) + '%';
        button.setAttribute('aria-label', 'Answer region for question ' + question.id);
        button.setAttribute('aria-pressed', String(Number(state.activeQuestionId) === Number(question.id)));
        if (Number(state.activeQuestionId) === Number(question.id)) button.classList.add('is-active');
        if (question.needs_layout_review) {
          button.classList.add('needs-review');
          button.setAttribute('aria-description', 'This answer region needs layout review.');
        }
        if (state.correctionMode && Number(state.selectedQuestionId) === Number(question.id)) {
          button.classList.add('is-correcting');
        }
        var answer = state.answers[question.id] || '';
        button.innerHTML = '<span class="region-number">Q' + question.id + '</span><span class="region-answer"></span>';
        button.querySelector('.region-answer').textContent = answer || 'Answer area';
        button.addEventListener('click', function () {
          state.activeQuestionId = question.id;
          if (state.correctionMode) state.selectedQuestionId = question.id;
          renderOverlays();
          if (options.onSelectQuestion) options.onSelectQuestion(question);
        });
        button.addEventListener('keydown', function (event) {
          if (!state.correctionMode || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
          event.preventDefault();
          var dx = event.key === 'ArrowLeft' ? -0.002 : (event.key === 'ArrowRight' ? 0.002 : 0);
          var dy = event.key === 'ArrowUp' ? -0.002 : (event.key === 'ArrowDown' ? 0.002 : 0);
          adjust(question.id, dx, dy, 0, 0);
        });
        overlayLayer.appendChild(button);
      });
    }

    function renderPage() {
      pageImage.alt = 'Original worksheet page ' + state.currentPage;
      pageImage.src = '/api/assignments/' + state.assignmentId + '/pages/' + state.currentPage + '.png';
      updateToolbar();
      renderOverlays();
    }

    function load(data) {
      state.assignmentId = data.assignmentId;
      state.questions = data.questions || [];
      state.pageCount = Math.max(1, Number(data.pageCount || 1));
      state.currentPage = 1;
      state.activeQuestionId = state.questions.length ? state.questions[0].id : null;
      state.selectedQuestionId = state.activeQuestionId;
      state.answers = data.answers || {};
      renderPage();
    }

    function setPage(page) {
      state.currentPage = clamp(Number(page), 1, state.pageCount);
      renderPage();
    }

    function setZoom(zoom) {
      state.zoom = clamp(Math.round(Number(zoom)), 75, 175);
      updateToolbar();
    }

    function fitWidth() {
      setZoom(100);
    }

    function setActiveQuestion(questionId) {
      var question = state.questions.find(function (item) { return Number(item.id) === Number(questionId); });
      if (!question) return;
      state.activeQuestionId = question.id;
      state.currentPage = Number(question.page || 1);
      renderPage();
      var activeRegion = overlayLayer.querySelector('[data-question-id="' + question.id + '"]');
      if (activeRegion) activeRegion.scrollIntoView({ block: 'center', inline: 'center' });
    }

    function updateAnswer(questionId, text) {
      state.answers[questionId] = text || '';
      renderOverlays();
    }

    function setCorrectionMode(enabled) {
      state.correctionMode = !!enabled;
      state.selectedQuestionId = state.activeQuestionId;
      container.dataset.correctionMode = String(state.correctionMode);
      renderOverlays();
    }

    function adjust(questionId, dx, dy, dw, dh) {
      var question = state.questions.find(function (item) { return Number(item.id) === Number(questionId); });
      if (!question || !question.answer_region) return;
      var region = question.answer_region;
      region.x = clamp(Number(region.x) + dx, 0, 0.96);
      region.y = clamp(Number(region.y) + dy, 0, 0.96);
      region.width = clamp(Number(region.width) + dw, 0.04, 1 - region.x);
      region.height = clamp(Number(region.height) + dh, 0.025, 1 - region.y);
      question.needs_layout_review = true;
      renderOverlays();
      if (options.onRegionChange) options.onRegionChange(question, copyRegion(region));
    }

    function resetSelected() {
      var question = state.questions.find(function (item) {
        return Number(item.id) === Number(state.selectedQuestionId);
      });
      if (!question || !question.detected_answer_region) return;
      question.answer_region = copyRegion(question.detected_answer_region);
      renderOverlays();
      if (options.onRegionChange) options.onRegionChange(question, copyRegion(question.answer_region));
    }

    function confirmSelected() {
      var question = state.questions.find(function (item) {
        return Number(item.id) === Number(state.selectedQuestionId);
      });
      if (!question) return;
      question.needs_layout_review = false;
      renderOverlays();
      if (options.onRegionConfirm) options.onRegionConfirm(question);
    }

    return {
      load: load,
      setPage: setPage,
      setZoom: setZoom,
      fitWidth: fitWidth,
      setActiveQuestion: setActiveQuestion,
      updateAnswer: updateAnswer,
      setCorrectionMode: setCorrectionMode,
      adjust: adjust,
      resetSelected: resetSelected,
      confirmSelected: confirmSelected,
      getState: function () { return state; }
    };
  }

  root.ClarosWorksheetView = { create: create };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.ClarosWorksheetView;
})(typeof window !== 'undefined' ? window : this);
