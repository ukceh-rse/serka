import React, { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Box, Button, Chip, CircularProgress, Divider, IconButton, Link, Paper,
  Table, TableBody, TableCell, TableHead, TableRow, Tooltip, Typography,
} from '@mui/material'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { useSearchStore } from '../stores/searchStore'
import FeedbackWidget from './FeedbackWidget'
import { brand } from '../theme'

// ─── Helpers ──────────────────────────────────────────────────────────────────

interface LinkItem { num: number; title: string; url: string }

/** Extract unique links from markdown text in order of first appearance. */
function extractLinks(text: string): LinkItem[] {
  const re = /\[([^\]]+)\]\(([^)\s]+)\)/g
  const seen = new Map<string, LinkItem>()
  let m: RegExpExecArray | null
  let i = 1
  while ((m = re.exec(text)) !== null) {
    if (!seen.has(m[2])) seen.set(m[2], { num: i++, title: m[1], url: m[2] })
  }
  return Array.from(seen.values())
}

// ─── Reference list ───────────────────────────────────────────────────────────

function ReferenceList({ items }: { items: LinkItem[] }) {
  if (!items.length) return null
  return (
    <Box sx={{ mt: 0.25 }}>
      {items.map((item) => (
        <Box key={item.url} id={`ref-${item.num}`} sx={{ mb: 0.75 }}>
          <Typography
            variant="caption"
            sx={{ display: 'flex', gap: 0.75, lineHeight: 1.5, color: 'text.secondary' }}
          >
            <Box component="span" sx={{ fontWeight: 700, flexShrink: 0, minWidth: '1.1rem' }}>
              {item.num}.
            </Box>
            <Box component="span">
              <Link
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                color="text.secondary"
                underline="hover"
                sx={{ fontWeight: 500 }}
              >
                {item.title}
              </Link>
              {' ↗'}
            </Box>
          </Typography>
        </Box>
      ))}
    </Box>
  )
}

// ─── Constants ────────────────────────────────────────────────────────────────

const provenanceChipSx = {
  height: 22,
  fontSize: '0.7rem',
  color: 'text.secondary',
  borderColor: 'divider',
  borderRadius: 1,
  '& .MuiChip-label': { px: 0.875 },
}


const COLLAPSED_HEIGHT = '4.5rem'
const EXPANDED_MAX = '120rem'

// Chip-like styling for inline markdown links — applied via the `a` mdComponent.
// Uses `&&` for specificity over MUI Link's default colour.
const linkChipSx = {
  '&&': {
    display: 'inline-block',
    mx: 0.25,
    px: 0.75,
    lineHeight: '16px',
    height: '18px',
    fontSize: '0.68rem',
    fontWeight: 600,
    verticalAlign: 'middle',
    borderRadius: '4px',
    border: '1px solid',
    borderColor: 'divider',
    color: 'text.secondary',
    bgcolor: 'transparent',
    textDecoration: 'none',
    cursor: 'pointer',
    transition: 'background-color 0.15s',
    '&:hover': { bgcolor: 'action.hover', color: 'text.primary', textDecoration: 'none' },
  },
}

// ─── Markdown components ──────────────────────────────────────────────────────

const mdComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
  p: ({ children }) => (
    <Typography variant="body2" sx={{ mb: 1, '&:last-child': { mb: 0 }, textAlign: 'left' }}>
      {children}
    </Typography>
  ),
  h1: ({ children }) => <Typography variant="h6" sx={{ mt: 1.5, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  h2: ({ children }) => <Typography variant="subtitle1" sx={{ mt: 1.5, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  h3: ({ children }) => <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5, fontWeight: 600 }}>{children}</Typography>,
  li: ({ children }) => (
    <Typography component="li" variant="body2" sx={{ mb: 0.25, textAlign: 'left' }}>
      {children}
    </Typography>
  ),
  a: ({ href, children }) => {
    if (!href) return <Link>{children}</Link>

    const rawText = React.Children.toArray(children)
      .map((c) => (typeof c === 'string' ? c : ''))
      .join('')
    const title = rawText || href
    const short = title.length > 22 ? title.slice(0, 22) + '…' : title

    const chip = (
      <Link href={href} target="_blank" rel="noopener noreferrer" sx={linkChipSx}>
        {short}
      </Link>
    )

    return (
      <Tooltip
        arrow
        placement="top"
        slotProps={{ tooltip: { sx: { maxWidth: 300, p: 1 } } }}
        title={
          <Box>
            <Typography sx={{ fontWeight: 700, fontSize: '0.8rem', lineHeight: 1.3, mb: 0.75 }}>
              {title}
            </Typography>
            <Link
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              sx={{ fontSize: '0.7rem', color: 'primary.light' }}
            >
              View record ↗
            </Link>
          </Box>
        }
      >
        {chip}
      </Tooltip>
    )
  },
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

// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  query: string
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function AISummary({ query }: Props) {
  const { aiSummary, aiLoading, aiModel, aiDate } = useSearchStore()
  const [expanded, setExpanded] = useState(false)
  const [isOverflowing, setIsOverflowing] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (aiLoading) {
      setExpanded(false)
      setIsOverflowing(false)
    }
  }, [aiLoading])

  useEffect(() => {
    const el = contentRef.current
    if (!el || expanded) return
    const raf = requestAnimationFrame(() => {
      setIsOverflowing(el.scrollHeight > el.clientHeight + 2)
    })
    return () => cancelAnimationFrame(raf)
  }, [aiSummary]) // eslint-disable-line react-hooks/exhaustive-deps

  // Links in order of first appearance — used for building the ref list.
  const links = useMemo(() => extractLinks(aiSummary), [aiSummary])


  const visible = aiLoading || !!aiSummary
  if (!visible) return null

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 2,
        mb: 3,
        borderLeftColor: (theme) => theme.palette.mode === 'dark' ? brand.data : 'primary.main',
        borderLeftWidth: 3,
      }}
    >
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
        <AutoAwesomeIcon sx={{ fontSize: '0.9rem', color: 'primary.main', opacity: 0.85 }} />
        <Typography
          variant="caption"
          sx={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'primary.main', opacity: 0.85 }}
        >
          AI Summary
        </Typography>
        {aiLoading && <CircularProgress size={12} sx={{ ml: 0.5 }} />}
        {aiSummary && isOverflowing && (
          <IconButton size="small" onClick={() => setExpanded((v) => !v)} sx={{ ml: 'auto', p: 0.25 }}>
            {expanded
              ? <ExpandLessIcon sx={{ fontSize: '1rem' }} />
              : <ExpandMoreIcon sx={{ fontSize: '1rem' }} />}
          </IconButton>
        )}
      </Box>

      {aiSummary && (
        <>
          {/* Prose — collapses to 3 lines */}
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

          {/* Provenance chips — visible after stream completes */}
          {!aiLoading && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1.5 }}>
              {aiModel && (
                <Chip variant="outlined" size="small" label={`Model: ${aiModel}`} sx={provenanceChipSx} />
              )}
              {aiDate && (
                <Chip variant="outlined" size="small" label={`Date: ${aiDate}`} sx={provenanceChipSx} />
              )}
            </Box>
          )}

          {/* Reference list — auto-generated from inline links */}
          {!aiLoading && links.length > 0 && (
            <>
              <Divider sx={{ mt: 1.5, mb: 1 }} />
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600, display: 'block', mb: 0.75 }}>
                Sources:
              </Typography>
              <ReferenceList items={links} />
            </>
          )}

          {/* Feedback — only after stream completes to avoid logging partial summary */}
          {!aiLoading && (
            <>
              <Divider sx={{ mt: links.length > 0 ? 1 : 1.5, mb: 1 }} />
              <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                <FeedbackWidget context={{ type: 'ai_summary', query, summary: aiSummary }} />
              </Box>
            </>
          )}
        </>
      )}
    </Paper>
  )
}
