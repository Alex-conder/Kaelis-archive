/**
 * Kaelis Chrome Extension — Content Script
 */
(function() {
  'use strict';
  const SIDEBAR_ID = 'kaelis-sidebar-frame';
  let sidebarVisible = true;

  function createSidebar() {
    if (document.getElementById(SIDEBAR_ID)) return;
    const iframe = document.createElement('iframe');
    iframe.id = SIDEBAR_ID;
    iframe.src = chrome.runtime.getURL('sidebar.html');
    iframe.style.cssText = 'position:fixed;top:0;right:0;width:320px;height:100vh;border:none;z-index:99999;box-shadow:-2px 0 12px rgba(0,0,0,0.15);background:#0f172a;transition:transform 0.3s ease;';
    document.body.appendChild(iframe);
    document.body.style.marginRight = '320px';
  }

  function toggleSidebar() {
    const iframe = document.getElementById(SIDEBAR_ID);
    if (!iframe) { createSidebar(); sidebarVisible = true; return; }
    sidebarVisible = !sidebarVisible;
    iframe.style.transform = sidebarVisible ? 'translateX(0)' : 'translateX(100%)';
    document.body.style.marginRight = sidebarVisible ? '320px' : '0';
  }

  function extractDialogue() {
    const host = window.location.hostname;
    let texts = [];
    if (host.includes('chat.openai.com')) {
      document.querySelectorAll('[data-testid="conversation-turn-2"] .whitespace-pre-wrap').forEach(el => texts.push(el.innerText));
    } else if (host.includes('claude.ai')) {
      document.querySelectorAll('.font-claude-message, .font-user-message').forEach(el => texts.push(el.innerText));
    } else if (host.includes('kimi.moonshot.cn')) {
      document.querySelectorAll('.chat-item-content').forEach(el => texts.push(el.innerText));
    }
    return texts.slice(-4).join('\n').slice(-500);
  }

  createSidebar();

  setInterval(() => {
    const dialogue = extractDialogue();
    if (dialogue.length > 10) {
      chrome.runtime.sendMessage({ type: 'FETCH_MEMORIES', context: dialogue }).catch(() => {});
    }
  }, 30000);

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'TOGGLE_SIDEBAR') { toggleSidebar(); sendResponse({ visible: sidebarVisible }); }
    if (request.type === 'GET_DIALOGUE') { sendResponse({ context: extractDialogue() }); }
  });
})();
