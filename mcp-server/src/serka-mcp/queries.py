import re
from typing import List, Literal, Optional

from models import BoundingBox

_LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')

_ALLOWED_SORT_FIELDS = {"citations", "publication_date"}

_SEARCH_RETURN = (
	"RETURN "
	"apoc.map.removeKeys(properties(matched), ['embedding']) AS matched_props, "
	"labels(matched) AS matched_labels, "
	"score, "
	"apoc.map.removeKeys(properties(target), ['embedding']) AS target_props, "
	"labels(target) AS target_labels, "
	"via "
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


def dataset_cypher_query(tx, uri: str):
	return tx.run("MATCH (d:Dataset {uri: $uri}) RETURN d", uri=uri).single()


def get_entity_query(tx, uri: str):
	return tx.run(
		"MATCH (n {uri: $uri}) "
		"RETURN labels(n) AS labels, apoc.map.removeKeys(properties(n), ['embedding']) AS props",
		uri=uri,
	).single()


def get_relations_query(tx, uri: str, direction: str = "outgoing"):
	if direction == "incoming":
		query = (
			"MATCH (b {uri: $uri})<-[r]-(a) "
			"RETURN type(r) AS rel_type, properties(r) AS rel_props, "
			"labels(a) AS node_labels, apoc.map.removeKeys(properties(a), ['embedding']) AS node_props"
		)
	else:
		query = (
			"MATCH (a {uri: $uri})-[r]->(b) "
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
		"MATCH (a {uri: $uri})<-[r:ASSOCIATED_WITH]-(d:Dataset) "
		"RETURN DISTINCT r.role AS role, labels(d) AS labels, "
		"apoc.map.removeKeys(properties(d), ['embedding']) AS props",
		uri=agent_uri,
	).data()


def get_content_query(tx, uri: str) -> list[str]:
	results = tx.run(
		"MATCH (t:TextChunk)-[r]->(n {uri: $uri}) "
		"WHERE type(r) IN ['PART_OF', 'DESCRIPTION_OF', 'LINEAGE_OF', 'SUPPORTING_DOC_OF'] "
		"RETURN t.content AS content",
		uri=uri,
	).data()
	return [r["content"] for r in results if r["content"]]


def _filter_conditions(
	bounding_box: Optional[BoundingBox],
	published_after: Optional[str],
	published_before: Optional[str],
	params: dict,
	node_alias: str = "target",
) -> List[str]:
	"""Return a list of Cypher condition strings (no WHERE keyword) for bbox/date filters."""
	conditions: List[str] = []
	if bounding_box:
		bb = bounding_box.expand(20)
		conditions += [
			f"'Dataset' IN labels({node_alias})",
			f"{node_alias}.north_boundary >= $south",
			f"{node_alias}.south_boundary <= $north",
			f"{node_alias}.east_boundary >= $west",
			f"{node_alias}.west_boundary <= $east",
		]
		params.update({"south": bb.south, "north": bb.north, "west": bb.west, "east": bb.east})
	if published_after:
		conditions.append(f"{node_alias}.publication_date >= $published_after")
		params["published_after"] = published_after
	if published_before:
		conditions.append(f"{node_alias}.publication_date <= $published_before")
		params["published_before"] = published_before
	return conditions


def _via_clause() -> str:
	return (
		"[n IN nodes(path)[1..-1] | {"
		"props: apoc.map.removeKeys(properties(n), ['embedding']), "
		"labels: labels(n)"
		"}] AS via "
	)


def search_query(
	tx,
	embedding: List[float],
	limit: int = 10,
	max_hops: int = 1,
	target_label: Optional[str] = None,
	bounding_box: Optional[BoundingBox] = None,
	published_after: Optional[str] = None,
	published_before: Optional[str] = None,
):
	params: dict = {"embedding": embedding, "limit": limit}
	max_hops = max(0, min(max_hops, 5))
	extra = _filter_conditions(bounding_box, published_after, published_before, params)

	if target_label:
		params["target_label"] = target_label
		all_conditions = ["$target_label IN labels(target)"] + extra
		where = "WHERE " + " AND ".join(all_conditions) + " "
		query = (
			"CALL db.index.vector.queryNodes('vec_lookup', $limit, $embedding) "
			"YIELD node AS matched, score "
			f"MATCH path = shortestPath((matched)-[*0..{max_hops}]-(target)) "
			+ where
			+ "WITH matched, score, path, target, " + _via_clause()
			+ _SEARCH_RETURN
		)
	else:
		base = ["target IS NOT NULL"] + extra
		where = "WHERE " + " AND ".join(base) + " "
		query = (
			"CALL db.index.vector.queryNodes('vec_lookup', $limit, $embedding) "
			"YIELD node AS matched, score "
			"OPTIONAL MATCH (matched)-[]-(neighbour) "
			"WHERE NOT 'TextChunk' IN labels(neighbour) "
			"WITH matched, score, "
			"CASE WHEN 'TextChunk' IN labels(matched) THEN neighbour ELSE matched END AS target "
			+ where
			+ "WITH matched, score, target, [] AS via "
			+ _SEARCH_RETURN
		)

	return tx.run(query, **params).data()


def fulltext_search_query(
	tx,
	search_term: str,
	limit: int = 50,
	max_hops: int = 1,
	target_label: Optional[str] = None,
	bounding_box: Optional[BoundingBox] = None,
	published_after: Optional[str] = None,
	published_before: Optional[str] = None,
):
	params: dict = {"search_term": search_term, "limit": limit}
	max_hops = max(0, min(max_hops, 5))
	extra = _filter_conditions(bounding_box, published_after, published_before, params)

	if target_label:
		params["target_label"] = target_label
		all_conditions = ["$target_label IN labels(target)"] + extra
		where = "WHERE " + " AND ".join(all_conditions) + " "
		query = (
			"CALL db.index.fulltext.queryNodes('ft_search', $search_term, {limit: $limit}) "
			"YIELD node AS matched, score "
			f"MATCH path = shortestPath((matched)-[*0..{max_hops}]-(target)) "
			+ where
			+ "WITH matched, score, path, target, " + _via_clause()
			+ _SEARCH_RETURN
		)
	else:
		base = ["target IS NOT NULL"] + extra
		where = "WHERE " + " AND ".join(base) + " "
		query = (
			"CALL db.index.fulltext.queryNodes('ft_search', $search_term, {limit: $limit}) "
			"YIELD node AS matched, score "
			"OPTIONAL MATCH (matched)-[]-(neighbour) "
			"WHERE NOT 'TextChunk' IN labels(neighbour) "
			"WITH matched, score, "
			"CASE WHEN 'TextChunk' IN labels(matched) THEN neighbour ELSE matched END AS target "
			+ where
			+ "WITH matched, score, target, [] AS via "
			+ _SEARCH_RETURN
		)

	return tx.run(query, **params).data()
