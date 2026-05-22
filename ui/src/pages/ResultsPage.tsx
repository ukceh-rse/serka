import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Box, Container, Typography } from '@mui/material'
import SearchBar from '../components/SearchBar'
import ResultCard from '../components/ResultCard'
import AISummary from '../components/AISummary'
import { useSearchStore } from '../stores/searchStore'
import { search } from '../api/search'
import { streamSummary } from '../api/chat'

export default function ResultsPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const {
    query, results, loading, error,
    setQuery, setResults, setLoading, setError,
    aiSummaryEnabled, aiSummary, aiLoading,
    toggleAiSummary, appendAiSummary, setAiThinking, setAiLoading, resetAiSummary,
  } = useSearchStore()

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

  const handleAiSummary = async () => {
    toggleAiSummary()
    if (!aiSummaryEnabled && !aiSummary && !aiLoading) {
      setAiLoading(true)
      try {
        await streamSummary(q, (event) => {
          if (event.type === 'THINKING_START') setAiThinking(true)
          if (event.type === 'THINKING_END') setAiThinking(false)
          if (event.type === 'TEXT_MESSAGE_CONTENT' && event.delta) appendAiSummary(event.delta)
          if (event.type === 'RUN_FINISHED') setAiLoading(false)
        })
      } catch {
        setAiLoading(false)
      }
    }
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 4 }}>
        <SearchBar
          onSearch={handleSearch}
          loading={loading}
          initialValue={q}
          onAiSummary={results.length > 0 ? handleAiSummary : undefined}
          aiSummaryActive={aiSummaryEnabled}
          aiSummaryLoading={aiLoading}
        />
      </Box>

      {error && (
        <Typography color="error" sx={{ mt: 2 }}>
          {error}
        </Typography>
      )}

      {!loading && results.length > 0 && (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 3, mb: 2 }}>
            {results.length} result{results.length !== 1 ? 's' : ''} for <strong>"{q}"</strong>
          </Typography>

          <AISummary query={q} />

          {results.map((r, i) => (
            <ResultCard key={r.result.item.doc_id + i} result={r} index={i} />
          ))}
        </>
      )}

      {!loading && !error && results.length === 0 && q && (
        <Typography color="text.secondary" sx={{ mt: 2 }}>
          No results found for "{q}".
        </Typography>
      )}
    </Container>
  )
}
