import math
import time
from typing import Annotated, List, Literal, Optional, Union

from app import embedder, geolocator, logger, mcp, neo4j_driver, reranker, reranking_enabled
from geopy.location import Location
from models import (
	Attribution,
	BoundingBox,
	Dataset,
	DatasetPage,
	Entity,
	Error,
	GeoCodedLocation,
	Relation,
	SearchHit,
)
from ontology import NODE_TYPES, JSONLD_CONTEXT, PROPERTY_TERMS, ROLE_TERMS
from queries import (
	count_datasets_query,
	dataset_cypher_query,
	escape_fts_query,
	find_by_contributor_query,
	fulltext_search_query,
	get_content_query,
	get_contributors_query,
	get_entity_query,
	get_relations_query,
	list_query,
	search_query,
)

_DOO_TO_NEO4J: dict[str, str] = {v: k for k, v in NODE_TYPES.items()}

_REL_TYPE_TO_PREDICATE: dict[str, str] = {
	"HAS_THEME": "dcat:theme",
	"AFFILIATED_WITH": "org:memberOf",
}


def _props_to_entity(labels: list[str], props: dict) -> Entity:
	semantic = [l for l in labels if l != "embedded"]
	type_uris = [NODE_TYPES.get(l, l) for l in semantic]
	label = props.get("title") or props.get("name") or props.get("label")
	clean_props = {k: v for k, v in props.items() if k not in ("uri", "embedding", "doc_id")}
	return Entity(id=props.get("uri", ""), type=type_uris, label=label, properties=clean_props)


def _rel_to_predicate(rel_type: str, rel_props: dict) -> str:
	if rel_type == "RELATION":
		return rel_props.get("predicate", "dcterms:relation")
	if rel_type == "ASSOCIATED_WITH":
		return rel_props.get("role", "pro:RoleInTime")
	return _REL_TYPE_TO_PREDICATE.get(rel_type, rel_type)


def _build_search_hits(nodes: list[dict], label_filter: set[str] | None) -> list[SearchHit]:
	hits = []
	for n in nodes:
		labels = n["start_labels"]
		if "TextChunk" in labels:
			if "Dataset" not in n.get("connected_labels", []):
				continue
			if label_filter and "Dataset" not in label_filter:
				continue
			entity = _props_to_entity(n["connected_labels"], n["connected_node"])
			matched_on = n["start_node"].get("field") or "text_content"
			excerpt = n["start_node"].get("content")
		else:
			semantic = [l for l in labels if l != "embedded"]
			if label_filter and not set(semantic).intersection(label_filter):
				continue
			entity = _props_to_entity(labels, n["start_node"])
			matched_on = "metadata"
			excerpt = None
		hits.append(SearchHit(entity=entity, score=n["score"], matched_on=matched_on, excerpt=excerpt))
	return hits


def _rrf_merge(lists: list[list[SearchHit]], k: int = 60) -> list[SearchHit]:
	scores: dict[str, float] = {}
	items: dict[str, SearchHit] = {}
	for ranked_list in lists:
		for rank, hit in enumerate(ranked_list, start=1):
			key = hit.entity.id
			scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
			if key not in items:
				items[key] = hit
	return [items[k] for k in sorted(scores, key=lambda k: scores[k], reverse=True)]


@mcp.resource("doo://context")
def get_doo_context() -> dict:
	"""Returns the DOO JSON-LD context, node types, property terms, and role terms.

	Use this resource to understand the @type values, predicate URIs, and role URIs
	returned by other tools before interpreting their output.
	"""
	return {
		"@context": JSONLD_CONTEXT,
		"nodeTypes": NODE_TYPES,
		"propertyTerms": PROPERTY_TERMS,
		"roleTerms": ROLE_TERMS,
	}


