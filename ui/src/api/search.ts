import type { SearchHit } from '../stores/searchStore'

export async function search(query: string): Promise<SearchHit[]> {
  // Default to datasets reached within 2 hops so supporting-document matches surface.
  const params = new URLSearchParams({ q: query, return_type: 'Dataset', hops: '2' })
  const res = await fetch(`/v1/query/semantic?${params}`)
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`)
  return res.json()
}
