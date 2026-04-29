import * as vscode from 'vscode';
import { KaelisParticipant } from './participant';
import { createStatusBarItem, updateStatusBar, checkHealth } from './statusBar';

let participant: KaelisParticipant | null = null;
let statusBar: vscode.StatusBarItem | null = null;
let healthInterval: NodeJS.Timeout | null = null;

export async function activate(context: vscode.ExtensionContext) {
  console.log('[Kaelis] Extension activating...');

  participant = new KaelisParticipant();
  await participant.initialize();

  // Chat Participant
  const chatParticipant = vscode.chat.createChatParticipant('kaelis', async (request, context, response, token) => {
    if (!participant) {
      response.markdown('Kaelis is not initialized. Please reload the window.');
      return;
    }
    await participant.handleRequest(request, context, response, token);
  });
  chatParticipant.iconPath = vscode.Uri.joinPath(context.extensionUri, 'icon.png');
  context.subscriptions.push(chatParticipant);

  // Status Bar
  statusBar = createStatusBarItem();
  context.subscriptions.push(statusBar);

  // Health polling
  const config = vscode.workspace.getConfiguration('kaelis');
  const baseUrl = config.get<string>('apiBaseUrl', 'http://localhost:5000');

  const pollHealth = async () => {
    const status = await checkHealth(baseUrl);
    updateStatusBar(status);
  };

  await pollHealth();
  healthInterval = setInterval(pollHealth, 10000);
  context.subscriptions.push({ dispose: () => { if (healthInterval) clearInterval(healthInterval); } });

  // Open Chat command
  context.subscriptions.push(
    vscode.commands.registerCommand('kaelis.openChat', () => {
      vscode.commands.executeCommand('workbench.action.chat.open');
    })
  );

  context.subscriptions.push({
    dispose: () => {
      participant?.dispose();
      participant = null;
    }
  });

  console.log('[Kaelis] Extension activated successfully');
}

export function deactivate() {
  if (healthInterval) clearInterval(healthInterval);
  participant?.dispose();
  participant = null;
}