@mcp.resource("doo://entity/{uri}")
def get_entity_resource(uri: str) -> Union[Entity, Error]:
	"""Retrieve any graph node by its URI as a DOO Entity."""
	logger.info(f"Entity resource request: {uri}")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			result = session.execute_read(get_entity_query, uri=uri)
		if result is None:
			return Error(msg=f"Entity '{uri}' not found")
		return _props_to_entity(result["labels"], result["props"])
	except Exception as e:
		logger.error(f"Error fetching entity {uri}: {e}")
		return Error(msg=str(e))


@mcp.tool()
def geocode_location(location: str) -> Union[GeoCodedLocation, Error]:
	"""Geocode a UK place name to geographic boundaries.

	Args:
	    location: A UK place name, city, region, or geographic feature.

	Returns:
	    GeoCodedLocation with display name and BoundingBox, or Error.
	"""
	try:
		result: Location = geolocator.geocode(location, country_codes="GB")
		if result is None:
			return Error(msg=f"Location '{location}' not found")
		boundary: BoundingBox = BoundingBox.from_nominatim(result.raw["boundingbox"])
		return GeoCodedLocation(name=result.raw["display_name"], boundary=boundary)
	except Exception as e:
		logger.error(f"Error geocoding location {location}: {e}")
		return Error(msg=f"Error geocoding location {location}: {str(e)}")


@mcp.tool()
def list_datasets(
	page: int = 1,
	page_size: int = 25,
	sort_by: Literal["citations", "publication_date"] = "citations",
	order: Literal["ascending", "descending"] = "descending",
) -> Union[DatasetPage, Error]:
	"""List datasets in the EIDC catalogue with pagination.

	Args:
	    page: Page number (1-based, default 1).
	    page_size: Number of datasets per page (default 25).
	    sort_by: Sort field — "citations" or "publication_date".
	    order: "ascending" or "descending" (default).

	Returns:
	    DatasetPage with datasets, total count, and pagination metadata, or Error.
	"""
	logger.info(f"Listing datasets page={page} page_size={page_size}.")
	try:
		skip = (page - 1) * page_size
		with neo4j_driver.session(database="neo4j") as session:
			total = session.execute_read(count_datasets_query)
			nodes = session.execute_read(list_query, skip=skip, limit=page_size, sort_by=sort_by, order=order)
		return DatasetPage(
			datasets=[Dataset(**n["dataset"]) for n in nodes],
			total=total,
			page=page,
			page_size=page_size,
			total_pages=math.ceil(total / page_size) if page_size else 0,
		)
	except Exception as e:
		logger.error(f"Error listing datasets: {e}")
		return Error(msg=str(e))


