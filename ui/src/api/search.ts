import type { ReturnType, SearchHit } from '../stores/searchStore'

export async function search(query: string, returnType: ReturnType | null): Promise<SearchHit[]> {
  // Reach the chosen type within 2 hops so matches mediated by a dataset (e.g. an
  // author found via a dataset description) and supporting-document matches surface.
  const params = new URLSearchParams({ q: query, hops: '2' })
  if (returnType) params.set('return_type', returnType)
  const res = await fetch(`/v1/query/semantic?${params}`)
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`)
  return res.json()
}
