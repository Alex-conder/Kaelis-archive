import * as vscode from 'vscode';

let statusBarItem: vscode.StatusBarItem | null = null;

export function createStatusBarItem(): vscode.StatusBarItem {
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'kaelis.openChat';
  updateStatusBar('unknown');
  statusBarItem.show();
  return statusBarItem;
}

export function updateStatusBar(status: 'online' | 'offline' | 'degraded' | 'unknown'): void {
  if (!statusBarItem) return;

  const icons = {
    online: '$(pass)',
    offline: '$(error)',
    degraded: '$(warning)',
    unknown: '$(question)',
  };

  const colors = {
    online: undefined,
    offline: new vscode.ThemeColor('statusBarItem.errorForeground'),
    degraded: new vscode.ThemeColor('statusBarItem.warningForeground'),
    unknown: undefined,
  };

  statusBarItem.text = `${icons[status]} Kaelis`;
  statusBarItem.tooltip = `Kaelis Agent Status: ${status}`;
  statusBarItem.color = colors[status];
}

export async function checkHealth(baseUrl: string): Promise<'online' | 'offline' | 'degraded'> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);
    const res = await fetch(`${baseUrl}/api/health`, { signal: controller.signal });
    clearTimeout(timeout);
    if (!res.ok) return 'degraded';
    const data = await res.json();
    return data.status === 'healthy' ? 'online' : 'degraded';
  } catch {
    return 'offline';
  }
}
