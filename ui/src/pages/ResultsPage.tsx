import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Box, Container, Divider, Typography } from '@mui/material'
import SearchBar from '../components/SearchBar'
import ResultCard from '../components/ResultCard'
import AISummary from '../components/AISummary'
import { useSearchStore } from '../stores/searchStore'
import { search } from '../api/search'

export default function ResultsPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const { query, results, loading, error, setQuery, setResults, setLoading, setError, resetAiSummary } =
    useSearchStore()

  useEffect(() => {
    if (!q) return
    if (q === query && results.length > 0) return
    setQuery(q)
    resetAiSummary()
    setLoading(true)
    setError(null)
    search(q)
      .then(setResults)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }, [q])

  const handleSearch = (newQ: string) => {
    navigate(`/search?q=${encodeURIComponent(newQ)}`)
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, maxWidth: 720 }}>
        <SearchBar onSearch={handleSearch} loading={loading} initialValue={q} />
      </Box>

      {error && (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}

      {!loading && results.length > 0 && (
        <>
          <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {results.length} result{results.length !== 1 ? 's' : ''} for{' '}
              <strong>"{q}"</strong>
            </Typography>
          </Box>

          <AISummary query={q} />

          <Divider sx={{ mb: 3 }} />

          {results.map((r, i) => (
            <ResultCard key={r.result.item.doc_id + i} result={r} index={i} />
          ))}
        </>
      )}

      {!loading && !error && results.length === 0 && q && (
        <Typography color="text.secondary">No results found for "{q}".</Typography>
      )}
    </Container>
  )
}
