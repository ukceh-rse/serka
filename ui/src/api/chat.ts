export type SSEEventType =
  | 'RUN_STARTED'
  | 'RUN_FINISHED'
  | 'RUN_ERROR'
  | 'RUN_METADATA'
  | 'STEP_STARTED'
  | 'STEP_FINISHED'
  | 'CUSTOM'
  | 'TEXT_MESSAGE_START'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_ARGS'
  | 'TOOL_CALL_END'
  | 'TOOL_CALL_RESULT'

/** The fields of the chat event contract (openspec `chat-agent-events`) that the UI consumes. */
export interface SSEEvent {
  type: SSEEventType
  /** STEP_STARTED / STEP_FINISHED */
  stepName?: string
  /** CUSTOM: event name (e.g. `serka.step`) and its payload */
  name?: string
  value?: unknown
  /** TOOL_CALL_* */
  toolCallId?: string
  toolCallName?: string
  /** TEXT_MESSAGE_CONTENT and TOOL_CALL_ARGS */
  delta?: string
  /** TOOL_CALL_RESULT: JSON string, or `Error: ...` */
  content?: string
  /** RUN_ERROR */
  message?: string
  /** RUN_METADATA: answer model and the stage -> model mapping */
  model?: string
  models?: Record<string, string>
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

/** A daily cap rejected the request; `message` is the server's text for showing to the user. */
export class UsageLimitError extends Error {}

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
  if (res.status === 429) {
    const body = await res.json().catch(() => null)
    throw new UsageLimitError(body?.detail?.message ?? 'The daily limit for AI summaries has been reached.')
  }
  if (!res.ok || !res.body) throw new Error(`Stream failed: ${res.statusText}`)
  for await (const event of parseSSE(res.body)) {
    onEvent(event)
    if (event.type === 'RUN_FINISHED' || event.type === 'RUN_ERROR') break
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
    if (event.type === 'RUN_FINISHED' || event.type === 'RUN_ERROR') break
  }
}
