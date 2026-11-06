export const EXAMPLE_SEARCHES = [
  'How are butterflies monitored in the UK?',
  'What are the LCM classes?',
  'What are the most popular datasets?',
]

// Mirrors the API's limit (src/serka/usage.py), which remains the enforcement point.
export const MAX_QUERY_CHARS = 500

// Large fixed max-height standing in for `none`/`auto`, which CSS cannot transition.
export const EXPANDED_MAX = '120rem'
