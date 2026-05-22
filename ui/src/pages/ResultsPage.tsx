import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Box, CircularProgress, Container, IconButton, Stack, Tooltip, Typography } from '@mui/material'
import ViewModuleIcon from '@mui/icons-material/ViewModule'
import ViewListIcon from '@mui/icons-material/ViewList'
import Masonry from '@mui/lab/Masonry'
import SearchBar from '../components/SearchBar'
import DatasetResultCard, { type GroupedResult } from '../components/DatasetResultCard'
import AISummary from '../components/AISummary'
import { useSearchStore } from '../stores/searchStore'
import { search } from '../api/search'
import { streamSummary } from '../api/chat'
import { EXAMPLE_SEARCHES } from '../constants'

export default function ResultsPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const q = params.get('q') ?? ''
  const {
    query, results, loading, error,
    setQuery, setResults, setLoading, setError,
    aiSummaryEnabled, aiSummary, aiLoading,
    toggleAiSummary, appendAiSummary, setAiThinking, setAiLoading, resetAiSummary,
    addRecentSearch,
  } = useSearchStore()

  const [searchFocused, setSearchFocused] = useState(false)
  useEffect(() => { setSearchFocused(false) }, [q])

  const summaryAbortRef = useRef<AbortController | null>(null)

  const runSummary = async (queryStr: string) => {
    summaryAbortRef.current?.abort()
    const controller = new AbortController()
    summaryAbortRef.current = controller
    setAiLoading(true)
    try {
      await streamSummary(queryStr, (event) => {
        if (event.type === 'THINKING_START') setAiThinking(true)
        if (event.type === 'THINKING_END') setAiThinking(false)
        if (event.type === 'TEXT_MESSAGE_CONTENT' && event.delta) appendAiSummary(event.delta)
        if (event.type === 'RUN_FINISHED') setAiLoading(false)
      }, controller.signal)
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setAiLoading(false)
    }
  }

  useEffect(() => {
    if (!q) return
    if (q === query && results.length > 0) return
    if (!EXAMPLE_SEARCHES.includes(q)) addRecentSearch(q)
    setQuery(q)
    resetAiSummary()
    setLoading(true)
    setError(null)
    search(q)
      .then(setResults)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
    // Read state directly to avoid stale closure; resetAiSummary doesn't clear the enabled flag
    if (useSearchStore.getState().aiSummaryEnabled) {
      runSummary(q)
    }
    return () => { summaryAbortRef.current?.abort() }
  }, [q])

  const groupedResults = useMemo<GroupedResult[]>(() => {
    const map = new Map<string, GroupedResult>()
    for (const r of results) {
      const key = r.dataset.uri
      if (!map.has(key)) map.set(key, { dataset: r.dataset, chunks: [] })
      map.get(key)!.chunks.push(r)
    }
    return Array.from(map.values())
      .map((g) => ({ ...g, chunks: [...g.chunks].sort((a, b) => b.score - a.score) }))
      .sort((a, b) => b.chunks[0].score - a.chunks[0].score)
  }, [results])

  const [viewMode, setViewMode] = useState<'masonry' | 'list'>('masonry')

  const handleSearch = (newQ: string) => {
    navigate(`/search?q=${encodeURIComponent(newQ)}`)
  }

  const handleExampleSearch = (newQ: string) => {
    if (!aiSummaryEnabled) toggleAiSummary()
    handleSearch(newQ)
  }

  const handleAiSummary = async () => {
    toggleAiSummary()
    if (!aiSummaryEnabled && !aiSummary && !aiLoading) {
      await runSummary(q)
    }
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {searchFocused && (
        <Box sx={{ position: 'fixed', inset: 0, zIndex: 1101, bgcolor: 'rgba(0,0,0,0.35)', backdropFilter: 'blur(4px)' }} />
      )}
      <Box sx={{ mb: 4, position: 'relative', zIndex: searchFocused ? 1102 : 'auto' }}>
        <SearchBar
          key={q}
          onSearch={handleSearch}
          initialValue={q}
          onAiSummary={!loading && results.length > 0 ? handleAiSummary : undefined}
          aiSummaryActive={aiSummaryEnabled}
          showSuggestions
          onFocusChange={setSearchFocused}
          onExampleSearch={handleExampleSearch}
        />
      </Box>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Typography color="error" sx={{ mt: 2 }}>
          {error}
        </Typography>
      )}

      {!loading && groupedResults.length > 0 && (
        <>
          <AISummary query={q} />

          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="subtitle2" color="text.secondary">
              Hybrid (semantic/full-text) search results for "<strong>{q}</strong>" ({groupedResults.length} dataset{groupedResults.length !== 1 ? 's' : ''}, {results.length} result{results.length !== 1 ? 's' : ''}):
            </Typography>
            <Box>
              <Tooltip title="Grid view">
                <IconButton size="small" onClick={() => setViewMode('masonry')} color={viewMode === 'masonry' ? 'primary' : 'default'}>
                  <ViewModuleIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title="List view">
                <IconButton size="small" onClick={() => setViewMode('list')} color={viewMode === 'list' ? 'primary' : 'default'}>
                  <ViewListIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          {viewMode === 'masonry' ? (
            <Masonry columns={{ xs: 1, sm: 2, md: 3 }} spacing={2}>
              {groupedResults.map((g, i) => (
                <DatasetResultCard
                  key={g.dataset.uri} group={g} index={i}
                  collapsedLines={Math.min(g.chunks.length * 3 + 2, 20)}
                />
              ))}
            </Masonry>
          ) : (
            <Stack spacing={2}>
              {groupedResults.map((g, i) => (
                <DatasetResultCard
                  key={g.dataset.uri} group={g} index={i}
                  collapsedLines={5}
                />
              ))}
            </Stack>
          )}
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
