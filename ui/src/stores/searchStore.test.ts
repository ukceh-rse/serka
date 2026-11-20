// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { groupHits, type SearchHit } from './searchStore'

const hit = (concept: string, n: number, score: number, type = 'dataset'): SearchHit => ({
  chunk_id: `${concept}#${n}`,
  text: `passage ${n} of ${concept}`,
  score,
  concept: { id: concept, type, title: concept, tags: [] },
})

describe('groupHits', () => {
  it('shows a concept once, ordered by its best hit', () => {
    const groups = groupHits([hit('datasets/a', 0, 0.9), hit('datasets/b', 0, 0.8), hit('datasets/a', 1, 0.7)])
    expect(groups.map((g) => g.concept.id)).toEqual(['datasets/a', 'datasets/b'])
    expect(groups[0].hits.map((h) => h.chunk_id)).toEqual(['datasets/a#0', 'datasets/a#1'])
  })

  it('orders groups by best score even when hits arrive out of order', () => {
    const groups = groupHits([hit('people/x', 0, 0.2, 'person'), hit('datasets/a', 3, 0.5), hit('datasets/a', 1, 0.95)])
    expect(groups.map((g) => g.concept.id)).toEqual(['datasets/a', 'people/x'])
    expect(groups[0].hits.map((h) => h.score)).toEqual([0.95, 0.5])
  })

  it('keeps a document separate from its dataset', () => {
    const groups = groupHits([hit('datasets/a', 0, 0.9), hit('datasets/a/docs/m', 0, 0.8, 'document')])
    expect(groups).toHaveLength(2)
  })

  it('returns no groups for no hits', () => {
    expect(groupHits([])).toEqual([])
  })
})
