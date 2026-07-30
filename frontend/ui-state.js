(function (root) {
  'use strict';

  var WORKSPACE_STATES = [
    'empty', 'uploading', 'parsing', 'ready', 'needs_layout_review',
    'exporting', 'complete', 'error'
  ];
  var VOICE_STATES = [
    'unavailable', 'idle', 'connecting', 'listening', 'speaking',
    'answer_detected', 'confirming', 'confirmed', 'writing', 'stopped', 'error'
  ];

  var workspaceCopy = {
    empty: ['Add a worksheet', 'Choose a selectable-text PDF, or try the sample.'],
    uploading: ['Uploading PDF', 'Sending the selected worksheet.'],
    parsing: ['Preparing worksheet', 'Reading pages and locating answer regions.'],
    ready: ['Worksheet ready', 'Choose a question, then type or start voice guidance.'],
    needs_layout_review: ['Layout review needed', 'Check the marked answer regions before starting.'],
    exporting: ['Preparing your PDF', 'Writing approved answers onto the original worksheet.'],
    complete: ['Export ready', 'Your completed worksheet has downloaded.'],
    error: ['Worksheet could not be prepared', 'Retry this PDF or choose a different file.']
  };

  var voiceCopy = {
    unavailable: ['Voice unavailable', 'Typed answers and export are still available.', 'Offline'],
    idle: ['Session ready', 'Start when you are ready to talk through the selected question.', 'Offline'],
    connecting: ['Connecting', 'Setting up a private voice session.', 'Connecting'],
    listening: ['Listening', 'Claros is listening for your response.', 'Live'],
    speaking: ['Claros is speaking', 'You can interrupt at any time.', 'Live'],
    answer_detected: ['Answer ready for review', 'Check the exact words below.', 'Review'],
    confirming: ['Confirming answer', 'Checking the exact answer you chose.', 'Review'],
    confirmed: ['Answer confirmed', 'Choose Write confirmed answer when you are ready.', 'Ready'],
    writing: ['Writing answer', 'Adding the confirmed answer to the selected destination.', 'Writing'],
    stopped: ['Session ended', 'Your worksheet and typed answers remain available.', 'Offline'],
    error: ['Voice connection failed', 'Continue by typing, or try voice again.', 'Offline']
  };

  function assertState(state, values, domain) {
    if (values.indexOf(state) === -1) throw new Error('Unknown ' + domain + ' state: ' + state);
  }

  function getWorkspaceModel(state, context) {
    assertState(state, WORKSPACE_STATES, 'workspace');
    var copy = workspaceCopy[state];
    var hasAssignment = !!(context && context.hasAssignment);
    return {
      state: state,
      title: copy[0],
      description: copy[1],
      busy: state === 'uploading' || state === 'parsing' || state === 'exporting',
      showSetup: state === 'empty' || state === 'uploading' || state === 'parsing' || state === 'error',
      showWorkspace: hasAssignment && ['ready', 'needs_layout_review', 'exporting', 'complete'].indexOf(state) !== -1,
      showLayoutReview: state === 'needs_layout_review',
      canExport: hasAssignment && state !== 'uploading' && state !== 'parsing' && state !== 'exporting',
      exportLabel: state === 'exporting' ? 'Exporting\u2026' : (state === 'complete' ? 'Export again' : 'Export')
    };
  }

  function getVoiceModel(state, context) {
    assertState(state, VOICE_STATES, 'voice');
    var copy = voiceCopy[state];
    var hasAssignment = !!(context && context.hasAssignment);
    var sessionActive = !!(context && context.liveSession);
    var disabledReason = '';
    if (!hasAssignment) disabledReason = 'Add a worksheet before starting voice.';
    else if (state === 'connecting') disabledReason = 'Claros is still connecting.';
    else if (!sessionActive && state === 'confirmed') disabledReason = 'Write or change the confirmed answer before starting voice.';
    else if (!sessionActive && state === 'writing') disabledReason = 'Wait until the confirmed answer is written.';
    return {
      state: state,
      title: copy[0],
      description: copy[1],
      badge: sessionActive ? copy[2] : (copy[2] === 'Live' ? 'Offline' : copy[2]),
      isLive: sessionActive,
      sessionActive: sessionActive,
      showInterrupt: state === 'speaking',
      showConfirmation: state === 'answer_detected' || state === 'confirming',
      showWriteConfirmation: state === 'confirmed',
      primaryLabel: sessionActive ? 'End voice guidance' : (state === 'connecting' ? 'Connecting\u2026' : (state === 'error' ? 'Try voice again' : 'Use voice guidance')),
      primaryDisabled: !!disabledReason,
      disabledReason: disabledReason
    };
  }

  function getResponseModel(context) {
    context = context || {};
    var placement = context.placementStatus === 'side_panel'
      ? 'side_panel'
      : (context.placementBlocked ? 'blocked' : 'physical');
    var stage = 'capture';
    if (context.writeInProgress) stage = 'writing';
    else if (context.writtenAnswer && context.writtenDestination) stage = 'written';
    else if (context.writeFailure) stage = 'review';
    else if (context.confirmed) stage = 'confirmed';
    else if (context.reviewRequested) stage = 'review';

    return {
      stage: stage,
      placement: placement,
      showEditor: stage === 'capture',
      showReview: stage === 'review',
      showConfirmed: stage === 'confirmed' || stage === 'writing',
      showWritten: stage === 'written',
      typeInsteadVisible: stage === 'capture',
      actionLabel: placement === 'side_panel' ? 'Add to export side panel' : 'Write confirmed answer',
      actionDisabled: placement === 'blocked' || stage === 'writing',
      destinationDescription: placement === 'side_panel'
        ? 'This adds the confirmed answer to the export side panel. The original worksheet page stays unchanged.'
        : (placement === 'blocked'
          ? 'A safe destination is not available. This answer cannot be written yet.'
          : 'This writes the confirmed answer to the selected answer area on the worksheet.'),
      writtenDescription: context.writtenDestination === 'side_panel'
        ? 'Added to the export side panel. The original worksheet page is unchanged.'
        : 'Written to the selected answer area on the worksheet.'
    };
  }

  var api = {
    WORKSPACE_STATES: WORKSPACE_STATES,
    VOICE_STATES: VOICE_STATES,
    getWorkspaceModel: getWorkspaceModel,
    getVoiceModel: getVoiceModel,
    getResponseModel: getResponseModel
  };

  root.ClarosUiState = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : this);
