'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────
const WS_BACKOFF = [1000, 2000, 4000, 8000, 16000, 30000];
const ALERT_DURATION = 8000;
const SILENCE_TIMEOUT_MS = 8000;
const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

// ── State ─────────────────────────────────────────────────────────────────────
let ws = null;
let wsRetry = 0;
let wsReconnectTimer = null;
let recognition = null;
let voiceState = 'idle';  // idle | listening | processing | speaking
let continuousMode = localStorage.getItem('continuousMode') !== 'false'; // default ON
let ttsEnabled = localStorage.getItem('tts') === 'true';
let thinkingEl = null;
let settingsOpen = false;
let silenceTimer = null;
let currentUtterance = null;
let bestVoice = null;
let jarvisToken = localStorage.getItem('jarvisToken') || '';

// Audio analysis for waveform
let audioCtx = null;
let analyserNode = null;
let micStream = null;
let waveAnimId = null;

// ── DOM ───────────────────────────────────────────────────────────────────────
const conversation    = document.getElementById('conversation');
const textInput       = document.getElementById('text-input');
const sendBtn         = document.getElementById('send-btn');
const micBtn          = document.getElementById('mic-btn');
const micRing         = document.getElementById('mic-ring');
const waveform        = document.getElementById('waveform');
const waveBars        = [...document.querySelectorAll('.wbar')];
const settingsBtn     = document.getElementById('settings-btn');
const settingsClose   = document.getElementById('settings-close');
const settingsDrawer  = document.getElementById('settings-drawer');
const settingsOverlay = document.getElementById('settings-overlay');
const clearBtn        = document.getElementById('clear-btn');
const ttsToggle       = document.getElementById('tts-toggle');
const continuousToggle= document.getElementById('continuous-toggle');
const connStatusText  = document.getElementById('conn-status-text');
const toolCountText   = document.getElementById('tool-count-text');
const memoryList      = document.getElementById('memory-list');
const refreshMemory   = document.getElementById('refresh-memory');
const statusDot       = document.getElementById('status-dot');
const voiceStatus     = document.getElementById('voice-status');
const alertBanner     = document.getElementById('alert-banner');
const alertText       = document.getElementById('alert-text');
const alertClose      = document.getElementById('alert-close');
const jarvisAvatar    = document.getElementById('jarvis-avatar');
const tokenInput      = document.getElementById('token-input');

// ── Init ──────────────────────────────────────────────────────────────────────
ttsToggle.checked = ttsEnabled;
continuousToggle.checked = continuousMode;
if (tokenInput) tokenInput.value = jarvisToken;

connectWS();
initSpeechRecognition();
textInput.focus();
fetchStatus();

// Pre-load voices (async on Chrome)
if (window.speechSynthesis) {
  window.speechSynthesis.onvoiceschanged = () => { bestVoice = getBestVoice(); };
  bestVoice = getBestVoice();
}

// ── Auth helper ───────────────────────────────────────────────────────────────
function apiFetch(url, options = {}) {
  if (jarvisToken) {
    options.headers = { ...(options.headers || {}), 'X-Jarvis-Token': jarvisToken };
  }
  return fetch(url, options);
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWS() {
  clearTimeout(wsReconnectTimer);
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const tokenParam = jarvisToken ? `?token=${encodeURIComponent(jarvisToken)}` : '';
  ws = new WebSocket(`${proto}//${location.host}/ws${tokenParam}`);

  ws.onopen = () => {
    wsRetry = 0;
    setDot('online');
    connStatusText.textContent = 'Connected';
  };

  ws.onclose = (ev) => {
    setDot('offline');
    connStatusText.textContent = ev.code === 4001 ? 'Auth failed — check token' : 'Disconnected';
    const delay = WS_BACKOFF[Math.min(wsRetry, WS_BACKOFF.length - 1)];
    wsRetry++;
    wsReconnectTimer = setTimeout(connectWS, delay);
  };

  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);

    if (data.type === 'thinking') {
      showThinking();
      setDot('thinking');
      setVoiceState('processing');

    } else if (data.type === 'response') {
      hideThinking();
      setDot('online');
      const text = data.content || data.message || '';
      appendMessage('jarvis', text);
      navigator.vibrate?.([50, 50, 50]);

      if (ttsEnabled && text) {
        speakText(text);
      } else {
        // Not speaking → go back to listening in continuous mode
        if (continuousMode && recognition) {
          setTimeout(() => { if (voiceState !== 'listening') startListening(); }, 300);
        } else {
          setVoiceState('idle');
        }
      }

    } else if (data.type === 'alert') {
      hideThinking();
      showAlert(data.content);
      if (ttsEnabled) speakText(data.content);

    } else if (data.type === 'error') {
      hideThinking();
      setDot('online');
      appendMessage('error', data.content || data.message || 'Unknown error');
      setVoiceState('idle');
    }
  };
}

