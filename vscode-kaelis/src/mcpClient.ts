import { ChildProcess, spawn } from 'child_process';
import * as vscode from 'vscode';

interface MCPRequest {
  jsonrpc: '2.0';
  method: string;
  params?: any;
  id: number;
}

interface MCPResponse {
  jsonrpc: '2.0';
  id: number;
  result?: any;
  error?: { code: number; message: string };
}

export class KaelisMCPClient {
  private process: ChildProcess | null = null;
  private requestId = 0;
  private pendingRequests = new Map<number, { resolve: (value: any) => void; reject: (reason: any) => void }>();
  private buffer = '';
  private pythonPath: string;
  private serverPath: string;

  constructor(pythonPath: string, serverPath: string) {
    this.pythonPath = pythonPath;
    this.serverPath = serverPath;
  }

  async start(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.process = spawn(this.pythonPath, ['-u', this.serverPath], {
        cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || process.cwd(),
        env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      });

      this.process.stdout?.on('data', (data: Buffer) => {
        this.buffer += data.toString('utf-8');
        this._processBuffer();
      });

      this.process.stderr?.on('data', (data: Buffer) => {
        const line = data.toString('utf-8').trim();
        if (line) {
          console.log('[MCP stderr]', line);
        }
      });

      this.process.on('error', (err) => {
        reject(new Error(`Failed to start MCP server: ${err.message}`));
      });

      this.process.on('exit', (code) => {
        if (code !== 0 && code !== null) {
          console.error(`MCP server exited with code ${code}`);
        }
      });

      // Give the server a moment to initialize
      setTimeout(resolve, 2000);
    });
  }

  private _processBuffer() {
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() || '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const response: MCPResponse = JSON.parse(trimmed);
        if (response.id !== undefined) {
          const pending = this.pendingRequests.get(response.id);
          if (pending) {
            this.pendingRequests.delete(response.id);
            if (response.error) {
              pending.reject(new Error(response.error.message));
            } else {
              pending.resolve(response.result);
            }
          }
        }
      } catch {
        // Not a JSON-RPC line, might be log output
        console.log('[MCP stdout]', trimmed);
      }
    }
  }

  async callTool(name: string, args: Record<string, any>): Promise<any> {
    if (!this.process) {
      throw new Error('MCP client not started');
    }

    const id = ++this.requestId;
    const request: MCPRequest = {
      jsonrpc: '2.0',
      method: 'tools/call',
      params: { name, arguments: args },
      id,
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });
      this.process!.stdin!.write(JSON.stringify(request) + '\n');
    });
  }

  async listTools(): Promise<any[]> {
    if (!this.process) {
      throw new Error('MCP client not started');
    }

    const id = ++this.requestId;
    const request: MCPRequest = {
      jsonrpc: '2.0',
      method: 'tools/list',
      id,
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(id, { resolve, reject });
      this.process!.stdin!.write(JSON.stringify(request) + '\n');
    });
  }

  stop() {
    if (this.process) {
      this.process.kill();
      this.process = null;
    }
    this.pendingRequests.clear();
    this.buffer = '';
  }
}
