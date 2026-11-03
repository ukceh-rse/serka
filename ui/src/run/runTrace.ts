/**
 * Turns the chat event stream (openspec `chat-agent-events`) into a run model that the
 * AI Summary progress line, summary row, timeline and feedback all read from.
 * Pure: no React, no store, no clock (`now` is passed in).
 */
import type { SSEEvent } from '../api/chat'

/** A contract event, or the synthetic close the client applies when the stream ends. */
export type RunEvent = SSEEvent | { type: 'STREAM_CLOSED' }

export type RunStatus = 'running' | 'accepted' | 'limit_reached' | 'refused' | 'error'

export interface ToolCall {
  id: string
  name: string
  /** Raw JSON arguments, concatenated from TOOL_CALL_ARGS deltas. */
  args: string
  /** Raw result content: a JSON string, or `Error: ...`. */
  result?: string
  ok?: boolean
}

export interface Classification {
  inScope: boolean
  label: string | null
  reason: string
}

export interface PlanResult {
  summary: string
  steps: string[]
}

export interface Evaluation {
  attempt: number
  passed: boolean
  score: number
  problem: string
  feedback: string
}

export interface Outcome {
  status: Exclude<RunStatus, 'running' | 'error'>
  path: string | null
  attemptsUsed: number
  maxAttempts: number | null
  score: number | null
  feedback: string | null
}

/** One execution of a pipeline stage. */
export interface RunStep {
  name: string
  attempt: number
  maxAttempts: number | null
  model: string | null
  startedAt: number
  finishedAt?: number
  /** True when the run ended (error or early close) while this step was still open. */
  failed?: boolean
  classification?: Classification
  plan?: PlanResult
  draft?: string
  evaluation?: Evaluation
  toolCalls: ToolCall[]
}

export interface RunTrace {
  status: RunStatus
  error?: string
  path: string | null
  models: Record<string, string>
  startedAt: number
  finishedAt?: number
  steps: RunStep[]
  outcome?: Outcome
}

export function emptyRun(now: number): RunTrace {
  return { status: 'running', path: null, models: {}, startedAt: now, steps: [] }
}

function openStepIndex(trace: RunTrace): number {
  const i = trace.steps.length - 1
  return i >= 0 && trace.steps[i].finishedAt === undefined ? i : -1
}

function updateOpenStep(trace: RunTrace, patch: (s: RunStep) => Partial<RunStep>): RunTrace {
  const i = openStepIndex(trace)
  if (i < 0) return trace
  const steps = trace.steps.slice()
  steps[i] = { ...steps[i], ...patch(steps[i]) }
  return { ...trace, steps }
}

function updateToolCall(trace: RunTrace, id: string | undefined, patch: (c: ToolCall) => Partial<ToolCall>): RunTrace {
  if (!id || !trace.steps.some((s) => s.toolCalls.some((c) => c.id === id))) return trace
  const steps = trace.steps.map((s) =>
    s.toolCalls.some((c) => c.id === id)
      ? { ...s, toolCalls: s.toolCalls.map((c) => (c.id === id ? { ...c, ...patch(c) } : c)) }
      : s,
  )
  return { ...trace, steps }
}

/** Ends the run, closing any step left open (a stage that raised gets no STEP_FINISHED). */
function finish(trace: RunTrace, status: RunStatus, now: number, error?: string): RunTrace {
  const steps = trace.steps.map((s) => (s.finishedAt === undefined ? { ...s, finishedAt: now, failed: true } : s))
  return { ...trace, status, error, steps, finishedAt: now }
}

function noticeText(e: Evaluation): string {
  return `Attempt ${e.attempt} didn't pass: ${e.feedback.trim().replace(/[.\s]+$/, '')}, retrying`
}

function reduceCustom(trace: RunTrace, name: string | undefined, value: unknown): RunTrace {
  const v = (value ?? {}) as Record<string, unknown>
  switch (name) {
    case 'serka.step':
      return updateOpenStep(trace, () => ({
        attempt: (v.attempt as number) ?? 1,
        maxAttempts: (v.maxAttempts as number | null) ?? null,
        model: (v.model as string | null) ?? null,
      }))
    case 'serka.classification': {
      const classification = v as unknown as Classification
      const next = updateOpenStep(trace, () => ({ classification }))
      return classification.inScope ? { ...next, path: classification.label } : next
    }
    case 'serka.plan':
      return updateOpenStep(trace, () => ({ plan: v as unknown as PlanResult }))
    case 'serka.draft':
      return updateOpenStep(trace, () => ({ draft: v.text as string }))
    case 'serka.evaluation':
      return updateOpenStep(trace, () => ({ evaluation: v as unknown as Evaluation }))
    case 'serka.outcome': {
      const outcome = v as unknown as Outcome
      return { ...trace, outcome, path: outcome.path ?? trace.path }
    }
    default:
      return trace
  }
}

