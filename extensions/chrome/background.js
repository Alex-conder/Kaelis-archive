/**
 * Kaelis Chrome Extension — Background Service Worker
 */

const API_BASE = 'http://localhost:5000';

chrome.runtime.onInstalled.addListener(() => {
  console.log('Kaelis extension installed');
});

// 监听来自 content script 的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'KAELIS_MEMORY_SEARCH') {
    fetch(`${API_BASE}/api/memory/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ layer: 'L2', query: request.query, top_k: 3 })
    })
    .then(r => r.json())
    .then(data => sendResponse({ success: true, data }))
    .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // async response
  }

  if (request.type === 'KAELIS_STATUS') {
    fetch(`${API_BASE}/api/health`)
    .then(r => r.json())
    .then(data => sendResponse({ success: true, online: true, data }))
    .catch(err => sendResponse({ success: false, online: false, error: err.message }));
    return true;
  }
});
