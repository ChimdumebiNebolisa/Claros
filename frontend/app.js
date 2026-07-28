(function () {
  'use strict';

  const UiState = window.ClarosUiState;
  const SessionRules = window.ClarosSessionRules;
  const WorksheetView = window.ClarosWorksheetView;
  const VoiceProductBridge = window.ClarosVoiceProductBridge;
  const VoiceLiveTransport = window.ClarosVoiceLiveTransport;
  if (!UiState || !SessionRules || !WorksheetView || !VoiceProductBridge || !VoiceLiveTransport) {
    throw new Error('Claros frontend modules failed to load');
  }

  const API_BASE = location.origin || 'http://127.0.0.1:8000';
  const SESSION_STORAGE_KEY = 'claros_session_v1';
  const MAX_VOICE_RECONNECT_ATTEMPTS = 2;

  const elements = {
    setupMode: document.getElementById('setupMode'),
    workspaceMode: document.getElementById('workspaceMode'),
    workspaceStatus: document.getElementById('workspaceStatus'),
    startCard: document.querySelector('.start-card'),
    uploadZone: document.getElementById('uploadZone'),
    fileInput: document.getElementById('fileInput'),
    uploadBtn: document.getElementById('uploadBtn'),
    uploadLabel: document.getElementById('uploadLabel'),
    sampleChooserActions: document.getElementById('sampleChooserActions'),
    processingPanel: document.getElementById('processingPanel'),
    processingTitle: document.getElementById('processingTitle'),
    selectedFilename: document.getElementById('selectedFilename'),
    processingActions: document.getElementById('processingActions'),
    retryBtn: document.getElementById('retryBtn'),
    replaceBtn: document.getElementById('replaceBtn'),
    errors: document.getElementById('errors'),
    workspaceErrors: document.getElementById('workspaceErrors'),
    assignmentTitle: document.getElementById('assignmentTitle'),
    demoReplayIndicator: document.getElementById('demoReplayIndicator'),
    replaceWorksheetBtn: document.getElementById('replaceWorksheetBtn'),
    exportBtn: document.getElementById('exportBtn'),
    previousPageBtn: document.getElementById('previousPageBtn'),
    nextPageBtn: document.getElementById('nextPageBtn'),
    fitWidthBtn: document.getElementById('fitWidthBtn'),
    zoomOutBtn: document.getElementById('zoomOutBtn'),
    zoomInBtn: document.getElementById('zoomInBtn'),
    pageLabel: document.getElementById('pageLabel'),
    zoomLabel: document.getElementById('zoomLabel'),
    documentViewport: document.getElementById('documentViewport'),
    documentPage: document.getElementById('documentPage'),
    documentPageCaption: document.getElementById('documentPageCaption'),
    pageImage: document.getElementById('pageImage'),
    answerOverlayLayer: document.getElementById('answerOverlayLayer'),
    sessionPanel: document.getElementById('sessionPanel'),
    voiceBadge: document.getElementById('voiceBadge'),
    voicePanelToggle: document.getElementById('voicePanelToggle'),
    status: document.getElementById('status'),
    statusLabel: document.getElementById('statusLabel'),
    statusDescription: document.getElementById('statusDescription'),
    meterBar: document.getElementById('meterBar'),
    currentQuestionLabel: document.getElementById('currentQuestionLabel'),
    currentQuestionExcerpt: document.getElementById('currentQuestionExcerpt'),
    taskChoices: document.getElementById('taskChoices'),
    answerProgress: document.getElementById('answerProgress'),
    layoutReviewNotice: document.getElementById('layoutReviewNotice'),
    questionListToggle: document.getElementById('questionListToggle'),
    questionsContainer: document.getElementById('questionsContainer'),
    responseTargets: document.getElementById('responseTargets'),
    currentResponseLabel: document.getElementById('currentResponseLabel'),
    typedAnswer: document.getElementById('typedAnswer'),
    confirmTypedBtn: document.getElementById('confirmTypedBtn'),
    answerConfirmation: document.getElementById('answerConfirmation'),
    confirmationTitle: document.getElementById('confirmationTitle'),
    proposedAnswer: document.getElementById('proposedAnswer'),
    editAnswerBtn: document.getElementById('editAnswerBtn'),
    rejectAnswerBtn: document.getElementById('rejectAnswerBtn'),
    confirmAnswerBtn: document.getElementById('confirmAnswerBtn'),
    writeConfirmation: document.getElementById('writeConfirmation'),
    writeTitle: document.getElementById('writeTitle'),
    writeDestination: document.getElementById('writeDestination'),
    confirmedAnswerPreview: document.getElementById('confirmedAnswerPreview'),
    changeConfirmedAnswerBtn: document.getElementById('changeConfirmedAnswerBtn'),
    writeConfirmedAnswerBtn: document.getElementById('writeConfirmedAnswerBtn'),
    placementSummary: document.getElementById('placementSummary'),
    returnToWorksheetBtn: document.getElementById('returnToWorksheetBtn'),
    notice: document.getElementById('notice'),
    keyboardFallback: document.getElementById('keyboardFallback'),
    micBtn: document.getElementById('micBtn'),
    interruptBtn: document.getElementById('interruptBtn'),
    transcript: document.getElementById('transcript')
  };

  const state = {
    workspace: 'empty',
    voice: 'unavailable',
    assignmentId: null,
    title: '',
    parseStatus: '',
    filename: '',
    pageCount: 1,
    document: null,
    tasks: [],
    responseTargetsById: Object.create(null),
    responseStates: Object.create(null),
    activeTaskId: null,
    activeResponseRegionId: null,
    proposedResponseRegionId: null,
    lastFile: null,
    assignmentCapability: null,
    sessionId: null,
    sessionSecret: null,
    liveSession: null,
    conversation: [],
    writeInProgress: false,
    lastExportVoiceNorm: ''
  };

  let worksheet;
  let voiceTransport = VoiceLiveTransport.create();
  let mediaStream = null;
  let intentionalVoiceStop = false;
  let voiceReconnectAttempts = 0;
  let voiceConnectGeneration = 0;
  let voiceReconnectTimer = null;
  let voiceReconnectInFlight = false;
  let suppressPlaybackUntilTurnComplete = false;
  let activeClarosMessage = null;
  let userPartialElement = null;
  let userPartialText = '';
  let userTranscriptBuffer = '';
  let clarosOutputBuffer = '';
  let transcriptPinned = true;
  let processingTimer = null;

  function setWorkspaceState(next) {
    state.workspace = next;
    const model = UiState.getWorkspaceModel(next, { hasAssignment: !!state.assignmentId });
    document.body.dataset.workspaceState = next;
    elements.setupMode.hidden = !model.showSetup;
    elements.workspaceMode.hidden = !model.showWorkspace;
    elements.startCard.hidden = next !== 'empty';
    elements.processingPanel.hidden = !['uploading', 'parsing', 'error'].includes(next);
    elements.processingActions.hidden = next !== 'error';
    elements.processingTitle.textContent = model.title;
    elements.workspaceStatus.textContent = model.title + '. ' + model.description;
    elements.exportBtn.disabled = !model.canExport;
    elements.exportBtn.textContent = model.exportLabel;
    if (elements.layoutReviewNotice) {
      elements.layoutReviewNotice.hidden = !model.showLayoutReview;
    }
    if (next === 'error') elements.processingPanel.focus?.();
  }

  function setSessionPanelExpanded(expanded) {
    elements.sessionPanel.classList.toggle('is-expanded', expanded);
    elements.voicePanelToggle.setAttribute('aria-expanded', String(expanded));
    elements.voicePanelToggle.setAttribute(
      'aria-label',
      expanded ? 'Collapse Claros panel' : 'Expand Claros panel'
    );
  }

  function setVoiceState(next) {
    state.voice = next;
    const model = UiState.getVoiceModel(next, {
      hasAssignment: !!state.assignmentId,
      liveSession: !!state.liveSession
    });
    document.body.dataset.voiceState = next;
    elements.status.className = 'status-bar ' + next;
    elements.statusLabel.textContent = model.title;
    elements.statusDescription.textContent = model.description;
    elements.voiceBadge.textContent = model.badge;
    elements.sessionPanel.classList.toggle('is-live', model.isLive);
    elements.interruptBtn.classList.toggle('visible', model.showInterrupt);
    elements.micBtn.textContent = model.primaryLabel;
    elements.micBtn.disabled = model.primaryDisabled;
    elements.micBtn.title = model.disabledReason;
    elements.micBtn.setAttribute('aria-describedby', model.disabledReason ? 'statusDescription' : '');
    elements.answerConfirmation.hidden = !model.showConfirmation;
    elements.writeConfirmation.hidden = !model.showWriteConfirmation;
    elements.returnToWorksheetBtn.hidden = !(model.showConfirmation || model.showWriteConfirmation);
    if (model.showConfirmation || model.showWriteConfirmation || next === 'writing') {
      setSessionPanelExpanded(true);
      if (window.matchMedia('(max-width: 760px)').matches && (model.showConfirmation || model.showWriteConfirmation)) {
        window.setTimeout(function () {
          (model.showWriteConfirmation ? elements.writeTitle : elements.confirmationTitle).focus();
        }, 0);
      }
    }
  }

  function setNotice(message) {
    elements.notice.textContent = message || '';
    elements.notice.classList.remove('is-error');
  }

  function setError(message) {
    const text = message || '';
    elements.errors.textContent = text;
    if (elements.workspaceErrors) {
      elements.workspaceErrors.textContent = text;
      elements.workspaceErrors.hidden = !text;
    }
    if (text && state.workspace === 'ready') {
      elements.notice.textContent = text;
      elements.notice.classList.add('is-error');
    } else if (!text) {
      elements.notice.classList.remove('is-error');
    }
  }

  function applyTypedDraft(text) {
    const cleaned = text == null ? '' : String(text);
    elements.typedAnswer.textContent = cleaned;
    const target = getResponseTarget(state.activeResponseRegionId);
    if (!target) {
      elements.confirmTypedBtn.disabled = !cleaned.trim();
      return;
    }
    const responseState = responseStateFor(target.id);
    responseState.draft = cleaned;
    elements.confirmTypedBtn.disabled = !cleaned.trim();
    if (responseState.confirmed) {
      responseState.writeToken = '';
      responseState.confirmed = false;
      state.proposedResponseRegionId = target.id;
      elements.proposedAnswer.textContent = cleaned;
      if (elements.confirmedAnswerPreview) elements.confirmedAnswerPreview.textContent = '';
      setVoiceState('answer_detected');
      setNotice('Draft changed. Review it again before writing.');
    }
    syncWorksheetResponseState(target.id);
    refreshActiveProgress();
  }

  function setProcessingStep(index) {
    document.querySelectorAll('[data-processing-step]').forEach(function (item, itemIndex) {
      item.classList.toggle('is-complete', itemIndex < index);
      item.classList.toggle('is-active', itemIndex === index);
    });
  }

  function startProcessingProgress() {
    let index = 0;
    setProcessingStep(index);
    clearInterval(processingTimer);
    processingTimer = setInterval(function () {
      index = Math.min(3, index + 1);
      setProcessingStep(index);
    }, 800);
  }

  function finishProcessingProgress() {
    clearInterval(processingTimer);
    processingTimer = null;
    document.querySelectorAll('[data-processing-step]').forEach(function (item) {
      item.classList.remove('is-active');
      item.classList.add('is-complete');
    });
  }

  function sameId(left, right) {
    return left != null && right != null && String(left) === String(right);
  }

  function getTask(taskId) {
    return WorksheetView.findTask(state.document, taskId);
  }

  function getResponseTarget(responseRegionId) {
    return WorksheetView.findResponseTarget(state.document, responseRegionId);
  }

  function taskTargets(task) {
    return WorksheetView.taskTargets(state.document, task);
  }

  function defaultResponseTarget(task) {
    return WorksheetView.defaultResponseTarget(state.document, task);
  }

  function taskLabel(task) {
    return WorksheetView.displayTaskLabel(task);
  }

  function targetLabel(target, task) {
    return WorksheetView.displayTargetLabel(target, task);
  }

  function responseStateFor(responseRegionId) {
    const key = String(responseRegionId);
    if (!state.responseStates[key]) {
      state.responseStates[key] = {
        draft: '',
        confirmed: false,
        writeToken: '',
        written: ''
      };
    }
    return state.responseStates[key];
  }

  function syncWorksheetResponseState(responseRegionId) {
    if (worksheet) worksheet.updateResponseState(responseRegionId, responseStateFor(responseRegionId));
  }

  function unresolvedTasks() {
    return state.tasks.filter(function (task) {
      return taskTargets(task).some(function (target) { return !target.canWrite; });
    });
  }

  function targetPlacementText(target) {
    if (!target) return 'No response destination is available';
    if (target.safeForWrite) return 'Safe answer area';
    if (target.useSidePanel) return 'Side-panel answer';
    return 'Placement needs review';
  }

  function responseProgressLabel(responseState) {
    if (!responseState) return 'Not started';
    if ((responseState.written || '').trim()) return 'Written';
    if (responseState.confirmed) return 'Confirmed';
    if ((responseState.draft || '').trim()) return 'Draft';
    return 'Not started';
  }

  function taskProgressLabel(task) {
    const targets = taskTargets(task);
    if (!targets.length) return 'No destination';
    if (targets.some(function (target) { return !target.canWrite; })) return 'Needs review';
    if (targets.every(function (target) {
      return !!((responseStateFor(target.id).written || '').trim());
    })) return 'Written';
    if (targets.some(function (target) {
      return responseStateFor(target.id).confirmed || !!(responseStateFor(target.id).written || '').trim() || !!(responseStateFor(target.id).draft || '').trim();
    })) return 'In progress';
    if (targets.some(function (target) { return target.useSidePanel; })) return 'Side panel';
    return 'Ready';
  }

  function renderTaskChoices(task) {
    if (!elements.taskChoices) return;
    elements.taskChoices.replaceChildren();
    const choices = task && Array.isArray(task.choices) ? task.choices : [];
    if (!choices.length) {
      elements.taskChoices.hidden = true;
      return;
    }
    choices.forEach(function (choice) {
      const item = document.createElement('li');
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'task-choice-btn';
      const label = choice && (choice.label || choice.id) ? String(choice.label || choice.id) : '';
      const text = choice && choice.text != null ? String(choice.text) : '';
      const display = label ? (label + '. ' + text) : text;
      button.textContent = display;
      button.setAttribute('aria-label', 'Use choice ' + (display || 'option'));
      button.addEventListener('click', function () {
        applyTypedDraft(text || display);
        setSessionPanelExpanded(true);
        elements.typedAnswer.focus();
        setNotice('Choice placed in the draft. Review it before confirming.');
      });
      item.appendChild(button);
      elements.taskChoices.appendChild(item);
    });
    elements.taskChoices.hidden = false;
  }

  function renderAnswerProgress(task, target) {
    if (!elements.answerProgress) return;
    if (!task || !target) {
      elements.answerProgress.textContent = 'Select a task to begin.';
      return;
    }
    const responseState = responseStateFor(target.id);
    const progress = responseProgressLabel(responseState);
    let nextStep = 'Type or use voice, then review the exact answer.';
    if (progress === 'Draft') nextStep = 'Review and confirm this exact draft before writing.';
    else if (progress === 'Confirmed') {
      nextStep = target.canWrite
        ? 'Choose Write confirmed answer, or change the answer first.'
        : 'This destination is not safe to write. Claros will keep the confirmed answer for the export side panel path, or you can change the answer.';
    } else if (progress === 'Written') nextStep = 'This response is authorized. Continue another task or export when ready.';
    elements.answerProgress.textContent = targetLabel(target, task) + ': ' + progress + '. ' + nextStep;
  }

  function refreshActiveProgress() {
    const task = getTask(state.activeTaskId);
    const target = getResponseTarget(state.activeResponseRegionId);
    renderAnswerProgress(task, target);
    renderQuestionPicker();
    if (task) renderResponseTargetPicker(task);
  }

  function renderQuestionPicker() {
    elements.questionsContainer.replaceChildren();
    state.tasks.forEach(function (task) {
      const row = document.createElement('div');
      row.className = 'question-choice';
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.taskId = task.id;
      button.textContent = 'Question ' + taskLabel(task);
      const progress = taskProgressLabel(task);
      const targets = taskTargets(task);
      const placementText = targets.some(function (target) { return !target.canWrite; })
        ? 'One or more response locations need review'
        : (targets.some(function (target) { return target.useSidePanel; })
          ? 'Includes a side-panel answer'
          : 'Response destinations ready');
      button.setAttribute('aria-label', 'Question ' + taskLabel(task) + '. ' + progress + '. ' + placementText);
      button.setAttribute('aria-current', String(sameId(task.id, state.activeTaskId)));
      button.addEventListener('click', function () {
        selectTask(task.id);
        elements.questionsContainer.hidden = true;
      });
      row.appendChild(button);
      const placement = document.createElement('span');
      const progressClass = progress === 'Written'
        ? 'written'
        : (progress === 'In progress' || progress === 'Confirmed' || progress === 'Draft'
          ? 'in_progress'
          : (progress === 'Needs review' ? 'missing' : (progress === 'Side panel' ? 'side_panel' : 'approved')));
      placement.className = 'question-placement ' + progressClass;
      placement.textContent = progress;
      row.appendChild(placement);
      elements.questionsContainer.appendChild(row);
    });
  }

  function renderResponseTargetPicker(task) {
    elements.responseTargets.replaceChildren();
    const targets = taskTargets(task);
    if (targets.length <= 1) return;
    targets.forEach(function (target) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'response-target';
      if (target.useSidePanel) button.classList.add('is-side-panel');
      if (!target.canWrite) button.classList.add('is-unavailable');
      const label = targetLabel(target, task);
      const progress = responseProgressLabel(responseStateFor(target.id));
      button.textContent = label + ' — ' + targetPlacementText(target) + ' (' + progress + ')';
      button.dataset.taskId = task.id;
      button.dataset.responseRegionId = target.id;
      button.setAttribute('aria-current', String(sameId(target.id, state.activeResponseRegionId)));
      button.setAttribute('aria-label', label + '. ' + targetPlacementText(target) + '. ' + progress);
      button.addEventListener('click', function () {
        selectResponseTarget(task.id, target.id);
      });
      elements.responseTargets.appendChild(button);
    });
  }

  function selectTask(taskId) {
    const task = getTask(taskId);
    if (!task) return;
    const selected = getResponseTarget(state.activeResponseRegionId);
    const defaultTarget = defaultResponseTarget(task);
    const targetId = selected && sameId(selected.taskId, task.id)
      ? selected.id
      : (defaultTarget && defaultTarget.id);
    if (targetId) selectResponseTarget(task.id, targetId);
  }

  function selectResponseTarget(taskId, responseRegionId, options) {
    const task = getTask(taskId);
    const target = getResponseTarget(responseRegionId);
    if (!task || !target || !sameId(target.taskId, task.id)) return;
    const responseState = responseStateFor(target.id);
    state.activeTaskId = task.id;
    state.activeResponseRegionId = target.id;
    if (!options || !options.preserveConfirmation) {
      state.proposedResponseRegionId = responseState.confirmed && !(responseState.written || '').trim()
        ? target.id
        : null;
    }
    elements.currentQuestionLabel.textContent = 'Working on Question ' + taskLabel(task);
    elements.currentQuestionExcerpt.textContent = task.promptText || '';
    renderTaskChoices(task);
    elements.currentResponseLabel.textContent = targetLabel(target, task) + ': ' + targetPlacementText(target);
    elements.typedAnswer.setAttribute('aria-label', 'Draft ' + targetLabel(target, task) + ' for Question ' + taskLabel(task));
    elements.typedAnswer.textContent = responseState.draft || responseState.written || '';
    elements.confirmTypedBtn.disabled = !elements.typedAnswer.textContent.trim();
    if (elements.confirmedAnswerPreview && responseState.confirmed) {
      elements.confirmedAnswerPreview.textContent = responseState.draft || responseState.written || '';
    } else if (elements.confirmedAnswerPreview) {
      elements.confirmedAnswerPreview.textContent = '';
    }
    renderPlacementSummary(task, target);
    renderAnswerProgress(task, target);
    setWriteDestination(task, target);
    renderResponseTargetPicker(task);
    if (worksheet) worksheet.setActiveTarget(task.id, target.id);
    renderQuestionPicker();
    if (!options || !options.preserveVoice) {
      if (responseState.confirmed && !(responseState.written || '').trim()) {
        setVoiceState('confirmed');
      } else if (state.voice === 'answer_detected' || state.voice === 'confirming' || state.voice === 'confirmed') {
        setVoiceState(state.liveSession ? 'listening' : 'idle');
      }
    }
    persistSessionLocally();
  }

  function renderPlacementSummary(task, target) {
    if (!target || target.useSidePanel) {
      elements.placementSummary.className = 'placement-summary side-panel';
      elements.placementSummary.textContent = 'Side panel: Claros adds this response to the export side panel. The original page stays unchanged.';
      return;
    }
    if (!target.safeForWrite) {
      elements.placementSummary.className = 'placement-summary needs-review';
      elements.placementSummary.textContent = 'Needs layout review: writing stays disabled until this response destination is processed safely.';
      return;
    }
    elements.placementSummary.className = 'placement-summary answer-line';
    elements.placementSummary.textContent = 'Answer area: Claros can write a confirmed response to this selected destination.';
  }

  function setWriteDestination(task, target) {
    const unavailable = !task || !target || !target.canWrite;
    elements.writeConfirmedAnswerBtn.disabled = unavailable;
    if (target && target.useSidePanel) {
      elements.writeDestination.textContent = 'This will be added to the clearly labeled export side panel. The original worksheet page will not change.';
    } else if (unavailable) {
      elements.writeDestination.textContent = 'This response destination needs layout review before it can be written. Your confirmed answer remains a draft.';
    } else {
      elements.writeDestination.textContent = 'This will be written to the selected response area on the worksheet.';
    }
  }

  function renderLayoutState() {
    renderQuestionPicker();
    const task = getTask(state.activeTaskId);
    if (task) renderResponseTargetPicker(task);
  }

  function initializeWorksheet() {
    worksheet = WorksheetView.create({
      container: elements.documentViewport,
      pageImage: elements.pageImage,
      overlayLayer: elements.answerOverlayLayer,
      pageLabel: elements.pageLabel,
      zoomLabel: elements.zoomLabel,
      fitWidthBtn: elements.fitWidthBtn,
      onSelectTarget: function (taskId, responseRegionId) {
        selectResponseTarget(taskId, responseRegionId);
      },
    });
    worksheet.load({
      assignmentId: state.assignmentId,
      assignmentCapability: state.assignmentCapability,
      document: state.document,
      pageCount: state.pageCount,
      responseStates: state.responseStates,
      activeTaskId: state.activeTaskId,
      activeResponseRegionId: state.activeResponseRegionId
    });
  }

  function applyDocumentPayload(data, preserveResponseStates) {
    const previousStates = state.responseStates;
    state.document = WorksheetView.normalizeDocument({
      document: data.document,
      questions: data.questions,
      pages: data.pages,
      pageCount: data.page_count || data.pageCount
    });
    state.tasks = state.document.tasks;
    state.responseTargetsById = state.document.responseTargetsById;
    state.pageCount = Number(data.page_count || data.pageCount || state.document.pageCount || 1);
    const nextStates = Object.create(null);
    if (preserveResponseStates) {
      state.document.responseTargets.forEach(function (target) {
        const previous = previousStates[String(target.id)];
        if (previous) nextStates[String(target.id)] = previous;
      });
    }
    state.responseStates = nextStates;
    const firstTask = state.tasks[0] || null;
    const activeTask = getTask(state.activeTaskId) || firstTask;
    const activeTarget = getResponseTarget(state.activeResponseRegionId);
    const selectedTarget = activeTarget && activeTask && sameId(activeTarget.taskId, activeTask.id)
      ? activeTarget
      : defaultResponseTarget(activeTask);
    state.activeTaskId = activeTask ? activeTask.id : null;
    state.activeResponseRegionId = selectedTarget ? selectedTarget.id : null;
  }

  function reloadWorksheetFromState() {
    if (!worksheet) return;
    worksheet.load({
      assignmentId: state.assignmentId,
      assignmentCapability: state.assignmentCapability,
      document: state.document,
      pageCount: state.pageCount,
      responseStates: state.responseStates,
      activeTaskId: state.activeTaskId,
      activeResponseRegionId: state.activeResponseRegionId
    });
  }

  function applyAssignment(data) {
    clearAssignmentSessionState();
    state.assignmentId = data.assignment_id;
    state.assignmentCapability = data.assignment_capability || null;
    state.title = data.title || state.filename || 'Worksheet';
    state.parseStatus = data.parse_status || 'ok';
    applyDocumentPayload(data, false);
    persistSessionLocally();
    elements.assignmentTitle.textContent = state.filename || state.title;
    elements.demoReplayIndicator.hidden = data.parser !== 'offline-synthetic-fixture-v1';
    elements.previousPageBtn.disabled = state.pageCount <= 1;
    elements.nextPageBtn.disabled = state.pageCount <= 1;
    initializeWorksheet();
    renderQuestionPicker();
    if (state.activeTaskId != null && state.activeResponseRegionId != null) {
      selectResponseTarget(state.activeTaskId, state.activeResponseRegionId, { preserveVoice: true });
    }
    const rejected = state.parseStatus === 'requires_ocr' || state.parseStatus === 'unsupported_layout';
    setWorkspaceState(rejected || unresolvedTasks().length ? 'needs_layout_review' : 'ready');
    setVoiceState(rejected ? 'unavailable' : 'idle');
    if (state.parseStatus === 'requires_ocr') {
      setError('This PDF needs OCR before Claros can identify questions.');
    } else if (state.parseStatus === 'unsupported_layout') {
      setError('Claros could not safely identify a supported student worksheet layout.');
    }
    renderLayoutState();
    restoreSessionFromStorage();
  }

  async function doUpload(file) {
    if (!file) return;
    if (state.assignmentId || state.sessionId || state.sessionSecret) clearAssignmentSessionState();
    state.lastFile = file;
    state.filename = file.name;
    elements.selectedFilename.textContent = file.name;
    elements.uploadLabel.textContent = file.name;
    setSampleButtonsDisabled(true);
    elements.uploadBtn.disabled = true;
    setError('');
    setNotice('');
    setWorkspaceState('uploading');
    startProcessingProgress();
    const form = new FormData();
    form.append('file', file);
    try {
      const response = await fetch('/upload?review_mode=direct', { method: 'POST', body: form });
      setWorkspaceState('parsing');
      if (!response.ok) {
        const detail = await response.json().catch(function () { return {}; });
        throw new Error(detail.detail || detail.error || 'The PDF could not be prepared.');
      }
      const data = await response.json();
      finishProcessingProgress();
      applyAssignment(data);
      setNotice('Worksheet ready. The microphone is still off.');
    } catch (error) {
      clearInterval(processingTimer);
      processingTimer = null;
      setWorkspaceState('error');
      setError(error.message || 'We could not read this PDF. Retry or choose a different file.');
    } finally {
      setSampleButtonsDisabled(false);
      elements.uploadBtn.disabled = false;
    }
  }

  function setSampleButtonsDisabled(disabled) {
    const buttons = elements.sampleChooserActions
      ? elements.sampleChooserActions.querySelectorAll('.sample-choice')
      : [];
    buttons.forEach(function (button) { button.disabled = disabled; });
  }

  async function loadSamplePdf(sampleId) {
    setError('');
    const aliases = {
      '1': 'canonical-short-answer-ecosystems',
      default: 'canonical-short-answer-ecosystems',
      true: 'canonical-short-answer-ecosystems'
    };
    const requestedId = aliases[String(sampleId || '').trim()] || sampleId || 'canonical-short-answer-ecosystems';
    try {
      const catalogResponse = await fetch(API_BASE + '/api/samples');
      if (!catalogResponse.ok) throw new Error('The sample catalog is unavailable.');
      const catalog = await catalogResponse.json();
      const sample = (catalog.samples || []).find(function (entry) {
        return entry.id === requestedId;
      }) || (catalog.samples || [])[0];
      if (!sample) throw new Error('No official sample worksheets are configured.');
      const response = await fetch(sample.pdf_url);
      if (!response.ok) throw new Error('The sample worksheet is unavailable.');
      const blob = await response.blob();
      const filename = 'Claros sample — ' + sample.sample_name + '.pdf';
      await doUpload(new File([blob], filename, { type: 'application/pdf' }));
    } catch (error) {
      setWorkspaceState('error');
      setError(error.message || 'The sample worksheet could not be loaded.');
    }
  }

  function resetWorkspace() {
    clearAssignmentSessionState();
    state.assignmentId = null;
    state.document = null;
    state.tasks = [];
    state.responseTargetsById = Object.create(null);
    state.responseStates = Object.create(null);
    state.activeTaskId = null;
    state.activeResponseRegionId = null;
    worksheet = null;
    elements.fileInput.value = '';
    elements.uploadLabel.textContent = 'Choose a worksheet PDF';
    setError('');
    setNotice('');
    setWorkspaceState('empty');
    setVoiceState('unavailable');
  }

  function clearAssignmentSessionState() {
    stopSession();
    state.sessionId = null;
    state.sessionSecret = null;
    state.assignmentCapability = null;
    state.liveSession = null;
    state.conversation = [];
    state.responseStates = Object.create(null);
    state.proposedResponseRegionId = null;
    state.lastExportVoiceNorm = '';
    try { sessionStorage.removeItem(SESSION_STORAGE_KEY); } catch (_) {}
  }

  function assignmentHeaders() {
    return state.assignmentCapability ? { 'X-Assignment-Capability': state.assignmentCapability } : {};
  }

  function persistSessionLocally() {
    if (!state.assignmentId || !state.assignmentCapability) return;
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
        assignmentId: state.assignmentId,
        sessionId: state.sessionId || null,
        sessionSecret: state.sessionSecret || null,
        assignmentCapability: state.assignmentCapability,
        activeTaskId: state.activeTaskId || null,
        activeResponseRegionId: state.activeResponseRegionId || null
      }));
    } catch (_) {}
  }

  async function ensureServerSession() {
    if (state.sessionId && state.sessionSecret && state.assignmentCapability) return;
    const response = await fetch(API_BASE + '/api/session/start', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, assignmentHeaders()),
      body: JSON.stringify({ assignment_id: state.assignmentId })
    });
    if (!response.ok) throw new Error('Could not start the worksheet session.');
    const data = await response.json();
    state.sessionId = data.session_id;
    state.sessionSecret = data.session_secret;
    if (data.document) {
      applyDocumentPayload(data, true);
      reloadWorksheetFromState();
    }
    persistSessionLocally();
  }

  function restoreResponseState(responseRegionId, restored) {
    const target = getResponseTarget(responseRegionId);
    if (!target || !restored || typeof restored !== 'object') return false;
    const responseState = responseStateFor(target.id);
    const confirmedAnswer = typeof restored.confirmed_answer === 'string'
      ? restored.confirmed_answer
      : (typeof restored.draft_answer === 'string' ? restored.draft_answer : null);
    if (restored.confirmed && confirmedAnswer != null) {
      responseState.confirmed = true;
      responseState.draft = confirmedAnswer;
    }
    if (typeof restored.written_answer === 'string') {
      responseState.written = restored.written_answer;
      if (!responseState.draft) responseState.draft = restored.written_answer;
    }
    if (typeof restored.write_token === 'string' && restored.write_token) {
      responseState.writeToken = restored.write_token;
    } else if (responseState.confirmed && !(responseState.written || '').trim()) {
      responseState.writeToken = responseState.writeToken || '';
    }
    syncWorksheetResponseState(target.id);
    return true;
  }

  async function reauthorizeWriteToken(task, target) {
    if (!state.sessionId || !state.sessionSecret || !task || !target) return '';
    const payload = {
      session_secret: state.sessionSecret,
      task_id: task.id,
      response_region_id: target.id
    };
    if (task.legacyQuestionId != null) payload.question_id = task.legacyQuestionId;
    const response = await fetch(API_BASE + '/api/session/' + state.sessionId + '/reauthorize-write', {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, assignmentHeaders()),
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      const detail = await response.json().catch(function () { return {}; });
      throw new Error(detail.detail || 'Could not restore write authorization.');
    }
    const data = await response.json();
    const responseState = responseStateFor(target.id);
    responseState.confirmed = true;
    if (typeof data.answer_text === 'string' && data.answer_text) {
      responseState.draft = data.answer_text;
    }
    if (data.written) {
      responseState.written = data.answer_text || responseState.written || responseState.draft;
      responseState.writeToken = '';
    } else {
      responseState.writeToken = data.write_token || '';
    }
    syncWorksheetResponseState(target.id);
    return responseState.writeToken || '';
  }

  async function restoreSessionFromStorage() {
    try {
      const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (!raw || !state.assignmentId) return;
      const saved = JSON.parse(raw);
      if (saved.assignmentId !== state.assignmentId || !saved.assignmentCapability || saved.assignmentCapability !== state.assignmentCapability) {
        clearAssignmentSessionState();
        return;
      }
      state.sessionId = saved.sessionId;
      state.sessionSecret = saved.sessionSecret;
      if (!state.sessionId || !state.sessionSecret) return;
      let response = await fetch(API_BASE + '/api/session/' + saved.sessionId + '/restore', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, assignmentHeaders()),
        body: JSON.stringify({ session_secret: saved.sessionSecret })
      });
      if (response.status === 409) {
        // Concurrent confirm/write can race restore persistence; retry once.
        response = await fetch(API_BASE + '/api/session/' + saved.sessionId + '/restore', {
          method: 'POST',
          headers: Object.assign({ 'Content-Type': 'application/json' }, assignmentHeaders()),
          body: JSON.stringify({ session_secret: saved.sessionSecret })
        });
      }
      if (!response.ok) {
        if (response.status === 403 || response.status === 404 || response.status === 410) {
          clearAssignmentSessionState();
        } else {
          setNotice('Could not restore confirmed answers yet. Refresh again if needed.');
        }
        return;
      }
      const data = await response.json();
      if (data.document) {
        applyDocumentPayload(data, true);
        reloadWorksheetFromState();
      }
      let restoredAny = false;
      const responseStates = data.response_states || data.responses || data.response_targets || {};
      Object.keys(responseStates).forEach(function (responseRegionId) {
        restoredAny = restoreResponseState(responseRegionId, responseStates[responseRegionId]) || restoredAny;
      });
      Object.keys(data.questions || {}).forEach(function (legacyQuestionId) {
        const task = state.tasks.find(function (item) {
          return sameId(item.legacyQuestionId, legacyQuestionId);
        });
        const target = defaultResponseTarget(task);
        if (target) restoredAny = restoreResponseState(target.id, data.questions[legacyQuestionId]) || restoredAny;
      });
      if (saved.activeTaskId) state.activeTaskId = saved.activeTaskId;
      if (saved.activeResponseRegionId) state.activeResponseRegionId = saved.activeResponseRegionId;
      if (restoredAny) {
        const task = getTask(state.activeTaskId) || state.tasks[0];
        const preferredTargetId = state.activeResponseRegionId
          || (task && defaultResponseTarget(task) && defaultResponseTarget(task).id);
        if (task && preferredTargetId) {
          selectResponseTarget(task.id, preferredTargetId, { preserveVoice: true, preserveConfirmation: true });
        }
        const needsWrite = state.document && state.document.responseTargets.some(function (target) {
          const responseState = state.responseStates[String(target.id)];
          return !!(responseState && responseState.confirmed && !(responseState.written || '').trim());
        });
        setNotice(needsWrite
          ? 'Confirmed answers from this session were restored. Choose Write confirmed answer when you are ready.'
          : 'Confirmed answers from this session were restored.');
        persistSessionLocally();
      }
    } catch (_) {}
  }

  function presentAnswer(responseRegionId, text) {
    const cleaned = text || '';
    const target = getResponseTarget(responseRegionId);
    const task = target && getTask(target.taskId);
    if (!task || !target || !cleaned.trim()) return;
    const responseState = responseStateFor(target.id);
    responseState.writeToken = '';
    responseState.confirmed = false;
    responseState.draft = cleaned;
    state.proposedResponseRegionId = target.id;
    selectResponseTarget(task.id, target.id, { preserveConfirmation: true, preserveVoice: true });
    elements.typedAnswer.textContent = cleaned;
    elements.proposedAnswer.textContent = cleaned;
    elements.confirmationTitle.textContent = 'Confirm ' + targetLabel(target, task) + ' for Question ' + taskLabel(task);
    setVoiceState('answer_detected');
    setNotice('Review the proposed answer. Nothing has been written yet.');
    refreshActiveProgress();
  }

  function dismissAnswer(clearText) {
    if (clearText && state.proposedResponseRegionId != null) {
      const responseState = responseStateFor(state.proposedResponseRegionId);
      responseState.draft = '';
      responseState.writeToken = '';
      responseState.confirmed = false;
      syncWorksheetResponseState(state.proposedResponseRegionId);
      elements.typedAnswer.textContent = '';
    }
    state.proposedResponseRegionId = null;
    setVoiceState(state.liveSession ? 'listening' : 'idle');
    refreshActiveProgress();
    elements.typedAnswer.focus();
  }

  async function confirmProposedAnswer() {
    const responseRegionId = state.proposedResponseRegionId;
    const target = getResponseTarget(responseRegionId);
    const task = target && getTask(target.taskId);
    const responseState = target && responseStateFor(target.id);
    const text = responseState && responseState.draft !== '' ? responseState.draft : (elements.typedAnswer.textContent || '');
    if (!task || !target || !text.trim()) {
      setError('Add an answer before confirming it.');
      return;
    }
    setVoiceState('confirming');
    elements.confirmAnswerBtn.disabled = true;
    try {
      await ensureServerSession();
      const payload = {
        session_secret: state.sessionSecret,
        task_id: task.id,
        response_region_id: target.id,
        answer_text: text
      };
      if (task.legacyQuestionId != null) payload.question_id = task.legacyQuestionId;
      const response = await fetch(API_BASE + '/api/session/' + state.sessionId + '/confirm', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, assignmentHeaders()),
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const detail = await response.json().catch(function () { return {}; });
        throw new Error(detail.detail || 'The answer could not be confirmed.');
      }
      const data = await response.json();
      responseState.confirmed = true;
      responseState.draft = text;
      responseState.writeToken = data.write_token;
      state.proposedResponseRegionId = target.id;
      if (elements.confirmedAnswerPreview) elements.confirmedAnswerPreview.textContent = text;
      syncWorksheetResponseState(target.id);
      setError('');
      setWriteDestination(task, target);
      renderAnswerProgress(task, target);
      renderQuestionPicker();
      setVoiceState('confirmed');
      setNotice('Answer confirmed. Choose Write confirmed answer when you are ready.');
    } catch (error) {
      setError(error.message || 'The answer could not be confirmed.');
      setVoiceState('confirming');
    } finally {
      elements.confirmAnswerBtn.disabled = false;
    }
  }

  async function triggerWrite(responseRegionId) {
    if (state.writeInProgress) return;
    const target = getResponseTarget(responseRegionId);
    const task = target && getTask(target.taskId);
    if (!task || !target || !target.canWrite) {
      setWorkspaceState('needs_layout_review');
      setError('This task does not have a safe answer destination yet.');
      return;
    }
    const responseState = responseStateFor(target.id);
    if (!responseState.confirmed) {
      presentAnswer(target.id, responseState.draft || '');
      setNotice('Confirm this answer before choosing to write it.');
      return;
    }
    if (!responseState.writeToken && !(responseState.written || '').trim()) {
      try {
        await reauthorizeWriteToken(task, target);
      } catch (error) {
        presentAnswer(target.id, responseState.draft || '');
        setError(error.message || 'Confirm this answer before choosing to write it.');
        return;
      }
    }
    if (!responseState.writeToken && !(responseState.written || '').trim()) {
      presentAnswer(target.id, responseState.draft || '');
      setNotice('Confirm this answer before choosing to write it.');
      return;
    }
    state.writeInProgress = true;
    setVoiceState('writing');
    setNotice('Authorizing the confirmed ' + targetLabel(target, task).toLowerCase() + ' for Question ' + taskLabel(task) + '.');
    let written = '';
    try {
      const payload = {
        task_id: task.id,
        response_region_id: target.id,
        conversation: state.conversation,
        answer_candidate: responseState.draft || '',
        write_token: responseState.writeToken || '',
        session_id: state.sessionId,
        session_secret: state.sessionSecret
      };
      // The numeric question ID is a transitional transport field only. Client
      // state and authorization always use the canonical task/response IDs.
      if (task.legacyQuestionId != null) payload.question_id = task.legacyQuestionId;
      const response = await fetch(API_BASE + '/api/write/' + state.assignmentId, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, assignmentHeaders()),
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const detail = await response.json().catch(function () { return {}; });
        const code = detail.code || '';
        const message = detail.detail || 'The confirmed answer could not be written.';
        if (code === 'SESSION_WRITE_CONFLICT' || response.status === 409) {
          throw Object.assign(new Error(typeof message === 'string' ? message : 'Session changed. Refresh and try again.'), {
            retryable: true,
            conflict: true
          });
        }
        if (response.status === 403) {
          throw Object.assign(new Error(typeof message === 'string' ? message : 'Write authorization expired.'), {
            reauthorize: true
          });
        }
        throw new Error(typeof message === 'string' ? message : 'The confirmed answer could not be written.');
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const result = await reader.read();
        if (result.done) break;
        written += decoder.decode(result.value, { stream: true });
        responseState.written = written;
        responseState.draft = written;
        elements.typedAnswer.textContent = written;
        syncWorksheetResponseState(target.id);
      }
      responseState.writeToken = '';
      state.proposedResponseRegionId = null;
      syncWorksheetResponseState(target.id);
      persistSessionLocally();
      renderAnswerProgress(task, target);
      renderQuestionPicker();
      setNotice('Answer authorized for Question ' + taskLabel(task) + '. Export places it on the worksheet. Continue another task or export when ready.');
      elements.typedAnswer.focus();
    } catch (error) {
      // Keep server-aligned confirmation intact so retries remain possible.
      if (error && error.reauthorize) {
        responseState.writeToken = '';
        try {
          await reauthorizeWriteToken(task, target);
          setError('Write authorization was refreshed. Choose Write confirmed answer again.');
        } catch (reauthError) {
          setError(reauthError.message || error.message || 'The confirmed answer could not be written.');
        }
      } else if (error && error.conflict) {
        setError(error.message || 'Session changed. Refresh and try again.');
      } else {
        responseState.writeToken = '';
        setError(error.message || 'The confirmed answer could not be written.');
      }
      syncWorksheetResponseState(target.id);
    } finally {
      state.writeInProgress = false;
      setVoiceState(state.liveSession ? 'listening' : 'idle');
    }
  }

  function shouldAutoScrollTranscript() {
    const distance = elements.transcript.scrollHeight - elements.transcript.scrollTop - elements.transcript.clientHeight;
    return distance < 36;
  }

  function scrollTranscriptIfPinned() {
    if (transcriptPinned) elements.transcript.scrollTop = elements.transcript.scrollHeight;
  }

  function addTranscript(speaker, text) {
    if (!text || !text.trim()) return;
    if (speaker === 'claros') {
      if (!activeClarosMessage) {
        activeClarosMessage = document.createElement('div');
        activeClarosMessage.className = 'msg claros';
        const label = document.createElement('span');
        label.className = 'msg-label';
        label.textContent = 'Claros';
        activeClarosMessage.appendChild(label);
        elements.transcript.appendChild(activeClarosMessage);
      }
      activeClarosMessage.appendChild(document.createTextNode(text));
    } else {
      activeClarosMessage = null;
      const item = document.createElement('div');
      item.className = 'msg user';
      const label = document.createElement('span');
      label.className = 'msg-label';
      label.textContent = 'You';
      item.appendChild(label);
      item.appendChild(document.createTextNode(text));
      elements.transcript.appendChild(item);
    }
    scrollTranscriptIfPinned();
  }

  function showUserPartial(text) {
    userPartialText += text;
    if (!userPartialElement) {
      userPartialElement = document.createElement('div');
      userPartialElement.className = 'msg user partial';
      const label = document.createElement('span');
      label.className = 'msg-label';
      label.textContent = 'You, live';
      userPartialElement.appendChild(label);
      userPartialElement._text = document.createTextNode('');
      userPartialElement.appendChild(userPartialElement._text);
      elements.transcript.appendChild(userPartialElement);
    }
    userPartialElement._text.textContent = userPartialText;
    scrollTranscriptIfPinned();
  }

  function clearUserPartial() {
    if (userPartialElement) userPartialElement.remove();
    userPartialElement = null;
    userPartialText = '';
  }

  function applyVoiceProductEvents(events) {
    let preferredVoiceState = null;
    (events || []).forEach(function (event) {
      if (!event || !event.type) return;
      if (event.type === 'task_selected') {
        const requestedTask = state.tasks.find(function (task) {
          return String(task.legacyQuestionId || '') === String(event.legacyQuestionId);
        });
        if (requestedTask) selectTask(requestedTask.id);
        return;
      }
      if (event.type === 'answer_proposed') {
        const target = getResponseTarget(state.activeResponseRegionId);
        if (!target || !(event.text || '').trim()) return;
        const responseState = responseStateFor(target.id);
        if (responseState.confirmed || responseState.writeToken) {
          setNotice('This answer is already confirmed. Reject or edit it before proposing a new one.');
          setSessionPanelExpanded(true);
          preferredVoiceState = 'confirmed';
          return;
        }
        presentAnswer(target.id, event.text);
        preferredVoiceState = 'answer_detected';
        return;
      }
      if (event.type === 'needs_answer_before_write') {
        setNotice('State your exact answer first. Claros will not invent an answer to write.');
        setSessionPanelExpanded(true);
        return;
      }
      if (event.type === 'write_ready_notice') {
        const target = getResponseTarget(state.activeResponseRegionId);
        const responseState = target ? responseStateFor(target.id) : null;
        if (responseState && responseState.confirmed && responseState.writeToken) {
          setNotice('Your answer is confirmed. Choose Write confirmed answer to place it on the worksheet.');
          preferredVoiceState = 'confirmed';
        } else {
          setNotice('Confirm the exact answer, then choose Write confirmed answer. Voice never writes by itself.');
        }
        setSessionPanelExpanded(true);
        return;
      }
      if (event.type === 'export_requested') {
        if (event.normalized && event.normalized !== state.lastExportVoiceNorm) {
          state.lastExportVoiceNorm = event.normalized;
          performExport();
        }
      }
    });
    return preferredVoiceState;
  }

  function releaseVoiceMedia() {
    if (mediaStream) mediaStream.getTracks().forEach(function (track) { track.stop(); });
    mediaStream = null;
  }

  function showVoiceFallback(message) {
    voiceTransport.stopCapture();
    releaseVoiceMedia();
    elements.keyboardFallback.hidden = false;
    setSessionPanelExpanded(true);
    setNotice(message || 'Voice is unavailable. Continue by typing an answer.');
    setVoiceState('error');
    elements.typedAnswer.focus();
  }

  function scheduleVoiceReconnect(reason, generation) {
    if (!state.assignmentId || intentionalVoiceStop) return false;
    if (generation != null && generation !== voiceConnectGeneration) return false;
    if (voiceReconnectInFlight || state.liveSession) return false;
    if (voiceReconnectAttempts >= MAX_VOICE_RECONNECT_ATTEMPTS) return false;
    voiceReconnectAttempts += 1;
    voiceReconnectInFlight = true;
    setNotice((reason || 'Voice disconnected.') + ' Reconnecting (' + voiceReconnectAttempts + '/' + MAX_VOICE_RECONNECT_ATTEMPTS + ')…');
    setVoiceState('connecting');
    if (voiceReconnectTimer) window.clearTimeout(voiceReconnectTimer);
    voiceReconnectTimer = window.setTimeout(function () {
      voiceReconnectTimer = null;
      voiceReconnectInFlight = false;
      if (intentionalVoiceStop || !state.assignmentId) return;
      if (state.liveSession) return;
      startSession({ reconnect: true });
    }, 700 * voiceReconnectAttempts);
    return true;
  }

  function handleProviderDisconnect(session, generation, reason) {
    if (generation !== voiceConnectGeneration) return;
    if (state.liveSession && state.liveSession !== session) return;
    state.liveSession = null;
    voiceTransport.stopCapture();
    voiceTransport.closeSession(session);
    if (intentionalVoiceStop) {
      releaseVoiceMedia();
      setVoiceState(state.assignmentId ? 'stopped' : 'unavailable');
      return;
    }
    if (scheduleVoiceReconnect(reason, generation)) return;
    showVoiceFallback((reason || 'The voice connection closed.') + ' Continue by typing, or try voice again.');
  }

  async function startSession(options) {
    const reconnect = !!(options && options.reconnect);
    if (!state.assignmentId || state.liveSession || voiceReconnectInFlight && !reconnect) return;
    const connectGeneration = ++voiceConnectGeneration;
    intentionalVoiceStop = false;
    voiceReconnectInFlight = false;
    suppressPlaybackUntilTurnComplete = false;
    setError('');
    elements.keyboardFallback.hidden = true;
    setVoiceState('connecting');
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Microphone access is not available in this browser.');
      }
      if (!mediaStream || !mediaStream.active) {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            channelCount: 1
          }
        });
      }
      setNotice(reconnect ? 'Reconnecting Claros voice…' : 'Microphone access granted. Connecting Claros now.');
    } catch (error) {
      const message = error && error.name === 'NotAllowedError'
        ? 'Microphone access was denied. You can still type, confirm, and export answers.'
        : (error.message || 'The microphone is unavailable.');
      showVoiceFallback(message);
      return;
    }

    try {
      await ensureServerSession();
      if (connectGeneration !== voiceConnectGeneration || intentionalVoiceStop) return;
      const configResponse = await fetch(API_BASE + '/api/session-config/' + state.assignmentId, { headers: assignmentHeaders() });
      if (!configResponse.ok) {
        if (configResponse.status === 429) {
          throw new Error('Voice is temporarily rate-limited. Continue by typing, or try again shortly.');
        }
        throw new Error('Claros could not connect to the voice provider.');
      }
      const config = await configResponse.json();
      const module = await import(API_BASE + '/genai.bundle.js');
      const GoogleGenAI = module.GoogleGenAI || module.default;
      const client = new GoogleGenAI({ apiKey: config.token, httpOptions: { apiVersion: 'v1alpha' } });
      const session = await client.live.connect({
        model: config.model,
        config: {
          responseModalities: ['AUDIO'],
          speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Puck' } } },
          systemInstruction: { parts: [{ text: config.system_prompt || '' }] },
          inputAudioTranscription: { mode: 'ACTIVITY', interimResults: true },
          outputAudioTranscription: { mode: 'TURN_BASED' }
        },
        callbacks: {
          onmessage: function (message) {
            if (connectGeneration !== voiceConnectGeneration) return;
            if (state.liveSession && state.liveSession !== session) return;
            handleLiveMessage(message, connectGeneration);
          },
          onerror: function () {
            handleProviderDisconnect(session, connectGeneration, 'The voice connection failed.');
          },
          onclose: function () {
            handleProviderDisconnect(session, connectGeneration, 'The voice connection closed.');
          }
        }
      });
      if (connectGeneration !== voiceConnectGeneration || intentionalVoiceStop) {
        voiceTransport.closeSession(session);
        return;
      }
      state.liveSession = session;
      voiceReconnectAttempts = 0;
      voiceTransport.startCapture(mediaStream, function (audio) {
        if (connectGeneration !== voiceConnectGeneration || !state.liveSession || state.liveSession !== session) return;
        try {
          session.sendRealtimeInput({ audio: audio });
        } catch (_) {}
      });
      startMeter(mediaStream);
      setVoiceState('listening');
      setNotice(reconnect ? 'Voice reconnected. Claros is listening.' : 'Voice session started. Claros is listening.');
    } catch (error) {
      if (connectGeneration !== voiceConnectGeneration) return;
      if (!reconnect) releaseVoiceMedia();
      if (!intentionalVoiceStop && scheduleVoiceReconnect(error.message || 'Claros could not connect to the voice provider.', connectGeneration)) {
        return;
      }
      showVoiceFallback(error.message || 'Claros could not connect to the voice provider.');
    }
  }

  function handleLiveMessage(message, generation) {
    if (generation != null && generation !== voiceConnectGeneration) return;
    const content = message.serverContent;
    if (!content) return;
    if (content.inputTranscription && content.inputTranscription.text) {
      userTranscriptBuffer += content.inputTranscription.text;
      if (voiceTransport.hasScheduledPlayback() || state.voice === 'speaking') {
        voiceTransport.clearPlayback();
        suppressPlaybackUntilTurnComplete = true;
        setVoiceState('listening');
      }
      showUserPartial(content.inputTranscription.text);
    }
    if (content.outputTranscription && content.outputTranscription.text) {
      const text = content.outputTranscription.text;
      state.conversation.push({ speaker: 'claros', text: text });
      addTranscript('claros', text);
      clarosOutputBuffer = (clarosOutputBuffer + text).slice(-2000);
    }
    if (content.modelTurn && content.modelTurn.parts) {
      content.modelTurn.parts.forEach(function (part) {
        if (part.inlineData && part.inlineData.data) {
          if (suppressPlaybackUntilTurnComplete) return;
          voiceTransport.queuePcm24kChunk(part.inlineData.data);
          if (!state.writeInProgress) setVoiceState('speaking');
        }
      });
    }
    if (content.turnComplete) {
      suppressPlaybackUntilTurnComplete = false;
      const clarosText = clarosOutputBuffer;
      clarosOutputBuffer = '';
      const clarosPreferred = applyVoiceProductEvents(VoiceProductBridge.interpretClarosTurn(clarosText));

      const full = userTranscriptBuffer.trim();
      userTranscriptBuffer = '';
      clearUserPartial();
      activeClarosMessage = null;
      if (!full) {
        if (clarosPreferred) setVoiceState(clarosPreferred);
        else if (state.voice !== 'confirmed') setVoiceState('listening');
        return;
      }
      state.conversation.push({ speaker: 'user', text: full });
      addTranscript('user', full);
      const target = getResponseTarget(state.activeResponseRegionId);
      const responseState = target ? responseStateFor(target.id) : null;
      const userPreferred = applyVoiceProductEvents(VoiceProductBridge.interpretUserTurn(full, {
        draft: responseState && responseState.draft || '',
        confirmed: !!(responseState && responseState.confirmed),
        writeToken: responseState && responseState.writeToken || ''
      }));
      const preferred = userPreferred || clarosPreferred;
      if (preferred) setVoiceState(preferred);
      else if (state.voice !== 'confirmed' && state.voice !== 'answer_detected' && state.voice !== 'confirming') {
        setVoiceState('listening');
      }
    }
  }

  function stopSession(closeProvider) {
    intentionalVoiceStop = true;
    voiceConnectGeneration += 1;
    voiceReconnectAttempts = 0;
    voiceReconnectInFlight = false;
    suppressPlaybackUntilTurnComplete = false;
    if (voiceReconnectTimer) {
      window.clearTimeout(voiceReconnectTimer);
      voiceReconnectTimer = null;
    }
    const session = state.liveSession;
    state.liveSession = null;
    voiceTransport.stopCapture();
    releaseVoiceMedia();
    if (closeProvider !== false) voiceTransport.closeSession(session);
    elements.meterBar.style.width = '0%';
    clearUserPartial();
    setVoiceState(state.assignmentId ? 'stopped' : 'unavailable');
  }

  function interruptAgent() {
    if (!state.liveSession) return;
    suppressPlaybackUntilTurnComplete = true;
    voiceTransport.interruptProvider(state.liveSession);
    setVoiceState('listening');
    setNotice('Claros stopped speaking. You can continue.');
  }

  function startMeter(stream) {
    const context = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = context.createAnalyser();
    const source = context.createMediaStreamSource(stream);
    const values = new Uint8Array(analyser.frequencyBinCount);
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;
    source.connect(analyser);
    function tick() {
      if (!mediaStream || !mediaStream.active) {
        context.close();
        return;
      }
      analyser.getByteFrequencyData(values);
      const average = values.reduce(function (sum, value) { return sum + value; }, 0) / values.length;
      elements.meterBar.style.width = Math.min(100, average * 2) + '%';
      requestAnimationFrame(tick);
    }
    tick();
  }

  async function performExport() {
    if (!state.assignmentId || state.workspace === 'exporting') return;
    setWorkspaceState('exporting');
    setError('');
    const hasWrittenAnswer = state.document && state.document.responseTargets.some(function (target) {
      const responseState = state.responseStates[String(target.id)];
      return !!(responseState && responseState.confirmed && (responseState.written || '').trim());
    });
    if (!hasWrittenAnswer || !state.sessionId || !state.sessionSecret) {
      setWorkspaceState(unresolvedTasks().length ? 'needs_layout_review' : 'ready');
      setError('Confirm and write at least one answer before exporting.');
      return;
    }
    try {
      const response = await fetch('/export/' + state.assignmentId, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json' }, assignmentHeaders()),
        body: JSON.stringify({ session_id: state.sessionId, session_secret: state.sessionSecret })
      });
      if (!response.ok) throw new Error('The completed PDF could not be prepared.');
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'claros-' + state.assignmentId + '.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 0);
      setWorkspaceState('complete');
      setNotice('Export ready. Your browser downloaded the completed worksheet.');
    } catch (error) {
      setWorkspaceState(unresolvedTasks().length ? 'needs_layout_review' : 'ready');
      setError(error.message || 'The completed PDF could not be prepared.');
    }
  }

  elements.uploadBtn.addEventListener('click', function () { elements.fileInput.click(); });
  elements.uploadZone.addEventListener('click', function (event) {
    if (event.target === elements.uploadZone || event.target.closest('.upload-copy') || event.target.closest('.upload-art')) {
      elements.fileInput.click();
    }
  });
  elements.uploadZone.addEventListener('dragover', function (event) {
    event.preventDefault();
    elements.uploadZone.classList.add('hover');
  });
  elements.uploadZone.addEventListener('dragleave', function () { elements.uploadZone.classList.remove('hover'); });
  elements.uploadZone.addEventListener('drop', function (event) {
    event.preventDefault();
    elements.uploadZone.classList.remove('hover');
    const file = event.dataTransfer.files[0];
    if (file && file.name.toLowerCase().endsWith('.pdf')) doUpload(file);
    else setError('Choose a PDF file.');
  });
  elements.fileInput.addEventListener('change', function () { doUpload(elements.fileInput.files[0]); });
  if (elements.sampleChooserActions) {
    elements.sampleChooserActions.addEventListener('click', function (event) {
      const button = event.target.closest('.sample-choice');
      if (!button) return;
      loadSamplePdf(button.getAttribute('data-sample-id'));
    });
  }
  elements.retryBtn.addEventListener('click', function () { doUpload(state.lastFile); });
  elements.replaceBtn.addEventListener('click', function () { elements.fileInput.click(); });
  elements.replaceWorksheetBtn.addEventListener('click', resetWorkspace);
  elements.exportBtn.addEventListener('click', performExport);
  elements.previousPageBtn.addEventListener('click', function () {
    worksheet.setPage(worksheet.getState().currentPage - 1);
  });
  elements.nextPageBtn.addEventListener('click', function () {
    worksheet.setPage(worksheet.getState().currentPage + 1);
  });
  elements.fitWidthBtn.addEventListener('click', function () { worksheet.fitWidth(); });
  elements.zoomOutBtn.addEventListener('click', function () {
    worksheet.setZoom(worksheet.getState().zoom - 10);
  });
  elements.zoomInBtn.addEventListener('click', function () {
    worksheet.setZoom(worksheet.getState().zoom + 10);
  });
  elements.questionListToggle.addEventListener('click', function () {
    const open = elements.questionsContainer.hidden;
    elements.questionsContainer.hidden = !open;
    elements.questionListToggle.setAttribute('aria-expanded', String(open));
    if (open) setSessionPanelExpanded(true);
  });
  elements.typedAnswer.addEventListener('input', function () {
    applyTypedDraft(elements.typedAnswer.textContent);
    // Unconfirmed drafts stay in the editor only; overlays and export use written responses.
  });
  elements.confirmTypedBtn.addEventListener('click', function () {
    presentAnswer(state.activeResponseRegionId, elements.typedAnswer.textContent);
  });
  elements.editAnswerBtn.addEventListener('click', function () {
    setVoiceState(state.liveSession ? 'listening' : 'idle');
    elements.typedAnswer.focus();
  });
  elements.rejectAnswerBtn.addEventListener('click', function () {
    dismissAnswer(true);
    setNotice('Proposed answer rejected. Nothing was written.');
  });
  elements.confirmAnswerBtn.addEventListener('click', confirmProposedAnswer);
  elements.changeConfirmedAnswerBtn.addEventListener('click', function () {
    const responseRegionId = state.proposedResponseRegionId;
    if (responseRegionId != null) {
      const responseState = responseStateFor(responseRegionId);
      responseState.writeToken = '';
      responseState.confirmed = false;
      responseState.draft = responseState.draft || elements.typedAnswer.textContent || '';
      elements.proposedAnswer.textContent = responseState.draft;
      if (elements.confirmedAnswerPreview) elements.confirmedAnswerPreview.textContent = '';
      syncWorksheetResponseState(responseRegionId);
      setVoiceState('answer_detected');
      setNotice('Update the draft, then review it again. Nothing was written.');
      elements.typedAnswer.focus();
      refreshActiveProgress();
    }
  });
  elements.writeConfirmedAnswerBtn.addEventListener('click', function () {
    triggerWrite(state.proposedResponseRegionId || state.activeResponseRegionId);
  });
  elements.returnToWorksheetBtn.addEventListener('click', function () {
    setSessionPanelExpanded(false);
    elements.documentViewport.focus();
  });
  elements.micBtn.addEventListener('click', function () {
    if (state.liveSession) stopSession();
    else startSession();
  });
  elements.interruptBtn.addEventListener('click', interruptAgent);
  elements.voicePanelToggle.addEventListener('click', function () {
    setSessionPanelExpanded(!elements.sessionPanel.classList.contains('is-expanded'));
  });
  elements.transcript.addEventListener('scroll', function () {
    transcriptPinned = shouldAutoScrollTranscript();
  });

  setWorkspaceState('empty');
  setVoiceState('unavailable');

  if (new URLSearchParams(location.search).get('sample')) {
    loadSamplePdf(new URLSearchParams(location.search).get('sample'));
  }
})();
