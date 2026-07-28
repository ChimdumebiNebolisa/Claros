/**
 * Gemini Live transport helpers isolated from Claros product/session state.
 * Owns PCM encode, playback queue, capture wiring, and provider interrupt signals.
 */
'use strict';

(function (root) {
  const SAMPLE_RATE = 16000;
  const OUT_SAMPLE_RATE = 24000;

  function int16ArrayToBase64(values) {
    const bytes = new Uint8Array(values.buffer);
    let binary = '';
    for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]);
    return btoa(binary);
  }

  function createTransport() {
    let audioContext = null;
    let sourceNode = null;
    let processorNode = null;
    let silentGain = null;
    let keepaliveInterval = null;
    let playbackContext = null;
    let nextPlaybackTime = 0;
    let scheduledSources = [];

    function clearPlayback() {
      scheduledSources.forEach(function (source) {
        try { source.stop(); } catch (_) {}
      });
      scheduledSources = [];
      nextPlaybackTime = 0;
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

    function hasScheduledPlayback() {
      return scheduledSources.length > 0;
    }

    function startCapture(stream, sendAudio) {
      stopCapture();
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const ratio = audioContext.sampleRate / SAMPLE_RATE;
      sourceNode = audioContext.createMediaStreamSource(stream);
      processorNode = audioContext.createScriptProcessor(1024, 1, 1);
      silentGain = audioContext.createGain();
      silentGain.gain.value = 0;
      processorNode.onaudioprocess = function (event) {
        const input = event.inputBuffer.getChannelData(0);
        const output = new Int16Array(Math.floor(input.length / ratio));
        for (let index = 0; index < output.length; index += 1) {
          const sample = Math.max(-1, Math.min(1, input[Math.min(Math.floor(index * ratio), input.length - 1)]));
          output[index] = sample < 0 ? sample * 32768 : sample * 32767;
        }
        try {
          sendAudio({
            data: int16ArrayToBase64(output),
            mimeType: 'audio/pcm;rate=16000',
          });
        } catch (_) {}
      };
      sourceNode.connect(processorNode);
      // Keep the processor graph alive without monitoring into speakers.
      processorNode.connect(silentGain);
      silentGain.connect(audioContext.destination);
      const silence = new Int16Array(320);
      keepaliveInterval = setInterval(function () {
        try {
          sendAudio({
            data: int16ArrayToBase64(silence),
            mimeType: 'audio/pcm;rate=16000',
          });
        } catch (_) {}
      }, 5000);
    }

    function stopCapture() {
      if (keepaliveInterval) clearInterval(keepaliveInterval);
      keepaliveInterval = null;
      clearPlayback();
      if (processorNode) {
        try {
          processorNode.disconnect();
          if (sourceNode) sourceNode.disconnect();
          if (silentGain) silentGain.disconnect();
        } catch (_) {}
      }
      processorNode = null;
      sourceNode = null;
      silentGain = null;
      if (audioContext) {
        try { audioContext.close(); } catch (_) {}
      }
      audioContext = null;
    }

    function interruptProvider(session) {
      clearPlayback();
      if (!session) return false;
      try {
        if (typeof session.sendRealtimeInput === 'function') {
          session.sendRealtimeInput({ activityEnd: {} });
          return true;
        }
      } catch (_) {}
      return false;
    }

    function closeSession(session) {
      if (!session || typeof session.close !== 'function') return;
      try { session.close(); } catch (_) {}
    }

    return {
      startCapture: startCapture,
      stopCapture: stopCapture,
      queuePcm24kChunk: queuePcm24kChunk,
      clearPlayback: clearPlayback,
      hasScheduledPlayback: hasScheduledPlayback,
      interruptProvider: interruptProvider,
      closeSession: closeSession,
      int16ArrayToBase64: int16ArrayToBase64,
      SAMPLE_RATE: SAMPLE_RATE,
      OUT_SAMPLE_RATE: OUT_SAMPLE_RATE,
    };
  }

  const ClarosVoiceLiveTransport = {
    create: createTransport,
    int16ArrayToBase64: int16ArrayToBase64,
    SAMPLE_RATE: SAMPLE_RATE,
    OUT_SAMPLE_RATE: OUT_SAMPLE_RATE,
  };

  root.ClarosVoiceLiveTransport = ClarosVoiceLiveTransport;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = ClarosVoiceLiveTransport;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
