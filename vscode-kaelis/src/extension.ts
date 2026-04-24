import * as vscode from 'vscode';
import { KaelisParticipant } from './participant';

let participant: KaelisParticipant | null = null;

export async function activate(context: vscode.ExtensionContext) {
  console.log('[Kaelis] Extension activating...');

  participant = new KaelisParticipant();
  try {
    await participant.initialize();
  } catch (err) {
    console.error('[Kaelis] Initialization warning (will use HTTP fallback):', err);
    // Participant remains usable even if MCP init fails
  }

  const chatParticipant = vscode.chat.createChatParticipant('kaelis', async (request, context, response, token) => {
    if (!participant) {
      response.markdown('Kaelis is not initialized. Please reload the window.');
      return;
    }
    await participant.handleRequest(request, context, response, token);
  });

  // Use the actual icon path under resources/
  chatParticipant.iconPath = vscode.Uri.joinPath(context.extensionUri, 'resources', 'kaelis-icon.png');

  context.subscriptions.push(chatParticipant);
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
