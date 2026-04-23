import * as vscode from 'vscode';
import { KaelisParticipant } from './participant';

let participant: KaelisParticipant | null = null;

export async function activate(context: vscode.ExtensionContext) {
  console.log('[Kaelis] Extension activating...');

  participant = new KaelisParticipant();
  await participant.initialize();

  const chatParticipant = vscode.chat.createChatParticipant('kaelis', async (request, context, response, token) => {
    if (!participant) {
      response.markdown('Kaelis is not initialized. Please reload the window.');
      return;
    }
    await participant.handleRequest(request, context, response, token);
  });

  chatParticipant.iconPath = vscode.Uri.joinPath(context.extensionUri, 'icon.png');

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
