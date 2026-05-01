/**
 * Kaelis Chrome Extension — Background Service Worker (Enhanced v2)
 *
 * Features:
 * - HTTP API proxy for memory search & proactive push
 * - WebSocket connection to Kaelis sync server (cross-device messaging)
 * - Device registration with Kaelis backend
 * - Offline queue for messages sent while disconnected
 */

const API_BASE = 'http://localhost:5000';
const WS_URL = 'ws://localhost:5001';

let ws = null;
let wsReconnectTimer = null;
let deviceId = null;

// ======================================================================
// Device Registration
// ======================================================================

async function registerDevice() {
  try {
    const res = await fetch(`${API_BASE}/api/sync/devices/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: `chrome_${chrome.runtime.id.slice(0, 8)}`,
        user_id: 'chrome_extension_user',
        platform: 'browser',
        capabilities: ['memory_search', 'proactive_push', 'chat_context'],
      }),
    });
    const data = await res.json();
    if (data.success) {
      deviceId = data.data.device_id;
      console.log('[Kaelis BG] Device registered:', deviceId);
      return deviceId;
    }
  } catch (e) {
    console.warn('[Kaelis BG] Device registration failed:', e);
  }
  return null;
}

// ======================================================================
// WebSocket Connection
// ======================================================================

function connectWS() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }

  try {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('[Kaelis BG] WS connected');
      // Authenticate
      ws.send(JSON.stringify({
        type: 'auth',
        device_id: deviceId || `chrome_${chrome.runtime.id.slice(0, 8)}`,
        user_id: 'chrome_extension_user',
        platform: 'browser',
        capabilities: ['memory_search', 'proactive_push'],
      }));
      // Notify all tabs
      notifyTabs({ type: 'WS_STATUS', connected: true });
      // Clear reconnect timer
      if (wsReconnectTimer) {
        clearTimeout(wsReconnectTimer);
        wsReconnectTimer = null;
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log('[Kaelis BG] WS message:', msg.type);
        if (msg.type === 'auth_ok') {
          console.log('[Kaelis BG] WS auth OK');
        }
        if (msg.type === 'offline_batch') {
          // Notify user of offline messages
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon-48.png',
            title: 'Kaelis Sync',
            message: `Received offline message: ${msg.message?.type || 'update'}`,
          });
        }
      } catch (e) {
        console.warn('[Kaelis BG] WS parse error:', e);
      }
    };

    ws.onclose = () => {
      console.log('[Kaelis BG] WS disconnected');
      notifyTabs({ type: 'WS_STATUS', connected: false });
      scheduleReconnect();
    };

    ws.onerror = (e) => {
      console.warn('[Kaelis BG] WS error:', e);
      ws.close();
    };
  } catch (e) {
    console.warn('[Kaelis BG] WS connect failed:', e);
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (wsReconnectTimer) return;
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null;
    connectWS();
  }, 10000);
}

function notifyTabs(message) {
  chrome.tabs.query({}, (tabs) => {
    tabs.forEach(tab => {
      if (tab.id) {
        chrome.tabs.sendMessage(tab.id, message).catch(() => {});
      }
    });
  });
}

// ======================================================================
// Message Handlers
// ======================================================================

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Memory search
  if (request.type === 'KAELIS_MEMORY_SEARCH') {
    fetch(`${API_BASE}/api/memory/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ layer: 'L2', query: request.query, top_k: 5 }),
    })
    .then(r => r.json())
    .then(data => sendResponse({ success: true, data }))
    .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  // Proactive push (context-aware memory recommendations)
  if (request.type === 'KAELIS_PROACTIVE_PUSH') {
    fetch(`${API_BASE}/api/memory/proactive/context_push`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'chrome_extension_user',
        context: request.context,
        limit: 5,
      }),
    })
    .then(r => r.json())
    .then(data => sendResponse({ success: true, data }))
    .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  // Health check
  if (request.type === 'KAELIS_STATUS') {
    fetch(`${API_BASE}/api/health`)
    .then(r => r.json())
    .then(data => sendResponse({ success: true, online: true, data }))
    .catch(err => sendResponse({ success: false, online: false, error: err.message }));
    return true;
  }

  // Send message via WebSocket
  if (request.type === 'KAELIS_WS_SEND') {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(request.payload));
      sendResponse({ success: true });
    } else {
      sendResponse({ success: false, error: 'WebSocket not connected' });
    }
    return true;
  }
});

// ======================================================================
// Lifecycle
// ======================================================================

chrome.runtime.onInstalled.addListener(() => {
  console.log('[Kaelis BG] Extension installed');
});

chrome.runtime.onStartup.addListener(() => {
  console.log('[Kaelis BG] Extension startup');
  registerDevice().then(() => connectWS());
});

// Attempt initial connection
registerDevice().then(() => connectWS());
