import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamSummary, UsageLimitError } from './chat'

function stubFetch(response: Response) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamSummary', () => {
  it('throws a UsageLimitError with the server message on 429', async () => {
    const detail = { code: 'client_daily_limit', message: "You have reached today's limit." }
    stubFetch(new Response(JSON.stringify({ detail }), { status: 429 }))
    const error = await streamSummary('q', () => {}).catch((e) => e)
    expect(error).toBeInstanceOf(UsageLimitError)
    expect(error.message).toBe("You have reached today's limit.")
  })

  it('falls back to its own message when a 429 has no usable body', async () => {
    stubFetch(new Response('Too Many Requests', { status: 429 }))
    const error = await streamSummary('q', () => {}).catch((e) => e)
    expect(error).toBeInstanceOf(UsageLimitError)
    expect(error.message).toBe('The daily limit for AI summaries has been reached.')
  })

  it.each([422, 500, 503])('keeps a plain error on %i', async (status) => {
    stubFetch(new Response('{}', { status, statusText: 'Nope' }))
    const error = await streamSummary('q', () => {}).catch((e) => e)
    expect(error).toBeInstanceOf(Error)
    expect(error).not.toBeInstanceOf(UsageLimitError)
    expect(error.message).toBe('Stream failed: Nope')
  })

  it('delivers stream events on success', async () => {
    const body = 'data: {"type":"RUN_STARTED"}\n\ndata: {"type":"RUN_FINISHED"}\n\n'
    stubFetch(new Response(body, { status: 200 }))
    const events: string[] = []
    await streamSummary('q', (e) => events.push(e.type))
    expect(events).toEqual(['RUN_STARTED', 'RUN_FINISHED'])
  })
})
