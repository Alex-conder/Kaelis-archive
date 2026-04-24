/**
 * Kaelis Sidebar Logic
 */

const statusEl = document.getElementById('status');
const memoriesEl = document.getElementById('memories');
const pushMessageEl = document.getElementById('push-message');
const refreshBtn = document.getElementById('refresh');

let currentMemories = [];

// 初始加载
loadMemories();

// 监听 background 推送
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'UPDATE_MEMORIES') {
    renderMemories(request.data);
  }
});

// 刷新按钮
refreshBtn.addEventListener('click', () => {
  refreshBtn.classList.add('spin');
  loadMemories().finally(() => {
    setTimeout(() => refreshBtn.classList.remove('spin'), 500);
  });
});

async function loadMemories() {
  try {
    // 先获取当前页面对话
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;

    const response = await chrome.tabs.sendMessage(tab.id, { type: 'GET_DIALOGUE' }).catch(() => null);
    const context = response?.context || '';

    // 调用本地 API
    const res = await fetch('http://localhost:5000/api/memory/proactive/context_push', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'chrome_extension_user', context, limit: 5 })
    });

    if (!res.ok) throw new Error('API error');
    const data = await res.json();
    renderMemories(data);
  } catch (err) {
    console.error('[Kaelis Sidebar] Load failed:', err);
    statusEl.textContent = '离线';
    statusEl.classList.remove('online');
    memoriesEl.innerHTML = '<div class="empty">无法连接到 Kaelis 服务。<br>请确认本地服务已启动：<br><code style="color:#60a5fa">python mcp_standalone.py</code></div>';
  }
}

function renderMemories(data) {
  currentMemories = data.memories || [];

  // 状态
  if (data.has_memories) {
    statusEl.textContent = '在线';
    statusEl.classList.add('online');
  } else {
    statusEl.textContent = '在线 · 无记忆';
    statusEl.classList.add('online');
  }

  // 推送消息
  if (data.push_message) {
    pushMessageEl.textContent = data.push_message;
    pushMessageEl.style.display = 'block';
  } else {
    pushMessageEl.style.display = 'none';
  }

  // 记忆卡片
  if (!currentMemories.length) {
    memoriesEl.innerHTML = '<div class="empty">暂无相关记忆。<br>与 AI 多聊几句，Kaelis 会记住上下文。</div>';
    return;
  }

  memoriesEl.innerHTML = currentMemories.map((m, idx) => {
    const summary = extractSummary(m.value);
    const layerTag = m.layer || 'L2';
    return `
      <div class="memory-card" data-idx="${idx}">
        <div class="reason">${escapeHtml(m.reason || '相关记忆')} · ${layerTag}</div>
        <div class="summary">${escapeHtml(summary)}</div>
        <div class="meta">
          <span>${formatDate(m.created_at)}</span>
          <span>置信度 ${Math.round((m.confidence || 0.5) * 100)}%</span>
        </div>
        <div class="actions">
          <button class="primary" onclick="copyMemory(${idx})">复制到剪贴板</button>
        </div>
      </div>
    `;
  }).join('');
}

function extractSummary(value) {
  if (typeof value === 'string') return value;
  if (typeof value === 'object' && value !== null) {
    return value.summary || value.decision || JSON.stringify(value).slice(0, 120);
  }
  return String(value).slice(0, 120);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatDate(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

// 全局暴露给 HTML onclick
window.copyMemory = async function(idx) {
  const mem = currentMemories[idx];
  if (!mem) return;
  const text = extractSummary(mem.value);
  try {
    await navigator.clipboard.writeText(text);
    const btn = document.querySelector(`[data-idx="${idx}"] button`);
    if (btn) { btn.textContent = '已复制 ✓'; setTimeout(() => btn.textContent = '复制到剪贴板', 1500); }
  } catch (err) {
    console.error('Copy failed:', err);
  }
};
