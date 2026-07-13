(function (root) {
  function pct(box, pageWidth, pageHeight) {
    return {
      left: (box[0] / pageWidth) * 100,
      top: (box[1] / pageHeight) * 100,
      width: ((box[2] - box[0]) / pageWidth) * 100,
      height: ((box[3] - box[1]) / pageHeight) * 100
    };
  }

  function createPageShell(page, previewUrl) {
    var wrap = document.createElement('div');
    wrap.className = 'worksheet-page';
    wrap.dataset.pageIndex = String(page.page_index);

    var status = document.createElement('div');
    status.className = 'worksheet-page-status';
    status.setAttribute('role', 'status');
    if (page.requires_ocr) {
      status.textContent = 'This page has no usable text and requires OCR before answer regions can be detected.';
      status.classList.add('requires-ocr');
    } else {
      status.textContent = 'Page ' + (page.page_index + 1);
    }
    wrap.appendChild(status);

    var stage = document.createElement('div');
    stage.className = 'worksheet-page-stage';
    stage.style.setProperty('--page-aspect', String(page.height_points / page.width_points));

    var img = document.createElement('img');
    img.className = 'worksheet-page-image';
    img.alt = 'Original worksheet page ' + (page.page_index + 1);
    img.decoding = 'async';
    img.src = previewUrl;
    stage.appendChild(img);

    var overlays = document.createElement('div');
    overlays.className = 'worksheet-overlays';
    stage.appendChild(overlays);

    wrap.appendChild(stage);
    wrap._overlays = overlays;
    wrap._page = page;
    return wrap;
  }

  function createOverlayField(question, page, options) {
    options = options || {};
    var bbox = question.answer_bbox;
    var field = document.createElement('div');
    field.className = 'worksheet-answer-overlay';
    field.dataset.questionId = String(question.id);
    field.dataset.layoutConfidence = question.layout_confidence || 'low';

    if (!bbox) {
      field.classList.add('unresolved');
      field.style.left = '8%';
      field.style.top = '8%';
      field.style.width = '84%';
      field.style.height = '12%';
    } else {
      var box = pct(bbox, page.width_points, page.height_points);
      field.style.left = box.left + '%';
      field.style.top = box.top + '%';
      field.style.width = box.width + '%';
      field.style.height = box.height + '%';
    }

    var labelText = 'Answer for question ' + question.id + ': ' + String(question.text || '');
    var input = document.createElement('div');
    input.className = 'answer-field worksheet-answer-field';
    input.dataset.questionId = String(question.id);
    input.dataset.placeholder = 'Type or dictate your answer';
    input.contentEditable = 'true';
    input.spellcheck = true;
    input.setAttribute('role', 'textbox');
    input.setAttribute('aria-multiline', 'true');
    input.setAttribute('aria-label', labelText);
    field.appendChild(input);

    var meta = document.createElement('div');
    meta.className = 'overlay-meta';
    meta.innerHTML = '<span class="overlay-qid">Q' + question.id + '</span>';
    if (question.layout_confidence && question.layout_confidence !== 'high') {
      var warn = document.createElement('span');
      warn.className = 'overlay-warning';
      warn.textContent = question.layout_confidence === 'manual'
        ? 'Manual region'
        : 'Layout ' + question.layout_confidence;
      meta.appendChild(warn);
    }
    if (!bbox) {
      var missing = document.createElement('span');
      missing.className = 'overlay-warning';
      missing.textContent = 'Region unresolved — correct before export';
      meta.appendChild(missing);
    }
    field.appendChild(meta);

    var confirm = document.createElement('button');
    confirm.type = 'button';
    confirm.className = 'btn-confirm-answer overlay-confirm';
    confirm.dataset.questionId = String(question.id);
    confirm.disabled = true;
    confirm.textContent = 'Confirm answer';
    confirm.setAttribute('aria-label', 'Confirm answer for question ' + question.id);
    field.appendChild(confirm);

    if (typeof options.onReady === 'function') options.onReady(field, input, confirm);
    return field;
  }

  function createLegacyCard(question) {
    var id = String(question.id);
    var card = document.createElement('div');
    card.className = 'question-card';
    card.dataset.questionId = id;
    card.innerHTML = '<div class="question-header"><div style="display:flex;align-items:center"><span class="question-index"></span><div class="question-label">Question <span class="ready-badge">Answer confirmed</span></div></div><div class="question-meta">&nbsp;</div></div><div class="question-text"></div><div class="answer-field" data-placeholder="Say your answer in a session, or type it here" contenteditable="true" spellcheck="true"></div><button type="button" class="btn-confirm-answer" disabled>Confirm answer</button>';

    card.querySelector('.question-index').textContent = id;
    card.querySelector('.question-label').firstChild.textContent = 'Question ' + id;
    card.querySelector('.question-text').textContent = question.text == null ? '' : String(question.text);

    var answer = card.querySelector('.answer-field');
    answer.dataset.questionId = id;
    answer.setAttribute('role', 'textbox');
    answer.setAttribute('aria-label', 'Answer for question ' + id + (question.text ? ': ' + question.text : ''));
    answer.setAttribute('aria-multiline', 'true');

    var confirm = card.querySelector('.btn-confirm-answer');
    confirm.dataset.questionId = id;
    confirm.setAttribute('aria-label', 'Confirm answer for question ' + id);
    return card;
  }

  function clientToPagePoint(stageEl, page, clientX, clientY) {
    var rect = stageEl.getBoundingClientRect();
    var x = ((clientX - rect.left) / rect.width) * page.width_points;
    var y = ((clientY - rect.top) / rect.height) * page.height_points;
    return {
      x: Math.max(0, Math.min(page.width_points, x)),
      y: Math.max(0, Math.min(page.height_points, y))
    };
  }

  root.ClarosWorksheetView = {
    createPageShell: createPageShell,
    createOverlayField: createOverlayField,
    createLegacyCard: createLegacyCard,
    clientToPagePoint: clientToPagePoint,
    pct: pct
  };

  // Keep legacy question-card renderer available for fallback/list mode.
  root.ClarosQuestionView = {
    createCard: createLegacyCard
  };
})(typeof window !== 'undefined' ? window : this);