@mcp.tool()
def search(
	query: Annotated[str, "Search term for semantic and full-text search."],
	types: Annotated[
		Optional[List[str]],
		"Filter results by DOO class URI(s), e.g. ['dcat:Dataset'], ['foaf:Person']. "
		"See doo://context for available types. Omit to return all types.",
	] = None,
	bounding_box: Annotated[
		Optional[BoundingBox],
		"Filter to datasets within this geographic area (expanded ~20%).",
	] = None,
	published_after: Annotated[Optional[str], "ISO date (YYYY-MM-DD) — exclude older datasets."] = None,
	published_before: Annotated[Optional[str], "ISO date (YYYY-MM-DD) — exclude newer datasets."] = None,
	limit: Annotated[int, "Maximum number of results to return."] = 25,
) -> Union[List[SearchHit], Error]:
	"""Hybrid vector + full-text search over the DOO knowledge graph.

	Returns Entity objects ranked by relevance. For text matches, the parent Dataset
	entity is returned rather than the raw TextChunk. Use get_relations or get_contributors
	on the returned @id values to traverse the graph further.

	Args:
	    query: Natural language search term.
	    types: Optional list of DOO class URIs to restrict result types.
	    bounding_box: Geographic filter (use geocode_location to obtain one).
	    published_after: Exclude datasets published before this date.
	    published_before: Exclude datasets published after this date.
	    limit: Max results (default 25).

	Returns:
	    List of SearchHit (entity + score + matched_on), or Error.
	"""
	logger.info(f'Search: "{query}" [types={types}, bbox={bounding_box is not None}]')
	try:
		t0 = time.perf_counter()

		label_filter = {_DOO_TO_NEO4J.get(t, t) for t in types} if types else None
		embedding = embedder.run(query)["embedding"]
		logger.info(f"  embed: {(time.perf_counter() - t0) * 1000:.0f}ms")

		with neo4j_driver.session(database="neo4j") as session:
			t1 = time.perf_counter()
			vector_nodes = session.execute_read(
				search_query,
				embedding=embedding,
				limit=limit * 4,
				bounding_box=bounding_box,
				published_after=published_after,
				published_before=published_before,
			)
			logger.info(f"  vector: {(time.perf_counter() - t1) * 1000:.0f}ms ({len(vector_nodes)} rows)")

			t2 = time.perf_counter()
			try:
				ft_nodes = session.execute_read(
					fulltext_search_query,
					search_term=escape_fts_query(query),
					limit=limit * 4,
					bounding_box=bounding_box,
					published_after=published_after,
					published_before=published_before,
				)
				logger.info(f"  fts: {(time.perf_counter() - t2) * 1000:.0f}ms ({len(ft_nodes)} rows)")
			except Exception as fts_err:
				logger.warning(f"FTS query failed, falling back to vector-only: {fts_err}")
				ft_nodes = []

		vector_hits = _build_search_hits(vector_nodes, label_filter)
		ft_hits = _build_search_hits(ft_nodes, label_filter)
		results = _rrf_merge([vector_hits, ft_hits])

		if reranking_enabled and len(results) > 1:
			t3 = time.perf_counter()
			pairs = [(query, h.entity.label or h.entity.id) for h in results]
			ce_scores = reranker.predict(pairs, batch_size=128, show_progress_bar=False)
			for hit, score in zip(results, ce_scores):
				hit.score = float(score)
			results.sort(key=lambda h: h.score, reverse=True)
			results = results[:limit]
			logger.info(f"  rerank: {(time.perf_counter() - t3) * 1000:.0f}ms")

		logger.info(f"  total: {(time.perf_counter() - t0) * 1000:.0f}ms")
		return results
	except Exception as e:
		logger.error(f'Error searching for "{query}": {e}')
		return Error(msg=str(e))


@mcp.tool()
def get_relations(
	uri: Annotated[str, "The @id (URI) of the entity to traverse from."],
	predicate: Annotated[
		Optional[str],
		"DOO predicate to filter on (e.g. 'dcat:theme', 'dcterms:isPartOf', 'scoro:AuthorshipRole'). "
		"See doo://context for available predicates. Omit to return all.",
	] = None,
	direction: Annotated[
		Literal["outgoing", "incoming"],
		"'outgoing' follows edges from this entity; 'incoming' finds entities that point to it.",
	] = "outgoing",
	target_type: Annotated[
		Optional[str],
		"Filter by target entity DOO class URI (e.g. 'dcat:Dataset', 'skos:Concept').",
	] = None,
) -> Union[List[Relation], Error]:
	"""Traverse relationships in the knowledge graph from a given entity.

	Covers all edge types: RELATION{predicate} (dcterms:isPartOf, dcterms:references,
	dcterms:isReferencedBy, ...), HAS_THEME → dcat:theme, AFFILIATED_WITH → org:memberOf,
	ASSOCIATED_WITH{role} → scoro roles. Use direction='incoming' to find e.g. all datasets
	that share a theme, or all datasets a person contributed to.

	Args:
	    uri: The entity URI (@id) to start from.
	    predicate: Optional predicate URI to filter edges.
	    direction: Traverse outgoing or incoming edges.
	    target_type: Optional DOO class URI to filter target entities.

	Returns:
	    List of Relation objects, or Error.
	"""
	logger.info(f"get_relations: {uri} [{direction}, predicate={predicate}, target_type={target_type}]")
	try:
		target_neo4j = _DOO_TO_NEO4J.get(target_type) if target_type else None
		with neo4j_driver.session(database="neo4j") as session:
			rows = session.execute_read(get_relations_query, uri=uri, direction=direction)

		relations = []
		for row in rows:
			node_labels = row["node_labels"]
			if target_neo4j and target_neo4j not in node_labels:
				continue
			pred = _rel_to_predicate(row["rel_type"], row["rel_props"])
			if predicate and pred != predicate:
				continue
			target = _props_to_entity(node_labels, row["node_props"])
			relations.append(Relation(predicate=pred, source=uri, target=target))

		return relations
	except Exception as e:
		logger.error(f"Error getting relations for {uri}: {e}")
		return Error(msg=str(e))


