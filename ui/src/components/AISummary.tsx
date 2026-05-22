import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Box, CircularProgress, Collapse, Divider, Link, Paper, Typography } from '@mui/material'
import { useSearchStore } from '../stores/searchStore'
import FeedbackWidget from './FeedbackWidget'

const mdComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => <Typography variant="body2" sx={{ mb: 1, '&:last-child': { mb: 0 } }}>{children}</Typography>,
  h1: ({ children }) => <Typography variant="h6" sx={{ mt: 1.5, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  h2: ({ children }) => <Typography variant="subtitle1" sx={{ mt: 1.5, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  h3: ({ children }) => <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  li: ({ children }) => <Typography component="li" variant="body2" sx={{ mb: 0.25 }}>{children}</Typography>,
  a: ({ href, children }) => <Link href={href} target="_blank" rel="noopener noreferrer">{children}</Link>,
  code: ({ children }) => (
    <Box
      component="code"
      sx={{
        fontFamily: 'monospace',
        fontSize: '0.8rem',
        bgcolor: 'action.hover',
        px: 0.5,
        py: 0.25,
        borderRadius: 0.5,
      }}
    >
      {children}
    </Box>
  ),
  pre: ({ children }) => (
    <Box
      component="pre"
      sx={{
        fontFamily: 'monospace',
        fontSize: '0.8rem',
        bgcolor: 'action.hover',
        p: 1.5,
        borderRadius: 1,
        overflowX: 'auto',
        my: 1,
      }}
    >
      {children}
    </Box>
  ),
  blockquote: ({ children }) => (
    <Box
      component="blockquote"
      sx={{ borderLeft: '3px solid', borderColor: 'divider', pl: 1.5, ml: 0, my: 1, color: 'text.secondary' }}
    >
      {children}
    </Box>
  ),
  hr: () => <Divider sx={{ my: 1.5 }} />,
}

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
            <Typography variant="caption" color="text.secondary">Thinking…</Typography>
          </Box>
        )}
        {aiLoading && !aiSummary && !aiThinking && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CircularProgress size={14} />
            <Typography variant="caption" color="text.secondary">Generating summary…</Typography>
          </Box>
        )}
        {aiSummary && (
          <>
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
              {aiSummary}
            </ReactMarkdown>
            {!aiLoading && (
              <>
                <Divider sx={{ my: 1.5 }} />
                <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <FeedbackWidget context={{ type: 'ai_summary', query }} />
                </Box>
              </>
            )}
          </>
        )}
      </Paper>
    </Collapse>
  )
}
