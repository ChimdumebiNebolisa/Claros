(function () {
  const SAMPLE_RATE = 16000;
  const OUT_SAMPLE_RATE = 24000;
  let state = { assignmentId: null, title: '', questions: [], answers: {} };

  const assignmentTitleEl = document.getElementById('assignmentTitle');
  const uploadZone = document.getElementById('uploadZone');
  const fileInput = document.getElementById('fileInput');
  const uploadBtn = document.getElementById('uploadBtn');
  const uploadLabel = document.getElementById('uploadLabel');
  const questionsContainer = document.getElementById('questionsContainer');
  const exportBtn = document.getElementById('exportBtn');
  const statusEl = document.getElementById('status');
  const sessionPanel = document.getElementById('sessionPanel');
  const statusLabel = document.getElementById('statusLabel');
  const meterBar = document.getElementById('meterBar');
  const transcriptEl = document.getElementById('transcript');
  const noticeEl = document.getElementById('notice');
  const errorsEl = document.getElementById('errors');
  const micBtn = document.getElementById('micBtn');
  const interruptBtn = document.getElementById('interruptBtn');
  const setupStepUpload = document.getElementById('setupStepUpload');
  const setupStepReview = document.getElementById('setupStepReview');
  const setupStepSession = document.getElementById('setupStepSession');
  const setupStepExport = document.getElementById('setupStepExport');

  const SR = typeof ClarosSessionRules !== 'undefined' ? ClarosSessionRules : null;
  if (!SR) {
    errorsEl.textContent = 'Claros failed to load session rules (session-rules.js).';
    throw new Error('ClarosSessionRules missing');
  }
  var normalizeTranscript = SR.normalizeTranscript;
  var parseQuestionNum = SR.parseQuestionNum;
  var parseClarosWriteQuestionNum = SR.parseClarosWriteQuestionNum;
  var WRITE_INTENT_RE = SR.WRITE_INTENT_RE;
  var CLAROS_WRITE_PHRASE_RE = SR.CLAROS_WRITE_PHRASE_RE;
  var ANSWER_STATED_RE = SR.ANSWER_STATED_RE;
  var hasExportIntent = SR.hasExportIntent;

  function setChecklistStep(stepEl, done) {
    if (!stepEl) return;
    if (done) stepEl.classList.add('done');
    else stepEl.classList.remove('done');
  }

  function syncChecklist() {
    var hasAssignment = !!state.assignmentId;
    document.body.classList.toggle('has-assignment', hasAssignment);
    setChecklistStep(setupStepUpload, hasAssignment);
    setChecklistStep(setupStepReview, hasAssignment && Array.isArray(state.questions) && state.questions.length > 0);
    setChecklistStep(setupStepSession, hasAssignment);
    setChecklistStep(setupStepExport, !!liveSession);
  }

  /* ?????? Upload ?????? */
  uploadBtn.addEventListener('click', () => fileInput.click());
  uploadZone.addEventListener('click', (e) => {
    if (e.target === uploadZone || e.target.closest('.upload-inner')) fileInput.click();
  });
  uploadZone.addEventListener('dragover', (e) => { e.preventDefault(); uploadZone.classList.add('hover'); });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('hover'));
  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('hover');
    const file = e.dataTransfer.files[0];
    if (file && file.name.toLowerCase().endsWith('.pdf')) doUpload(file);
  });
  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (file) doUpload(file);
  });

  const testPdfBtn = document.getElementById('testPdfBtn');

  async function loadSamplePdf() {
    uploadLabel.textContent = 'Loading test PDF...';
    testPdfBtn.disabled = true;
    errorsEl.textContent = '';
    noticeEl.textContent = '';
    try {
      const r = await fetch('/test-assignment.pdf');
      if (!r.ok) throw new Error('Failed to load sample worksheet');
      const blob = await r.blob();
      const file = new File([blob], 'test_assignment.pdf', { type: 'application/pdf' });
      await doUpload(file);
    } catch (err) {
      errorsEl.textContent = err.message || 'Failed to load sample worksheet';
    } finally {
      uploadLabel.textContent = 'Drop your assignment PDF here';
      testPdfBtn.disabled = false;
    }
  }

  testPdfBtn.addEventListener('click', loadSamplePdf);

  async function doUpload(file) {
    uploadLabel.textContent = 'Uploading and reading your assignment...';
    errorsEl.textContent = '';
    noticeEl.textContent = '';
    const form = new FormData();
    form.append('file', file);
    try {
      const r = await fetch('/upload', { method: 'POST', body: form });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail || err.error || 'Upload failed');
      }
      const data = await r.json();
      console.log('[doUpload] Full upload response:', JSON.stringify(data, null, 2));
      state.assignmentId = data.assignment_id;
      state.title = data.title || 'Assignment';
      state.questions = data.questions || [];
      state.answers = {};
      assignmentTitleEl.textContent = state.title;
      renderQuestions();
      micBtn.disabled = false;
      micBtn.classList.remove('stop');
      micBtn.textContent = 'Start Session';
      uploadLabel.textContent = 'Drop your assignment PDF here';
      noticeEl.textContent = 'Worksheet ready. You can start your voice session now.';
      syncChecklist();
    } catch (err) {
      uploadLabel.textContent = 'Drop your assignment PDF here';
      errorsEl.textContent = err.message || 'We could not upload that file. Please try another PDF.';
      syncChecklist();
    }
  }

  /* ?????? Question rendering ?????? */
  function renderQuestions() {
    console.log('[renderQuestions] Received state.questions:', state.questions?.length, state.questions);
    questionsContainer.innerHTML = '';
    state.questions.forEach((q) => {
      const card = document.createElement('div');
      card.className = 'question-card';
      card.dataset.questionId = String(q.id);
      const questionText = (q.text != null && q.text !== '') ? String(q.text) : '';
      card.innerHTML = '<div class="question-header"><div style="display:flex;align-items:center"><span class="question-index">' + q.id + '</span><div class="question-label">Question ' + q.id + '<span class="ready-badge">Answer stated</span></div></div><div class="question-meta">&nbsp;</div></div><div class="question-text"></div><div class="answer-field" data-question-id="' + q.id + '" data-placeholder="Say your answer in a session, or type it here" contenteditable="true" spellcheck="true"></div>';
      const questionTextEl = card.querySelector('.question-text');
      const answerEl = card.querySelector('.answer-field');
      answerEl.setAttribute('role', 'textbox');
      answerEl.setAttribute('aria-label', 'Answer for question ' + q.id);
      answerEl.setAttribute('aria-multiline', 'true');
      if (questionTextEl) {
        questionTextEl.textContent = questionText;
        console.log('[renderQuestions] Card for Q' + q.id + ': set question-text to', questionText ? questionText.substring(0, 50) + (questionText.length > 50 ? '...' : '') : '(empty)');
      }
      answerEl.addEventListener('input', () => {
        state.answers[q.id] = answerEl.textContent;
        if (answerEl.textContent.trim()) exportBtn.classList.add('visible');
        syncChecklist();
      });
      questionsContainer.appendChild(card);
    });
    if (state.questions && state.questions.length > 0) {
      exportBtn.classList.add('visible');
    }
    console.log('[renderQuestions] Created', state.questions?.length || 0, 'card(s). DOM children:', questionsContainer.children.length);
  }

  function getAnswerEl(questionId) {
    return document.querySelector('.answer-field[data-question-id="' + questionId + '"]');
  }
  function getCardEl(questionId) {
    return document.querySelector('.question-card[data-question-id="' + questionId + '"]');
  }

  const API_BASE = location.origin || 'http://127.0.0.1:8000';

  let liveSession = null;
  let audioContext = null;
  let mediaStream = null;
  let sourceNode = null;
  let processorNode = null;
  let playbackContext = null;
  let nextPlaybackTime = 0;
  let scheduledSources = [];
  let conversationContext = [];
  let answerReady = {};
  let answerCandidate = {};
  let currentQuestion = null;
  let clarosOutputBuffer = '';
  let userTranscriptBuffer = '';
  let lastExportVoiceNorm = '';
  let writeInProgress = false;
  let keepaliveInterval = null;

  function int16ArrayToBase64(int16Arr) {
    var bytes = new Uint8Array(int16Arr.buffer);
    var binary = '';
    for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
  }

  /* ?????? Status ?????? */
  let currentMode = 'idle';

  function setStatus(mode) {
    currentMode = mode;
    var labels = {
      idle: 'Waiting for worksheet',
      connecting: 'Connecting\u2026',
      listening: 'Listening for your response',
      speaking: 'Claros is speaking',
      writing: 'Writing your answer\u2026'
    };
    statusLabel.textContent = labels[mode] || mode;
    statusEl.className = 'status-bar ' + mode;
    if (sessionPanel) {
      sessionPanel.classList.remove('is-live', 'is-connecting', 'is-listening', 'is-speaking', 'is-writing');
      if (mode === 'connecting') {
        sessionPanel.classList.add('is-connecting');
      } else if (mode === 'listening' || mode === 'speaking' || mode === 'writing') {
        sessionPanel.classList.add('is-live', 'is-' + mode);
      }
    }
  }

  /* ?????? Transcript (streaming) ?????? */
  let activeClarosMsg = null;
  let userPartialEl = null;
  let userPartialText = '';

  function addTranscript(speaker, text) {
    if (!text || !text.trim()) return;
    if (speaker === 'claros') {
      if (!activeClarosMsg) {
        activeClarosMsg = document.createElement('div');
        activeClarosMsg.className = 'msg claros';
        var label = document.createElement('span');
        label.className = 'msg-label';
        label.textContent = 'Claros ';
        activeClarosMsg.appendChild(label);
        transcriptEl.appendChild(activeClarosMsg);
      }
      activeClarosMsg.appendChild(document.createTextNode(text));
    } else {
      activeClarosMsg = null;
      var div = document.createElement('div');
      div.className = 'msg user';
      var label = document.createElement('span');
      label.className = 'msg-label';
      label.textContent = 'You ';
      div.appendChild(label);
      div.appendChild(document.createTextNode(text));
      transcriptEl.appendChild(div);
    }
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  function showUserPartial(text) {
    userPartialText += text;
    if (!userPartialEl) {
      userPartialEl = document.createElement('div');
      userPartialEl.className = 'msg user partial';
      var label = document.createElement('span');
      label.className = 'msg-label';
      label.textContent = 'You ';
      userPartialEl.appendChild(label);
      userPartialEl._tn = document.createTextNode('');
      userPartialEl.appendChild(userPartialEl._tn);
      transcriptEl.appendChild(userPartialEl);
    }
    userPartialEl._tn.textContent = userPartialText;
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  function clearUserPartial() {
    if (userPartialEl) {
      userPartialEl.remove();
      userPartialEl = null;
    }
    userPartialText = '';
  }

  /* ?????? Audio playback with barge-in support ?????? */
  function queuePcm24kChunk(base64Data) {
    if (!playbackContext) playbackContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: OUT_SAMPLE_RATE });
    if (playbackContext.state === 'suspended') playbackContext.resume();
    var ctx = playbackContext;
    var binary = atob(base64Data);
    var byteLength = binary.length;
    var numSamples = byteLength >> 1;
    var bytes = new Uint8Array(byteLength);
    for (var i = 0; i < byteLength; i++) bytes[i] = binary.charCodeAt(i);
    var int16Samples = new Int16Array(bytes.buffer, 0, numSamples);
    var buf = ctx.createBuffer(1, numSamples, OUT_SAMPLE_RATE);
    var channel = buf.getChannelData(0);
    for (var i = 0; i < numSamples; i++) channel[i] = int16Samples[i] / 32768;
    var startTime = Math.max(ctx.currentTime, nextPlaybackTime);
    var source = ctx.createBufferSource();
    source.buffer = buf;
    source.connect(ctx.destination);
    source.start(startTime);
    nextPlaybackTime = startTime + buf.duration;
    scheduledSources.push(source);
    source.onended = function () {
      var idx = scheduledSources.indexOf(source);
      if (idx !== -1) scheduledSources.splice(idx, 1);
    };
  }

  function clearPlayback() {
    var count = scheduledSources.length;
    if (count > 0 || nextPlaybackTime > 0) {
      console.log('[barge-in] Playback stopping. Active sources:', count, 'nextPlaybackTime:', nextPlaybackTime);
    }
    for (var i = 0; i < scheduledSources.length; i++) {
      try { scheduledSources[i].stop(); } catch (_) {}
    }
    scheduledSources = [];
    nextPlaybackTime = 0;
    if (count > 0) {
      console.log('[barge-in] Playback queue cleared.');
    }
  }

  function performExport(opts) {
    if (!state.assignmentId) return false;
    var answers = state.questions.map(function (q) {
      return { question_id: q.id, answer_text: state.answers[q.id] || '' };
    });
    var source = (opts && opts.source) || 'manual';
    var href = '/export/' + state.assignmentId;
    console.log('[voice-export] Triggering PDF export.', { source: source, href: href });
    errorsEl.textContent = 'Exporting your PDF... your browser should download the file.';
    setChecklistStep(setupStepExport, true);
    fetch(href, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers: answers })
    })
      .then(function (res) {
        if (!res.ok) {
          return res.text().then(function (text) {
            throw new Error(text || res.statusText || 'Export failed');
          });
        }
        return res.blob();
      })
      .then(function (blob) {
        var url = window.URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'claros-' + state.assignmentId + '.pdf';
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(function () { window.URL.revokeObjectURL(url); }, 0);
        errorsEl.textContent = '';
      })
      .catch(function (err) {
        errorsEl.textContent = (err && err.message) || 'Export failed';
        setChecklistStep(setupStepExport, false);
      });
    return true;
  }

  function triggerVoiceExport(raw, norm) {
    if (!hasExportIntent(norm)) return;
    if (!state.assignmentId) return;
    if (norm === lastExportVoiceNorm) {
      console.log('[voice-export] Skipping duplicate export phrase for same normalized utterance.');
      return;
    }
    console.log('[voice-export] Voice export intent detected.', { raw: raw, normalized: norm });
    var ok = performExport({ source: 'voice' });
    if (ok) {
      lastExportVoiceNorm = norm;
    }
  }

  function triggerWrite(questionId) {
    var qid = questionId;
    var candPreview = (answerCandidate[qid] || '').slice(0, 120);
    var aid = state.assignmentId;
    console.log('[write-chain] triggerWrite qid=' + qid + ' writeInProgress=' + writeInProgress + ' answerCandidate preview=' + (candPreview ? '"' + candPreview + '"' : '(empty)') + ' assignmentId=' + (aid || '(null)'));
    if (writeInProgress) {
      console.log('[write-chain] Aborting triggerWrite: writeInProgress is true');
      return;
    }
    var selector = '.answer-field[data-question-id="' + questionId + '"]';
    var el = document.querySelector(selector);
    var card = getCardEl(questionId);
    if (!el) {
      console.log('[write-chain] triggerWrite aborted: element not found selector=' + selector);
      return;
    }
    writeInProgress = true;
    setStatus('writing');
    el.textContent = '';
    state.answers[questionId] = '';
    if (card) card.classList.add('writing');
    var url = API_BASE + '/api/write/' + state.assignmentId;
    console.log('[write-chain] Sending fetch qid=' + qid + ' url=' + url);
    var body = JSON.stringify({
      question_id: questionId,
      conversation: conversationContext,
      answer_candidate: answerCandidate[questionId] || ''
    });
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body })
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return {}; }).then(function (data) {
            throw new Error(data.detail || res.statusText || 'Write failed');
          });
        }
        return res.body.getReader();
      })
      .then(function (reader) {
        var decoder = new TextDecoder();
        var totalChars = 0;
        var firstChunkLogged = false;
        function read() {
          return reader.read().then(function (_ref) {
            var done = _ref.done;
            var value = _ref.value;
            if (done) {
              console.log('[write-chain] Stream done qid=' + qid + ' totalCharsAppended=' + totalChars);
              return;
            }
            var text = decoder.decode(value, { stream: true });
            if (text) {
              if (!firstChunkLogged) {
                console.log('[write-chain] First chunk received qid=' + qid + ' chunkLength=' + text.length + ' chunkPreview=' + (text.length > 80 ? '"' + text.slice(0, 80) + '..."' : '"' + text + '"'));
                firstChunkLogged = true;
              }
              totalChars += text.length;
              var targetEl = document.querySelector(selector);
              if (!targetEl) {
                console.log('[write-chain] DOM update FAILED qid=' + qid + ' selector=' + selector + ' elementFound=false (element missing when appending)');
              } else {
                var raw = (targetEl.textContent || '') + text;
                targetEl.textContent = raw.replace(/\$([^$]+)\$/g, '$1');
                state.answers[questionId] = targetEl.textContent;
                console.log('[write-chain] DOM updated qid=' + qid + ' selector=' + selector + ' elementFound=true lengthAfterAppend=' + targetEl.textContent.length);
              }
              exportBtn.classList.add('visible');
            }
            return read();
          });
        }
        return read();
      })
      .catch(function (err) {
        errorsEl.textContent = err.message || 'Write failed';
      })
      .finally(function () {
        writeInProgress = false;
        if (card) card.classList.remove('writing');
        setStatus(liveSession ? 'listening' : 'idle');
      });
  }

  /* ?????? Mic level meter ?????? */
  function startMeter(stream) {
    var ctx = new (window.AudioContext || window.webkitAudioContext)();
    var src = ctx.createMediaStreamSource(stream);
    var analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.8;
    src.connect(analyser);
    var data = new Uint8Array(analyser.frequencyBinCount);
    function tick() {
      if (!mediaStream || !mediaStream.active) return;
      analyser.getByteFrequencyData(data);
      var sum = 0;
      for (var i = 0; i < data.length; i++) sum += data[i];
      meterBar.style.width = Math.min(100, (sum / data.length) * 2) + '%';
      requestAnimationFrame(tick);
    }
    tick();
  }

  /* ?????? Session lifecycle (direct Gemini Live) ?????? */
  async function startSession() {
    if (!state.assignmentId) return;
    errorsEl.textContent = '';
    setStatus('connecting');
    micBtn.disabled = true;
    micBtn.textContent = 'Connecting\u2026';
    conversationContext = [];
    answerReady = {};
    answerCandidate = {};
    currentQuestion = null;
    clarosOutputBuffer = '';
    userTranscriptBuffer = '';

    var config;
    try {
      var r = await fetch(API_BASE + '/api/session-config/' + state.assignmentId);
      if (!r.ok) throw new Error(r.status === 404 ? 'Assignment not found' : (await r.text()) || 'Session config failed');
      config = await r.json();
    } catch (e) {
      errorsEl.textContent = e.message || 'Failed to start session configuration';
      setStatus('idle');
      micBtn.disabled = false;
      micBtn.textContent = 'Start Session';
      return;
    }

    var GoogleGenAI;
    try {
      var mod = await import((API_BASE + '/genai.bundle.js'));
      GoogleGenAI = mod.GoogleGenAI || mod.default;
    } catch (e) {
      errorsEl.textContent = 'Failed to load Gemini SDK. ' + (e.message || 'Check console for details.');
      if (typeof console !== 'undefined' && console.error) console.error('Gemini SDK load error:', e);
      setStatus('idle');
      micBtn.disabled = false;
      micBtn.textContent = 'Start Session';
      return;
    }

    var ai = new GoogleGenAI({
      apiKey: config.token,
      httpOptions: { apiVersion: 'v1alpha' }
    });
    if (typeof console !== 'undefined' && console.log) {
      console.log('[Claros] Live connect: token present=' + !!(config.token) + ', token length=' + (config.token ? String(config.token).length : 0) + ', model=' + (config.model || '') + ', apiVersion=v1alpha, SDK client created with v1alpha');
    }
    var session;
    try {
      session = await ai.live.connect({
        model: config.model,
        config: {
          responseModalities: ['AUDIO'],
          speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: 'Puck' } } },
          systemInstruction: { parts: [{ text: config.system_prompt || '' }] },
          inputAudioTranscription: {
            // Prefer activity-based turns to reduce false positives from background noise,
            // while still allowing responsive interruption.
            mode: 'ACTIVITY',
            interimResults: true
          },
          outputAudioTranscription: {
            // Keep Claros' spoken turns well-bounded.
            mode: 'TURN_BASED'
          }
        },
        callbacks: {
          onmessage: function (msg) {
            var sc = msg.serverContent;
            if (!sc) return;
            if (sc.setupComplete) {
              setStatus('listening');
              setChecklistStep(setupStepSession, true);
              return;
            }
            if (sc.inputTranscription && sc.inputTranscription.text) {
              userTranscriptBuffer += sc.inputTranscription.text;
              var wasSpeaking = (scheduledSources && scheduledSources.length > 0) || currentMode === 'speaking';
              if (wasSpeaking) {
                console.log('[barge-in] Interruption detected: user started speaking while Claros audio was playing.');
              }
              clearPlayback();
              activeClarosMsg = null;
              if (wasSpeaking) {
                setStatus('listening');
                console.log('[barge-in] Playback stopped and listening resumed.');
              }
              showUserPartial(sc.inputTranscription.text);
            }
            if (sc.outputTranscription && sc.outputTranscription.text) {
              var text = sc.outputTranscription.text;
              conversationContext.push({ speaker: 'claros', text: text });
              addTranscript('claros', text);
              clarosOutputBuffer += text;
              if (clarosOutputBuffer.length > 2000) clarosOutputBuffer = clarosOutputBuffer.slice(-1000);
              var m = CLAROS_WRITE_PHRASE_RE.exec(clarosOutputBuffer);
              if (m) {
                var qid = parseClarosWriteQuestionNum(clarosOutputBuffer);
                var matchedText = m[0];
                console.log('[write-chain] Claros write phrase detected qid=' + qid + ' text="' + matchedText + '"');
                if (!writeInProgress) {
                  if (!answerReady[qid]) {
                    answerReady[qid] = true;
                    answerCandidate[qid] = clarosOutputBuffer.trim() || (answerCandidate[qid] || '');
                    var cardT = getCardEl(qid);
                    if (cardT) cardT.classList.add('answer-ready');
                    console.log('[write-chain] Set answerReady from Claros write phrase qid=' + qid + ' candidateLen=' + (answerCandidate[qid] || '').length);
                  }
                  clarosOutputBuffer = '';
                  console.log('[write-chain] triggerWrite about to run qid=' + qid);
                  triggerWrite(qid);
                } else {
                  console.log('[write-chain] Skipping triggerWrite (phrase path): writeInProgress=true');
                }
              }
            }
            if (sc.modelTurn && sc.modelTurn.parts) {
              for (var i = 0; i < sc.modelTurn.parts.length; i++) {
                var part = sc.modelTurn.parts[i];
                if (part.inlineData && part.inlineData.data) {
                  queuePcm24kChunk(part.inlineData.data);
                  if (!writeInProgress) setStatus('speaking');
                }
              }
            }
            if (sc.turnComplete) {
              var full = userTranscriptBuffer.trim();
              userTranscriptBuffer = '';
              clearUserPartial();
              activeClarosMsg = null;
              setStatus('listening');
              if (full) {
                var norm = normalizeTranscript(full);
                console.log('[transcript] Final turn.', {
                  raw: full,
                  normalized: norm
                });
                conversationContext.push({ speaker: 'user', text: full });
                addTranscript('user', full);
                var parsedQuestion = parseQuestionNum(norm);
                if (parsedQuestion != null) currentQuestion = parsedQuestion;
                if (ANSWER_STATED_RE.test(norm)) {
                  var tq = parsedQuestion != null ? parsedQuestion : currentQuestion;
                  if (tq != null) {
                    answerReady[tq] = true;
                    answerCandidate[tq] = full;
                    var cardT = getCardEl(tq);
                    if (cardT) cardT.classList.add('answer-ready');
                  }
                }
                var hasIntent = WRITE_INTENT_RE.test(norm);
                var qid = parsedQuestion != null ? parsedQuestion : (currentQuestion || 1);
                var readyBefore = !!answerReady[qid];
                var candidateBefore = answerCandidate[qid] || '';
                var usedFallback = false;
                if (hasIntent && !answerReady[qid] && ANSWER_STATED_RE.test(norm)) {
                  usedFallback = true;
                  answerReady[qid] = true;
                  answerCandidate[qid] = full;
                  console.log('[intent] Fallback applied for write.', {
                    qid: qid,
                    answerCandidatePreview: full.slice(0, 120)
                  });
                }
                console.log('[intent] Write decision.', {
                  raw: full,
                  normalized: norm,
                  qid: qid,
                  hasWriteIntent: hasIntent,
                  answerReadyBeforeFallback: readyBefore,
                  answerCandidateBeforeFallback: candidateBefore.slice(0, 120),
                  usedFallback: usedFallback,
                  answerReadyAfterFallback: !!answerReady[qid],
                  finalAnswerCandidatePreview: (answerCandidate[qid] || '').slice(0, 120),
                  writeInProgress: writeInProgress
                });
                if (hasIntent && answerReady[qid] && !writeInProgress) {
                  console.log('[write-chain] triggerWrite about to run qid=' + qid);
                  triggerWrite(qid);
                } else if (hasIntent && !answerReady[qid]) {
                  console.log('[intent] Not writing because answerReady is false after fallback.', { qid: qid });
                }
                if (hasExportIntent(norm)) {
                  console.log('[intent] Export intent matched.', { normalized: norm });
                }
                triggerVoiceExport(full, norm);
              }
            }
          },
          onerror: function (e) { errorsEl.textContent = (e && e.message) || 'Gemini Live error'; },
          onclose: function () { setStatus('idle'); stopSession(); }
        }
      });
    } catch (e) {
      errorsEl.textContent = (e && e.message) || 'Failed to connect to Gemini Live';
      setStatus('idle');
      micBtn.disabled = false;
      micBtn.textContent = 'Start Session';
      return;
    }

    liveSession = session;
    setStatus('listening');

    var stream;
    try {
      var audioConstraints = {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1
      };
      stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
    } catch (e) {
      errorsEl.textContent = 'Microphone access is required for voice tutoring. Please allow access and try again.';
      if (liveSession.close) liveSession.close();
      liveSession = null;
      setStatus('idle');
      micBtn.disabled = false;
      micBtn.textContent = 'Start Session';
      return;
    }
    mediaStream = stream;
    try {
      var tracks = mediaStream.getAudioTracks();
      if (tracks && tracks[0]) {
        console.log('[mic] Track settings granted:', tracks[0].getSettings());
      }
    } catch (_) {}
    startMeter(stream);

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    var inputRate = audioContext.sampleRate;
    var ratio = inputRate / SAMPLE_RATE;
    sourceNode = audioContext.createMediaStreamSource(stream);
    processorNode = audioContext.createScriptProcessor(1024, 1, 1);
    processorNode.onaudioprocess = function (e) {
      if (!liveSession) return;
      var input = e.inputBuffer.getChannelData(0);
      var outSamples = Math.floor(input.length / ratio);
      var out = new Int16Array(outSamples);
      for (var i = 0; i < outSamples; i++) {
        var idx = Math.min(Math.floor(i * ratio), input.length - 1);
        var s = Math.max(-1, Math.min(1, input[idx]));
        out[i] = s < 0 ? s * 32768 : s * 32767;
      }
      try {
        liveSession.sendRealtimeInput({ audio: { data: int16ArrayToBase64(out), mimeType: 'audio/pcm;rate=16000' } });
      } catch (_) {}
    };
    sourceNode.connect(processorNode);
    processorNode.connect(audioContext.destination);

    var SILENT_320 = new Int16Array(320);
    keepaliveInterval = setInterval(function () {
      if (!liveSession) return;
      try {
        liveSession.sendRealtimeInput({ audio: { data: int16ArrayToBase64(SILENT_320), mimeType: 'audio/pcm;rate=16000' } });
      } catch (_) {}
    }, 5000);

    micBtn.disabled = false;
    micBtn.textContent = 'End Session';
    micBtn.classList.add('stop');
    interruptBtn.classList.add('visible');
    syncChecklist();
  }

  function stopSession() {
    if (keepaliveInterval) { clearInterval(keepaliveInterval); keepaliveInterval = null; }
    clearPlayback();
    if (processorNode) {
      try { processorNode.disconnect(); sourceNode && sourceNode.disconnect(); } catch (_) {}
      processorNode = null; sourceNode = null;
    }
    if (mediaStream) { mediaStream.getTracks().forEach(function (t) { t.stop(); }); mediaStream = null; }
    if (liveSession && liveSession.close) { try { liveSession.close(); } catch (_) {} liveSession = null; }
    nextPlaybackTime = 0;
    if (audioContext) { audioContext.close(); audioContext = null; }
    meterBar.style.width = '0%';
    micBtn.disabled = !state.assignmentId;
    micBtn.textContent = 'Start Session';
    micBtn.classList.remove('stop');
    interruptBtn.classList.remove('visible');
    setStatus('idle');
    activeClarosMsg = null;
    clearUserPartial();
    syncChecklist();
  }

  function interruptAgent() {
    if (!liveSession) return;
    clearPlayback();
    setStatus('listening');
    if (errorsEl) errorsEl.textContent = '';
  }

  interruptBtn.addEventListener('click', function () { interruptAgent(); });

  micBtn.addEventListener('click', function () {
    if (liveSession) stopSession();
    else startSession();
  });

  exportBtn.addEventListener('click', function () {
    performExport({ source: 'button' });
  });

  syncChecklist();

  if (new URLSearchParams(location.search).get('sample') === '1' && !state.assignmentId && testPdfBtn) {
    loadSamplePdf();
  }
})();
