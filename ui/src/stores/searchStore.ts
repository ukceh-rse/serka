import { create } from 'zustand'
import { emptyRun, reduceRun, type RunEvent, type RunTrace } from '../run/runTrace'

/** The OKF concept a search hit belongs to, as the MCP `search` tool summarises it. */
export interface Concept {
  /** Bundle path without `.md`, e.g. "datasets/<eidc-id>" or "datasets/<eidc-id>/docs/<file-id>". */
  id: string
  /** OKF type: "dataset", "document", "person", "organisation", "grant", "theme", "ontology", ... */
  type: string
  title: string
  description?: string | null
  /** Canonical URI, e.g. the dataset's EIDC catalogue page. */
  resource?: string | null
  tags: string[]
  citations?: number
  /** ISO date. */
  published?: string
}

/** One matching chunk (passage) of a concept file. */
export interface SearchHit {
  chunk_id: string
  text: string
  score: number
  concept: Concept
}

/** All hits for one concept, best first. */
export interface ConceptGroup {
  concept: Concept
  hits: SearchHit[]
}

/** Buckets hits by concept ID, orders groups by their best hit's score and hits by score, highest first. */
export function groupHits(hits: SearchHit[]): ConceptGroup[] {
  const byId = new Map<string, ConceptGroup>()
  for (const hit of hits) {
    const group = byId.get(hit.concept.id) ?? { concept: hit.concept, hits: [] }
    group.hits.push(hit)
    byId.set(hit.concept.id, group)
  }
  return Array.from(byId.values())
    .map((g) => ({ ...g, hits: [...g.hits].sort((a, b) => b.score - a.score) }))
    .sort((a, b) => b.hits[0].score - a.hits[0].score)
}

interface SearchState {
  query: string
  /** OKF type filter; null for any type. */
  conceptType: string | null
  results: SearchHit[]
  loading: boolean
  error: string | null
  aiSummaryEnabled: boolean
  aiSummary: string
  /** The current summary run, built from its event stream; null before a run starts. */
  aiRun: RunTrace | null
  recentSearches: string[]
  setQuery: (q: string) => void
  setConceptType: (type: string | null) => void
  setResults: (r: SearchHit[]) => void
  setLoading: (v: boolean) => void
  setError: (e: string | null) => void
  setAiSummaryEnabled: (v: boolean) => void
  toggleAiSummary: () => void
  appendAiSummary: (delta: string) => void
  /** Starts a fresh run trace. */
  startAiRun: () => void
  applyAiEvent: (event: RunEvent) => void
  resetAiSummary: () => void
  addRecentSearch: (q: string) => void
}

export const useSearchStore = create<SearchState>()((set) => ({
  query: '',
  conceptType: null,
  results: [],
  loading: false,
  error: null,
  aiSummaryEnabled: false,
  aiSummary: '',
  aiRun: null,
  recentSearches: JSON.parse(localStorage.getItem('serka_recent') ?? '[]') as string[],
  setQuery: (q) => set({ query: q }),
  setConceptType: (type) => set({ conceptType: type }),
  setResults: (r) => set({ results: r }),
  setLoading: (v) => set({ loading: v }),
  setError: (e) => set({ error: e }),
  setAiSummaryEnabled: (v) => set({ aiSummaryEnabled: v }),
  toggleAiSummary: () => set((s) => ({ aiSummaryEnabled: !s.aiSummaryEnabled })),
  appendAiSummary: (delta) => set((s) => ({ aiSummary: s.aiSummary + delta })),
  startAiRun: () => set({ aiRun: emptyRun(Date.now()) }),
  applyAiEvent: (event) => set((s) => {
    if (!s.aiRun) return s
    const aiRun = reduceRun(s.aiRun, event, Date.now())
    // Returning the same state skips notifying subscribers (most events, e.g. text deltas, leave the trace as is).
    return aiRun === s.aiRun ? s : { aiRun }
  }),
  resetAiSummary: () => set({ aiSummary: '', aiRun: null }),
  addRecentSearch: (q) => set((s) => {
    const updated = [q, ...s.recentSearches.filter((r) => r !== q)].slice(0, 5)
    localStorage.setItem('serka_recent', JSON.stringify(updated))
    return { recentSearches: updated }
  }),
}))
