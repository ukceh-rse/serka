import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Box, Button, CircularProgress, Divider, IconButton, Link, Paper,
  Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { useSearchStore } from '../stores/searchStore'
import FeedbackWidget from './FeedbackWidget'
import { brand } from '../theme'

const mdComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => <Typography variant="body2" sx={{ mb: 1, '&:last-child': { mb: 0 }, textAlign: 'left' }}>{children}</Typography>,
  h1: ({ children }) => <Typography variant="h6" sx={{ mt: 1.5, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  h2: ({ children }) => <Typography variant="subtitle1" sx={{ mt: 1.5, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  h3: ({ children }) => <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  li: ({ children }) => <Typography component="li" variant="body2" sx={{ mb: 0.25, textAlign: 'left' }}>{children}</Typography>,
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
    <Box component="blockquote" sx={{ borderLeft: '3px solid', borderColor: 'primary.main', pl: 1.5, ml: 0, my: 1, color: 'text.secondary' }}>
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

// ~3 lines of body2 text (0.875rem × 1.43 line-height ≈ 1.25rem/line)
const COLLAPSED_HEIGHT = '4.5rem'
// Generous upper bound so the expand CSS transition looks smooth
const EXPANDED_MAX = '80rem'

interface Props {
  query: string
}

export default function AISummary({ query }: Props) {
  const { aiSummary, aiLoading } = useSearchStore()
  const [expanded, setExpanded] = useState(false)
  const [isOverflowing, setIsOverflowing] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  // Reset on each new load
  useEffect(() => {
    if (aiLoading) {
      setExpanded(false)
      setIsOverflowing(false)
    }
  }, [aiLoading])

  // Re-measure overflow only when content changes (streaming updates).
  // Deliberately excludes `expanded` from deps: when the user collapses,
  // the CSS max-height transition is still in progress so clientHeight is
  // still at the expanded value, causing a false negative. Since content
  // hasn't changed, the last measured value is still correct.
  // rAF defers measurement until after MUI CSS class regeneration (theme switch).
  useEffect(() => {
    const el = contentRef.current
    if (!el || expanded) return
    const raf = requestAnimationFrame(() => {
      setIsOverflowing(el.scrollHeight > el.clientHeight + 2)
    })
    return () => cancelAnimationFrame(raf)
  }, [aiSummary]) // eslint-disable-line react-hooks/exhaustive-deps

  const visible = aiLoading || !!aiSummary

  if (!visible) return null

  return (
    <Paper variant="outlined" sx={{ p: 2, mb: 3, borderLeftColor: (theme) => theme.palette.mode === 'dark' ? brand.data : 'primary.main', borderLeftWidth: 3 }}>

      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
        <AutoAwesomeIcon sx={{ fontSize: '0.9rem', color: 'primary.main', opacity: 0.85 }} />
        <Typography variant="caption" sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'primary.main', opacity: 0.85 }}>
          AI Summary
        </Typography>
        {aiLoading && <CircularProgress size={12} sx={{ ml: 0.5 }} />}
        {aiSummary && isOverflowing && (
          <IconButton size="small" onClick={() => setExpanded((v) => !v)} sx={{ ml: 'auto', p: 0.25 }}>
            {expanded ? <ExpandLessIcon sx={{ fontSize: '1rem' }} /> : <ExpandMoreIcon sx={{ fontSize: '1rem' }} />}
          </IconButton>
        )}
      </Box>

      {aiSummary && (
        <>
          {/* Content — grows to 3 lines during streaming, clipped beyond that */}
          <Box
            sx={(theme) => ({
              position: 'relative',
              ...(!expanded && isOverflowing && {
                '&::after': {
                  content: '""',
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  right: 0,
                  height: '2rem',
                  background: `linear-gradient(transparent, ${theme.palette.background.paper})`,
                  pointerEvents: 'none',
                },
              }),
            })}
          >
            <Box
              ref={contentRef}
              sx={{
                maxHeight: expanded ? EXPANDED_MAX : COLLAPSED_HEIGHT,
                overflow: 'hidden',
                transition: 'max-height 0.3s ease-in-out',
              }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                {aiSummary}
              </ReactMarkdown>
            </Box>
          </Box>

          {/* Show more / show less */}
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: '4px' }}>
            {!expanded && isOverflowing && (
              <Button size="small" color="primary" onClick={() => setExpanded(true)} sx={{ fontSize: '0.7rem', textTransform: 'none' }}>
                Show more
              </Button>
            )}
            {expanded && (
              <Button size="small" color="primary" onClick={() => setExpanded(false)} sx={{ fontSize: '0.7rem', textTransform: 'none' }}>
                Show less
              </Button>
            )}
          </Box>

          <Divider sx={{ my: 1.5 }} />
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <FeedbackWidget context={{ type: 'ai_summary', query }} />
          </Box>
        </>
      )}

    </Paper>
  )
}
