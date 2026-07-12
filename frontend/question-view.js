(function (root) {
  function createCard(question) {
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
    answer.setAttribute('aria-label', 'Answer for question ' + id);
    answer.setAttribute('aria-multiline', 'true');

    var confirm = card.querySelector('.btn-confirm-answer');
    confirm.dataset.questionId = id;
    confirm.setAttribute('aria-label', 'Confirm answer for question ' + id);
    return card;
  }

  root.ClarosQuestionView = { createCard: createCard };
})(typeof window !== 'undefined' ? window : this);
