// Mirrors the DOO JSON-LD context (mcp-server/src/serka-mcp/ontology.py).
const PREFIX_NS: Record<string, string> = {
  dcat: "https://www.w3.org/ns/dcat#",
  dcterms: "http://purl.org/dc/terms/",
  doo: "https://digital.ceh.ac.uk/ontology/doo/",
  fabio: "http://purl.org/spar/fabio/",
  foaf: "http://xmlns.com/foaf/0.1/",
  frapo: "http://purl.org/cerif/frapo/",
  geo: "http://www.opengis.net/ont/geosparql#",
  org: "http://www.w3.org/ns/org#",
  pro: "http://purl.org/spar/pro/",
  prov: "http://www.w3.org/ns/prov#",
  scoro: "http://purl.org/spar/scoro/",
  skos: "http://www.w3.org/2004/02/skos/core#",
};

/** Resolve a CURIE (e.g. "dcat:Dataset") to its full ontology term URL, or null. */
export function curieToUrl(curie: string): string | null {
  const i = curie.indexOf(":");
  if (i < 0) return null;
  const ns = PREFIX_NS[curie.slice(0, i)];
  return ns ? ns + curie.slice(i + 1) : null;
}

/** The ontology prefix of a CURIE (e.g. "scoro:AuthorshipRole" → "scoro"), or null. */
export function curiePrefix(curie: string): string | null {
  const i = curie.indexOf(":");
  return i < 0 ? null : curie.slice(0, i);
}

// Friendly overrides for the role/predicate URIs on a SearchHit path step.
const CONNECTION_LABELS: Record<string, string> = {
  "scoro:AuthorshipRole": "Author",
  "dcterms:creator": "Author",
  "dcterms:publisher": "Publisher",
  "scoro:DataRole": "Custodian",
  "scoro:InvestigationRole": "Investigator",
  "pro:RoleInTime": "Contact",
  "dcterms:rightsHolder": "Rights holder",
  "org:memberOf": "Affiliation",
  "dcat:theme": "Theme",
};

/** Human-readable label for any connection predicate/role URI. Falls back to humanising the CURIE. */
export function connectionLabel(predicate: string): string {
  if (CONNECTION_LABELS[predicate]) return CONNECTION_LABELS[predicate];
  const local = predicate.includes(":")
    ? predicate.slice(predicate.indexOf(":") + 1)
    : predicate;
  const spaced = local
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
