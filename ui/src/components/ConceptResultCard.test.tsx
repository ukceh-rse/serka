// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { groupHits, type Concept, type SearchHit } from '../stores/searchStore'
import { typeMeta } from '../typeMeta'

// jsdom has no matchMedia, which the app store reads when it is created
vi.stubGlobal('matchMedia', (query: string) => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} }))
const { default: ConceptResultCard, documentDataset, plainText } = await import('./ConceptResultCard')
const { TYPE_OPTIONS } = await import('./SearchBar')

afterEach(cleanup)

const dataset: Concept = {
  id: 'datasets/abc',
  type: 'dataset',
  title: 'Pike in Windermere',
  description: 'Annual pike counts.',
  resource: 'https://catalogue.ceh.ac.uk/id/abc',
  tags: [],
  citations: 4,
  published: '2020-05-01',
}

const hit = (n: number, score: number, concept: Concept = dataset): SearchHit => ({
  chunk_id: `${concept.id}#${n}`,
  text: `Passage ${n} about [pike](/themes/pike).`,
  score,
  concept,
})

const card = (hits: SearchHit[]) => render(<ConceptResultCard group={groupHits(hits)[0]} />)

describe('ConceptResultCard', () => {
  it('shows a single hit with its type, linked title, description and passage, and no expander', () => {
    card([hit(0, 0.9)])
    expect(screen.getByRole('link', { name: 'Pike in Windermere' }).getAttribute('href')).toBe(dataset.resource)
    expect(screen.getByText('Dataset')).toBeTruthy()
    expect(screen.getByText('Annual pike counts.')).toBeTruthy()
    expect(screen.getByText('Passage 0 about pike.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: /more passage/ })).toBeNull()
  })

  it('collapses other passages behind a count, shown in score order when expanded', () => {
    card([hit(2, 0.5), hit(0, 0.9), hit(1, 0.7)])
    expect(screen.getByText('Passage 0 about pike.')).toBeTruthy()
    expect(screen.queryByText('Passage 1 about pike.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '2 more passages' }))
    const more = screen.getAllByTestId('more-passage').map((el) => el.textContent)
    expect(more).toEqual(['Passage 1 about pike.', 'Passage 2 about pike.'])
  })

  it('links a supporting document to its dataset', () => {
    const doc: Concept = { id: 'datasets/abc/docs/s1', type: 'document', title: 'methods.pdf', tags: [], resource: null }
    card([hit(0, 0.8, doc)])
    expect(screen.queryByRole('link', { name: 'methods.pdf' })).toBeNull()
    expect(screen.getByText('methods.pdf')).toBeTruthy()
    const link = screen.getByRole('link', { name: 'Supporting document of this dataset' })
    expect(link.getAttribute('href')).toBe('https://catalogue.ceh.ac.uk/id/abc')
    expect(screen.getByText('Supporting document')).toBeTruthy()
  })

  it('shows an unknown type with a generic label', () => {
    card([hit(0, 0.8, { ...dataset, id: 'maps/x', type: 'map' })])
    expect(screen.getByText('Other')).toBeTruthy()
  })
})

describe('types', () => {
  it('has a generic fallback for unknown types', () => {
    expect(typeMeta('map').label).toBe('Other')
    expect(typeMeta('person').label).toBe('People')
  })

  it('offers the OKF types in the type filter', () => {
    expect(TYPE_OPTIONS.map((o) => o.value)).toEqual([
      'Any', 'dataset', 'document', 'person', 'organisation', 'grant', 'theme', 'ontology',
    ])
  })
})

describe('helpers', () => {
  it('turns passage markdown into plain text', () => {
    expect(plainText('## Contributors\n\n- [Jane \\[PI\\]](/people/x) — [author](/ontology/roles/author)'))
      .toBe('Contributors Jane [PI] — author')
  })

  it('derives a document\'s dataset', () => {
    expect(documentDataset('datasets/abc/docs/s1')).toBe('https://catalogue.ceh.ac.uk/id/abc')
    expect(documentDataset('datasets/abc')).toBeNull()
  })
})
