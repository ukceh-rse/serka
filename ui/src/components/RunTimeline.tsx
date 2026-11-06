import { useState, type ReactNode } from 'react'
import { Box, Collapse, IconButton, Typography } from '@mui/material'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import { capitalize, showsAttempt, stoppedAtRetrievalLimit, type RunStep, type RunTrace, type ToolCall } from '../run/runTrace'

// ─── Formatting ───────────────────────────────────────────────────────────────

const OUTCOME_LABELS: Record<string, string> = {
  accepted: 'Accepted',
  limit_reached: 'Attempt limit reached',
  refused: 'Refused',
  usage_limit: 'Daily limit',
  error: 'Error',
}

function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

/** One-line tool arguments, e.g. `query: "soil carbon", return_type: "dcat:Dataset"`. */
function shortArgs(raw: string, max = 60): string {
  let s = raw
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      s = Object.entries(parsed).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')
    }
  } catch {
    // keep raw
  }
  return s.length > max ? s.slice(0, max) + '…' : s
}

function toolLine(c: ToolCall): string {
  const status = c.result === undefined ? '…' : c.ok ? '✓' : '✗'
  return `${c.name}(${shortArgs(c.args)}) ${status}`
}

function stepSummary(step: RunStep, trace: RunTrace): ReactNode {
  if (step.failed) return 'Did not finish'
  switch (step.name) {
    case 'classify': {
      const c = step.classification
      if (!c) return null
      return `${c.inScope ? c.label : 'out of scope'}: ${c.reason}`
    }
    case 'route':
      return trace.path ? `${trace.path} path` : null
    case 'plan':
      return step.plan?.summary ?? null
    case 'execute':
      if (!step.toolCalls.length) return 'No catalogue calls'
      return (
        <>
          {step.toolCalls.map((c) => (
            <Box key={c.id} component="span" sx={{ display: 'block', color: c.ok === false ? 'error.main' : undefined }}>
              {toolLine(c)}
            </Box>
          ))}
        </>
      )
    case 'synthesize': {
      if (step.draft === undefined) return 'Answer streamed'
      const ev = trace.steps.find((s) => s.name === 'evaluate' && s.evaluation?.attempt === step.attempt)?.evaluation
      return ev && !ev.passed ? 'Draft rejected by evaluation' : 'Draft written'
    }
    case 'evaluate': {
      const e = step.evaluation
      if (!e) return null
      return [e.passed ? 'Passed' : 'Failed', `score ${e.score} of 5`, e.problem !== 'none' && `problem: ${e.problem}`]
        .filter(Boolean)
        .join(' · ')
    }
    case 'refuse':
      return 'Refusal returned'
    case 'limit':
      return 'Daily limit message returned'
    default:
      return null
  }
}

const preSx = {
  m: 0,
  mt: 0.5,
  p: 1,
  maxHeight: 240,
  overflow: 'auto',
  fontFamily: 'monospace',
  fontSize: '0.7rem',
  lineHeight: 1.4,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  bgcolor: 'action.hover',
  borderRadius: 1,
} as const

/** Pretty-printed JSON; a component so the parse only runs once its row is expanded. */
function Json({ raw }: { raw: string }) {
  let text = raw
  try {
    text = JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    // keep raw
  }
  return <Box component="pre" sx={preSx}>{text}</Box>
}

function stepDetail(step: RunStep): ReactNode {
  switch (step.name) {
    case 'execute':
      if (!step.toolCalls.length) return null
      return step.toolCalls.map((c) => (
        <Box key={c.id} sx={{ mb: 1 }}>
          <Typography variant="caption" sx={{ fontWeight: 600 }}>{c.name} arguments</Typography>
          <Json raw={c.args} />
          <Typography variant="caption" sx={{ fontWeight: 600 }}>{c.name} result</Typography>
          <Json raw={c.result ?? '(no result)'} />
        </Box>
      ))
    case 'plan':
      if (!step.plan?.steps.length) return null
      return (
        <Box component="ol" sx={{ m: 0, pl: 2.5 }}>
          {step.plan.steps.map((s, i) => (
            <Typography key={i} component="li" variant="caption" sx={{ fontFamily: 'monospace', wordBreak: 'break-word' }}>
              {s}
            </Typography>
          ))}
        </Box>
      )
    case 'synthesize':
      return step.draft === undefined ? null : <Box component="pre" sx={{ ...preSx, fontFamily: 'inherit' }}>{step.draft}</Box>
    case 'evaluate':
      return step.evaluation?.feedback ? <Typography variant="caption">{step.evaluation.feedback}</Typography> : null
    default:
      return null
  }
}

// ─── Rows ─────────────────────────────────────────────────────────────────────

function Row({ label, meta, summary, detail, error }: {
  label: string
  meta?: string
  summary: ReactNode
  detail?: ReactNode
  error?: boolean
}) {
  const [open, setOpen] = useState(false)
  return (
    <Box sx={{ py: 0.5, borderTop: '1px solid', borderColor: 'divider' }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5 }}>
        <Box sx={{ width: 22, flexShrink: 0 }}>
          {detail && (
            <IconButton size="small" onClick={() => setOpen((v) => !v)} sx={{ p: 0 }} aria-label={open ? 'Hide detail' : 'Show detail'}>
              <ChevronRightIcon sx={{ fontSize: '1rem', transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s' }} />
            </IconButton>
          )}
        </Box>
        <Typography variant="caption" sx={{ fontWeight: 600, width: 130, flexShrink: 0, color: error ? 'error.main' : undefined }}>
          {label}
        </Typography>
        <Typography variant="caption" component="div" sx={{ flex: 1, minWidth: 0, color: error ? 'error.main' : 'text.secondary', wordBreak: 'break-word' }}>
          {summary}
        </Typography>
        {meta && (
          <Typography variant="caption" sx={{ flexShrink: 0, color: 'text.secondary', textAlign: 'right', ml: 1 }}>
            {meta}
          </Typography>
        )}
      </Box>
      {detail && (
        <Collapse in={open} unmountOnExit>
          <Box sx={{ pl: '22px', pt: 0.5, minWidth: 0 }}>{detail}</Box>
        </Collapse>
      )}
    </Box>
  )
}

// ─── Timeline ─────────────────────────────────────────────────────────────────

export default function RunTimeline({ run }: { run: RunTrace }) {
  const o = run.outcome
  const outcomeLabel = stoppedAtRetrievalLimit(run) ? 'Retrieval limit reached' : OUTCOME_LABELS[run.status] ?? run.status
  const outcomeSummary =
    run.status === 'error'
      ? run.error ?? 'The summary stopped unexpectedly.'
      : [
          o && o.attemptsUsed > 0 && `${o.attemptsUsed} of ${o.maxAttempts} attempts used`,
          o?.score != null && `score ${o.score} of 5`,
          o?.feedback,
        ].filter(Boolean).join(' · ')

  return (
    <Box sx={{ mt: 1 }}>
      {run.steps.map((step, i) => {
        const label = capitalize(step.name) + (showsAttempt(step) ? ` · attempt ${step.attempt}` : '')
        const meta = [step.model, step.finishedAt !== undefined && formatDuration(step.finishedAt - step.startedAt)].filter(Boolean).join(' · ')
        const failedEval = step.evaluation && !step.evaluation.passed
        return (
          <Row
            key={i}
            label={label}
            meta={meta}
            summary={stepSummary(step, run)}
            detail={stepDetail(step)}
            error={step.failed || failedEval}
          />
        )
      })}
      <Row label={`Outcome: ${outcomeLabel}`} summary={outcomeSummary} error={run.status === 'error'} />
    </Box>
  )
}
