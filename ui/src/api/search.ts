import type { SearchHit } from '../stores/searchStore'

export async function search(query: string): Promise<SearchHit[]> {
  const res = await fetch(`/v1/query/semantic?q=${encodeURIComponent(query)}`)
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`)
  return res.json()
}
