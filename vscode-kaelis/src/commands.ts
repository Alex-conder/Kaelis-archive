import * as vscode from 'vscode';

export function registerCommands(context: vscode.ExtensionContext): void {
  // Command: Save selected code to Kaelis memory
  const saveToMemory = vscode.commands.registerCommand('kaelis.saveToMemory', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('Kaelis: 没有活动的编辑器');
      return;
    }

    const selection = editor.selection;
    const text = editor.document.getText(selection);
    if (!text || text.trim().length === 0) {
      vscode.window.showWarningMessage('Kaelis: 请先选中要保存的代码');
      return;
    }

    const key = await vscode.window.showInputBox({
      prompt: '输入记忆键名（如: auth_pattern_v2）',
      placeHolder: 'memory_key',
    });
    if (!key) return;

    const config = vscode.workspace.getConfiguration('kaelis');
    const baseUrl = config.get<string>('apiBaseUrl', 'http://localhost:5000');
    const userId = config.get<string>('userId', 'vscode_user');
    const layer = 'L2'; // Episodic memory for code snippets

    try {
      const res = await fetch(`${baseUrl}/api/memory/write`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          layer,
          key,
          value: {
            code: text,
            language: editor.document.languageId,
            file: editor.document.fileName,
            timestamp: new Date().toISOString(),
          },
          metadata: { source: 'vscode_extension', user_id: userId },
        }),
      });
      const data = await res.json() as { success?: boolean };
      if (data.success) {
        vscode.window.showInformationMessage(`Kaelis: 已保存到 ${layer} 记忆 → ${key}`);
      } else {
        vscode.window.showErrorMessage('Kaelis: 保存失败');
      }
    } catch (err) {
      vscode.window.showErrorMessage(`Kaelis: 保存失败 — ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // Command: Search memory from sidebar
  const searchMemory = vscode.commands.registerCommand('kaelis.searchMemory', async () => {
    const query = await vscode.window.showInputBox({
      prompt: '输入搜索关键词',
      placeHolder: '搜索记忆...',
    });
    if (!query) return;

    const config = vscode.workspace.getConfiguration('kaelis');
    const baseUrl = config.get<string>('apiBaseUrl', 'http://localhost:5000');
    const userId = config.get<string>('userId', 'vscode_user');

    try {
      const res = await fetch(`${baseUrl}/api/memory/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layer: 'L2', query, top_k: 5 }),
      });
      const data = await res.json() as { success?: boolean; data?: any[] };
      const results = data.data || [];
      if (results.length === 0) {
        vscode.window.showInformationMessage('Kaelis: 未找到相关记忆');
        return;
      }
      const items = results.map((r: any) => ({
        label: r.key,
        description: typeof r.value === 'string' ? r.value.substring(0, 60) : JSON.stringify(r.value).substring(0, 60),
        detail: r.key,
      }));
      const picked = await vscode.window.showQuickPick(items, { placeHolder: '选择记忆项查看详情' });
      if (picked) {
        const detail = results.find((r: any) => r.key === picked.label);
        if (detail) {
          const doc = await vscode.workspace.openTextDocument({
            content: JSON.stringify(detail, null, 2),
            language: 'json',
          });
          await vscode.window.showTextDocument(doc, { preview: true });
        }
      }
    } catch (err) {
      vscode.window.showErrorMessage(`Kaelis: 搜索失败 — ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  // Command: Refresh sidebar
  const refreshSidebar = vscode.commands.registerCommand('kaelis.refreshSidebar', (treeProvider: { refresh: () => void }) => {
    treeProvider.refresh();
    vscode.window.showInformationMessage('Kaelis: 侧边栏已刷新');
  });

  // Command: Generate MCP config
  const generateMcpConfig = vscode.commands.registerCommand('kaelis.generateMcpConfig', async () => {
    const config = vscode.workspace.getConfiguration('kaelis');
    const pythonPath = config.get<string>('pythonPath', 'python');
    const serverPath = config.get<string>('mcpServerPath', '');

    if (!serverPath) {
      vscode.window.showWarningMessage('Kaelis: 未配置 MCP Server 路径，请在设置中指定 kaelis.mcpServerPath');
      return;
    }

    const mcpConfig = {
      servers: {
        kaelis: {
          type: 'stdio',
          command: pythonPath,
          args: ['-u', serverPath],
        },
      },
    };

    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showWarningMessage('Kaelis: 未打开工作区');
      return;
    }

    const configUri = vscode.Uri.joinPath(workspaceFolder.uri, '.vscode', 'mcp.json');
    try {
      await vscode.workspace.fs.writeFile(
        configUri,
        Buffer.from(JSON.stringify(mcpConfig, null, 2), 'utf-8')
      );
      vscode.window.showInformationMessage(`Kaelis: MCP 配置已生成 → ${configUri.fsPath}`);
    } catch (err) {
      vscode.window.showErrorMessage(`Kaelis: 配置生成失败 — ${err instanceof Error ? err.message : String(err)}`);
    }
  });

  context.subscriptions.push(saveToMemory, searchMemory, refreshSidebar, generateMcpConfig);
}
