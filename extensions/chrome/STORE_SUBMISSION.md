# Kaelis Chrome Extension v0.2.0

## Submission Notes

**What's new in v0.2.0:**

1. **Deep Context Awareness** — Automatically extracts dialogue context from ChatGPT, Claude, and Gemini. As the user types, the extension queries Kaelis for relevant memories and shows inline suggestions.

2. **WebSocket Cross-Device Sync** — Connects to the Kaelis WebSocket server (port 5001) for real-time bidirectional messaging. Receives offline messages when back online.

3. **Device Registration** — Registers itself as a "browser" device with the Kaelis sync hub, enabling cross-device memory sharing.

4. **Auto-Recommendations** — Floating panel shows contextually relevant memories based on the current AI conversation. One-click to search or insert into chat.

## Permissions Justification

| Permission | Why |
|---|---|
| `storage` | Cache device credentials and settings |
| `activeTab` | Detect current AI chat page for context extraction |
| `notifications` | Alert user of cross-device messages |

## Host Permissions

- `chat.openai.com`, `claude.ai`, `gemini.google.com` — Content script injection for context extraction
- `localhost:5000` — Kaelis local API
- `localhost:5001` — Kaelis WebSocket sync server
