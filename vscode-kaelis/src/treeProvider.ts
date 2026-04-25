import * as vscode from 'vscode';

interface MemoryItem {
  key: string;
  value: string;
  layer: string;
}

interface SkillItem {
  id: string;
  name: string;
  task_type: string;
  success_rate: number;
}

interface InsightItem {
  title: string;
  summary: string;
  timestamp: string;
}

export class KaelisTreeDataProvider implements vscode.TreeDataProvider<KaelisTreeItem> {
  private _onDidChangeTreeData: vscode.EventEmitter<KaelisTreeItem | undefined | void> = new vscode.EventEmitter<KaelisTreeItem | undefined | void>();
  readonly onDidChangeTreeData: vscode.Event<KaelisTreeItem | undefined | void> = this._onDidChangeTreeData.event;

  private httpBaseUrl: string;
  private userId: string;

  constructor() {
    const config = vscode.workspace.getConfiguration('kaelis');
    this.httpBaseUrl = config.get<string>('apiBaseUrl', 'http://localhost:5000');
    this.userId = config.get<string>('userId', 'vscode_user');
  }

  refresh(): void {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element: KaelisTreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: KaelisTreeItem): Promise<KaelisTreeItem[]> {
    if (!element) {
      // Root nodes
      return [
        new KaelisTreeItem('今日洞察', vscode.TreeItemCollapsibleState.Collapsed, 'insights'),
        new KaelisTreeItem('记忆搜索', vscode.TreeItemCollapsibleState.Collapsed, 'memory'),
        new KaelisTreeItem('技能列表', vscode.TreeItemCollapsibleState.Collapsed, 'skills'),
      ];
    }

    if (element.contextValue === 'insights') {
      return this._getInsights();
    }
    if (element.contextValue === 'memory') {
      return this._getRecentMemory();
    }
    if (element.contextValue === 'skills') {
      return this._getSkills();
    }

    return [];
  }

  private async _getInsights(): Promise<KaelisTreeItem[]> {
    try {
      const res = await fetch(`${this.httpBaseUrl}/api/insights/daily?user_id=${this.userId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json() as { success?: boolean; data?: InsightItem[] };
      const items = data.data || [];
      if (items.length === 0) {
        return [new KaelisTreeItem('暂无洞察', vscode.TreeItemCollapsibleState.None, 'empty')];
      }
      return items.map(i => new KaelisTreeItem(
        i.title,
        vscode.TreeItemCollapsibleState.None,
        'insight',
        i.summary,
        new vscode.ThemeIcon('lightbulb')
      ));
    } catch {
      return [new KaelisTreeItem('无法加载洞察', vscode.TreeItemCollapsibleState.None, 'empty')];
    }
  }

  private async _getRecentMemory(): Promise<KaelisTreeItem[]> {
    try {
      const res = await fetch(`${this.httpBaseUrl}/api/memory/recent?user_id=${this.userId}&limit=10`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json() as { success?: boolean; data?: MemoryItem[] };
      const items = data.data || [];
      if (items.length === 0) {
        return [new KaelisTreeItem('暂无记忆', vscode.TreeItemCollapsibleState.None, 'empty')];
      }
      return items.map(m => new KaelisTreeItem(
        m.key,
        vscode.TreeItemCollapsibleState.None,
        'memory-item',
        `[${m.layer}] ${m.value.substring(0, 80)}`,
        new vscode.ThemeIcon('database')
      ));
    } catch {
      return [new KaelisTreeItem('无法加载记忆', vscode.TreeItemCollapsibleState.None, 'empty')];
    }
  }

  private async _getSkills(): Promise<KaelisTreeItem[]> {
    try {
      const res = await fetch(`${this.httpBaseUrl}/api/skills?user_id=${this.userId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json() as { success?: boolean; data?: SkillItem[] };
      const items = data.data || [];
      if (items.length === 0) {
        return [new KaelisTreeItem('暂无技能', vscode.TreeItemCollapsibleState.None, 'empty')];
      }
      return items.map(s => new KaelisTreeItem(
        s.name,
        vscode.TreeItemCollapsibleState.None,
        'skill',
        `${s.task_type} · 成功率 ${((s.success_rate || 0) * 100).toFixed(0)}%`,
        new vscode.ThemeIcon('symbol-function')
      ));
    } catch {
      return [new KaelisTreeItem('无法加载技能', vscode.TreeItemCollapsibleState.None, 'empty')];
    }
  }
}

export class KaelisTreeItem extends vscode.TreeItem {
  constructor(
    public readonly label: string,
    public readonly collapsibleState: vscode.TreeItemCollapsibleState,
    public readonly contextValue: string,
    public readonly description?: string,
    public readonly iconPath?: vscode.ThemeIcon
  ) {
    super(label, collapsibleState);
    this.tooltip = description || label;
    this.description = description;
    this.iconPath = iconPath || new vscode.ThemeIcon('circle-outline');
  }
}
