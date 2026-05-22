import { Box, Card, CardContent, Chip, Divider, Link, Typography } from '@mui/material'
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
  const { dataset, chunks } = group

  return (
    <Card variant="outlined">
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 1.5 }}>
          <Typography variant="h6" component="h2" sx={{ fontSize: '1rem', fontWeight: 600, flex: 1 }}>
            <Link href={dataset.uri} target="_blank" rel="noopener noreferrer" underline="hover" color="primary">
              {dataset.title || dataset.uri}
            </Link>
          </Typography>
          {chunks.length > 1 && (
            <Chip label={`${chunks.length} results`} size="small" variant="outlined" sx={{ flexShrink: 0, opacity: 0.65 }} />
          )}
        </Box>

        {chunks.map((r, i) => (
          <Box key={r.result.item.doc_id + i}>
            {i > 0 && <Divider sx={{ my: 1.5 }} />}
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.75 }}>
              {r.result.item.content}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Chip label={r.result.type} size="small" variant="outlined" sx={{ opacity: 0.55 }} />
              <Chip label={`score ${r.score.toFixed(2)}`} size="small" variant="outlined" sx={{ opacity: 0.55 }} />
            </Box>
          </Box>
        ))}

        <Divider sx={{ mt: 1.5, mb: 1 }} />
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <FeedbackWidget
            context={{ type: 'result', index, dataset_uri: dataset.uri }}
          />
        </Box>
      </CardContent>
    </Card>
  )
}
