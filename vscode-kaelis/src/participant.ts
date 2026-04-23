import * as vscode from 'vscode';
import { KaelisMCPClient } from './mcpClient';

export class KaelisParticipant {
  private mcpClient: KaelisMCPClient | null = null;
  private httpFallback = false;

  async initialize(): Promise<void> {
    const config = vscode.workspace.getConfiguration('kaelis');
    const pythonPath = config.get<string>('pythonPath', 'python');
    let serverPath = config.get<string>('mcpServerPath', '');

    if (!serverPath) {
      // Auto-detect: look for mcp_standalone.py in workspace or parent directories
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (workspaceFolder) {
        const possiblePaths = [
          `${workspaceFolder}/mcp_standalone.py`,
          `${workspaceFolder}/../mcp_standalone.py`,
          `${workspaceFolder}/../../mcp_standalone.py`,
        ];
        for (const p of possiblePaths) {
          try {
            await vscode.workspace.fs.stat(vscode.Uri.file(p));
            serverPath = p;
            break;
          } catch {
            // not found
          }
        }
      }
    }

    if (!serverPath) {
      vscode.window.showWarningMessage('Kaelis: mcp_standalone.py not found. Using HTTP fallback.');
      this.httpFallback = true;
      return;
    }

    this.mcpClient = new KaelisMCPClient(pythonPath, serverPath);
    try {
      await this.mcpClient.start();
      console.log('[Kaelis] MCP client started successfully');
    } catch (err) {
      vscode.window.showWarningMessage(`Kaelis: MCP start failed, using HTTP fallback. ${err}`);
      this.httpFallback = true;
    }
  }

  async handleRequest(
    request: vscode.ChatRequest,
    context: vscode.ChatContext,
    response: vscode.ChatResponseStream,
    token: vscode.CancellationToken
  ): Promise<void> {
    const config = vscode.workspace.getConfiguration('kaelis');
    const userId = config.get<string>('userId', 'vscode_user');
    const prompt = request.prompt;

    response.progress('Searching Kaelis memory...');

    // Step 1: Search memory for relevant context
    let memoryContext = '';
    try {
      const searchResults = await this._searchMemory(prompt, userId);
      if (searchResults && searchResults.length > 0) {
        memoryContext = searchResults.map((r: any) => {
          const val = typeof r.value === 'string' ? r.value : JSON.stringify(r.value);
          return `- ${r.key}: ${val}`;
        }).join('\n');
      }
    } catch (err) {
      console.error('[Kaelis] Memory search failed:', err);
    }

    // Step 2: Build augmented prompt
    let augmentedPrompt = prompt;
    if (memoryContext) {
      augmentedPrompt = `User question: ${prompt}\n\nRelevant memories from Kaelis:\n${memoryContext}\n\nPlease answer the user's question, referencing the above memories when relevant.`;
    }

    // Step 3: Call VSCode LLM
    try {
      const models = await vscode.lm.selectChatModels({ vendor: 'copilot' });
      if (models.length === 0) {
        response.markdown('Sorry, no language model is available. Please ensure you have a Copilot subscription or another model provider configured.');
        return;
      }

      const model = models[0];
      const messages = [
        vscode.LanguageModelChatMessage.User(augmentedPrompt)
      ];

      const chatResponse = await model.sendRequest(messages, {}, token);

      for await (const fragment of chatResponse.text) {
        response.markdown(fragment);
      }

      if (memoryContext) {
        response.markdown('\n\n---\n*Powered by Kaelis memory search*');
      }
    } catch (err) {
      response.markdown(`Error: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  private async _searchMemory(query: string, userId: string): Promise<any[]> {
    if (this.httpFallback) {
      return this._searchMemoryHttp(query, userId);
    }

    if (!this.mcpClient) {
      throw new Error('MCP client not available');
    }

    try {
      const result = await this.mcpClient.callTool('memory_search', {
        layer: 'L2',
        query: query,
        top_k: 5,
      });
      // Parse MCP tool result
      const content = result?.content?.[0]?.text;
      if (content) {
        const data = JSON.parse(content);
        return data.results || data.data || [];
      }
      return [];
    } catch (err) {
      console.error('[Kaelis] MCP memory_search failed, falling back to HTTP:', err);
      return this._searchMemoryHttp(query, userId);
    }
  }

  private async _searchMemoryHttp(query: string, userId: string): Promise<any[]> {
    const config = vscode.workspace.getConfiguration('kaelis');
    const baseUrl = config.get<string>('apiBaseUrl', 'http://localhost:5000');

    try {
      const res = await fetch(`${baseUrl}/api/memory/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layer: 'L2', query, top_k: 5 }),
      });
      const data = await res.json() as { data?: any[] };
      return data.data || [];
    } catch (err) {
      console.error('[Kaelis] HTTP fallback failed:', err);
      return [];
    }
  }

  dispose() {
    this.mcpClient?.stop();
  }
}
