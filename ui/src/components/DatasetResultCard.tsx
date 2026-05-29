import { useState } from 'react'
import {
  Box, Card, CardContent, Chip, Collapse,
  Divider, IconButton, Link, Typography,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { useSearchStore } from '../stores/searchStore'
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
  const { query } = useSearchStore()
  const [expanded, setExpanded] = useState(false)
  const { dataset, chunks } = group
  const top = chunks[0]
  const needsExpand = chunks.length > 1 || top.result.item.content.length > TRUNCATE_THRESHOLD

  return (
    <Card variant="outlined">
      <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>

        {/* Title */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.5, mb: 1 }}>
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
              sx={{ flexShrink: 0, opacity: 0.6, fontSize: '0.7rem', height: 18, alignSelf: 'center' }}
            />
          )}
          {needsExpand && (
            <IconButton size="small" onClick={() => setExpanded((v) => !v)} sx={{ p: 0.25, flexShrink: 0 }}>
              {expanded
                ? <ExpandLessIcon sx={{ fontSize: '1rem' }} />
                : <ExpandMoreIcon sx={{ fontSize: '1rem' }} />}
            </IconButton>
          )}
        </Box>

        {/* Top chunk + extra chunks — animated collapse */}
        <Collapse in={expanded} collapsedSize={`${collapsedLines * 1.17}rem`}>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ fontSize: '0.78rem', lineHeight: 1.5, mb: 0.75, textAlign: 'left' }}
          >
            {top.result.item.content}
          </Typography>

          {chunks.slice(1).map((r, i) => (
            <Box key={r.result.item.doc_id + i}>
              <Divider sx={{ my: 1 }} />
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ fontSize: '0.78rem', lineHeight: 1.5, mb: 0.75, textAlign: 'left' }}
              >
                {r.result.item.content}
              </Typography>
            </Box>
          ))}
        </Collapse>

        {/* Footer */}
        <Divider sx={{ mt: 1, mb: 0.75 }} />
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Box sx={{ ml: 'auto' }}>
            <FeedbackWidget context={{ type: 'result', index, dataset_uri: dataset.uri, query }} />
          </Box>
        </Box>

      </CardContent>
    </Card>
  )
}
