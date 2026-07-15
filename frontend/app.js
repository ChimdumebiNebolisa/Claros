(function () {
  'use strict';

  const SAMPLE_RATE = 16000;
  const OUT_SAMPLE_RATE = 24000;
  const API_BASE = location.origin || 'http://127.0.0.1:8000';
  const SESSION_STORAGE_KEY = 'claros_session_v1';

  const UiState = window.ClarosUiState;
  const SessionRules = window.ClarosSessionRules;
  const WorksheetView = window.ClarosWorksheetView;
  if (!UiState || !SessionRules || !WorksheetView) {
    throw new Error('Claros frontend modules failed to load');
  }

  const elements = {
    setupMode: document.getElementById('setupMode'),
    workspaceMode: document.getElementById('workspaceMode'),
    workspaceStatus: document.getElementById('workspaceStatus'),
    startCard: document.querySelector('.start-card'),
    uploadZone: document.getElementById('uploadZone'),
    fileInput: document.getElementById('fileInput'),
    uploadBtn: document.getElementById('uploadBtn'),
    uploadLabel: document.getElementById('uploadLabel'),
    testPdfBtn: document.getElementById('testPdfBtn'),
    processingPanel: document.getElementById('processingPanel'),
    processingTitle: document.getElementById('processingTitle'),
    selectedFilename: document.getElementById('selectedFilename'),
    processingActions: document.getElementById('processingActions'),
    retryBtn: document.getElementById('retryBtn'),
    replaceBtn: document.getElementById('replaceBtn'),
    errors: document.getElementById('errors'),
    assignmentTitle: document.getElementById('assignmentTitle'),
    replaceWorksheetBtn: document.getElementById('replaceWorksheetBtn'),
    exportBtn: document.getElementById('exportBtn'),
    previousPageBtn: document.getElementById('previousPageBtn'),
    nextPageBtn: document.getElementById('nextPageBtn'),
    fitWidthBtn: document.getElementById('fitWidthBtn'),
    zoomOutBtn: document.getElementById('zoomOutBtn'),
    zoomInBtn: document.getElementById('zoomInBtn'),
    pageLabel: document.getElementById('pageLabel'),
    zoomLabel: document.getElementById('zoomLabel'),
    layoutReviewBtn: document.getElementById('layoutReviewBtn'),
    layoutReviewPanel: document.getElementById('layoutReviewPanel'),
    layoutReviewSummary: document.getElementById('layoutReviewSummary'),
    resetRegionBtn: document.getElementById('resetRegionBtn'),
    confirmRegionBtn: document.getElementById('confirmRegionBtn'),
    finishLayoutBtn: document.getElementById('finishLayoutBtn'),
    documentViewport: document.getElementById('documentViewport'),
    documentPage: document.getElementById('documentPage'),
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
    questionListToggle: document.getElementById('questionListToggle'),
    questionsContainer: document.getElementById('questionsContainer'),
    typedAnswer: document.getElementById('typedAnswer'),
    confirmTypedBtn: document.getElementById('confirmTypedBtn'),
    answerConfirmation: document.getElementById('answerConfirmation'),
    confirmationTitle: document.getElementById('confirmationTitle'),
    proposedAnswer: document.getElementById('proposedAnswer'),
    editAnswerBtn: document.getElementById('editAnswerBtn'),
    rejectAnswerBtn: document.getElementById('rejectAnswerBtn'),
    confirmAnswerBtn: document.getElementById('confirmAnswerBtn'),
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
    filename: '',
    pageCount: 1,
    questions: [],
    answers: {},
    drafts: {},
    confirmed: {},
    writeTokens: {},
    activeQuestionId: null,
    proposedQuestionId: null,
    proposedText: '',
    lastFile: null,
    sessionId: null,
    sessionSecret: null,
    liveSession: null,
    conversation: [],
    writeInProgress: false,
    correctionMode: false,
    lastExportVoiceNorm: ''
  };

  let worksheet;
  let audioContext = null;
  let playbackContext = null;
  let mediaStream = null;
  let sourceNode = null;
  let processorNode = null;
  let nextPlaybackTime = 0;
  let scheduledSources = [];
  let keepaliveInterval = null;
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
    if (model.showConfirmation || next === 'writing') {
      setSessionPanelExpanded(true);
    }
  }

  function setNotice(message) {
    elements.notice.textContent = message || '';
  }

  function setError(message) {
    elements.errors.textContent = message || '';
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

  function getQuestion(questionId) {
    return state.questions.find(function (question) {
      return Number(question.id) === Number(questionId);
    });
  }

  function unresolvedQuestions() {
    return state.questions.filter(function (question) { return question.needs_layout_review; });
  }

  function renderQuestionPicker() {
    elements.questionsContainer.innerHTML = '';
    state.questions.forEach(function (question) {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.questionId = question.id;
      button.textContent = 'Question ' + question.id + (question.needs_layout_review ? ' (layout review)' : '');
      button.setAttribute('aria-current', String(Number(question.id) === Number(state.activeQuestionId)));
      button.addEventListener('click', function () {
        selectQuestion(question.id);
        elements.questionsContainer.hidden = true;
      });
      elements.questionsContainer.appendChild(button);
    });
  }

  function selectQuestion(questionId) {
    const question = getQuestion(questionId);
    if (!question) return;
    state.activeQuestionId = question.id;
    elements.currentQuestionLabel.textContent = 'Working on Question ' + question.id;
    elements.currentQuestionExcerpt.textContent = question.text || '';
    elements.typedAnswer.textContent = state.answers[question.id] || state.drafts[question.id] || '';
    elements.confirmTypedBtn.disabled = !elements.typedAnswer.textContent.trim();
    if (worksheet) worksheet.setActiveQuestion(question.id);
    renderQuestionPicker();
  }

  function renderLayoutState() {
    const unresolved = unresolvedQuestions();
    elements.layoutReviewBtn.hidden = unresolved.length === 0;
    elements.layoutReviewBtn.textContent = unresolved.length
      ? 'Review layout (' + unresolved.length + ')'
      : 'Review layout';
    elements.layoutReviewSummary.textContent = unresolved.length
      ? unresolved.length + ' answer ' + (unresolved.length === 1 ? 'region needs' : 'regions need') + ' attention.'
      : 'All answer regions are ready.';
    if (state.workspace === 'ready' || state.workspace === 'needs_layout_review') {
      setWorkspaceState(unresolved.length ? 'needs_layout_review' : 'ready');
    }
    renderQuestionPicker();
  }

  function initializeWorksheet() {
    worksheet = WorksheetView.create({
      container: elements.documentViewport,
      pageImage: elements.pageImage,
      overlayLayer: elements.answerOverlayLayer,
      pageLabel: elements.pageLabel,
      zoomLabel: elements.zoomLabel,
      onSelectQuestion: function (question) { selectQuestion(question.id); },
      onRegionChange: function (question) {
        elements.layoutReviewSummary.textContent = 'Question ' + question.id + ' region changed. Confirm it when ready.';
      },
      onRegionConfirm: function (question) {
        setNotice('Answer region confirmed for Question ' + question.id + '.');
        renderLayoutState();
      }
    });
    worksheet.load({
      assignmentId: state.assignmentId,
      questions: state.questions,
      pageCount: state.pageCount,
      answers: state.answers
    });
  }

  function applyAssignment(data) {
    state.assignmentId = data.assignment_id;
    state.title = data.title || state.filename || 'Worksheet';
    state.questions = data.questions || [];
    state.pageCount = Number(data.page_count || 1);
    state.answers = {};
    state.drafts = {};
    state.confirmed = {};
    state.writeTokens = {};
    state.activeQuestionId = state.questions.length ? state.questions[0].id : null;
    elements.assignmentTitle.textContent = state.filename || state.title;
    elements.previousPageBtn.disabled = state.pageCount <= 1;
    elements.nextPageBtn.disabled = state.pageCount <= 1;
    initializeWorksheet();
    renderQuestionPicker();
    if (state.activeQuestionId != null) selectQuestion(state.activeQuestionId);
    setWorkspaceState(unresolvedQuestions().length ? 'needs_layout_review' : 'ready');
    setVoiceState('idle');
    renderLayoutState();
    restoreSessionFromStorage();
  }

  async function doUpload(file) {
    if (!file) return;
    state.lastFile = file;
    state.filename = file.name;
    elements.selectedFilename.textContent = file.name;
    elements.uploadLabel.textContent = file.name;
    elements.testPdfBtn.disabled = true;
    elements.uploadBtn.disabled = true;
    setError('');
    setNotice('');
    setWorkspaceState('uploading');
    startProcessingProgress();
    const form = new FormData();
    form.append('file', file);
    try {
      const response = await fetch('/upload', { method: 'POST', body: form });
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
      elements.testPdfBtn.disabled = false;
      elements.uploadBtn.disabled = false;
    }
  }

  async function loadSamplePdf() {
    setError('');
    try {
      const response = await fetch('/test-assignment.pdf');
      if (!response.ok) throw new Error('The sample worksheet is unavailable.');
      const blob = await response.blob();
      await doUpload(new File([blob], 'Claros sample algebra worksheet.pdf', { type: 'application/pdf' }));
    } catch (error) {
      setWorkspaceState('error');
      setError(error.message || 'The sample worksheet could not be loaded.');
    }
  }

  function resetWorkspace() {
    stopSession();
    state.assignmentId = null;
    state.questions = [];
    state.answers = {};
    state.activeQuestionId = null;
    worksheet = null;
    elements.fileInput.value = '';
    elements.uploadLabel.textContent = 'Choose a worksheet PDF';
    setError('');
    setNotice('');
    setWorkspaceState('empty');
    setVoiceState('unavailable');
  }

  function persistSessionLocally() {
    if (!state.sessionId || !state.sessionSecret || !state.assignmentId) return;
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
        assignmentId: state.assignmentId,
        sessionId: state.sessionId,
        sessionSecret: state.sessionSecret
      }));
    } catch (_) {}
  }

  async function ensureServerSession() {
    if (state.sessionId && state.sessionSecret) return;
    const response = await fetch(API_BASE + '/api/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assignment_id: state.assignmentId })
    });
    if (!response.ok) throw new Error('Could not start the worksheet session.');
    const data = await response.json();
    state.sessionId = data.session_id;
    state.sessionSecret = data.session_secret;
    persistSessionLocally();
  }

  async function restoreSessionFromStorage() {
    try {
      const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (!raw || !state.assignmentId) return;
      const saved = JSON.parse(raw);
      if (saved.assignmentId !== state.assignmentId) return;
      state.sessionId = saved.sessionId;
      state.sessionSecret = saved.sessionSecret;
      const response = await fetch(API_BASE + '/api/session/' + saved.sessionId + '/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_secret: saved.sessionSecret })
      });
      if (!response.ok) return;
      const data = await response.json();
      Object.keys(data.questions || {}).forEach(function (questionId) {
        const restored = data.questions[questionId];
        if (restored.confirmed && restored.confirmed_answer) {
          state.confirmed[questionId] = true;
          state.drafts[questionId] = restored.confirmed_answer;
        }
      });
      setNotice('Confirmed answers from this session were restored.');
    } catch (_) {}
  }

  function presentAnswer(questionId, text) {
    const cleaned = (text || '').trim();
    const question = getQuestion(questionId);
    if (!question || !cleaned) return;
    state.activeQuestionId = question.id;
    state.proposedQuestionId = question.id;
    state.proposedText = cleaned;
    state.drafts[question.id] = cleaned;
    selectQuestion(question.id);
    elements.typedAnswer.textContent = cleaned;
    elements.proposedAnswer.textContent = cleaned;
    elements.confirmationTitle.textContent = 'Confirm answer for Question ' + question.id;
    setVoiceState('answer_detected');
    setNotice('Review the proposed answer. Nothing has been written yet.');
  }

  function dismissAnswer(clearText) {
    if (clearText && state.proposedQuestionId != null) {
      delete state.drafts[state.proposedQuestionId];
      state.proposedText = '';
      elements.typedAnswer.textContent = '';
    }
    state.proposedQuestionId = null;
    state.proposedText = '';
    setVoiceState(state.liveSession ? 'listening' : 'idle');
  }

  async function confirmProposedAnswer() {
    const questionId = state.proposedQuestionId;
    const text = (state.proposedText || elements.typedAnswer.textContent || '').trim();
    if (questionId == null || !text) {
      setError('Add an answer before confirming it.');
      return;
    }
    setVoiceState('confirming');
    elements.confirmAnswerBtn.disabled = true;
    try {
      await ensureServerSession();
      const response = await fetch(API_BASE + '/api/session/' + state.sessionId + '/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_secret: state.sessionSecret,
          question_id: questionId,
          answer_text: text
        })
      });
      if (!response.ok) {
        const detail = await response.json().catch(function () { return {}; });
        throw new Error(detail.detail || 'The answer could not be confirmed.');
      }
      const data = await response.json();
      state.confirmed[questionId] = true;
      state.drafts[questionId] = text;
      state.writeTokens[questionId] = data.write_token;
      setError('');
      await triggerWrite(questionId);
    } catch (error) {
      setError(error.message || 'The answer could not be confirmed.');
      setVoiceState('confirming');
    } finally {
      elements.confirmAnswerBtn.disabled = false;
    }
  }

  async function triggerWrite(questionId) {
    if (state.writeInProgress) return;
    if (!state.confirmed[questionId] || !state.writeTokens[questionId]) {
      presentAnswer(questionId, state.drafts[questionId] || '');
      setNotice('Confirm this answer before Claros writes it.');
      return;
    }
    state.writeInProgress = true;
    setVoiceState('writing');
    setNotice('Writing the confirmed answer into Question ' + questionId + '.');
    let written = '';
    try {
      const response = await fetch(API_BASE + '/api/write/' + state.assignmentId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_id: questionId,
          conversation: state.conversation,
          answer_candidate: state.drafts[questionId] || '',
          write_token: state.writeTokens[questionId],
          session_id: state.sessionId,
          session_secret: state.sessionSecret
        })
      });
      if (!response.ok) {
        const detail = await response.json().catch(function () { return {}; });
        throw new Error(detail.detail || 'The confirmed answer could not be written.');
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const result = await reader.read();
        if (result.done) break;
        written += decoder.decode(result.value, { stream: true });
        written = written.replace(/\$([^$]+)\$/g, '$1');
        state.answers[questionId] = written;
        elements.typedAnswer.textContent = written;
        worksheet.updateAnswer(questionId, written);
      }
      delete state.writeTokens[questionId];
      state.proposedQuestionId = null;
      state.proposedText = '';
      setNotice('Answer written into Question ' + questionId + '.');
      elements.typedAnswer.focus();
    } catch (error) {
      delete state.writeTokens[questionId];
      state.confirmed[questionId] = false;
      setError(error.message || 'The confirmed answer could not be written.');
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
        activeClarosMessage.innerHTML = '<span class="msg-label">Claros</span>';
        elements.transcript.appendChild(activeClarosMessage);
      }
      activeClarosMessage.appendChild(document.createTextNode(text));
    } else {
      activeClarosMessage = null;
      const item = document.createElement('div');
      item.className = 'msg user';
      item.innerHTML = '<span class="msg-label">You</span>';
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
      userPartialElement.innerHTML = '<span class="msg-label">You, live</span>';
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

  function int16ArrayToBase64(values) {
    const bytes = new Uint8Array(values.buffer);
    let binary = '';
    for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]);
    return btoa(binary);
  }

  function queuePcm24kChunk(base64Data) {
    if (!playbackContext) {
      playbackContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: OUT_SAMPLE_RATE });
    }
    if (playbackContext.state === 'suspended') playbackContext.resume();
    const binary = atob(base64Data);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const samples = new Int16Array(bytes.buffer, 0, binary.length >> 1);
    const buffer = playbackContext.createBuffer(1, samples.length, OUT_SAMPLE_RATE);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < samples.length; index += 1) channel[index] = samples[index] / 32768;
    const startTime = Math.max(playbackContext.currentTime, nextPlaybackTime);
    const source = playbackContext.createBufferSource();
    source.buffer = buffer;
    source.connect(playbackContext.destination);
    source.start(startTime);
    nextPlaybackTime = startTime + buffer.duration;
    scheduledSources.push(source);
    source.onended = function () {
      scheduledSources = scheduledSources.filter(function (item) { return item !== source; });
    };
  }

  function clearPlayback() {
    scheduledSources.forEach(function (source) {
      try { source.stop(); } catch (_) {}
    });
    scheduledSources = [];
    nextPlaybackTime = 0;
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

  function showVoiceFallback(message) {
    elements.keyboardFallback.hidden = false;
    setNotice(message || 'Voice is unavailable. Continue by typing an answer.');
    setVoiceState('error');
  }

  async function startSession() {
    if (!state.assignmentId || state.liveSession) return;
    setError('');
    elements.keyboardFallback.hidden = true;
    setVoiceState('connecting');
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Microphone access is not available in this browser.');
      }
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1
        }
      });
      setNotice('Microphone access granted. Connecting Claros now.');
    } catch (error) {
      const message = error && error.name === 'NotAllowedError'
        ? 'Microphone access was denied. You can still type, confirm, and export answers.'
        : (error.message || 'The microphone is unavailable.');
      showVoiceFallback(message);
      return;
    }

    try {
      await ensureServerSession();
      const configResponse = await fetch(API_BASE + '/api/session-config/' + state.assignmentId);
      if (!configResponse.ok) throw new Error('Claros could not connect to the voice provider.');
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
          onmessage: handleLiveMessage,
          onerror: function () {
            stopSession(false);
            showVoiceFallback('The voice connection failed. Continue by typing, or try voice again.');
          },
          onclose: function () {
            stopSession(false);
            setVoiceState('stopped');
          }
        }
      });
      state.liveSession = session;
      startAudioInput(mediaStream);
      startMeter(mediaStream);
      setVoiceState('listening');
      setNotice('Voice session started. Claros is listening.');
    } catch (error) {
      if (mediaStream) mediaStream.getTracks().forEach(function (track) { track.stop(); });
      mediaStream = null;
      showVoiceFallback(error.message || 'Claros could not connect to the voice provider.');
    }
  }

  function startAudioInput(stream) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const ratio = audioContext.sampleRate / SAMPLE_RATE;
    sourceNode = audioContext.createMediaStreamSource(stream);
    processorNode = audioContext.createScriptProcessor(1024, 1, 1);
    processorNode.onaudioprocess = function (event) {
      if (!state.liveSession) return;
      const input = event.inputBuffer.getChannelData(0);
      const output = new Int16Array(Math.floor(input.length / ratio));
      for (let index = 0; index < output.length; index += 1) {
        const sample = Math.max(-1, Math.min(1, input[Math.min(Math.floor(index * ratio), input.length - 1)]));
        output[index] = sample < 0 ? sample * 32768 : sample * 32767;
      }
      try {
        state.liveSession.sendRealtimeInput({
          audio: { data: int16ArrayToBase64(output), mimeType: 'audio/pcm;rate=16000' }
        });
      } catch (_) {}
    };
    sourceNode.connect(processorNode);
    processorNode.connect(audioContext.destination);
    const silence = new Int16Array(320);
    keepaliveInterval = setInterval(function () {
      if (!state.liveSession) return;
      try {
        state.liveSession.sendRealtimeInput({
          audio: { data: int16ArrayToBase64(silence), mimeType: 'audio/pcm;rate=16000' }
        });
      } catch (_) {}
    }, 5000);
  }

  function handleLiveMessage(message) {
    const content = message.serverContent;
    if (!content) return;
    if (content.inputTranscription && content.inputTranscription.text) {
      userTranscriptBuffer += content.inputTranscription.text;
      if (scheduledSources.length || state.voice === 'speaking') {
        clearPlayback();
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
          queuePcm24kChunk(part.inlineData.data);
          if (!state.writeInProgress) setVoiceState('speaking');
        }
      });
    }
    if (content.turnComplete) {
      const full = userTranscriptBuffer.trim();
      userTranscriptBuffer = '';
      clearUserPartial();
      activeClarosMessage = null;
      setVoiceState('listening');
      if (!full) return;
      const normalized = SessionRules.normalizeTranscript(full);
      state.conversation.push({ speaker: 'user', text: full });
      addTranscript('user', full);
      const parsedQuestion = SessionRules.parseQuestionNum(normalized);
      if (parsedQuestion != null && getQuestion(parsedQuestion)) selectQuestion(parsedQuestion);
      const targetQuestion = parsedQuestion != null ? parsedQuestion : state.activeQuestionId;
      if (SessionRules.ANSWER_STATED_RE.test(normalized) && targetQuestion != null) {
        presentAnswer(targetQuestion, SessionRules.extractDraftAnswer(normalized) || full);
      }
      if (SessionRules.WRITE_INTENT_RE.test(normalized) && targetQuestion != null) {
        if (state.confirmed[targetQuestion]) triggerWrite(targetQuestion);
        else presentAnswer(targetQuestion, state.drafts[targetQuestion] || full);
      }
      if (SessionRules.hasExportIntent(normalized) && normalized !== state.lastExportVoiceNorm) {
        state.lastExportVoiceNorm = normalized;
        performExport();
      }
    }
  }

  function stopSession(closeProvider) {
    if (keepaliveInterval) clearInterval(keepaliveInterval);
    keepaliveInterval = null;
    clearPlayback();
    if (processorNode) {
      try {
        processorNode.disconnect();
        if (sourceNode) sourceNode.disconnect();
      } catch (_) {}
    }
    processorNode = null;
    sourceNode = null;
    if (mediaStream) mediaStream.getTracks().forEach(function (track) { track.stop(); });
    mediaStream = null;
    if (state.liveSession && closeProvider !== false && state.liveSession.close) {
      try { state.liveSession.close(); } catch (_) {}
    }
    state.liveSession = null;
    if (audioContext) audioContext.close();
    audioContext = null;
    elements.meterBar.style.width = '0%';
    clearUserPartial();
    setVoiceState(state.assignmentId ? 'stopped' : 'unavailable');
  }

  function interruptAgent() {
    if (!state.liveSession) return;
    clearPlayback();
    setVoiceState('listening');
    setNotice('Claros stopped speaking. You can continue.');
  }

  async function performExport() {
    if (!state.assignmentId || state.workspace === 'exporting') return;
    setWorkspaceState('exporting');
    setError('');
    const answers = state.questions
      .filter(function (question) {
        return !!(state.confirmed[question.id] && (state.answers[question.id] || '').trim());
      })
      .map(function (question) {
        return {
          question_id: question.id,
          answer_text: state.answers[question.id] || '',
          answer_region: question.answer_region || undefined
        };
      });
    if (!answers.length) {
      setWorkspaceState(unresolvedQuestions().length ? 'needs_layout_review' : 'ready');
      setError('Confirm and write at least one answer before exporting.');
      return;
    }
    try {
      const response = await fetch('/export/' + state.assignmentId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: answers })
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
      setWorkspaceState(unresolvedQuestions().length ? 'needs_layout_review' : 'ready');
      setError(error.message || 'The completed PDF could not be prepared.');
    }
  }

  function enterLayoutReview() {
    state.correctionMode = true;
    elements.layoutReviewPanel.hidden = false;
    worksheet.setCorrectionMode(true);
    elements.layoutReviewSummary.textContent = unresolvedQuestions().length
      + ' answer ' + (unresolvedQuestions().length === 1 ? 'region needs' : 'regions need') + ' attention.';
    elements.confirmRegionBtn.focus();
  }

  function finishLayoutReview() {
    state.correctionMode = false;
    elements.layoutReviewPanel.hidden = true;
    worksheet.setCorrectionMode(false);
    renderLayoutState();
    setNotice(unresolvedQuestions().length ? 'Some answer regions still need review.' : 'Layout ready.');
    elements.layoutReviewBtn.focus();
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
  elements.testPdfBtn.addEventListener('click', loadSamplePdf);
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
  elements.layoutReviewBtn.addEventListener('click', enterLayoutReview);
  elements.resetRegionBtn.addEventListener('click', function () { worksheet.resetSelected(); });
  elements.confirmRegionBtn.addEventListener('click', function () { worksheet.confirmSelected(); });
  elements.finishLayoutBtn.addEventListener('click', finishLayoutReview);
  document.querySelectorAll('[data-region-action]').forEach(function (button) {
    button.addEventListener('click', function () {
      const action = button.dataset.regionAction;
      const selected = worksheet.getState().selectedQuestionId;
      const adjustments = {
        left: [-0.005, 0, 0, 0],
        right: [0.005, 0, 0, 0],
        up: [0, -0.005, 0, 0],
        down: [0, 0.005, 0, 0],
        wider: [0, 0, 0.01, 0],
        narrower: [0, 0, -0.01, 0]
      };
      worksheet.adjust(selected, ...adjustments[action]);
    });
  });
  elements.questionListToggle.addEventListener('click', function () {
    elements.questionsContainer.hidden = !elements.questionsContainer.hidden;
  });
  elements.typedAnswer.addEventListener('input', function () {
    const text = elements.typedAnswer.textContent.trim();
    const questionId = state.activeQuestionId;
    state.drafts[questionId] = text;
    elements.confirmTypedBtn.disabled = !text;
    // Unconfirmed drafts stay in the editor only; overlays and export use written answers.
  });
  elements.confirmTypedBtn.addEventListener('click', function () {
    presentAnswer(state.activeQuestionId, elements.typedAnswer.textContent);
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

  if (new URLSearchParams(location.search).get('sample') === '1') loadSamplePdf();
})();
