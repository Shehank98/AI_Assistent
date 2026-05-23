'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
let ws = null;
let wsReconnectTimer = null;
let recognition = null;
let isListening = false;
let ttsEnabled = false;
let thinkingEl = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const conversation = document.getElementById('conversation');
const textInput    = document.getElementById('text-input');
const sendBtn      = document.getElementById('send-btn');
const micBtn       = document.getElementById('mic-btn');
const clearBtn     = document.getElementById('clear-btn');
const ttsBtn       = document.getElementById('tts-btn');
const statusDot    = document.getElementById('status-dot');
const voiceStatus  = document.getElementById('voice-status');

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWS() {
  clearTimeout(wsReconnectTimer);
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${location.host}/ws`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    setDot('online');
  };

  ws.onclose = () => {
    setDot('offline');
    wsReconnectTimer = setTimeout(connectWS, 3000);
  };

  ws.onerror = () => {
    // onclose fires after onerror, handles reconnect
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'thinking') {
      showThinking();
      setDot('thinking');
    } else if (data.type === 'response') {
      hideThinking();
      setDot('online');
      appendMessage('jarvis', data.message);
      if (ttsEnabled) speakText(data.message);
    } else if (data.type === 'error') {
      hideThinking();
      setDot('online');
      appendMessage('error', 'Error: ' + data.message);
    }
  };
}

// ── Messaging ─────────────────────────────────────────────────────────────────
function sendMessage(text) {
  text = (text || '').trim();
  if (!text) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    appendMessage('error', 'Not connected. Reconnecting...');
    connectWS();
    return;
  }
  appendMessage('user', text);
  ws.send(JSON.stringify({ message: text }));
  textInput.value = '';
  resetTextareaHeight();
}

// ── Message rendering ─────────────────────────────────────────────────────────
function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.textContent = text;
  conversation.appendChild(div);
  scrollToBottom();
  return div;
}

function showThinking() {
  hideThinking();
  thinkingEl = appendMessage('thinking', 'Thinking…');
}

function hideThinking() {
  if (thinkingEl) {
    thinkingEl.remove();
    thinkingEl = null;
  }
}

function scrollToBottom() {
  conversation.scrollTop = conversation.scrollHeight;
}

// ── Status dot ────────────────────────────────────────────────────────────────
function setDot(state) {
  statusDot.className = `dot ${state}`;
  statusDot.title = { online: 'Connected', offline: 'Disconnected', thinking: 'Thinking…' }[state] || state;
}

// ── Auto-growing textarea ─────────────────────────────────────────────────────
function resetTextareaHeight() {
  textInput.style.height = 'auto';
}

textInput.addEventListener('input', () => {
  textInput.style.height = 'auto';
  textInput.style.height = Math.min(textInput.scrollHeight, 120) + 'px';
});

// ── Web Speech API — voice INPUT ──────────────────────────────────────────────
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
    isListening = true;
    micBtn.classList.add('listening');
    voiceStatus.textContent = 'Listening…';
  };

  recognition.onresult = (event) => {
    let interim = '';
    let final = '';
    for (const result of event.results) {
      if (result.isFinal) final += result[0].transcript;
      else interim += result[0].transcript;
    }
    textInput.value = final || interim;
    textInput.style.height = 'auto';
    textInput.style.height = Math.min(textInput.scrollHeight, 120) + 'px';

    if (final) {
      sendMessage(final);
      stopListening();
    }
  };

  recognition.onerror = (e) => {
    voiceStatus.textContent = e.error === 'not-allowed'
      ? 'Mic permission denied'
      : `Voice error: ${e.error}`;
    stopListening();
  };

  recognition.onend = () => stopListening();
}

function toggleListening() {
  if (!recognition) return;
  if (isListening) stopListening();
  else startListening();
}

function startListening() {
  try {
    recognition.start();
  } catch (e) {
    // Already started; ignore
  }
}

function stopListening() {
  isListening = false;
  micBtn.classList.remove('listening');
  voiceStatus.textContent = '';
  try { recognition.stop(); } catch (e) {}
}

// ── Web Speech API — voice OUTPUT (TTS) ──────────────────────────────────────
function speakText(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  // Strip markdown-ish characters for cleaner speech
  const clean = text.replace(/[*_`#]/g, '').replace(/\n+/g, ' ');
  const utterance = new SpeechSynthesisUtterance(clean);
  utterance.rate = 1.0;
  utterance.pitch = 0.85; // slightly lower = more Jarvis-like
  utterance.volume = 1.0;
  window.speechSynthesis.speak(utterance);
}

function toggleTTS() {
  ttsEnabled = !ttsEnabled;
  ttsBtn.classList.toggle('active', ttsEnabled);
  ttsBtn.title = ttsEnabled ? 'Voice responses ON (tap to mute)' : 'Voice responses OFF';
  if (!ttsEnabled) window.speechSynthesis?.cancel();
}

// ── Clear conversation ────────────────────────────────────────────────────────
async function clearConversation() {
  try {
    await fetch('/api/conversation', { method: 'DELETE' });
  } catch (e) {}
  // Remove all messages except the welcome div
  [...conversation.querySelectorAll('.message:not(.welcome)')].forEach(el => el.remove());
}

// ── Event Listeners ───────────────────────────────────────────────────────────
sendBtn.addEventListener('click', () => sendMessage(textInput.value));

textInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(textInput.value);
  }
});

micBtn.addEventListener('click', toggleListening);
ttsBtn.addEventListener('click', toggleTTS);
clearBtn.addEventListener('click', clearConversation);

// ── Init ──────────────────────────────────────────────────────────────────────
initSpeechRecognition();
connectWS();
textInput.focus();
