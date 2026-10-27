import re
from typing import List, Literal, Optional

from models import BoundingBox

_LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')

_ALLOWED_SORT_FIELDS = {"citations", "publication_date"}

# TextChunk -> entity edges: text plumbing, not ontology relations
TEXT_REL_TYPES = ("PART_OF", "DESCRIPTION_OF", "LINEAGE_OF", "SUPPORTING_DOC_OF")

_SEARCH_RETURN = (
	"RETURN "
	"apoc.map.removeKeys(properties(matched), ['embedding']) AS matched_props, "
	"labels(matched) AS matched_labels, "
	"score, "
	"apoc.map.removeKeys(properties(target), ['embedding']) AS target_props, "
	"labels(target) AS target_labels, "
	"via, rels "
)


def escape_fts_query(query: str) -> str:
	return _LUCENE_SPECIAL.sub(r"\\\1", query)


def count_datasets_query(tx) -> int:
	return tx.run("MATCH (n:Dataset) RETURN count(n) AS total").single()["total"]


def list_query(
	tx,
	skip: int = 0,
	limit: int = 25,
	sort_by: Literal["citations", "publication_date"] = "citations",
	order: Literal["ascending", "descending"] = "descending",
):
	if sort_by not in _ALLOWED_SORT_FIELDS:
		raise ValueError(f"Invalid sort field: {sort_by!r}")
	cypher_order = "ASC" if order == "ascending" else "DESC"
	query = (
		f"MATCH (n:Dataset) "
		f"RETURN apoc.map.removeKey(properties(n), 'embedding') AS dataset "
		f"ORDER BY n.{sort_by} {cypher_order} SKIP {skip} LIMIT {limit}"
	)
	return tx.run(query).data()


def get_entity_query(tx, uri: str):
	return tx.run(
		"MATCH (n:embedded {uri: $uri}) "
		"RETURN labels(n) AS labels, apoc.map.removeKeys(properties(n), ['embedding']) AS props",
		uri=uri,
	).single()


def get_relations_query(tx, uri: str, direction: str = "outgoing"):
	if direction == "incoming":
		query = (
			"MATCH (b:embedded {uri: $uri})<-[r]-(a) "
			"RETURN type(r) AS rel_type, properties(r) AS rel_props, "
			"labels(a) AS node_labels, apoc.map.removeKeys(properties(a), ['embedding']) AS node_props"
		)
	else:
		query = (
			"MATCH (a:embedded {uri: $uri})-[r]->(b) "
			"RETURN type(r) AS rel_type, properties(r) AS rel_props, "
			"labels(b) AS node_labels, apoc.map.removeKeys(properties(b), ['embedding']) AS node_props"
		)
	return tx.run(query, uri=uri).data()


def get_contributors_query(tx, dataset_uri: str):
	return tx.run(
		"MATCH (d:Dataset {uri: $uri})-[r:ASSOCIATED_WITH]->(a) "
		"RETURN r.role AS role, labels(a) AS agent_labels, "
		"apoc.map.removeKeys(properties(a), ['embedding']) AS agent_props",
		uri=dataset_uri,
	).data()


def find_by_contributor_query(tx, agent_uri: str):
	return tx.run(
		"MATCH (a:embedded {uri: $uri})<-[r:ASSOCIATED_WITH]-(d:Dataset) "
		"RETURN DISTINCT r.role AS role, labels(d) AS labels, "
		"apoc.map.removeKeys(properties(d), ['embedding']) AS props",
		uri=agent_uri,
	).data()


def get_content_query(tx, uri: str) -> list[str]:
	results = tx.run(
		"MATCH (t:TextChunk)-[r]->(n:embedded {uri: $uri}) "
		"WHERE type(r) IN $text_rels "
		"RETURN t.content AS content "
		"UNION "
		"MATCH (d:Dataset {uri: $uri})-[:RELATION]->(doc:DigitalManifestation)<-[:PART_OF]-(t:TextChunk) "
		"RETURN t.content AS content",
		uri=uri,
		text_rels=list(TEXT_REL_TYPES),
	).data()
	return [r["content"] for r in results if r["content"]]


def expand_theme_query(tx, theme: str) -> list[str]:
	"""URIs of the theme Concept (matched by URI or label) and every narrower Concept below it."""
	records = tx.run(
		"MATCH (root:Concept) WHERE root.uri = $theme OR toLower(root.label) = toLower($theme) "
		"MATCH (c:Concept)-[:BROADER*0..10]->(root) "
		"RETURN DISTINCT c.uri AS uri",
		theme=theme,
	).data()
	return [r["uri"] for r in records]


def ontology_counts_query(tx) -> dict:
	"""Usage counts for node labels, relationship types, RELATION predicates and contributor roles."""
	labels = tx.run("MATCH (n) UNWIND labels(n) AS l RETURN l AS key, count(*) AS n").data()
	rel_types = tx.run("MATCH ()-[r]->() RETURN type(r) AS key, count(*) AS n").data()
	predicates = tx.run("MATCH ()-[r:RELATION]->() RETURN r.predicate AS key, count(*) AS n").data()
	roles = tx.run("MATCH ()-[r:ASSOCIATED_WITH]->() RETURN r.role AS key, count(*) AS n").data()
	as_dict = lambda rows: {r["key"]: r["n"] for r in rows}
	return {
		"labels": as_dict(labels),
		"rel_types": as_dict(rel_types),
		"predicates": as_dict(predicates),
		"roles": as_dict(roles),
	}


