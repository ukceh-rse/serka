import { create } from 'zustand'

export interface SearchResult {
  result: { item: { doc_id: string; content: string }; type: string }
  dataset: { uri: string; title: string }
  score: number
  description: string
}

interface SearchState {
  query: string
  results: SearchResult[]
  loading: boolean
  error: string | null
  aiSummaryEnabled: boolean
  aiSummary: string
  aiThinking: boolean
  aiLoading: boolean
  recentSearches: string[]
  setQuery: (q: string) => void
  setResults: (r: SearchResult[]) => void
  setLoading: (v: boolean) => void
  setError: (e: string | null) => void
  setAiSummaryEnabled: (v: boolean) => void
  toggleAiSummary: () => void
  appendAiSummary: (delta: string) => void
  setAiThinking: (v: boolean) => void
  setAiLoading: (v: boolean) => void
  resetAiSummary: () => void
  addRecentSearch: (q: string) => void
}

export const useSearchStore = create<SearchState>()((set) => ({
  query: '',
  results: [],
  loading: false,
  error: null,
  aiSummaryEnabled: false,
  aiSummary: '',
  aiThinking: false,
  aiLoading: false,
  recentSearches: JSON.parse(localStorage.getItem('serka_recent') ?? '[]') as string[],
  setQuery: (q) => set({ query: q }),
  setResults: (r) => set({ results: r }),
  setLoading: (v) => set({ loading: v }),
  setError: (e) => set({ error: e }),
  setAiSummaryEnabled: (v) => set({ aiSummaryEnabled: v }),
  toggleAiSummary: () => set((s) => ({ aiSummaryEnabled: !s.aiSummaryEnabled })),
  appendAiSummary: (delta) => set((s) => ({ aiSummary: s.aiSummary + delta })),
  setAiThinking: (v) => set({ aiThinking: v }),
  setAiLoading: (v) => set({ aiLoading: v }),
  resetAiSummary: () => set({ aiSummary: '', aiThinking: false, aiLoading: false }),
  addRecentSearch: (q) => set((s) => {
    const updated = [q, ...s.recentSearches.filter((r) => r !== q)].slice(0, 5)
    localStorage.setItem('serka_recent', JSON.stringify(updated))
    return { recentSearches: updated }
  }),
}))