@mcp.tool()
def get_contributors(
	dataset_uri: Annotated[str, "The @id (URI) of the dataset."],
	role: Annotated[
		Optional[str],
		"Filter by scoro/dcterms role URI (e.g. 'scoro:AuthorshipRole', 'dcterms:publisher'). "
		"See doo://context roleTerms for available values.",
	] = None,
) -> Union[List[Attribution], Error]:
	"""List all persons and organisations associated with a dataset, with their roles.

	Args:
	    dataset_uri: The dataset URI (@id).
	    role: Optional role URI to filter (see ROLE_TERMS in doo://context).

	Returns:
	    List of Attribution (agent Entity + role URI), or Error.
	"""
	logger.info(f"get_contributors: {dataset_uri} [role={role}]")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			rows = session.execute_read(get_contributors_query, dataset_uri=dataset_uri)

		attributions = []
		for row in rows:
			if role and row["role"] != role:
				continue
			agent = _props_to_entity(row["agent_labels"], row["agent_props"])
			attributions.append(Attribution(agent=agent, role=row["role"] or ""))

		return attributions
	except Exception as e:
		logger.error(f"Error getting contributors for {dataset_uri}: {e}")
		return Error(msg=str(e))


@mcp.tool()
def find_by_contributor(
	agent_uri: Annotated[str, "The @id (URI) of the person or organisation."],
	role: Annotated[
		Optional[str],
		"Filter by scoro/dcterms role URI. Omit to return datasets for all roles.",
	] = None,
) -> Union[List[Entity], Error]:
	"""Find all datasets a given person or organisation has contributed to.

	Args:
	    agent_uri: The person/organisation URI (@id).
	    role: Optional role URI to restrict which contributions are included.

	Returns:
	    List of Dataset Entity objects, or Error.
	"""
	logger.info(f"find_by_contributor: {agent_uri} [role={role}]")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			rows = session.execute_read(find_by_contributor_query, agent_uri=agent_uri)

		entities = []
		seen = set()
		for row in rows:
			if role and row.get("role") != role:
				continue
			uri = row["props"].get("uri", "")
			if uri in seen:
				continue
			seen.add(uri)
			entities.append(_props_to_entity(row["labels"], row["props"]))

		return entities
	except Exception as e:
		logger.error(f"Error in find_by_contributor for {agent_uri}: {e}")
		return Error(msg=str(e))


@mcp.tool()
def get_content(
	uri: Annotated[str, "The @id (URI) of a Document or Dataset to retrieve text from."],
) -> Union[str, Error]:
	"""Retrieve the full text content associated with a Document or Dataset URI.

	Supporting documents (fabio:Expression) and description/lineage text chunks are
	stored separately from the main entity to keep search results lightweight.
	Call this after identifying a relevant entity via search or get_relations.

	Args:
	    uri: The entity URI (@id) — typically a Document (dcterms:references target)
	         or a Dataset (to get its description/lineage text).

	Returns:
	    Concatenated text content, or Error if not found.
	"""
	logger.info(f"get_content: {uri}")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			chunks = session.execute_read(get_content_query, uri=uri)
		if not chunks:
			return Error(msg=f"No text content found for '{uri}'")
		return "\n\n---\n\n".join(chunks)
	except Exception as e:
		logger.error(f"Error getting content for {uri}: {e}")
		return Error(msg=str(e))
