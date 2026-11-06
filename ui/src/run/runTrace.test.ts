import { describe, expect, it } from 'vitest'
import type { SSEEvent } from '../api/chat'
import {
  compactOutcome, emptyRun, formatDate, progressText, reduceRun, stoppedAtRetrievalLimit,
  summaryText,
  type RunEvent, type RunTrace,
} from './runTrace'

// ─── Fixture builders (mirroring src/serka/chat/events.py) ────────────────────

const T0 = Date.UTC(2026, 10, 3, 12, 0, 0)
const MODELS = { classify: 'nova-lite', evaluate: 'haiku', synthesize_insight: 'sonnet' }

const custom = (name: string, value: unknown): SSEEvent => ({ type: 'CUSTOM', name, value })

function step(name: string, attempt = 1, maxAttempts: number | null = 1, model: string | null = null, body: SSEEvent[] = [], finished = true): SSEEvent[] {
  return [
    { type: 'STEP_STARTED', stepName: name },
    custom('serka.step', { step: name, attempt, maxAttempts, model }),
    ...body,
    ...(finished ? [{ type: 'STEP_FINISHED', stepName: name } as SSEEvent] : []),
  ]
}

function tool(id: string, name: string, args: object, result: string): SSEEvent[] {
  return [
    { type: 'TOOL_CALL_START', toolCallId: id, toolCallName: name },
    { type: 'TOOL_CALL_ARGS', toolCallId: id, delta: JSON.stringify(args) },
    { type: 'TOOL_CALL_END', toolCallId: id },
    { type: 'TOOL_CALL_RESULT', toolCallId: id, content: result },
  ]
}

const text = (t: string): SSEEvent[] => [
  { type: 'TEXT_MESSAGE_START' }, { type: 'TEXT_MESSAGE_CONTENT', delta: t }, { type: 'TEXT_MESSAGE_END' },
]

const evaluation = (attempt: number, passed: boolean, score: number, problem = 'none', feedback = 'Fine.') =>
  custom('serka.evaluation', { attempt, passed, score, problem, feedback })

const outcome = (status: string, path: string | null, attemptsUsed: number, maxAttempts: number | null, score: number | null) =>
  custom('serka.outcome', { status, path, attemptsUsed, maxAttempts, score, feedback: null })

const KEYWORD: RunEvent[] = [
  { type: 'RUN_STARTED' },
  ...step('classify', 1, null, 'nova-lite', [custom('serka.classification', { inScope: true, label: 'keyword', reason: 'Dataset search.' })]),
  ...step('route', 1, 1, null, [{ type: 'RUN_METADATA', model: 'nova-lite', models: MODELS }]),
  ...step('plan', 1, 1, 'nova-micro', [custom('serka.plan', { summary: 'Search soil carbon.', steps: ['search {}'] })]),
  ...step('execute', 1, 1, null, tool('t1', 'search', { query: 'soil carbon' }, '{"@graph": []}')),
  ...step('synthesize', 1, 1, 'nova-lite', [{ type: 'TEXT_MESSAGE_START' }, { type: 'TEXT_MESSAGE_CONTENT', delta: 'Answer' }]),
  ...step('evaluate', 1, 1, 'haiku', [evaluation(1, true, 5)]),
  { type: 'TEXT_MESSAGE_END' },
  outcome('accepted', 'keyword', 1, 1, 5),
  { type: 'RUN_FINISHED' },
]

const INSIGHT_RETRY: RunEvent[] = [
  { type: 'RUN_STARTED' },
  ...step('classify', 1, null, 'nova-lite', [custom('serka.classification', { inScope: true, label: 'insight', reason: 'Trends.' })]),
  ...step('route', 1, 2, null, [{ type: 'RUN_METADATA', model: 'sonnet', models: MODELS }]),
  ...step('plan', 1, 2, 'sonnet', [custom('serka.plan', { summary: 'Find datasets.', steps: ['a', 'b'] })]),
  ...step('execute', 1, 2, 'haiku', [
    ...tool('t1', 'search', { query: 'a' }, '{}'),
    ...tool('t2', 'search', { query: 'b' }, '{}'),
    ...tool('t3', 'get_dataset', { id: 'x' }, 'Error: not found'),
    ...tool('t4', 'search', { query: 'c' }, '{}'),
  ]),
  ...step('synthesize', 1, 2, 'sonnet', [custom('serka.draft', { attempt: 1, text: 'Draft one' })]),
  ...step('evaluate', 1, 2, 'haiku', [evaluation(1, false, 2, 'writing', 'Missing date ranges.')]),
  ...step('synthesize', 2, 2, 'sonnet', [custom('serka.draft', { attempt: 2, text: 'Draft two' })]),
  ...step('evaluate', 2, 2, 'haiku', [evaluation(2, true, 4)]),
  ...text('Draft two'),
  outcome('accepted', 'insight', 2, 2, 4),
  { type: 'RUN_FINISHED' },
]

