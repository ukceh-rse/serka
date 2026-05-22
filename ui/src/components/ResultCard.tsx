import { Box, Card, CardContent, Chip, Link, Typography } from '@mui/material'
import type { SearchResult } from '../stores/searchStore'
import FeedbackWidget from './FeedbackWidget'

interface Props {
  result: SearchResult
  index: number
}

export default function ResultCard({ result, index }: Props) {
  const { dataset, result: chunk, score } = result

  return (
    <Card variant="outlined" sx={{ mb: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 0.5 }}>
          <Chip label={chunk.type} size="small" variant="outlined" sx={{ opacity: 0.55, flexShrink: 0, mt: 0.25 }} />
          <Typography variant="h6" component="h2" sx={{ fontSize: '1rem', fontWeight: 600 }}>
            <Link href={dataset.uri} target="_blank" rel="noopener noreferrer" underline="hover" color="primary">
              {dataset.title || dataset.uri}
            </Link>
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {chunk.item.content}
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 1 }}>
          <Chip
            label={`score ${score.toFixed(2)}`}
            size="small"
            variant="outlined"
            sx={{ opacity: 0.55 }}
          />
          <FeedbackWidget
            context={{
              type: 'result',
              index,
              doc_id: chunk.item.doc_id,
              dataset_uri: dataset.uri,
            }}
          />
        </Box>
      </CardContent>
    </Card>
  )
}
