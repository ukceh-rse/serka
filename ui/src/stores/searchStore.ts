import { create } from 'zustand'

/** A JSON-LD entity from the MCP server: @id/@type plus DOO-mapped properties (title, name, temporal, ...). */
export interface Entity {
  /** Absent for unanchored text matches. */
  '@id'?: string
  /** DOO class CURIEs, e.g. ["dcat:Dataset"]. */
  '@type': string[]
  label?: string | null
  [property: string]: unknown
}

/** One hop connecting the returned entity to the node bearing the matched text. */
export interface PathStep {
  /** DOO predicate or role CURIE (e.g. "pro:author", "dcat:theme"). */
  predicate: string
  entity: Entity
}

export interface SearchHit {
  entity: Entity
  score: number
  /** Field name for text matches ("description", "lineage", "SUPPORTING_DOC"), "metadata" for node-level matches. */
  matched_on: string
  excerpt?: string | null
  /** Ordered hops FROM `entity` TO the node bearing the matched text. Empty when the entity itself matched. */
  path: PathStep[]
}

/** Return-type filter values; mirror the FastAPI ReturnType enum (omit for "Any"). */
export type ReturnType =
  | 'Dataset'
  | 'Person'
  | 'Organisation'
  | 'FundingAgency'
  | 'Grant'
  | 'Concept'
  | 'Document'
  | 'DigitalManifestation'


interface SearchState {
  query: string
  returnType: ReturnType | null
  results: SearchHit[]
  loading: boolean
  error: string | null
  aiSummaryEnabled: boolean
  aiSummary: string
  aiModel: string
  aiDate: string
  aiThinking: boolean
  aiLoading: boolean
  recentSearches: string[]
  setQuery: (q: string) => void
  setReturnType: (rt: ReturnType | null) => void
  setResults: (r: SearchHit[]) => void
  setLoading: (v: boolean) => void
  setError: (e: string | null) => void
  setAiSummaryEnabled: (v: boolean) => void
  toggleAiSummary: () => void
  appendAiSummary: (delta: string) => void
  setAiModel: (model: string) => void
  setAiDate: (date: string) => void
  setAiThinking: (v: boolean) => void
  setAiLoading: (v: boolean) => void
  resetAiSummary: () => void
  addRecentSearch: (q: string) => void
}

export const useSearchStore = create<SearchState>()((set) => ({
  query: '',
  returnType: null,
  results: [],
  loading: false,
  error: null,
  aiSummaryEnabled: false,
  aiSummary: '',
  aiModel: '',
  aiDate: '',
  aiThinking: false,
  aiLoading: false,
  recentSearches: JSON.parse(localStorage.getItem('serka_recent') ?? '[]') as string[],
  setQuery: (q) => set({ query: q }),
  setReturnType: (rt) => set({ returnType: rt }),
  setResults: (r) => set({ results: r }),
  setLoading: (v) => set({ loading: v }),
  setError: (e) => set({ error: e }),
  setAiSummaryEnabled: (v) => set({ aiSummaryEnabled: v }),
  toggleAiSummary: () => set((s) => ({ aiSummaryEnabled: !s.aiSummaryEnabled })),
  appendAiSummary: (delta) => set((s) => ({ aiSummary: s.aiSummary + delta })),
  setAiModel: (model) => set({ aiModel: model }),
  setAiDate: (date) => set({ aiDate: date }),
  setAiThinking: (v) => set({ aiThinking: v }),
  setAiLoading: (v) => set({ aiLoading: v }),
  resetAiSummary: () => set({ aiSummary: '', aiModel: '', aiDate: '', aiThinking: false, aiLoading: false }),
  addRecentSearch: (q) => set((s) => {
    const updated = [q, ...s.recentSearches.filter((r) => r !== q)].slice(0, 5)
    localStorage.setItem('serka_recent', JSON.stringify(updated))
    return { recentSearches: updated }
  }),
}))
