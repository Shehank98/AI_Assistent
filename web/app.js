'use strict';

// ── Constants ─────────────────────────────────────────────────────────────────
const WS_BACKOFF = [1000, 2000, 4000, 8000, 16000, 30000];
const ALERT_DURATION = 8000;

// ── State ─────────────────────────────────────────────────────────────────────
let ws = null;
let wsRetry = 0;
let wsReconnectTimer = null;
let recognition = null;
let isListening = false;
let ttsEnabled = localStorage.getItem('tts') === 'true';
let thinkingEl = null;
let settingsOpen = false;

// ── DOM ───────────────────────────────────────────────────────────────────────
const conversation   = document.getElementById('conversation');
const textInput      = document.getElementById('text-input');
const sendBtn        = document.getElementById('send-btn');
const micBtn         = document.getElementById('mic-btn');
const settingsBtn    = document.getElementById('settings-btn');
const settingsClose  = document.getElementById('settings-close');
const settingsDrawer = document.getElementById('settings-drawer');
const settingsOverlay= document.getElementById('settings-overlay');
const clearBtn       = document.getElementById('clear-btn');
const ttsToggle      = document.getElementById('tts-toggle');
const connStatusText = document.getElementById('conn-status-text');
const toolCountText  = document.getElementById('tool-count-text');
const memoryList     = document.getElementById('memory-list');
const refreshMemory  = document.getElementById('refresh-memory');
const statusDot      = document.getElementById('status-dot');
const voiceStatus    = document.getElementById('voice-status');
const alertBanner    = document.getElementById('alert-banner');
const alertText      = document.getElementById('alert-text');
const alertClose     = document.getElementById('alert-close');

// ── Init ──────────────────────────────────────────────────────────────────────
ttsToggle.checked = ttsEnabled;
connectWS();
initSpeechRecognition();
textInput.focus();
fetchStatus();

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWS() {
  clearTimeout(wsReconnectTimer);
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    wsRetry = 0;
    setDot('online');
    connStatusText.textContent = 'Connected';
  };

  ws.onclose = () => {
    setDot('offline');
    connStatusText.textContent = 'Disconnected';
    const delay = WS_BACKOFF[Math.min(wsRetry, WS_BACKOFF.length - 1)];
    wsRetry++;
    wsReconnectTimer = setTimeout(connectWS, delay);
  };

  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.type === 'thinking') {
      showThinking();
      setDot('thinking');
    } else if (data.type === 'response') {
      hideThinking();
      setDot('online');
      appendMessage('jarvis', data.content || data.message || '');
      if (ttsEnabled) speakText(data.content || data.message || '');
    } else if (data.type === 'alert') {
      hideThinking();
      showAlert(data.content);
      if (ttsEnabled) speakText(data.content);
    } else if (data.type === 'error') {
      hideThinking();
      setDot('online');
      appendMessage('error', data.content || data.message || 'Unknown error');
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
  resetTextareaHeight();
}

// ── Rendering ─────────────────────────────────────────────────────────────────
function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  if (role === 'jarvis') {
    div.innerHTML = renderMarkdown(text);
  } else {
    div.textContent = text;
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
  // Escape HTML first
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks ```...```
  html = html.replace(/```[\s\S]*?```/g, (m) => {
    const code = m.slice(3, -3).replace(/^\w*\n/, '');
    return `<pre><code>${code}</code></pre>`;
  });

  // Inline code `...`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold **...**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Bullet lists (lines starting with - or *)
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  // Collapse nested ul
  html = html.replace(/<\/ul>\s*<ul>/g, '');

  // Paragraphs (double newline)
  html = html.replace(/\n\n+/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');

  return `<p>${html}</p>`;
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
  void alertBanner.offsetWidth; // reflow to restart animation
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
  textInput.style.height = 'auto';
  textInput.style.height = Math.min(textInput.scrollHeight, 130) + 'px';
});

// ── Voice input (Web Speech API) ──────────────────────────────────────────────
function initSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { micBtn.style.display = 'none'; return; }

  recognition = new SR();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    isListening = true;
    micBtn.classList.add('listening');
    voiceStatus.textContent = 'Listening…';
  };

  recognition.onresult = (e) => {
    let interim = '', final = '';
    for (const r of e.results) {
      if (r.isFinal) final += r[0].transcript;
      else interim += r[0].transcript;
    }
    textInput.value = final || interim;
    textInput.style.height = 'auto';
    textInput.style.height = Math.min(textInput.scrollHeight, 130) + 'px';
    if (final) {
      sendMessage(final);
      stopListening();
    }
  };

  recognition.onerror = (e) => {
    voiceStatus.textContent = e.error === 'not-allowed' ? 'Mic permission denied — enable in browser settings' : `Voice error: ${e.error}`;
    stopListening();
  };

  recognition.onend = () => stopListening();
}

function toggleListening() {
  if (!recognition) return;
  isListening ? stopListening() : startListening();
}

function startListening() {
  try { recognition.start(); } catch (_) {}
}

function stopListening() {
  isListening = false;
  micBtn.classList.remove('listening');
  voiceStatus.textContent = '';
  try { recognition.stop(); } catch (_) {}
}

// ── TTS (SpeechSynthesis) ─────────────────────────────────────────────────────
function speakText(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  // Strip markdown and URLs for cleaner speech
  const clean = text
    .replace(/```[\s\S]*?```/g, 'code block')
    .replace(/`[^`]+`/g, '')
    .replace(/\*\*/g, '')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[*_#]/g, '')
    .replace(/\n+/g, ' ')
    .trim();
  if (!clean) return;
  const utt = new SpeechSynthesisUtterance(clean);
  utt.rate = 1.0;
  utt.pitch = 0.88;
  utt.volume = 1.0;
  window.speechSynthesis.speak(utt);
}

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

clearBtn.addEventListener('click', async () => {
  await fetch('/api/conversation', { method: 'DELETE' }).catch(() => {});
  [...conversation.querySelectorAll('.message')].forEach(el => el.remove());
  closeSettings();
});

// ── Memory viewer ─────────────────────────────────────────────────────────────
async function loadMemory() {
  memoryList.textContent = 'Loading…';
  try {
    const res = await fetch('/api/memory');
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
    const res = await fetch('/api/status');
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