const REFUSED: RunEvent[] = [
  { type: 'RUN_STARTED' },
  ...step('classify', 1, null, 'nova-lite', [custom('serka.classification', { inScope: false, label: null, reason: 'Not about environmental data' })]),
  { type: 'RUN_METADATA', model: 'nova-lite', models: MODELS },
  ...step('refuse', 1, null, null, text('Sorry.')),
  outcome('refused', null, 0, null, null),
  { type: 'RUN_FINISHED' },
]

const INSIGHT_LIMIT: RunEvent[] = [
  { type: 'RUN_STARTED' },
  ...step('classify', 1, null, 'nova-lite', [custom('serka.classification', { inScope: true, label: 'insight', reason: 'Trends.' })]),
  ...step('route', 1, 2, null, [{ type: 'RUN_METADATA', model: 'sonnet', models: MODELS }]),
  ...step('limit', 1, 2, null, text('Detailed analysis has reached its daily limit.')),
  outcome('insight_limit_reached', 'insight', 0, 2, null),
  { type: 'RUN_FINISHED' },
]

/** Replays events, 100 ms apart, returning the trace after each event. */
function replayAll(events: RunEvent[]): RunTrace[] {
  const traces: RunTrace[] = []
  let t = emptyRun(T0)
  events.forEach((e, i) => {
    t = reduceRun(t, e, T0 + (i + 1) * 100)
    traces.push(t)
  })
  return traces
}
const replay = (events: RunEvent[]) => replayAll(events).at(-1)!

/** Trace just after the `n`th (1-based) STEP_STARTED for `name` and its serka.step. */
function atStep(events: RunEvent[], name: string, n = 1): RunTrace {
  let seen = 0
  const i = events.findIndex((e) => e.type === 'STEP_STARTED' && e.stepName === name && ++seen === n)
  return replay(events.slice(0, i + 2))
}

// ─── reduceRun ────────────────────────────────────────────────────────────────

