INSTRUCTIONS: str = """Serka searches the EIDC environmental data catalogue, kept as an Open Knowledge Format
(OKF) bundle: one markdown file (concept) per dataset, supporting document, person, organisation, grant
and theme, linked to each other by bundle-relative links such as /people/0000-0002-1825-009X.

Tools:
- search: finds passages (chunks) of concept files by full-text and semantic relevance, or ranks
  concepts by citations or publication date. Each hit carries its concept's id, type, title,
  description, resource (canonical URI) and tags. Search as often as needed with different terms
  or filters.
- read: returns a whole concept file (YAML frontmatter and markdown body) by concept id. Follow the
  /... links in a passage or file with read to reach contributors, related datasets, supporting
  documents, grants and themes.
- aggregate: counts and ranks exactly over the whole catalogue, for questions such as "how many
  datasets are there?" or "which author contributed to the most datasets?": a total, or groups by
  person, organisation, grant, funder, theme, publication year or type. Never count search hits.
- geocode_location: turns a UK place name into a bounding box for search.

Relations are written in the text next to each link, with the role or predicate linked to its
ontology concept (for example "[author](/ontology/roles/author)"). read("ontology/index") lists
every concept type, contributor role and relation predicate with its meaning.
"""
