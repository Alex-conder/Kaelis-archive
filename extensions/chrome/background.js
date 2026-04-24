/**
 * Kaelis Chrome Extension — Background Service Worker
 * 
 * 负责：
 * 1. 接收 content.js 提取的对话上下文
 * 2. 调用本地 Kaelis API (/api/memory/proactive/context_push)
 * 3. 将记忆推送到 sidebar
 */

const KAELIS_API = 'http://localhost:5000/api/memory/proactive/context_push';

// 监听来自 content script 的请求
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'FETCH_MEMORIES') {
    fetchContextAwarePush(request.context)
      .then(data => {
        // 转发给 sidebar
        chrome.runtime.sendMessage({ type: 'UPDATE_MEMORIES', data })
          .catch(() => {}); // sidebar 可能还没打开，忽略错误
        sendResponse({ success: true, data });
      })
      .catch(err => {
        console.error('[Kaelis BG] Fetch failed:', err);
        sendResponse({ success: false, error: err.message });
      });
    return true; // 异步响应
  }

  if (request.type === 'COPY_TO_CLIPBOARD') {
    // background 有 clipboardWrite 权限（ indirectly via offscreen 或 activeTab）
    // 这里仅做日志，实际复制在 sidebar.js 中通过 navigator.clipboard 完成
    console.log('[Kaelis BG] Copy request:', request.text);
    sendResponse({ success: true });
  }
});

async function fetchContextAwarePush(context) {
  const payload = {
    user_id: 'chrome_extension_user',
    context: context || '',
    limit: 5
  };

  const res = await fetch(KAELIS_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${await res.text()}`);
  }

  return res.json();
}

// 点击扩展图标时，切换侧边栏显示
chrome.action.onClicked.addListener(async (tab) => {
  const isAIPage = /chat\.openai|claude\.ai|kimi\.moonshot/.test(tab.url);
  if (!isAIPage) {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => alert('Kaelis sidebar only works on ChatGPT, Claude, or Kimi pages.')
    });
    return;
  }

  chrome.tabs.sendMessage(tab.id, { type: 'TOGGLE_SIDEBAR' })
    .catch(() => {});
});
