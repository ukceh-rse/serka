export type SSEEventType =
  | 'THINKING_START'
  | 'THINKING_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_END'
  | 'TEXT_MESSAGE_CONTENT'
  | 'RUN_FINISHED'

export interface SSEEvent {
  type: SSEEventType
  delta?: string
  toolCallName?: string
}

export interface AGUIMessage {
  role: 'user' | 'assistant'
  content: string
}

async function* parseSSE(body: ReadableStream<Uint8Array>): AsyncGenerator<SSEEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6)) as SSEEvent
        } catch {
          // skip malformed
        }
      }
    }
  }
}

export async function streamSummary(
  message: string,
  onEvent: (e: SSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch('/v1/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(`Stream failed: ${res.statusText}`)
  for await (const event of parseSSE(res.body)) {
    onEvent(event)
    if (event.type === 'RUN_FINISHED') break
  }
}

export async function streamChat(
  messages: AGUIMessage[],
  threadId: string,
  onEvent: (e: SSEEvent) => void
): Promise<void> {
  const res = await fetch('/v1/chat/stream/agui', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      messages: messages.map((m, i) => ({
        id: String(i),
        role: m.role,
        content: m.content,
      })),
    }),
  })
  if (!res.ok || !res.body) throw new Error(`Stream failed: ${res.statusText}`)
  for await (const event of parseSSE(res.body)) {
    onEvent(event)
    if (event.type === 'RUN_FINISHED') break
  }
}
