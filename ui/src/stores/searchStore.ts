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
  setQuery: (q: string) => void
  setResults: (r: SearchResult[]) => void
  setLoading: (v: boolean) => void
  setError: (e: string | null) => void
  toggleAiSummary: () => void
  appendAiSummary: (delta: string) => void
  setAiThinking: (v: boolean) => void
  setAiLoading: (v: boolean) => void
  resetAiSummary: () => void
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
  setQuery: (q) => set({ query: q }),
  setResults: (r) => set({ results: r }),
  setLoading: (v) => set({ loading: v }),
  setError: (e) => set({ error: e }),
  toggleAiSummary: () => set((s) => ({ aiSummaryEnabled: !s.aiSummaryEnabled })),
  appendAiSummary: (delta) => set((s) => ({ aiSummary: s.aiSummary + delta })),
  setAiThinking: (v) => set({ aiThinking: v }),
  setAiLoading: (v) => set({ aiLoading: v }),
  resetAiSummary: () => set({ aiSummary: '', aiThinking: false, aiLoading: false }),
}))
