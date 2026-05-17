/**
 * Mock WebSocket factory for testing.
 * Returns a mock WebSocket class that captures sent messages and
 * allows programmatic triggering of onopen/onmessage/onclose.
 */
export function createMockWebSocket() {
  const instances: MockWebSocket[] = []

  class MockWebSocket {
    static CONNECTING = 0
    static OPEN = 1
    static CLOSING = 2
    static CLOSED = 3

    readyState = MockWebSocket.CONNECTING
    url: string
    onopen: ((ev: Event) => void) | null = null
    onmessage: ((ev: MessageEvent) => void) | null = null
    onclose: ((ev: CloseEvent) => void) | null = null
    onerror: ((ev: Event) => void) | null = null

    sent: string[] = []

    constructor(url: string | URL) {
      this.url = String(url)
      instances.push(this)
      // Simulate async connection
      queueMicrotask(() => {
        this.readyState = MockWebSocket.OPEN
        this.onopen?.(new Event('open'))
      })
    }

    send(data: string) {
      this.sent.push(data)
    }

    close() {
      this.readyState = MockWebSocket.CLOSED
      this.onclose?.(new CloseEvent('close'))
    }

    /** Test helper: simulate receiving a message from server */
    simulateMessage(data: unknown) {
      this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(data) }))
    }

    /** Test helper: simulate connection error */
    simulateError() {
      this.onerror?.(new Event('error'))
    }
  }

  return { MockWebSocket, instances }
}

/**
 * Wait for a specified number of milliseconds.
 */
export function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
