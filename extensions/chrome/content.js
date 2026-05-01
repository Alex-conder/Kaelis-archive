/**
 * Kaelis Chrome Extension — Content Script (Enhanced v2)
 *
 * Features:
 * - Auto-extract dialogue context from ChatGPT, Claude, Gemini
 * - Floating memory panel with search & recommendations
 * - Auto-suggest relevant memories as user types
 * - Message bridge to background service worker
 */

(function() {
  'use strict';

  const HOST = window.location.hostname;
  let panel = null;
  let suggestionBar = null;
  let lastContext = '';
  let debounceTimer = null;

  // ======================================================================
  // Platform-specific dialogue extractors
  // ======================================================================

  const EXTRACTORS = {
    'chat.openai.com': () => {
      const turns = document.querySelectorAll('[data-testid^="conversation-turn-"]');
      const msgs = [];
      turns.forEach(t => {
        const user = t.querySelector('.whitespace-pre-wrap');
        const assistant = t.querySelector('.markdown');
        if (user) msgs.push({ role: 'user', text: user.innerText.trim() });
        if (assistant) msgs.push({ role: 'assistant', text: assistant.innerText.trim() });
      });
      return msgs;
    },
    'claude.ai': () => {
      const turns = document.querySelectorAll('[data-testid="user-message"], [data-testid="assistant-message"]');
      const msgs = [];
      turns.forEach(t => {
        const isUser = t.getAttribute('data-testid') === 'user-message';
        const text = t.innerText.trim();
        if (text) msgs.push({ role: isUser ? 'user' : 'assistant', text });
      });
      return msgs;
    },
    'gemini.google.com': () => {
      const userMsgs = document.querySelectorAll('.user-query');
      const modelMsgs = document.querySelectorAll('.model-response-text');
      const msgs = [];
      const maxLen = Math.max(userMsgs.length, modelMsgs.length);
      for (let i = 0; i < maxLen; i++) {
        if (userMsgs[i]) msgs.push({ role: 'user', text: userMsgs[i].innerText.trim() });
        if (modelMsgs[i]) msgs.push({ role: 'assistant', text: modelMsgs[i].innerText.trim() });
      }
      return msgs;
    },
  };

  function extractDialogue() {
    const extractor = EXTRACTORS[HOST];
    const msgs = extractor ? extractor() : [];
    const text = msgs.slice(-4).map(m => `${m.role}: ${m.text}`).join('\n');
    return { messages: msgs, text, hasContent: msgs.length > 0 };
  }

  // ======================================================================
  // Floating Memory Panel
  // ======================================================================

  function createPanel() {
    if (panel) return panel;

    panel = document.createElement('div');
    panel.id = 'kaelis-web-panel';
    panel.innerHTML = `
      <div id="kaelis-header">
        <span>🧠 Kaelis</span>
        <div style="display:flex;gap:8px;align-items:center">
          <span id="kaelis-ws-status" style="font-size:10px;color:#64748b">●</span>
          <button id="kaelis-close">×</button>
        </div>
      </div>
      <div id="kaelis-body">
        <input id="kaelis-input" type="text" placeholder="Search memory..." />
        <div id="kaelis-recommendations" style="margin-bottom:10px"></div>
        <div id="kaelis-results"></div>
      </div>
    `;

    const style = document.createElement('style');
    style.textContent = `
      #kaelis-web-panel {
        position: fixed;
        top: 80px;
        right: 20px;
        width: 300px;
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 12px;
        color: #e2e8f0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        z-index: 999999;
        box-shadow: 0 10px 40px rgba(0,0,0,0.4);
        overflow: hidden;
      }
      #kaelis-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 14px;
        background: #1e293b;
        font-weight: 600;
        font-size: 14px;
      }
      #kaelis-close {
        background: none;
        border: none;
        color: #94a3b8;
        font-size: 18px;
        cursor: pointer;
      }
      #kaelis-body {
        padding: 12px;
      }
      #kaelis-input {
        width: 100%;
        padding: 8px 10px;
        border-radius: 8px;
        border: 1px solid #334155;
        background: #1e293b;
        color: #e2e8f0;
        font-size: 13px;
        box-sizing: border-box;
        margin-bottom: 10px;
      }
      #kaelis-results {
        max-height: 200px;
        overflow-y: auto;
        font-size: 12px;
      }
      .kaelis-result-item {
        padding: 8px;
        background: #1e293b;
        border-radius: 6px;
        margin-bottom: 6px;
        cursor: pointer;
      }
      .kaelis-result-item:hover {
        background: #334155;
      }
      .kaelis-rec-chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 8px;
        background: #1e3a5f;
        border: 1px solid #3b82f6;
        border-radius: 6px;
        font-size: 11px;
        color: #93c5fd;
        cursor: pointer;
        margin: 0 4px 4px 0;
      }
      .kaelis-rec-chip:hover {
        background: #2563eb;
        color: white;
      }
      #kaelis-ws-status.connected { color: #22c55e; }
      #kaelis-ws-status.disconnected { color: #ef4444; }
    `;
    document.head.appendChild(style);
    document.body.appendChild(panel);

    panel.querySelector('#kaelis-close').addEventListener('click', () => {
      panel.style.display = 'none';
    });

    const input = panel.querySelector('#kaelis-input');
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') searchMemory(input.value);
    });

    return panel;
  }

  function showPanel() {
    const p = createPanel();
    p.style.display = 'block';
    refreshRecommendations();
  }

  function togglePanel() {
    const p = createPanel();
    p.style.display = p.style.display === 'none' ? 'block' : 'none';
    if (p.style.display === 'block') refreshRecommendations();
  }

  // ======================================================================
  // Memory Search
  // ======================================================================

  function searchMemory(query) {
    const resultsDiv = panel.querySelector('#kaelis-results');
    resultsDiv.innerHTML = '<div style="color:#94a3b8">Searching...</div>';

    chrome.runtime.sendMessage(
      { type: 'KAELIS_MEMORY_SEARCH', query },
      (response) => {
        if (!response || !response.success) {
          resultsDiv.innerHTML = '<div style="color:#ef4444">Kaelis offline</div>';
          return;
        }
        const items = response.data?.data || [];
        if (!items.length) {
          resultsDiv.innerHTML = '<div style="color:#94a3b8">No memory found</div>';
          return;
        }
        resultsDiv.innerHTML = items.map(item => `
          <div class="kaelis-result-item" title="${(item.value || '').substring(0, 100)}">
            <strong>${item.key || 'Memory'}</strong>
            <div style="color:#94a3b8;margin-top:2px">${(item.value || '').substring(0, 60)}...</div>
          </div>
        `).join('');
      }
    );
  }

  // ======================================================================
  // Auto-Recommendation Bar
  // ======================================================================

  function createSuggestionBar() {
    if (suggestionBar) return suggestionBar;

    suggestionBar = document.createElement('div');
    suggestionBar.id = 'kaelis-suggestions';
    suggestionBar.style.cssText = `
      position: fixed;
      bottom: 80px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 999998;
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      max-width: 600px;
      pointer-events: none;
    `;
    document.body.appendChild(suggestionBar);
    return suggestionBar;
  }

  function refreshRecommendations() {
    if (!panel || panel.style.display === 'none') return;

    const recDiv = panel.querySelector('#kaelis-recommendations');
    const dialogue = extractDialogue();
    if (!dialogue.hasContent) {
      recDiv.innerHTML = '';
      return;
    }

    chrome.runtime.sendMessage(
      { type: 'KAELIS_PROACTIVE_PUSH', context: dialogue.text },
      (response) => {
        if (!response || !response.success) {
          recDiv.innerHTML = '';
          return;
        }
        const items = response.data?.data?.all || [];
        if (!items.length) {
          recDiv.innerHTML = '';
          return;
        }
        recDiv.innerHTML = `
          <div style="font-size:11px;color:#94a3b8;margin-bottom:6px">💡 Relevant memories</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px">
            ${items.slice(0, 5).map(item => `
              <span class="kaelis-rec-chip" data-key="${(item.key || '').replace(/"/g, '&quot;')}">
                ${(item.key || 'Memory').substring(0, 20)}
              </span>
            `).join('')}
          </div>
        `;
        recDiv.querySelectorAll('.kaelis-rec-chip').forEach(chip => {
          chip.addEventListener('click', () => {
            searchMemory(chip.dataset.key);
          });
        });
      }
    );
  }

  function showInlineSuggestions(items) {
    const bar = createSuggestionBar();
    if (!items || !items.length) {
      bar.innerHTML = '';
      return;
    }
    bar.innerHTML = items.slice(0, 3).map(item => `
      <span class="kaelis-rec-chip" style="pointer-events:auto" data-key="${(item.key || '').replace(/"/g, '&quot;')}">
        💡 ${(item.reason || item.key || 'Memory').substring(0, 25)}
      </span>
    `).join('');
    bar.querySelectorAll('.kaelis-rec-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        // Try to insert into chat input
        const input = findChatInput();
        if (input) {
          input.value += (input.value ? '\n' : '') + `Based on my memory: ${chip.dataset.key}`;
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        showPanel();
        searchMemory(chip.dataset.key);
      });
    });
  }

  function findChatInput() {
    const selectors = [
      'textarea[placeholder*="message"]',
      'textarea[placeholder*="Message"]',
      'textarea[placeholder*="Ask"]',
      'textarea[placeholder*="Chat"]',
      '[contenteditable="true"]',
      '#prompt-textarea',
    ];
    for (const s of selectors) {
      const el = document.querySelector(s);
      if (el) return el;
    }
    return null;
  }

  // ======================================================================
  // Auto-sense user typing
  // ======================================================================

  function onUserInput() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const dialogue = extractDialogue();
      if (!dialogue.hasContent || dialogue.text === lastContext) return;
      lastContext = dialogue.text;

      chrome.runtime.sendMessage(
        { type: 'KAELIS_PROACTIVE_PUSH', context: dialogue.text },
        (response) => {
          if (!response || !response.success) return;
          const items = response.data?.data?.all || [];
          showInlineSuggestions(items);
        }
      );
    }, 1500);
  }

  // ======================================================================
  // Message bridge from background / popup
  // ======================================================================

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'TOGGLE_PANEL') {
      togglePanel();
      sendResponse({ success: true });
      return true;
    }

    if (request.type === 'GET_DIALOGUE') {
      const dialogue = extractDialogue();
      sendResponse({ success: true, context: dialogue.text, messages: dialogue.messages });
      return true;
    }

    if (request.type === 'WS_STATUS') {
      const dot = panel?.querySelector('#kaelis-ws-status');
      if (dot) {
        dot.className = request.connected ? 'connected' : 'disconnected';
      }
      sendResponse({ success: true });
      return true;
    }
  });

  // ======================================================================
  // Keyboard shortcuts
  // ======================================================================

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'K') {
      e.preventDefault();
      togglePanel();
    }
  });

  // ======================================================================
  // Auto-observe chat input changes
  // ======================================================================

  function observeChatInput() {
    const input = findChatInput();
    if (input) {
      input.addEventListener('input', onUserInput);
    }
    // Re-check periodically for dynamic inputs
    setInterval(() => {
      const inp = findChatInput();
      if (inp && !inp._kaelisBound) {
        inp._kaelisBound = true;
        inp.addEventListener('input', onUserInput);
      }
    }, 2000);
  }

  observeChatInput();
  console.log('[Kaelis] Content script loaded on', HOST);
})();