// ── Messaging ─────────────────────────────────────────────────────────────────
function sendMessage(text) {
  text = (text || '').trim();
  if (!text) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    appendMessage('system', 'Not connected — reconnecting...');
    connectWS();
    return;
  }
  appendMessage('user', text);
  ws.send(JSON.stringify({ message: text }));
  textInput.value = '';
  textInput.classList.remove('interim');
  resetTextareaHeight();
  navigator.vibrate?.(50);
  setVoiceState('processing');
}

// ── Rendering ─────────────────────────────────────────────────────────────────
function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  if (role === 'jarvis') {
    div.innerHTML = renderMarkdown(text);
    const timeEl = document.createElement('time');
    timeEl.className = 'msg-time';
    timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    div.appendChild(timeEl);
  } else {
    div.textContent = text;
    if (role === 'user') {
      const timeEl = document.createElement('time');
      timeEl.className = 'msg-time';
      timeEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      div.appendChild(timeEl);
    }
  }

  conversation.appendChild(div);
  scrollToBottom();
  return div;
}

function showThinking() {
  hideThinking();
  thinkingEl = appendMessage('thinking', 'Thinking…');
}

function hideThinking() {
  if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; }
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    conversation.scrollTop = conversation.scrollHeight;
  });
}

// ── Markdown parser ───────────────────────────────────────────────────────────
function renderMarkdown(text) {
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  html = html.replace(/```[\s\S]*?```/g, (m) => {
    const code = m.slice(3, -3).replace(/^\w*\n/, '');
    return `<pre><code>${code}</code></pre>`;
  });
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  html = html.replace(/<\/ul>\s*<ul>/g, '');
  html = html.replace(/\n\n+/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');

  return `<p>${html}</p>`;
}

// ── Voice state machine ───────────────────────────────────────────────────────
// States: idle | listening | processing | speaking
function setVoiceState(state) {
  voiceState = state;

  // Clear ring classes
  micRing.className = 'mic-ring';
  jarvisAvatar.className = 'avatar';

  switch (state) {
    case 'idle':
      voiceStatus.textContent = continuousMode ? 'Tap mic or speak' : 'Tap to speak';
      stopWaveform();
      break;

    case 'listening':
      micRing.classList.add('state-listening');
      voiceStatus.textContent = 'Listening…';
      clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => {
        // Silence timeout — keep ready but dim
        if (voiceState === 'listening') voiceStatus.textContent = 'Waiting…';
      }, SILENCE_TIMEOUT_MS);
      startWaveform();
      break;

    case 'processing':
      micRing.classList.add('state-processing');
      voiceStatus.textContent = 'Processing…';
      jarvisAvatar.classList.add('thinking');
      stopWaveform();
      break;

    case 'speaking':
      micRing.classList.add('state-speaking');
      voiceStatus.textContent = 'Speaking…';
      jarvisAvatar.classList.add('speaking');
      stopWaveform();
      break;
  }
}

