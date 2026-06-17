// Mirrors the DOO JSON-LD context (mcp-server/src/serka-mcp/ontology.py).
const PREFIX_NS: Record<string, string> = {
  dcat: 'https://www.w3.org/ns/dcat#',
  dcterms: 'http://purl.org/dc/terms/',
  doo: 'https://digital.ceh.ac.uk/ontology/doo/',
  fabio: 'http://purl.org/spar/fabio/',
  foaf: 'http://xmlns.com/foaf/0.1/',
  frapo: 'http://purl.org/cerif/frapo/',
  geo: 'http://www.opengis.net/ont/geosparql#',
  org: 'http://www.w3.org/ns/org#',
  pro: 'http://purl.org/spar/pro/',
  prov: 'http://www.w3.org/ns/prov#',
  scoro: 'http://purl.org/spar/scoro/',
  skos: 'http://www.w3.org/2004/02/skos/core#',
}

/** Resolve a CURIE (e.g. "dcat:Dataset") to its full ontology term URL, or null. */
export function curieToUrl(curie: string): string | null {
  const i = curie.indexOf(':')
  if (i < 0) return null
  const ns = PREFIX_NS[curie.slice(0, i)]
  return ns ? ns + curie.slice(i + 1) : null
}
