import * as vscode from 'vscode';
import { KaelisParticipant } from './participant';
import { KaelisTreeDataProvider, KaelisTreeItem } from './treeProvider';
import { registerCommands } from './commands';

let participant: KaelisParticipant | null = null;

export async function activate(context: vscode.ExtensionContext) {
  console.log('[Kaelis] Extension activating...');

  // Initialize Chat Participant
  participant = new KaelisParticipant();
  try {
    await participant.initialize();
  } catch (err) {
    console.error('[Kaelis] Initialization warning (will use HTTP fallback):', err);
  }

  const chatParticipant = vscode.chat.createChatParticipant('kaelis', async (request, context, response, token) => {
    if (!participant) {
      response.markdown('Kaelis is not initialized. Please reload the window.');
      return;
    }
    await participant.handleRequest(request, context, response, token);
  });

  chatParticipant.iconPath = vscode.Uri.joinPath(context.extensionUri, 'resources', 'kaelis-icon.png');
  context.subscriptions.push(chatParticipant);

  // Register Sidebar TreeView
  const treeProvider = new KaelisTreeDataProvider();
  const treeView = vscode.window.createTreeView('kaelisSidebar', {
    treeDataProvider: treeProvider,
    showCollapseAll: true,
  });
  context.subscriptions.push(treeView);

  // Also register in explorer view
  const treeViewExplorer = vscode.window.createTreeView('kaelisSidebarExplorer', {
    treeDataProvider: treeProvider,
    showCollapseAll: true,
  });
  context.subscriptions.push(treeViewExplorer);

  // Register Commands
  registerCommands(context);

  // Auto-refresh sidebar every 60 seconds
  const refreshInterval = setInterval(() => {
    treeProvider.refresh();
  }, 60000);
  context.subscriptions.push({ dispose: () => clearInterval(refreshInterval) });

  context.subscriptions.push({
    dispose: () => {
      participant?.dispose();
      participant = null;
    }
  });

  console.log('[Kaelis] Extension activated successfully');
}

export function deactivate() {
  participant?.dispose();
  participant = null;
}