// ── Speech Recognition ────────────────────────────────────────────────────────
function initSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    micBtn.style.display = 'none';
    return;
  }

  recognition = new SR();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    setVoiceState('listening');
  };

  recognition.onresult = (e) => {
    let interim = '', final = '';
    for (const r of e.results) {
      if (r.isFinal) final += r[0].transcript;
      else interim += r[0].transcript;
    }

    // Show interim in textarea as grey ghost text
    if (interim && !final) {
      textInput.value = interim;
      textInput.classList.add('interim');
      textInput.style.height = 'auto';
      textInput.style.height = Math.min(textInput.scrollHeight, 130) + 'px';
    }

    if (final) {
      textInput.classList.remove('interim');

      // Barge-in: if Jarvis was speaking, interrupt
      if (voiceState === 'speaking') {
        window.speechSynthesis?.cancel();
        currentUtterance = null;
      }

      sendMessage(final);

      // On iOS: restart manually after result (recognition auto-stops)
      if (isIOS && continuousMode) {
        setTimeout(() => {
          if (voiceState === 'listening' || voiceState === 'idle') startListening();
        }, 300);
      }
    }
  };

  recognition.onerror = (e) => {
    if (e.error === 'not-allowed') {
      showMicPermissionBanner();
      setVoiceState('idle');
    } else if (e.error === 'no-speech' || e.error === 'aborted') {
      // Expected — restart in continuous mode
      if (continuousMode && voiceState === 'listening') {
        setTimeout(() => startListening(), isIOS ? 300 : 50);
      } else {
        setVoiceState('idle');
      }
    } else {
      voiceStatus.textContent = `Voice error: ${e.error}`;
      setVoiceState('idle');
    }
  };

  recognition.onend = () => {
    // Auto-restart in continuous mode (iOS handles this in onresult)
    if (!isIOS && continuousMode && (voiceState === 'listening' || voiceState === 'idle') && !thinkingEl) {
      setTimeout(() => startListening(), 100);
    } else if (voiceState === 'listening') {
      setVoiceState('idle');
    }
  };

  // Start continuous mode automatically
  if (continuousMode) {
    setTimeout(() => startListening(), 500);
  }
}

function startListening() {
  if (!recognition) return;
  if (voiceState === 'processing') return; // don't interrupt while waiting for Jarvis
  try {
    recognition.stop();
  } catch (_) {}
  setTimeout(() => {
    try {
      recognition.start();
    } catch (_) {}
  }, 50);
}

function stopListening() {
  clearTimeout(silenceTimer);
  try { recognition?.stop(); } catch (_) {}
  setVoiceState('idle');
}

function toggleListening() {
  if (!recognition) return;
  if (voiceState === 'listening') {
    stopListening();
  } else {
    startListening();
  }
}

// ── Waveform visualization ────────────────────────────────────────────────────
async function startWaveform() {
  if (!waveBars.length) return;
  waveform.classList.remove('hidden');

  if (!micStream) {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch (_) {
      waveform.classList.add('hidden');
      return;
    }
  }

  if (!audioCtx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) { waveform.classList.add('hidden'); return; }
    audioCtx = new AC();
  }

  if (!analyserNode) {
    analyserNode = audioCtx.createAnalyser();
    analyserNode.fftSize = 32;
    const src = audioCtx.createMediaStreamSource(micStream);
    src.connect(analyserNode);
  }

  if (audioCtx.state === 'suspended') audioCtx.resume();

  const dataArray = new Uint8Array(analyserNode.frequencyBinCount);

  function drawFrame() {
    if (voiceState !== 'listening') {
      stopWaveform();
      return;
    }
    waveAnimId = requestAnimationFrame(drawFrame);
    analyserNode.getByteFrequencyData(dataArray);
    const count = waveBars.length;
    for (let i = 0; i < count; i++) {
      const v = dataArray[i] / 255;
      const h = Math.max(3, Math.round(v * 22));
      waveBars[i].style.height = h + 'px';
    }
  }
  drawFrame();
}

