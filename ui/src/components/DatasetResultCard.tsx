import { useState } from 'react'
import {
  Box, Card, CardContent, Chip, Collapse, Divider,
  IconButton, Link, Tooltip, Typography,
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
}

export default function DatasetResultCard({ group, index }: Props) {
  const [expanded, setExpanded] = useState(false)
  const { dataset, chunks } = group
  const top = chunks[0]
  const hasMultiple = chunks.length > 1

  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardContent>
        {/* Title row */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 1 }}>
          <Typography variant="h6" component="h2" sx={{ fontSize: '1rem', fontWeight: 600, flex: 1 }}>
            <Link href={dataset.uri} target="_blank" rel="noopener noreferrer" underline="hover" color="primary">
              {dataset.title || dataset.uri}
            </Link>
          </Typography>
          {hasMultiple && (
            <Chip
              label={`${chunks.length} results`}
              size="small"
              variant="outlined"
              sx={{ flexShrink: 0, opacity: 0.65 }}
            />
          )}
          {hasMultiple && (
            <Tooltip title={expanded ? 'Show less' : 'Show all results'}>
              <IconButton size="small" onClick={() => setExpanded((v) => !v)} sx={{ flexShrink: 0, mt: -0.5 }}>
                {expanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {/* Best result content — always visible */}
        <Typography variant="body2" color="text.secondary">
          {top.result.item.content}
        </Typography>

        {/* Additional results on expand */}
        {hasMultiple && (
          <Collapse in={expanded} unmountOnExit>
            {chunks.slice(1).map((r, i) => (
              <Box key={r.result.item.doc_id + i}>
                <Divider sx={{ my: 1.5 }} />
                <Typography variant="body2" color="text.secondary" sx={{ mb: 0.75 }}>
                  {r.result.item.content}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Chip label={r.result.type} size="small" variant="outlined" sx={{ opacity: 0.55 }} />
                  <Chip label={`score ${r.score.toFixed(2)}`} size="small" variant="outlined" sx={{ opacity: 0.55 }} />
                </Box>
              </Box>
            ))}
          </Collapse>
        )}

        {/* Footer */}
        <Divider sx={{ mt: 1.5, mb: 1 }} />
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip label={top.result.type} size="small" variant="outlined" sx={{ opacity: 0.55 }} />
            <Chip label={`score ${top.score.toFixed(2)}`} size="small" variant="outlined" sx={{ opacity: 0.55 }} />
          </Box>
          <FeedbackWidget
            context={{
              type: 'result',
              index,
              doc_id: top.result.item.doc_id,
              dataset_uri: dataset.uri,
            }}
          />
        </Box>
      </CardContent>
    </Card>
  )
}
