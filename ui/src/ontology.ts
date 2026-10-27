import mapping from "./doo_mapping.json";

// Copy of mcp-server/src/serka-mcp/doo_mapping.json (scripts/sync-doo-mapping.py).
const PREFIX_NS: Record<string, string> = mapping.prefixes;

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
  "pro:author": "Author",
  "scoro:data-curator": "Custodian",
  "scoro:contact-person": "Contact",
  "org:memberOf": "Affiliation",
  "dcat:theme": "Theme",
  "skos:broader": "Broader concept",
  "doo:originatingGrant": "Funded by grant",
  "frapo:awards": "Awarded",
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