function stopWaveform() {
  if (waveAnimId) { cancelAnimationFrame(waveAnimId); waveAnimId = null; }
  waveform.classList.add('hidden');
  waveBars.forEach(b => b.style.height = '3px');
}

// ── TTS ───────────────────────────────────────────────────────────────────────
function getBestVoice() {
  if (!window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return null;

  const priority = [
    v => v.name === 'Google UK English Male',
    v => v.name === 'Google US English',
    v => v.name.includes('Microsoft') && v.name.toLowerCase().includes('guy'),
    v => v.lang.startsWith('en') && v.name.toLowerCase().includes('male'),
    v => v.lang.startsWith('en'),
    () => true,
  ];

  for (const check of priority) {
    const match = voices.find(check);
    if (match) return match;
  }
  return null;
}

function stripForSpeech(text) {
  return text
    .replace(/```[\s\S]*?```/g, 'code block')
    .replace(/`[^`]+`/g, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/https?:\/\/\S+/g, 'the link')
    .replace(/[*_#]/g, '')
    .replace(/^[-*] /gm, '')         // bullets → natural sentence flow
    .replace(/\n+/g, '. ')
    .replace(/\.\s*\./g, '.')
    .trim();
}

function speakText(text) {
  if (!window.speechSynthesis) {
    setVoiceState(continuousMode ? 'listening' : 'idle');
    return;
  }

  const clean = stripForSpeech(text);
  if (!clean) {
    setVoiceState(continuousMode ? 'listening' : 'idle');
    return;
  }

  window.speechSynthesis.cancel();
  setVoiceState('speaking');

  const utt = new SpeechSynthesisUtterance(clean);
  utt.rate = 1.05;
  utt.pitch = 0.95;
  utt.volume = 1.0;
  const voice = bestVoice || getBestVoice();
  if (voice) utt.voice = voice;

  utt.onend = () => {
    currentUtterance = null;
    if (continuousMode && recognition) {
      setTimeout(() => startListening(), isIOS ? 400 : 200);
    } else {
      setVoiceState('idle');
    }
  };

  utt.onerror = () => {
    currentUtterance = null;
    setVoiceState(continuousMode ? 'listening' : 'idle');
  };

  currentUtterance = utt;
  window.speechSynthesis.speak(utt);
}

// ── Mic permission banner ─────────────────────────────────────────────────────
function showMicPermissionBanner() {
  const existing = document.getElementById('mic-permission-banner');
  if (existing) return;

  const banner = document.createElement('div');
  banner.id = 'mic-permission-banner';
  banner.innerHTML = `
    <span>Mic access needed for hands-free mode. Enable in browser settings.</span>
    <button id="mic-permission-close">✕</button>
  `;
  document.body.appendChild(banner);

  document.getElementById('mic-permission-close').addEventListener('click', () => {
    banner.classList.add('hidden');
    setTimeout(() => banner.remove(), 300);
  });

  // Auto-hide after 8s
  setTimeout(() => {
    banner.classList.add('hidden');
    setTimeout(() => banner.remove(), 300);
  }, 8000);
}

// ── Status dot ────────────────────────────────────────────────────────────────
function setDot(state) {
  statusDot.className = `dot ${state}`;
}

// ── Alert banner ──────────────────────────────────────────────────────────────
let alertTimer = null;

function showAlert(message) {
  alertBanner.classList.remove('hidden');
  alertText.textContent = message;
  void alertBanner.offsetWidth;
  alertBanner.classList.add('show');
  clearTimeout(alertTimer);
  alertTimer = setTimeout(hideAlert, ALERT_DURATION);
}

function hideAlert() {
  alertBanner.classList.remove('show');
  setTimeout(() => alertBanner.classList.add('hidden'), 400);
}

alertClose.addEventListener('click', hideAlert);

// ── Auto-growing textarea ─────────────────────────────────────────────────────
function resetTextareaHeight() {
  textInput.style.height = 'auto';
}

textInput.addEventListener('input', () => {
  textInput.classList.remove('interim');
  textInput.style.height = 'auto';
  textInput.style.height = Math.min(textInput.scrollHeight, 130) + 'px';
});

// ── Settings ──────────────────────────────────────────────────────────────────
function openSettings() {
  settingsOpen = true;
  settingsDrawer.classList.remove('closed');
  settingsDrawer.classList.add('open');
  settingsOverlay.classList.remove('hidden');
  requestAnimationFrame(() => settingsOverlay.classList.add('visible'));
  loadMemory();
}

function closeSettings() {
  settingsOpen = false;
  settingsDrawer.classList.remove('open');
  settingsDrawer.classList.add('closed');
  settingsOverlay.classList.remove('visible');
  setTimeout(() => settingsOverlay.classList.add('hidden'), 300);
}

settingsBtn.addEventListener('click', openSettings);
settingsClose.addEventListener('click', closeSettings);
settingsOverlay.addEventListener('click', closeSettings);

ttsToggle.addEventListener('change', () => {
  ttsEnabled = ttsToggle.checked;
  localStorage.setItem('tts', ttsEnabled);
  if (!ttsEnabled) window.speechSynthesis?.cancel();
});

continuousToggle.addEventListener('change', () => {
  continuousMode = continuousToggle.checked;
  localStorage.setItem('continuousMode', continuousMode);
  if (continuousMode) {
    startListening();
  } else {
    stopListening();
    window.speechSynthesis?.cancel();
  }
});

if (tokenInput) {
  tokenInput.addEventListener('change', () => {
    jarvisToken = tokenInput.value.trim();
    localStorage.setItem('jarvisToken', jarvisToken);
    // Reconnect WS with new token
    if (ws) ws.close();
    connectWS();
  });
}

clearBtn.addEventListener('click', async () => {
  await apiFetch('/api/conversation', { method: 'DELETE' }).catch(() => {});
  [...conversation.querySelectorAll('.message')].forEach(el => el.remove());
  closeSettings();
});

// ── Memory viewer ─────────────────────────────────────────────────────────────
async function loadMemory() {
  memoryList.textContent = 'Loading…';
  try {
    const res = await apiFetch('/api/memory');
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      memoryList.textContent = err.error || `Error ${res.status}`;
      return;
    }
    const data = await res.json();
    const facts = data.facts || {};
    const keys = Object.keys(facts);
    if (keys.length === 0) {
      memoryList.textContent = 'Nothing stored yet.';
      return;
    }
    memoryList.innerHTML = keys.map(k =>
      `<div class="memory-item"><span class="memory-key">${k}</span><span class="memory-val">${facts[k]}</span></div>`
    ).join('');
  } catch {
    memoryList.textContent = 'Could not load memory.';
  }
}

refreshMemory.addEventListener('click', loadMemory);

// ── Status fetch ──────────────────────────────────────────────────────────────
async function fetchStatus() {
  try {
    const res = await apiFetch('/api/status');
    const data = await res.json();
    toolCountText.textContent = `${data.tool_count} active`;
  } catch {
    toolCountText.textContent = 'unavailable';
  }
}

// ── Input events ──────────────────────────────────────────────────────────────
sendBtn.addEventListener('click', () => sendMessage(textInput.value));
micBtn.addEventListener('click', toggleListening);

textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(textInput.value);
  }
});

// Restore scroll position on reload
window.addEventListener('beforeunload', () => {
  localStorage.setItem('scrollPos', conversation.scrollTop);
});
const savedScroll = localStorage.getItem('scrollPos');
if (savedScroll) conversation.scrollTop = parseInt(savedScroll, 10);
