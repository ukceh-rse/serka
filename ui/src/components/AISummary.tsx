import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Box, Button, CircularProgress, Collapse, Divider, Link, Paper,
  Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
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
    <Box component="code" sx={{ fontFamily: 'monospace', fontSize: '0.8rem', bgcolor: 'action.hover', px: 0.5, py: 0.25, borderRadius: 0.5 }}>
      {children}
    </Box>
  ),
  pre: ({ children }) => (
    <Box component="pre" sx={{ fontFamily: 'monospace', fontSize: '0.8rem', bgcolor: 'action.hover', p: 1.5, borderRadius: 1, overflowX: 'auto', my: 1 }}>
      {children}
    </Box>
  ),
  blockquote: ({ children }) => (
    <Box component="blockquote" sx={{ borderLeft: '3px solid', borderColor: 'divider', pl: 1.5, ml: 0, my: 1, color: 'text.secondary' }}>
      {children}
    </Box>
  ),
  hr: () => <Divider sx={{ my: 1.5 }} />,
  table: ({ children }) => (
    <Box sx={{ overflowX: 'auto', my: 1.5 }}>
      <Table size="small">{children}</Table>
    </Box>
  ),
  thead: ({ children }) => <TableHead>{children}</TableHead>,
  tbody: ({ children }) => <TableBody>{children}</TableBody>,
  tr: ({ children }) => <TableRow>{children}</TableRow>,
  th: ({ children }) => <TableCell sx={{ fontWeight: 600, fontSize: '0.8rem' }}>{children}</TableCell>,
  td: ({ children }) => <TableCell sx={{ fontSize: '0.8rem' }}>{children}</TableCell>,
}

interface Props {
  query: string
}

export default function AISummary({ query }: Props) {
  const { aiSummary, aiThinking, aiLoading } = useSearchStore()
  const [expanded, setExpanded] = useState(false)

  // Collapse whenever a new summary starts generating
  useEffect(() => { if (aiLoading) setExpanded(false) }, [aiLoading])

  const visible = aiLoading || !!aiSummary

  return (
    <Collapse in={visible} unmountOnExit>
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
            <Box sx={{
              overflow: 'hidden',
              display: '-webkit-box',
              WebkitBoxOrient: 'vertical',
              WebkitLineClamp: expanded ? 'unset' : 5,
            }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                {aiSummary}
              </ReactMarkdown>
            </Box>
            <Button
              size="small"
              onClick={() => setExpanded((v) => !v)}
              endIcon={expanded
                ? <ExpandLessIcon sx={{ fontSize: '0.9rem !important' }} />
                : <ExpandMoreIcon sx={{ fontSize: '0.9rem !important' }} />}
              sx={{ mt: 0.5, fontSize: '0.7rem', p: '2px 6px', minWidth: 0, textTransform: 'none', color: 'text.secondary' }}
            >
              {expanded ? 'Show less' : 'Show more'}
            </Button>
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
