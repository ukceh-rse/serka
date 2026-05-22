import { Box, CircularProgress, Collapse, Divider, Paper, Typography } from '@mui/material'
import { useSearchStore } from '../stores/searchStore'
import FeedbackWidget from './FeedbackWidget'

interface Props {
  query: string
}

export default function AISummary({ query }: Props) {
  const { aiSummaryEnabled, aiSummary, aiThinking, aiLoading } = useSearchStore()

  return (
    <Collapse in={aiSummaryEnabled} unmountOnExit>
      <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
        {aiLoading && aiThinking && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <CircularProgress size={14} />
            <Typography variant="caption" color="text.secondary">
              Thinking…
            </Typography>
          </Box>
        )}
        {aiLoading && !aiSummary && !aiThinking && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={14} />
            <Typography variant="caption" color="text.secondary">
              Generating summary…
            </Typography>
          </Box>
        )}
        {aiSummary && (
          <>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {aiSummary}
            </Typography>
            {!aiLoading && (
              <>
                <Divider sx={{ my: 1.5 }} />
                <FeedbackWidget context={{ type: 'ai_summary', query }} />
              </>
            )}
          </>
        )}
      </Paper>
    </Collapse>
  )
}
