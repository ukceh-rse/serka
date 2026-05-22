import { useState } from 'react'
import {
  Box, Button, Card, CardContent, Chip, Collapse,
  Divider, Link, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import type { SearchResult } from '../stores/searchStore'
import FeedbackWidget from './FeedbackWidget'

export interface GroupedResult {
  dataset: { uri: string; title: string }
  chunks: SearchResult[]  // sorted desc by score
}

interface Props {
  group: GroupedResult
  index: number
  collapsedLines: number
}

const TRUNCATE_THRESHOLD = 120

export default function DatasetResultCard({ group, index, collapsedLines }: Props) {
  const [expanded, setExpanded] = useState(false)
  const { dataset, chunks } = group
  const top = chunks[0]
  const needsExpand = chunks.length > 1 || top.result.item.content.length > TRUNCATE_THRESHOLD

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>

        {/* Title */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 1 }}>
          <Typography component="h2" sx={{ fontSize: '0.875rem', fontWeight: 600, flex: 1, lineHeight: 1.4 }}>
            <Link href={dataset.uri} target="_blank" rel="noopener noreferrer" underline="hover" color="primary">
              {dataset.title || dataset.uri}
            </Link>
          </Typography>
          {chunks.length > 1 && (
            <Chip
              label={chunks.length}
              size="small"
              variant="outlined"
              sx={{ flexShrink: 0, opacity: 0.6, fontSize: '0.7rem', height: 18 }}
            />
          )}
        </Box>

        {/* Top chunk — line clamp scales with chunk count */}
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{
            fontSize: '0.78rem',
            lineHeight: 1.5,
            mb: 0.75,
            overflow: 'hidden',
            display: '-webkit-box',
            WebkitBoxOrient: 'vertical',
            WebkitLineClamp: expanded ? 'unset' : collapsedLines,
          }}
        >
          {top.result.item.content}
        </Typography>

        {/* Extra chunks — only when expanded */}
        <Collapse in={expanded} unmountOnExit>
          {chunks.slice(1).map((r, i) => (
            <Box key={r.result.item.doc_id + i}>
              <Divider sx={{ my: 1 }} />
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ fontSize: '0.78rem', lineHeight: 1.5, mb: 0.75 }}
              >
                {r.result.item.content}
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Chip label={r.result.type} size="small" variant="outlined" sx={{ opacity: 0.55, fontSize: '0.65rem', height: 18 }} />
                <Chip label={r.score.toFixed(2)} size="small" variant="outlined" sx={{ opacity: 0.55, fontSize: '0.65rem', height: 18 }} />
              </Box>
            </Box>
          ))}
        </Collapse>

        {/* Expand / collapse */}
        {needsExpand && (
          <Button
            size="small"
            onClick={() => setExpanded((v) => !v)}
            endIcon={expanded ? <ExpandLessIcon sx={{ fontSize: '0.9rem !important' }} /> : <ExpandMoreIcon sx={{ fontSize: '0.9rem !important' }} />}
            sx={{ mt: 0.5, fontSize: '0.7rem', p: '2px 6px', minWidth: 0, textTransform: 'none', color: 'text.secondary' }}
          >
            {expanded ? 'Less' : chunks.length > 1 ? `+${chunks.length - 1} more` : 'More'}
          </Button>
        )}

        {/* Footer */}
        <Divider sx={{ mt: 1, mb: 0.75 }} />
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', gap: 0.5 }}>
            <Chip label={top.result.type} size="small" variant="outlined" sx={{ opacity: 0.55, fontSize: '0.65rem', height: 18 }} />
            <Chip label={top.score.toFixed(2)} size="small" variant="outlined" sx={{ opacity: 0.55, fontSize: '0.65rem', height: 18 }} />
          </Box>
          <Box sx={{ ml: 'auto' }}>
            <FeedbackWidget context={{ type: 'result', index, dataset_uri: dataset.uri }} />
          </Box>
        </Box>

      </CardContent>
    </Card>
  )
}
