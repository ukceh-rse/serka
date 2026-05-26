import type { SearchResult } from '../stores/searchStore'

export async function search(query: string): Promise<SearchResult[]> {
  const res = await fetch(`/v1/query/semantic?q=${encodeURIComponent(query)}`)
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`)
  return res.json()
}
