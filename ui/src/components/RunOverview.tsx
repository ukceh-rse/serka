import { useState } from 'react'
import { Box, Button, CircularProgress, Collapse, Typography } from '@mui/material'
import { alpha } from '@mui/material/styles'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import BlockIcon from '@mui/icons-material/Block'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { progressText, summaryText, type RunStatus, type RunTrace } from '../run/runTrace'
import RunTimeline from './RunTimeline'

type Tint = 'success' | 'warning' | 'error' | null

const STATUS_STYLE: Record<Exclude<RunStatus, 'running'>, { icon: typeof BlockIcon; color: Tint }> = {
  accepted: { icon: CheckCircleOutlineIcon, color: 'success' },
  limit_reached: { icon: WarningAmberIcon, color: 'warning' },
  refused: { icon: BlockIcon, color: null },
  error: { icon: ErrorOutlineIcon, color: 'error' },
}

/**
 * The line under the AI Summary header: live progress while the run is going, then, in the
 * same place, the settled summary row with a Details toggle for the run timeline.
 */
export default function RunOverview({ run }: { run: RunTrace }) {
  const [open, setOpen] = useState(false)

  if (run.status === 'running') {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1, py: 0.5, mb: 1.5, minHeight: 28 }}>
        <CircularProgress size={12} />
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {progressText(run)}…
        </Typography>
      </Box>
    )
  }

  const { icon: Icon, color } = STATUS_STYLE[run.status]
  // Accepted keeps a neutral row with a success icon; only warning and error rows are tinted.
  const tinted = color === 'warning' || color === 'error'
  return (
    <Box
      sx={(theme) => ({
        mb: 1.5,
        px: 1,
        py: 0.5,
        borderRadius: 1,
        bgcolor: tinted ? alpha(theme.palette[color].main, 0.1) : 'action.hover',
      })}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minHeight: 28 }}>
        <Icon sx={{ fontSize: '0.95rem', color: color ? `${color}.main` : 'text.secondary' }} />
        <Typography
          variant="caption"
          sx={{ flex: 1, minWidth: 0, color: tinted ? `${color}.main` : 'text.secondary' }}
        >
          {summaryText(run)}
        </Typography>
        <Button
          size="small"
          onClick={() => setOpen((v) => !v)}
          endIcon={<ExpandMoreIcon sx={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />}
          sx={{ fontSize: '0.7rem', textTransform: 'none', py: 0, flexShrink: 0 }}
        >
          Details
        </Button>
      </Box>
      <Collapse in={open} unmountOnExit>
        {/* Indented to line up with the summary text, past the status icon */}
        <Box sx={{ pl: 3, pb: 0.5 }}>
          <RunTimeline run={run} />
        </Box>
      </Collapse>
    </Box>
  )
}
