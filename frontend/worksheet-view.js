(function (root) {
  'use strict';

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function create(options) {
    var container = options.container;
    var pageImage = options.pageImage;
    var overlayLayer = options.overlayLayer;
    var pageLabel = options.pageLabel;
    var zoomLabel = options.zoomLabel;
    var state = {
      assignmentId: null,
      assignmentCapability: null,
      questions: [],
      answers: {},
      currentPage: 1,
      pageCount: 1,
      activeQuestionId: null,
      zoom: 100,
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
      overlayLayer.replaceChildren();
      pageQuestions().forEach(function (question) {
        if (Number(state.activeQuestionId) !== Number(question.id)) return;
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
        var placement = question.answer_region_status === 'side_panel'
          ? 'side panel only; the original page remains unchanged'
          : (question.needs_layout_review || question.answer_region_status === 'detected'
            ? 'location needs review; writing is unavailable'
            : 'safe answer line');
        button.setAttribute('aria-label', 'Question ' + (question.label || question.id) + ', ' + placement);
        button.setAttribute('aria-pressed', String(Number(state.activeQuestionId) === Number(question.id)));
        if (Number(state.activeQuestionId) === Number(question.id)) button.classList.add('is-active');
        if (question.needs_layout_review) {
          button.classList.add('needs-review');
        }
        var answer = state.answers[question.id] || '';
        var number = document.createElement('span');
        number.className = 'region-number';
        number.textContent = 'Q' + (question.label || question.id);
        var answerText = document.createElement('span');
        answerText.className = 'region-answer';
        answerText.textContent = answer || '';
        button.appendChild(number);
        button.appendChild(answerText);
        button.addEventListener('click', function () {
          state.activeQuestionId = question.id;
          renderOverlays();
          if (options.onSelectQuestion) options.onSelectQuestion(question);
        });
        overlayLayer.appendChild(button);
      });
    }

    function renderPage() {
      pageImage.alt = 'Original worksheet page ' + state.currentPage;
      var requestUrl = '/api/assignments/' + state.assignmentId + '/pages/' + state.currentPage + '.png';
      fetch(requestUrl, {
        headers: { 'X-Assignment-Capability': state.assignmentCapability || '' }
      }).then(function (response) {
        if (!response.ok) throw new Error('Could not load worksheet page.');
        return response.blob();
      }).then(function (blob) {
        if (state.pageObjectUrl) URL.revokeObjectURL(state.pageObjectUrl);
        state.pageObjectUrl = URL.createObjectURL(blob);
        pageImage.src = state.pageObjectUrl;
      }).catch(function () {
        pageImage.removeAttribute('src');
        if (options.onPageError) options.onPageError();
      });
      updateToolbar();
      renderOverlays();
    }

    function load(data) {
      state.assignmentId = data.assignmentId;
      state.assignmentCapability = data.assignmentCapability || null;
      state.questions = data.questions || [];
      state.pageCount = Math.max(1, Number(data.pageCount || 1));
      state.currentPage = 1;
      state.activeQuestionId = state.questions.length ? state.questions[0].id : null;
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

    return {
      load: load,
      setPage: setPage,
      setZoom: setZoom,
      fitWidth: fitWidth,
      setActiveQuestion: setActiveQuestion,
      updateAnswer: updateAnswer,
      getState: function () { return state; }
    };
  }

  root.ClarosWorksheetView = { create: create };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.ClarosWorksheetView;
})(typeof window !== 'undefined' ? window : this);