export function reduceRun(trace: RunTrace, event: RunEvent, now: number): RunTrace {
  if (trace.status !== 'running') return trace
  switch (event.type) {
    case 'STEP_STARTED': {
      const step: RunStep = {
        name: event.stepName ?? 'unknown',
        attempt: 1,
        maxAttempts: null,
        model: null,
        startedAt: now,
        toolCalls: [],
      }
      return { ...trace, steps: [...trace.steps, step] }
    }
    case 'STEP_FINISHED':
      return updateOpenStep(trace, () => ({ finishedAt: now }))
    case 'CUSTOM':
      return reduceCustom(trace, event.name, event.value)
    case 'RUN_METADATA':
      return event.models ? { ...trace, models: event.models } : trace
    case 'TOOL_CALL_START': {
      const call: ToolCall = { id: event.toolCallId ?? '', name: event.toolCallName ?? 'tool', args: '' }
      return updateOpenStep(trace, (s) => ({ toolCalls: [...s.toolCalls, call] }))
    }
    case 'TOOL_CALL_ARGS':
      return updateToolCall(trace, event.toolCallId, (c) => ({ args: c.args + (event.delta ?? '') }))
    case 'TOOL_CALL_RESULT': {
      const content = event.content ?? ''
      return updateToolCall(trace, event.toolCallId, () => ({ result: content, ok: !content.startsWith('Error:') }))
    }
    case 'RUN_FINISHED':
      return trace.outcome
        ? finish(trace, trace.outcome.status, now)
        : finish(trace, 'error', now, 'The run finished without an outcome.')
    case 'RUN_ERROR':
      return finish(trace, 'error', now, event.message)
    case 'STREAM_CLOSED':
      return finish(trace, 'error', now)
    default:
      return trace
  }
}

// ─── Wording ──────────────────────────────────────────────────────────────────

const STAGE_PHRASES: Record<string, string> = {
  classify: 'Understanding your question',
  route: 'Choosing an approach',
  plan: 'Planning the search',
  execute: 'Searching the catalogue',
  synthesize: 'Writing the answer',
  evaluate: 'Checking the answer',
  refuse: 'Out of scope',
}

const PATH_LABELS: Record<string, string> = {
  keyword: 'Keyword search',
  insight: 'Insight query',
}

export function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

/** Whether a step's attempt number is worth showing: retryable stages, or any retry. */
export function showsAttempt(step: RunStep): boolean {
  return (step.maxAttempts ?? 1) > 1 && (['synthesize', 'evaluate'].includes(step.name) || step.attempt > 1)
}

function stagePhrase(step: RunStep): string {
  let phrase = STAGE_PHRASES[step.name] ?? capitalize(step.name)
  if (step.name === 'execute') {
    const call = [...step.toolCalls].reverse().find((c) => c.result === undefined) ?? step.toolCalls.at(-1)
    if (call) phrase += ` (${call.name})`
  }
  if (showsAttempt(step)) phrase += ` (attempt ${step.attempt} of ${step.maxAttempts})`
  return phrase
}

/** The live progress line while the run is in progress. */
export function progressText(trace: RunTrace): string {
  // A failed evaluation that will be retried is announced through the stage that follows it.
  const evaluated = trace.steps.slice(-2).reverse().find((s) => s.evaluation)
  const e = evaluated?.evaluation
  const max = evaluated?.maxAttempts ?? null
  if (e && !e.passed && max !== null && e.attempt < max) return noticeText(e)
  const step = trace.steps.at(-1)
  return step ? stagePhrase(step) : 'Starting'
}

function catalogueCalls(trace: RunTrace): number {
  return trace.steps.reduce((n, s) => n + s.toolCalls.length, 0)
}

export function formatDate(ms: number): string {
  return new Date(ms).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

/** The settled summary row once the run has ended. */
export function summaryText(trace: RunTrace): string {
  const date = trace.finishedAt !== undefined ? formatDate(trace.finishedAt) : ''
  const join = (parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(' · ')

  if (trace.status === 'error') {
    return join([`Something went wrong: ${trace.error ?? 'the summary stopped unexpectedly. Please try again.'}`, date])
  }
  if (trace.status === 'refused') {
    const reason = trace.steps.find((s) => s.classification)?.classification?.reason
    return join([reason ? `Out of scope: ${reason}` : 'Out of scope', date])
  }
  const o = trace.outcome
  const calls = catalogueCalls(trace)
  const result =
    trace.status === 'limit_reached'
      ? `Best of ${o?.attemptsUsed} attempts returned without fully passing`
      : `Accepted on attempt ${o?.attemptsUsed}`
  return join([
    trace.path && (PATH_LABELS[trace.path] ?? trace.path),
    `${calls} catalogue ${calls === 1 ? 'call' : 'calls'}`,
    result,
    o?.score != null && `score ${o.score} of 5`,
    date,
  ])
}

interface CompactOutcome {
  status: RunStatus
  path: string | null
  attemptsUsed: number | null
  score: number | null
  models: Record<string, string>
}

/** The run outcome attached to AI Summary feedback: no tool results or drafts. */
export function compactOutcome(trace: RunTrace): CompactOutcome {
  return {
    status: trace.status,
    path: trace.path,
    attemptsUsed: trace.outcome?.attemptsUsed ?? null,
    score: trace.outcome?.score ?? null,
    models: trace.models,
  }
}