describe('reduceRun', () => {
  it('builds a keyword run', () => {
    const t = replay(KEYWORD)
    expect(t.status).toBe('accepted')
    expect(t.path).toBe('keyword')
    expect(t.models).toEqual(MODELS)
    expect(t.steps.map((s) => s.name)).toEqual(['classify', 'route', 'plan', 'execute', 'synthesize', 'evaluate'])
    expect(t.steps.every((s) => s.finishedAt !== undefined && !s.failed)).toBe(true)
    const execute = t.steps[3]
    expect(execute.toolCalls).toEqual([{ id: 't1', name: 'search', args: '{"query":"soil carbon"}', result: '{"@graph": []}', ok: true }])
    expect(t.steps[0].classification?.label).toBe('keyword')
    expect(t.steps[0].model).toBe('nova-lite')
    expect(t.steps[0].maxAttempts).toBeNull()
    expect(t.steps[2].plan?.summary).toBe('Search soil carbon.')
    expect(t.finishedAt).toBe(T0 + KEYWORD.length * 100)
  })

  it('builds an insight run with a retry', () => {
    const t = replay(INSIGHT_RETRY)
    expect(t.status).toBe('accepted')
    expect(t.steps.map((s) => `${s.name}:${s.attempt}`)).toEqual([
      'classify:1', 'route:1', 'plan:1', 'execute:1', 'synthesize:1', 'evaluate:1', 'synthesize:2', 'evaluate:2',
    ])
    expect(t.steps[3].toolCalls.map((c) => c.ok)).toEqual([true, true, false, true])
    expect(t.steps.filter((s) => s.name !== 'execute').every((s) => s.toolCalls.length === 0)).toBe(true)
    expect(t.steps[4].draft).toBe('Draft one')
    expect(t.steps[5].evaluation).toMatchObject({ passed: false, problem: 'writing' })
    expect(t.steps[7].evaluation?.passed).toBe(true)
    expect(t.outcome?.attemptsUsed).toBe(2)
  })

  it('builds a refused run', () => {
    const t = replay(REFUSED)
    expect(t.status).toBe('refused')
    expect(t.path).toBeNull()
    expect(t.steps.map((s) => s.name)).toEqual(['classify', 'refuse'])
  })

  it('maps the insight limit outcome to a usage limit', () => {
    const t = replay(INSIGHT_LIMIT)
    expect(t.status).toBe('usage_limit')
    expect(t.path).toBe('insight')
    expect(t.error).toBeUndefined()
    expect(t.steps.map((s) => s.name)).toEqual(['classify', 'route', 'limit'])
    expect(t.steps.every((s) => !s.failed)).toBe(true)
  })

  it('settles as a usage limit on USAGE_LIMIT, and later events change nothing', () => {
    const t = reduceRun(emptyRun(T0), { type: 'USAGE_LIMIT', message: 'Try tomorrow.' }, T0 + 100)
    expect(t.status).toBe('usage_limit')
    expect(t.limitMessage).toBe('Try tomorrow.')
    expect(t.finishedAt).toBe(T0 + 100)
    expect(reduceRun(t, { type: 'STREAM_CLOSED' }, T0 + 200)).toBe(t)
  })

  it('ends in error on RUN_ERROR and closes the open step', () => {
    const events: RunEvent[] = [
      ...INSIGHT_RETRY.slice(0, INSIGHT_RETRY.findIndex((e) => e.type === 'STEP_STARTED' && e.stepName === 'execute')),
      ...step('execute', 1, 2, 'haiku', [], false),
      { type: 'RUN_ERROR', message: 'Sorry, something went wrong.' },
    ]
    const t = replay(events)
    expect(t.status).toBe('error')
    expect(t.error).toBe('Sorry, something went wrong.')
    const last = t.steps.at(-1)!
    expect(last.name).toBe('execute')
    expect(last.failed).toBe(true)
    expect(last.finishedAt).toBe(t.finishedAt)
    expect(t.steps.slice(0, -1).every((s) => !s.failed)).toBe(true)
  })

  it('ends in error when the stream closes early', () => {
    const t = replay([...KEYWORD.slice(0, 10), { type: 'STREAM_CLOSED' }])
    expect(t.status).toBe('error')
    expect(t.error).toBeUndefined()
    expect(t.finishedAt).toBeDefined()
  })

  it('ignores STREAM_CLOSED after the run has finished', () => {
    const done = replay(KEYWORD)
    expect(reduceRun(done, { type: 'STREAM_CLOSED' }, T0 + 1e6)).toBe(done)
  })

  it('ignores unknown events and custom names', () => {
    const t = replay(KEYWORD.slice(0, 5))
    expect(reduceRun(t, { type: 'SOMETHING_NEW' } as unknown as RunEvent, T0)).toBe(t)
    expect(reduceRun(t, custom('serka.future', { x: 1 }), T0)).toBe(t)
    expect(reduceRun(t, { type: 'TOOL_CALL_RESULT', toolCallId: 'nope', content: '{}' }, T0)).toBe(t)
  })
})

// ─── Retry notice ─────────────────────────────────────────────────────────────

describe('retry notice', () => {
  it('shows on the next stage and clears one stage later', () => {
    const afterFail = replay(INSIGHT_RETRY.slice(0, INSIGHT_RETRY.findIndex((e) => e.type === 'CUSTOM' && e.name === 'serka.evaluation') + 1))
    expect(progressText(afterFail)).toBe("Attempt 1 didn't pass: Missing date ranges, retrying")
    const nextStage = atStep(INSIGHT_RETRY, 'synthesize', 2)
    expect(progressText(nextStage)).toBe("Attempt 1 didn't pass: Missing date ranges, retrying")
    const oneLater = atStep(INSIGHT_RETRY, 'evaluate', 2)
    expect(progressText(oneLater)).toBe('Checking the answer (attempt 2 of 2)')
  })

  it('is not set when no attempts remain', () => {
    const events = [...step('evaluate', 2, 2, 'haiku', [evaluation(2, false, 2, 'data', 'Still missing.')], false)]
    expect(progressText(replay(events))).toBe('Checking the answer (attempt 2 of 2)')
  })
})

// ─── Wording ──────────────────────────────────────────────────────────────────

