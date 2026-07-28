(function (root) {
  function createCard(question) {
    if (root.ClarosWorksheetView && root.ClarosWorksheetView.createLegacyCard) {
      return root.ClarosWorksheetView.createLegacyCard(question);
    }
    var id = String(question.id);
    var card = document.createElement('div');
    card.className = 'question-card';
    card.dataset.questionId = id;

    var header = document.createElement('div');
    header.className = 'question-header';
    var headerMain = document.createElement('div');
    headerMain.className = 'question-header-main';
    var index = document.createElement('span');
    index.className = 'question-index';
    index.textContent = id;
    var label = document.createElement('div');
    label.className = 'question-label';
    label.appendChild(document.createTextNode('Question ' + id));
    var ready = document.createElement('span');
    ready.className = 'ready-badge';
    ready.textContent = 'Answer confirmed';
    label.appendChild(ready);
    headerMain.appendChild(index);
    headerMain.appendChild(label);
    var meta = document.createElement('div');
    meta.className = 'question-meta';
    meta.textContent = '\u00a0';
    header.appendChild(headerMain);
    header.appendChild(meta);

    var questionText = document.createElement('div');
    questionText.className = 'question-text';
    questionText.textContent = question.text == null ? '' : String(question.text);

    var answer = document.createElement('div');
    answer.className = 'answer-field';
    answer.dataset.placeholder = 'Say your answer in a session, or type it here';
    answer.contentEditable = 'true';
    answer.spellcheck = true;
    answer.dataset.questionId = id;
    answer.setAttribute('role', 'textbox');
    answer.setAttribute('aria-label', 'Answer for question ' + id);
    answer.setAttribute('aria-multiline', 'true');

    var confirm = document.createElement('button');
    confirm.type = 'button';
    confirm.className = 'btn-confirm-answer';
    confirm.disabled = true;
    confirm.textContent = 'Confirm answer';
    confirm.dataset.questionId = id;
    confirm.setAttribute('aria-label', 'Confirm answer for question ' + id);
    card.appendChild(header);
    card.appendChild(questionText);
    card.appendChild(answer);
    card.appendChild(confirm);
    return card;
  }

  root.ClarosQuestionView = { createCard: createCard };
})(typeof window !== 'undefined' ? window : this);
