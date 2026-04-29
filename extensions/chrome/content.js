/**
 * Kaelis Chrome Extension — Content Script
 * Injects a floating Kaelis memory panel into AI chat interfaces.
 */

(function() {
  'use strict';

  const HOST = window.location.hostname;
  let panel = null;

  function createPanel() {
    if (panel) return panel;

    panel = document.createElement('div');
    panel.id = 'kaelis-web-panel';
    panel.innerHTML = `
      <div id="kaelis-header">
        <span>🧠 Kaelis</span>
        <button id="kaelis-close">×</button>
      </div>
      <div id="kaelis-body">
        <input id="kaelis-input" type="text" placeholder="Search memory..." />
        <div id="kaelis-results"></div>
      </div>
    `;

    // Styles
    const style = document.createElement('style');
    style.textContent = `
      #kaelis-web-panel {
        position: fixed;
        top: 80px;
        right: 20px;
        width: 280px;
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
    `;
    document.head.appendChild(style);
    document.body.appendChild(panel);

    panel.querySelector('#kaelis-close').addEventListener('click', () => {
      panel.style.display = 'none';
    });

    const input = panel.querySelector('#kaelis-input');
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        searchMemory(input.value);
      }
    });

    return panel;
  }

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

  // 监听 Ctrl/Cmd + Shift + K 唤起面板
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'K') {
      e.preventDefault();
      const p = createPanel();
      p.style.display = p.style.display === 'none' ? 'none' : 'block';
    }
  });

  console.log('Kaelis content script loaded on', HOST);
})();
