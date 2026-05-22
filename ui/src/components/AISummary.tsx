import { Box, Button, CircularProgress, Collapse, Divider, Paper, Typography } from '@mui/material'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import { useSearchStore } from '../stores/searchStore'
import FeedbackWidget from './FeedbackWidget'
import { streamSummary } from '../api/chat'

interface Props {
  query: string
}

export default function AISummary({ query }: Props) {
  const {
    aiSummaryEnabled,
    aiSummary,
    aiThinking,
    aiLoading,
    toggleAiSummary,
    appendAiSummary,
    setAiThinking,
    setAiLoading,
    resetAiSummary,
  } = useSearchStore()

  const handleToggle = async () => {
    toggleAiSummary()
    if (!aiSummaryEnabled && !aiSummary) {
      resetAiSummary()
      setAiLoading(true)
      try {
        await streamSummary(query, (event) => {
          if (event.type === 'THINKING_START') setAiThinking(true)
          if (event.type === 'THINKING_END') setAiThinking(false)
          if (event.type === 'TEXT_MESSAGE_CONTENT' && event.delta) appendAiSummary(event.delta)
          if (event.type === 'RUN_FINISHED') setAiLoading(false)
        })
      } catch {
        setAiLoading(false)
      }
    }
  }

  return (
    <Box sx={{ mb: 3 }}>
      <Button
        variant={aiSummaryEnabled ? 'contained' : 'outlined'}
        size="small"
        startIcon={<AutoAwesomeIcon />}
        onClick={handleToggle}
        sx={{ mb: 2 }}
      >
        AI summary
      </Button>
      <Collapse in={aiSummaryEnabled}>
        <Paper variant="outlined" sx={{ p: 2 }}>
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
    </Box>
  )
}