describe('progressText', () => {
  it('names each stage', () => {
    expect(progressText(emptyRun(T0))).toBe('Starting')
    expect(progressText(atStep(INSIGHT_RETRY, 'classify'))).toBe('Understanding your question')
    expect(progressText(atStep(INSIGHT_RETRY, 'route'))).toBe('Choosing an approach')
    expect(progressText(atStep(INSIGHT_RETRY, 'plan'))).toBe('Planning the search')
    expect(progressText(atStep(INSIGHT_RETRY, 'execute'))).toBe('Searching the catalogue')
    expect(progressText(atStep(INSIGHT_RETRY, 'synthesize'))).toBe('Writing the answer (attempt 1 of 2)')
    expect(progressText(atStep(INSIGHT_RETRY, 'evaluate'))).toBe('Checking the answer (attempt 1 of 2)')
    expect(progressText(atStep(REFUSED, 'refuse'))).toBe('Out of scope')
    expect(progressText(atStep(INSIGHT_LIMIT, 'limit'))).toBe('Daily limit reached')
  })

  it('omits the attempt on single-attempt keyword runs', () => {
    expect(progressText(atStep(KEYWORD, 'evaluate'))).toBe('Checking the answer')
  })

  it('names the tool during execute', () => {
    const t = replay([...step('execute', 1, 2, 'haiku', [{ type: 'TOOL_CALL_START', toolCallId: 'x', toolCallName: 'search' }], false)])
    expect(progressText(t)).toBe('Searching the catalogue (search)')
  })
})

describe('summaryText', () => {
  it('describes an accepted insight run', () => {
    const t = replay(INSIGHT_RETRY)
    expect(summaryText(t)).toBe(`Insight query · 4 catalogue calls · Accepted on attempt 2 · score 4 of 5 · ${formatDate(t.finishedAt!)}`)
    expect(formatDate(t.finishedAt!)).toBe('3 Nov 2026')
  })

  it('names the retrieval limit when a run ends with attempts left', () => {
    const events = [...INSIGHT_RETRY.slice(0, -2), outcome('limit_reached', 'insight', 1, 2, 2), { type: 'RUN_FINISHED' } as RunEvent]
    const t = replay(events)
    expect(stoppedAtRetrievalLimit(t)).toBe(true)
    expect(summaryText(t)).toContain('Retrieval stopped at its limit')
    expect(summaryText(t)).not.toContain('Best of')
  })

  it('describes a limit-reached run', () => {
    const events = [...INSIGHT_RETRY.slice(0, -2), outcome('limit_reached', 'insight', 2, 2, 2), { type: 'RUN_FINISHED' } as RunEvent]
    const t = replay(events)
    expect(t.status).toBe('limit_reached')
    expect(summaryText(t)).toContain('Best of 2 attempts returned without fully passing')
  })

  it('describes a refused run with its reason', () => {
    expect(summaryText(replay(REFUSED))).toMatch(/^Out of scope: Not about environmental data · /)
  })

  it('describes the insight limit without error or out-of-scope wording', () => {
    const summary = summaryText(replay(INSIGHT_LIMIT))
    expect(summary).toMatch(/^Detailed analysis has reached its daily limit · /)
    expect(summary).not.toMatch(/Something went wrong|Out of scope/)
  })

  it('shows the server message for a rejected request', () => {
    const t = reduceRun(emptyRun(T0), { type: 'USAGE_LIMIT', message: 'Try tomorrow.' }, T0 + 100)
    expect(summaryText(t)).toBe(`Try tomorrow. · ${formatDate(T0 + 100)}`)
  })

  it('describes an error with and without a message', () => {
    const withMessage = replay([{ type: 'RUN_STARTED' }, { type: 'RUN_ERROR', message: 'Boom.' }])
    expect(summaryText(withMessage)).toMatch(/^Something went wrong: Boom\./)
    const closed = replay([{ type: 'RUN_STARTED' }, { type: 'STREAM_CLOSED' }])
    expect(summaryText(closed)).toMatch(/^Something went wrong: the summary stopped unexpectedly/)
  })
})

describe('compactOutcome', () => {
  it('returns only status, path, attempts, score and models', () => {
    const c = compactOutcome(replay(INSIGHT_RETRY))
    expect(c).toEqual({ status: 'accepted', path: 'insight', attemptsUsed: 2, score: 4, models: MODELS })
    expect(JSON.stringify(c)).not.toMatch(/Draft|@graph|search/)
  })
})
