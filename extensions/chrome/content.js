/**
 * Kaelis Chrome Extension — Context-Aware Content Script
 *
 * 功能:
 * 1. 监听页面 URL/标题变化
 * 2. 每 15 秒提取页面内容并推送给 Kaelis
 * 3. 识别网站类型（GitHub/论文/通用），差异化处理
 * 4. 将相关记忆预填充到 AI 对话输入框
 */
(function() {
  'use strict';

  const SIDEBAR_ID = 'kaelis-sidebar-frame';
  let sidebarVisible = true;
  let lastUrl = location.href;
  let lastTitle = document.title;
  let pushInterval = null;

  // ==========================================================================
  // Sidebar
  // ==========================================================================

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

  // ==========================================================================
  // Site Type Detection
  // ==========================================================================

  function detectSiteType() {
    const host = window.location.hostname;
    const path = window.location.pathname;
    if (host.includes('github.com')) {
      if (path.includes('/issues/')) return { type: 'github_issue', label: 'GitHub Issue' };
      if (path.includes('/pull/')) return { type: 'github_pr', label: 'GitHub PR' };
      return { type: 'github_repo', label: 'GitHub Repository' };
    }
    if (host.includes('arxiv.org') || host.includes('pubmed.ncbi.nlm.nih.gov') || host.includes('scholar.google')) {
      return { type: 'academic_paper', label: '学术论文' };
    }
    if (host.includes('stackoverflow.com') || host.includes('stackexchange.com')) {
      return { type: 'qna', label: '技术问答' };
    }
    return { type: 'general', label: '通用网页' };
  }

  // ==========================================================================
  // Content Extraction
  // ==========================================================================

  function extractPageContent() {
    const site = detectSiteType();
    const title = document.title;
    let bodyText = '';

    // 提取主要文本内容（排除脚本/样式）
    const mainContent = document.querySelector('main, article, [role="main"], .markdown-body, .entry-content');
    if (mainContent) {
      bodyText = mainContent.innerText.slice(0, 3000);
    } else {
      // fallback: 提取段落文本
      const paragraphs = document.querySelectorAll('p, h1, h2, h3, li');
      bodyText = Array.from(paragraphs).slice(0, 50).map(el => el.innerText).join('\n').slice(0, 3000);
    }

    return {
      url: location.href,
      title,
      site_type: site.type,
      site_label: site.label,
      body: bodyText,
      timestamp: Date.now(),
    };
  }

  function extractDialogue() {
    const host = window.location.hostname;
    let texts = [];
    if (host.includes('chat.openai.com') || host.includes('chatgpt.com')) {
      document.querySelectorAll('[data-testid="conversation-turn-2"] .whitespace-pre-wrap, [data-message-author-role]').forEach(el => texts.push(el.innerText));
    } else if (host.includes('claude.ai')) {
      document.querySelectorAll('.font-claude-message, .font-user-message, [data-testid="user-message"], [data-testid="assistant-message"]').forEach(el => texts.push(el.innerText));
    } else if (host.includes('kimi.moonshot.cn')) {
      document.querySelectorAll('.chat-item-content, [data-testid="chat-item"]').forEach(el => texts.push(el.innerText));
    }
    return texts.slice(-4).join('\n').slice(-500);
  }

  // ==========================================================================
  // Context Push
  // ==========================================================================

  function pushContext() {
    const content = extractPageContent();
    const dialogue = extractDialogue();

    // 发送给 background
    chrome.runtime.sendMessage({
      type: 'CONTEXT_AWARE_PUSH',
      payload: {
        ...content,
        dialogue,
      }
    }).catch(() => {});
  }

  // ==========================================================================
  // URL Change Detection
  // ==========================================================================

  function onUrlChange() {
    const newUrl = location.href;
    const newTitle = document.title;
    if (newUrl !== lastUrl || newTitle !== lastTitle) {
      lastUrl = newUrl;
      lastTitle = newTitle;
      console.log('[Kaelis] URL changed:', newUrl);
      // 立即推送一次
      pushContext();
    }
  }

  // 监听 history 变化
  const originalPushState = history.pushState;
  const originalReplaceState = history.replaceState;
  history.pushState = function(...args) {
    originalPushState.apply(this, args);
    setTimeout(onUrlChange, 100);
  };
  history.replaceState = function(...args) {
    originalReplaceState.apply(this, args);
    setTimeout(onUrlChange, 100);
  };
  window.addEventListener('popstate', onUrlChange);

  // 也使用 MutationObserver 作为兜底
  const titleObserver = new MutationObserver(() => {
    onUrlChange();
  });
  const titleEl = document.querySelector('title');
  if (titleEl) {
    titleObserver.observe(titleEl, { childList: true });
  }

  // ==========================================================================
  // Pre-fill AI Input
  // ==========================================================================

  function findAIInput() {
    const host = window.location.hostname;
    if (host.includes('chat.openai.com') || host.includes('chatgpt.com')) {
      return document.querySelector('textarea[placeholder], #prompt-textarea');
    }
    if (host.includes('claude.ai')) {
      return document.querySelector('[contenteditable="true"], textarea');
    }
    if (host.includes('kimi.moonshot.cn')) {
      return document.querySelector('textarea, [contenteditable]');
    }
    return null;
  }

  function prefillInput(text) {
    const input = findAIInput();
    if (!input) return false;

    if (input.tagName === 'TEXTAREA') {
      const original = input.value;
      if (!original.includes(text)) {
        input.value = text + '\n\n' + original;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        return true;
      }
    } else if (input.isContentEditable) {
      const original = input.innerText;
      if (!original.includes(text)) {
        input.innerText = text + '\n\n' + original;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        return true;
      }
    }
    return false;
  }

  // ==========================================================================
  // Message Handler
  // ==========================================================================

  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'TOGGLE_SIDEBAR') {
      toggleSidebar();
      sendResponse({ visible: sidebarVisible });
    }
    if (request.type === 'GET_DIALOGUE') {
      sendResponse({ context: extractDialogue() });
    }
    if (request.type === 'GET_PAGE_CONTENT') {
      sendResponse(extractPageContent());
    }
    if (request.type === 'PREFILL_INPUT') {
      const ok = prefillInput(request.text);
      sendResponse({ success: ok });
    }
  });

  // ==========================================================================
  // Init
  // ==========================================================================

  createSidebar();
  pushContext(); // 初始推送

  // 每 15 秒定期推送
  pushInterval = setInterval(pushContext, 15000);

  console.log('[Kaelis] Context-aware content script loaded. Site:', detectSiteType().label);
})();