def _filter_conditions(
	bounding_box: Optional[BoundingBox],
	published_after: Optional[str],
	published_before: Optional[str],
	min_citations: Optional[int],
	params: dict,
	theme_uris: Optional[List[str]] = None,
) -> List[str]:
	"""Return a list of Cypher condition strings (no WHERE keyword) for bbox/date/citation/theme filters."""
	conditions: List[str] = []
	if theme_uris is not None:
		conditions += [
			"'Dataset' IN labels(target)",
			"EXISTS { MATCH (target)-[:HAS_THEME]->(c:Concept) WHERE c.uri IN $theme_uris }",
		]
		params["theme_uris"] = theme_uris
	if bounding_box:
		bb = bounding_box.expand(20)
		conditions += [
			"'Dataset' IN labels(target)",
			"target.north_boundary >= $south",
			"target.south_boundary <= $north",
			"target.east_boundary >= $west",
			"target.west_boundary <= $east",
		]
		params.update({"south": bb.south, "north": bb.north, "west": bb.west, "east": bb.east})
	# Date/citation filters only apply to datasets; they must not drop other entity types.
	if published_after:
		conditions.append(
			"(NOT 'Dataset' IN labels(target) OR target.publication_date >= $published_after)"
		)
		params["published_after"] = published_after
	if published_before:
		conditions.append(
			"(NOT 'Dataset' IN labels(target) OR target.publication_date <= $published_before)"
		)
		params["published_before"] = published_before
	if min_citations is not None:
		conditions.append(
			"(NOT 'Dataset' IN labels(target) OR target.citations >= $min_citations)"
		)
		params["min_citations"] = min_citations
	return conditions


_VIA = (
	"[n IN nodes(path)[1..-1] | {"
	"props: apoc.map.removeKeys(properties(n), ['embedding']), "
	"labels: labels(n)"
	"}] AS via, "
	"[r IN relationships(path) | {type: type(r), props: properties(r)}] AS rels "
)


def _build_search_cypher(index_call: str, max_hops: int, target_label: Optional[str], extra: List[str]) -> str:
	"""Build the search Cypher shared by vector and full-text search.

	`index_call` is the leading `CALL db.index... YIELD node AS matched, score` clause.
	With a target label we walk the shortest path to a node carrying that label; otherwise
	we resolve a matched TextChunk to its non-TextChunk neighbour and return that directly.
	"""
	if target_label:
		# target_label is a whitelisted Neo4j label (resolve_label), safe to interpolate
		where = "WHERE " + " AND ".join(extra) + " " if extra else ""
		return (
			index_call
			+ f"MATCH path = shortestPath((matched)-[*0..{max_hops}]-(target:{target_label})) "
			+ where
			+ "WITH matched, score, path, target, " + _VIA
			+ _SEARCH_RETURN
		)
	where = "WHERE " + " AND ".join(["target IS NOT NULL"] + extra) + " "
	return (
		index_call
		+ "OPTIONAL MATCH (matched)-[]-(neighbour) "
		# Only chunks resolve to a neighbour; other matches keep one row (else RRF counts them per edge).
		"WHERE 'TextChunk' IN labels(matched) AND NOT 'TextChunk' IN labels(neighbour) "
		"WITH matched, score, "
		"CASE WHEN 'TextChunk' IN labels(matched) AND neighbour IS NOT NULL THEN neighbour ELSE matched END AS target "
		+ where
		+ "WITH matched, score, target, [] AS via, [] AS rels "
		+ _SEARCH_RETURN
	)


def _run_search(
	tx,
	index_call: str,
	params: dict,
	max_hops: int = 1,
	target_label: Optional[str] = None,
	bounding_box: Optional[BoundingBox] = None,
	published_after: Optional[str] = None,
	published_before: Optional[str] = None,
	min_citations: Optional[int] = None,
	theme_uris: Optional[List[str]] = None,
):
	extra = _filter_conditions(
		bounding_box, published_after, published_before, min_citations, params, theme_uris=theme_uris
	)
	return tx.run(_build_search_cypher(index_call, max_hops, target_label, extra), **params).data()


def search_query(tx, embedding: List[float], limit: int = 10, **filters):
	index_call = (
		"CALL db.index.vector.queryNodes('vec_lookup', $limit, $embedding) "
		"YIELD node AS matched, score "
	)
	return _run_search(tx, index_call, {"embedding": embedding, "limit": limit}, **filters)


def fulltext_search_query(tx, search_term: str, limit: int = 50, **filters):
	index_call = (
		"CALL db.index.fulltext.queryNodes('ft_search', $search_term, {limit: $limit}) "
		"YIELD node AS matched, score "
	)
	return _run_search(tx, index_call, {"search_term": search_term, "limit": limit}, **filters)
