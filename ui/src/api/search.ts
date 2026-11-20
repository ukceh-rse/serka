import type { SearchHit } from '../stores/searchStore'

export async function search(query: string, type: string | null): Promise<SearchHit[]> {
  const params = new URLSearchParams({ q: query })
  if (type) params.set('type', type)
  const res = await fetch(`/v1/query/semantic?${params}`)
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`)
  return res.json()
}
