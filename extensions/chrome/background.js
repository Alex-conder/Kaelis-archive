/**
 * Kaelis Chrome Extension — Background Service Worker
 *
 * 负责:
 * 1. 接收 content.js 提取的对话上下文和页面内容
 * 2. 调用本地 Kaelis API (/api/memory/proactive/context_push)
 * 3. 将记忆推送到 sidebar
 * 4. 支持情景感知的差异化建议模板
 */

const KAELIS_API = 'http://localhost:5000/api/memory/proactive/context_push';
const KAELIS_CHAT_API = 'http://localhost:5000/api/kg-flywheel/chat';

// 网站类型 -> 建议模板映射
const SITE_TEMPLATES = {
  github_issue: (ctx) => `我在看一个 GitHub Issue「${ctx.title}」，请帮我分析这个问题是否与 Kaelis 中已知的架构决策相关。`,
  github_pr: (ctx) => `这个 PR「${ctx.title}」可能涉及代码变更，请帮我检查是否遵循了 Kaelis 的模块分层和测试规范。`,
  academic_paper: (ctx) => `这篇论文「${ctx.title}」提到的技术方案，Kaelis 是否有相关的知识或实现可以参考？`,
  qna: (ctx) => `这个技术问题「${ctx.title}」，Kaelis 的记忆库中是否有相关解决方案？`,
  general: (ctx) => `我正在浏览「${ctx.title}」，Kaelis 有什么相关的记忆或知识可以帮我理解？`,
};

// 监听来自 content script 的请求
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'FETCH_MEMORIES') {
    fetchContextAwarePush(request.context)
      .then(data => {
        chrome.runtime.sendMessage({ type: 'UPDATE_MEMORIES', data }).catch(() => {});
        sendResponse({ success: true, data });
      })
      .catch(err => {
        console.error('[Kaelis BG] Fetch failed:', err);
        sendResponse({ success: false, error: err.message });
      });
    return true;
  }

  if (request.type === 'CONTEXT_AWARE_PUSH') {
    const payload = request.payload || {};
    handleContextAwarePush(payload)
      .then(data => {
        chrome.runtime.sendMessage({ type: 'UPDATE_MEMORIES', data }).catch(() => {});
        // 尝试预填充 AI 输入框
        if (data.memories?.length && sender.tab?.id) {
          const template = SITE_TEMPLATES[payload.site_type] || SITE_TEMPLATES.general;
          const suggestion = template(payload);
          chrome.tabs.sendMessage(sender.tab.id, {
            type: 'PREFILL_INPUT',
            text: suggestion,
          }).catch(() => {});
        }
        sendResponse({ success: true, data });
      })
      .catch(err => {
        console.error('[Kaelis BG] Context push failed:', err);
        sendResponse({ success: false, error: err.message });
      });
    return true;
  }

  if (request.type === 'COPY_TO_CLIPBOARD') {
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

async function handleContextAwarePush(payload) {
  const { title, body, site_type, site_label, dialogue } = payload;

  // 构建更丰富的上下文
  const enrichedContext = [
    `站点类型: ${site_label}`,
    `标题: ${title}`,
    `URL: ${payload.url}`,
    `内容摘要: ${body?.slice(0, 500) || ''}`,
    dialogue ? `对话上下文: ${dialogue}` : '',
  ].filter(Boolean).join('\n');

  return fetchContextAwarePush(enrichedContext);
}

// 点击扩展图标时，切换侧边栏显示
chrome.action.onClicked.addListener(async (tab) => {
  const isSupported = /chat\.openai|chatgpt\.com|claude\.ai|kimi\.moonshot|github\.com|arxiv\.org/.test(tab.url);
  if (!isSupported) {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => alert('Kaelis sidebar works on ChatGPT, Claude, Kimi, GitHub, and academic sites.')
    });
    return;
  }

  chrome.tabs.sendMessage(tab.id, { type: 'TOGGLE_SIDEBAR' }).catch(() => {});
});
