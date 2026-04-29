document.addEventListener('DOMContentLoaded', () => {
  const dot = document.getElementById('status-dot');
  const text = document.getElementById('status-text');

  chrome.runtime.sendMessage({ type: 'KAELIS_STATUS' }, (res) => {
    if (res && res.online) {
      dot.classList.add('online');
      text.textContent = 'Connected';
    } else {
      text.textContent = 'Offline';
    }
  });

  document.getElementById('btn-panel').addEventListener('click', () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, { type: 'TOGGLE_PANEL' });
    });
  });
});
