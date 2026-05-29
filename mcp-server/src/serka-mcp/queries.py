import re
from typing import List, Literal, Optional

from models import BoundingBox

_LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')

_ALLOWED_NODE_TYPES = {"Dataset", "Person", "Organisation", "TextChunk"}
_ALLOWED_SORT_FIELDS = {"citations", "publication_date"}


def escape_fts_query(query: str) -> str:
	return _LUCENE_SPECIAL.sub(r"\\\1", query)


def list_query(
	tx,
	type: str = "Dataset",
	limit: int = 25,
	sort_by: Literal["citations", "publication_date"] = "citations",
	order: Literal["ascending", "descending"] = "descending",
):
	if type not in _ALLOWED_NODE_TYPES:
		raise ValueError(f"Invalid node type: {type!r}")
	if sort_by not in _ALLOWED_SORT_FIELDS:
		raise ValueError(f"Invalid sort field: {sort_by!r}")
	cypher_order = "ASC" if order == "ascending" else "DESC"
	query = f"MATCH (n:{type}) RETURN apoc.map.removeKey(properties(n), 'embedding') AS dataset ORDER BY n.{sort_by} {cypher_order} LIMIT {limit}"
	return tx.run(query).data()


def dataset_cypher_query(tx, uri: str):
	return tx.run("MATCH (d:Dataset {uri: $uri}) RETURN d", uri=uri).single()


def search_query(
	tx,
	embedding: List[float],
	limit: int = 10,
	bounding_box: Optional[BoundingBox] = None,
	published_after: Optional[str] = None,
	published_before: Optional[str] = None,
	min_citations: Optional[int] = None,
):
	params: dict = {"embedding": embedding, "limit": limit}
	conditions: List[str] = []

	if bounding_box:
		bb = bounding_box.expand(20)
		conditions += [
			"'Dataset' IN labels(connected_node)",
			"connected_node.north_boundary >= $south",
			"connected_node.south_boundary <= $north",
			"connected_node.east_boundary >= $west",
			"connected_node.west_boundary <= $east",
		]
		params.update(
			{"south": bb.south, "north": bb.north, "west": bb.west, "east": bb.east}
		)
	if published_after:
		conditions.append("connected_node.publication_date >= $published_after")
		params["published_after"] = published_after
	if published_before:
		conditions.append("connected_node.publication_date <= $published_before")
		params["published_before"] = published_before
	if min_citations is not None:
		conditions.append("connected_node.citations >= $min_citations")
		params["min_citations"] = min_citations

	where = ("WHERE " + " AND ".join(conditions) + " ") if conditions else ""
	query = (
		"CALL db.index.vector.queryNodes('vec_lookup', $limit, $embedding) "
		"YIELD node AS start_node, score "
		"MATCH (start_node)-[r]-(connected_node) "
		+ where
		+ "WITH start_node, r, connected_node, score, "
		"CASE WHEN startNode(r) = start_node THEN 'outgoing' ELSE 'incoming' END as direction "
		"RETURN apoc.map.removeKeys(start_node, ['embedding']) as start_node, "
		"id(start_node) as start_node_id, "
		"labels(start_node) as start_labels, "
		"type(r) as relationship_type, "
		"direction as relationship_direction, "
		"apoc.map.removeKeys(connected_node, ['embedding']) as connected_node, "
		"id(connected_node) as connected_node_id, "
		"labels(connected_node) as connected_labels, "
		"score"
	)
	return tx.run(query, **params).data()


def fulltext_search_query(
	tx,
	search_term: str,
	limit: int = 50,
	bounding_box: Optional[BoundingBox] = None,
	published_after: Optional[str] = None,
	published_before: Optional[str] = None,
	min_citations: Optional[int] = None,
):
	params: dict = {"search_term": search_term, "limit": limit}
	conditions: List[str] = []

	if bounding_box:
		bb = bounding_box.expand(20)
		conditions += [
			"'Dataset' IN labels(connected_node)",
			"connected_node.north_boundary >= $south",
			"connected_node.south_boundary <= $north",
			"connected_node.east_boundary >= $west",
			"connected_node.west_boundary <= $east",
		]
		params.update(
			{"south": bb.south, "north": bb.north, "west": bb.west, "east": bb.east}
		)
	if published_after:
		conditions.append("connected_node.publication_date >= $published_after")
		params["published_after"] = published_after
	if published_before:
		conditions.append("connected_node.publication_date <= $published_before")
		params["published_before"] = published_before
	if min_citations is not None:
		conditions.append("connected_node.citations >= $min_citations")
		params["min_citations"] = min_citations

	where = ("WHERE " + " AND ".join(conditions) + " ") if conditions else ""
	query = (
		"CALL db.index.fulltext.queryNodes('ft_search', $search_term, {limit: $limit}) "
		"YIELD node AS start_node, score "
		"MATCH (start_node)-[r]-(connected_node) "
		+ where
		+ "WITH start_node, r, connected_node, score, "
		"CASE WHEN startNode(r) = start_node THEN 'outgoing' ELSE 'incoming' END as direction "
		"RETURN apoc.map.removeKeys(start_node, ['embedding']) as start_node, "
		"id(start_node) as start_node_id, "
		"labels(start_node) as start_labels, "
		"type(r) as relationship_type, "
		"direction as relationship_direction, "
		"apoc.map.removeKeys(connected_node, ['embedding']) as connected_node, "
		"id(connected_node) as connected_node_id, "
		"labels(connected_node) as connected_labels, "
		"score"
	)
	return tx.run(query, **params).data()
