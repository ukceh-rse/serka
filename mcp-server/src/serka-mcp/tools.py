import json
import math
import time
from typing import Annotated, Any, Literal, Optional

from app import embedder, geolocator, logger, mcp, neo4j_driver, reranker, reranking_enabled
from entities import build_search_hits, props_to_entity, rel_to_predicate, resolve_label, rrf_merge
from fastmcp.exceptions import ResourceError, ToolError
from fastmcp.resources import ResourceContent, ResourceResult
from fastmcp.tools import ToolResult
from geopy.location import Location
from mcp.types import ResourceLink, TextContent
from models import (
	Attribution,
	AttributionList,
	BaseEntity,
	BoundingBox,
	DatasetPage,
	EntityList,
	GeoCodedLocation,
	OntologyDescription,
	PageMeta,
	Relation,
	RelationList,
	RoleInfo,
	SearchMeta,
	SearchResults,
	TermInfo,
)
from ontology import (
	DEFINITIONS,
	JSONLD_CONTEXT,
	MAPPING,
	NODE_TYPES,
	PREDICATES,
	PREFIXES,
	RELATION_TYPES,
	ROLE_CLASSES,
	ROLES,
	compact_iri,
	role_class,
	role_individual,
)
from pydantic import BaseModel
from queries import (
	count_datasets_query,
	escape_fts_query,
	expand_theme_query,
	find_by_contributor_query,
	fulltext_search_query,
	get_content_query,
	get_contributors_query,
	get_entity_query,
	get_relations_query,
	list_query,
	ontology_counts_query,
	search_query,
)

_DATASET = NODE_TYPES["Dataset"]
_LD_JSON = "application/ld+json"


def _schema(model: type[BaseModel]) -> dict[str, Any]:
	return model.model_json_schema(mode="serialization", by_alias=True)


def _entity_link(entity: BaseEntity) -> ResourceLink:
	return ResourceLink(
		type="resource_link",
		uri=f"doo://entity/{entity.id}",
		name=entity.label or entity.id or "",
		description=", ".join(entity.type) or None,
		mimeType=_LD_JSON,
	)


def _result(model: BaseModel, entities: list[BaseEntity] = ()) -> ToolResult:
	"""Structured JSON-LD result, mirrored as JSON text, plus a resource link per identified entity."""
	data = model.dump() if hasattr(model, "dump") else model.model_dump(mode="json")
	links = [_entity_link(e) for e in {e.id: e for e in entities if e.id}.values()]
	return ToolResult(content=[TextContent(type="text", text=json.dumps(data)), *links], structured_content=data)


def _jsonld_resource(doc: dict[str, Any]) -> ResourceResult:
	# Wrapped explicitly: FastMCP labels a template's plain str result text/plain.
	return ResourceResult([ResourceContent(json.dumps(doc), mime_type=_LD_JSON)])


def _iri(curie: str) -> str:
	prefix, _, local = curie.partition(":")
	return PREFIXES[prefix] + local if prefix in PREFIXES else curie


def _check_role(role: Optional[str]) -> Optional[str]:
	if role is None:
		return None
	role = compact_iri(role)
	if role not in ROLE_CLASSES and role not in ROLE_CLASSES.values():
		raise ToolError(
			f"Unknown role '{role}'. Use a role individual {sorted(ROLE_CLASSES)} "
			f"or a role class {sorted(set(ROLE_CLASSES.values()))}."
		)
	return role


def _role_matches(eidc_role: Optional[str], role_filter: Optional[str]) -> bool:
	if role_filter is None:
		return True
	individual = role_individual(eidc_role)
	return role_filter in (individual, role_class(individual))


@mcp.resource("doo://context", mime_type=_LD_JSON)
def get_doo_context() -> ResourceResult:
	"""The JSON-LD @context used by every Serka result: prefixes and term mappings to DOO/ontology IRIs."""
	return _jsonld_resource({"@context": JSONLD_CONTEXT})


@mcp.resource("doo://entity/{uri*}", mime_type=_LD_JSON)
def get_entity_resource(uri: str) -> ResourceResult:
	"""Any graph node by its URI, as a JSON-LD document."""
	with neo4j_driver.session(database="neo4j") as session:
		result = session.execute_read(get_entity_query, uri=uri)
	if result is None:
		raise ResourceError(f"Entity '{uri}' not found")
	return _jsonld_resource({"@context": JSONLD_CONTEXT, **props_to_entity(result["labels"], result["props"]).dump()})


@mcp.tool(output_schema=_schema(EntityList))
def get_entity(uri: Annotated[str, "The @id (URI) of any entity."]) -> ToolResult:
	"""Fetch a single entity of any DOO type by its @id. Also available as the doo://entity/{uri} resource.

	Returns:
	    JSON-LD document with the entity as the only item in @graph.
	"""
	with neo4j_driver.session(database="neo4j") as session:
		result = session.execute_read(get_entity_query, uri=uri)
	if result is None:
		raise ToolError(f"Entity '{uri}' not found")
	entity = props_to_entity(result["labels"], result["props"])
	return _result(EntityList(graph=[entity]), [entity])


@mcp.tool()
def describe_ontology() -> OntologyDescription:
	"""Describe the ontology terms used in Serka results, with definitions and usage counts.

	Call this first to learn the entity types (search return_type), predicates (get_relations)
	and contributor roles (get_contributors / find_by_contributor role filter) available.
	"""
	with neo4j_driver.session(database="neo4j") as session:
		counts = session.execute_read(ontology_counts_query)

	def info(curie: str, count: int) -> TermInfo:
		return TermInfo(curie=curie, iri=_iri(curie), definition=DEFINITIONS.get(curie), count=count)

	label_for = {v: k for k, v in NODE_TYPES.items()}
	rel_type_for = {v: k for k, v in RELATION_TYPES.items()}
	role_counts: dict[str, int] = {}
	for eidc_role, n in counts["roles"].items():
		individual = role_individual(eidc_role)
		role_counts[individual] = role_counts.get(individual, 0) + n

	return OntologyDescription(
		doo_version=MAPPING["doo_version"],
		prefixes=PREFIXES,
		types=[info(c, counts["labels"].get(label_for[c], 0)) for c in NODE_TYPES.values()],
		predicates=[
			info(p, counts["rel_types"].get(rel_type_for[p], 0) if p in rel_type_for else counts["predicates"].get(p, 0))
			for p in PREDICATES
		],
		role_classes=[
			info(c, sum(n for r, n in role_counts.items() if role_class(r) == c))
			for c in sorted(set(ROLE_CLASSES.values()))
		],
		roles=[
			RoleInfo(
				curie=r,
				iri=_iri(r),
				role_class=role_class(r),
				eidc_roles=sorted(k for k, v in ROLES.items() if v == r),
				count=role_counts.get(r, 0),
			)
			for r in ROLE_CLASSES
		],
	)


@mcp.tool()
def geocode_location(location: str) -> GeoCodedLocation:
	"""Geocode a UK place name to geographic boundaries.

	Args:
	    location: A UK place name, city, region, or geographic feature.

	Returns:
	    GeoCodedLocation with display name and BoundingBox.
	"""
	result: Location = geolocator.geocode(location, country_codes="GB")
	if result is None or "boundingbox" not in result.raw:
		raise ToolError(f"Could not geocode location '{location}'")
	boundary: BoundingBox = BoundingBox.from_nominatim(result.raw["boundingbox"])
	return GeoCodedLocation(name=result.raw["display_name"], boundary=boundary)


@mcp.tool(output_schema=_schema(DatasetPage))
def list_datasets(
	page: int = 1,
	page_size: int = 25,
	sort_by: Literal["citations", "publication_date"] = "citations",
	order: Literal["ascending", "descending"] = "descending",
) -> ToolResult:
	"""List datasets (dcat:Dataset) in the EIDC catalogue with pagination.

	Args:
	    page: Page number (1-based, default 1).
	    page_size: Number of datasets per page (default 25).
	    sort_by: Sort field — "citations" or "publication_date".
	    order: "ascending" or "descending" (default).

	Returns:
	    JSON-LD document: datasets in @graph, pagination in meta.
	"""
	logger.info(f"Listing datasets page={page} page_size={page_size}.")
	skip = (page - 1) * page_size
	with neo4j_driver.session(database="neo4j") as session:
		total = session.execute_read(count_datasets_query)
		nodes = session.execute_read(list_query, skip=skip, limit=page_size, sort_by=sort_by, order=order)
	datasets = [props_to_entity(["Dataset"], n["dataset"]) for n in nodes]
	page_model = DatasetPage(
		graph=datasets,
		meta=PageMeta(
			total=total,
			page=page,
			page_size=page_size,
			total_pages=math.ceil(total / page_size) if page_size else 0,
		),
	)
	return _result(page_model, datasets)


@mcp.tool(output_schema=_schema(SearchResults))
def search(
	query: Annotated[str, "Search term for semantic and full-text search."],
	return_type: Annotated[
		Optional[str],
		"DOO class CURIE of the entity type to return, e.g. 'dcat:Dataset', 'foaf:Person', "
		"'skos:Concept', 'frapo:Grant'. See describe_ontology for all types. "
		"Omit to return matched nodes directly (TextChunks resolve 1 hop to their parent).",
	] = None,
	hops: Annotated[
		int,
		"Maximum relationship hops from the matched node to the return_type entity. "
		"Use hops=2 with return_type='dcat:Dataset' to surface supporting document matches "
		"(TextChunk → PART_OF → DigitalManifestation ← dcterms:references ← Dataset). Default 1.",
	] = 1,
	theme: Annotated[
		Optional[str],
		"Restrict to datasets with this theme: a skos:Concept @id or label. Expanded to every narrower "
		"concept (skos:broader hierarchy), so a general theme also matches specific keywords.",
	] = None,
	bounding_box: Annotated[
		Optional[BoundingBox],
		"Filter to datasets within this geographic area (expanded ~20%).",
	] = None,
	published_after: Annotated[Optional[str], "ISO date (YYYY-MM-DD) — exclude older datasets."] = None,
	published_before: Annotated[Optional[str], "ISO date (YYYY-MM-DD) — exclude newer datasets."] = None,
	min_citations: Annotated[Optional[int], "Exclude datasets with fewer than this many citations."] = None,
	limit: Annotated[int, "Maximum number of results to return."] = 25,
) -> ToolResult:
	"""Hybrid vector + full-text search over the DOO knowledge graph.

	Finds any indexed node that matches the query, then traverses up to `hops`
	relationships to reach an entity of `return_type`. Each hit carries a `path` of
	(predicate, entity) steps back to the node bearing the matched text.

	Returns:
	    JSON-LD document: hits in @graph, details of how the search ran in meta.
	"""
	logger.info(f'Search: "{query}" [return_type={return_type}, hops={hops}, theme={theme}, bbox={bounding_box is not None}]')
	t0 = time.perf_counter()

	target_label = None
	if return_type:
		return_type = compact_iri(return_type)
		target_label = resolve_label(return_type)
		if target_label is None:
			raise ToolError(f"Unknown return_type '{return_type}'. Valid types: {sorted(NODE_TYPES.values())}.")
	max_hops = max(0, min(hops, 5))

	filters = {
		k: v
		for k, v in {
			"theme": theme,
			"bounding_box": bounding_box.model_dump() if bounding_box else None,
			"published_after": published_after,
			"published_before": published_before,
			"min_citations": min_citations,
		}.items()
		if v is not None
	}
	warnings: list[str] = []
	dataset_only = [f for f in ("theme", "bounding_box") if f in filters]
	if dataset_only and return_type != _DATASET:
		warnings.append(f"{' and '.join(dataset_only)} only match {_DATASET}, so only datasets are returned.")
	dataset_scoped = [f for f in ("published_after", "published_before", "min_citations") if f in filters]
	if dataset_scoped and return_type not in (None, _DATASET):
		warnings.append(f"{', '.join(dataset_scoped)} only constrain {_DATASET} results; {return_type} results are unaffected.")

	theme_uris = None
	theme_expansion = None
	if theme:
		with neo4j_driver.session(database="neo4j") as session:
			theme_uris = session.execute_read(expand_theme_query, theme=theme)
		if not theme_uris:
			raise ToolError(f"Unknown theme '{theme}'. Search with return_type='skos:Concept' to find theme concepts.")
		theme_expansion = {theme: len(theme_uris)}

	embedding = embedder.run(query)["embedding"]
	logger.info(f"  embed: {(time.perf_counter() - t0) * 1000:.0f}ms")
	search_args = dict(
		limit=limit * 4,
		max_hops=max_hops,
		target_label=target_label,
		bounding_box=bounding_box,
		published_after=published_after,
		published_before=published_before,
		min_citations=min_citations,
		theme_uris=theme_uris,
	)

	with neo4j_driver.session(database="neo4j") as session:
		t1 = time.perf_counter()
		vector_nodes = session.execute_read(search_query, embedding=embedding, **search_args)
		logger.info(f"  vector: {(time.perf_counter() - t1) * 1000:.0f}ms ({len(vector_nodes)} rows)")

		t2 = time.perf_counter()
		try:
			ft_nodes = session.execute_read(fulltext_search_query, search_term=escape_fts_query(query), **search_args)
			logger.info(f"  fts: {(time.perf_counter() - t2) * 1000:.0f}ms ({len(ft_nodes)} rows)")
		except Exception as fts_err:
			logger.warning(f"FTS query failed, falling back to vector-only: {fts_err}")
			warnings.append("Full-text search failed; results are from vector search only.")
			ft_nodes = []

	results = rrf_merge([build_search_hits(vector_nodes), build_search_hits(ft_nodes)])

	reranked = reranking_enabled and len(results) > 1
	if reranked:
		t3 = time.perf_counter()
		pairs = [(query, h.entity.label or h.excerpt or h.entity.id or "") for h in results]
		ce_scores = reranker.predict(pairs, batch_size=128, show_progress_bar=False)
		for hit, score in zip(results, ce_scores):
			hit.score = float(score)
		results.sort(key=lambda h: h.score, reverse=True)
		logger.info(f"  rerank: {(time.perf_counter() - t3) * 1000:.0f}ms")

	logger.info(f"  total: {(time.perf_counter() - t0) * 1000:.0f}ms")
	hits = results[:limit]
	meta = SearchMeta(
		return_type=return_type,
		hops=max_hops,
		filters=filters,
		theme_expansion=theme_expansion,
		reranked=reranked,
		warnings=warnings,
	)
	return _result(SearchResults(graph=hits, meta=meta), [h.entity for h in hits])


@mcp.tool(output_schema=_schema(RelationList))
def get_relations(
	uri: Annotated[str, "The @id (URI) of the entity to traverse from."],
	predicate: Annotated[
		Optional[str],
		"DOO predicate or role CURIE to filter on (e.g. 'dcat:theme', 'dcterms:isPartOf', 'skos:broader', "
		"'doo:originatingGrant', 'pro:author'). See describe_ontology. Omit to return all.",
	] = None,
	direction: Annotated[
		Literal["outgoing", "incoming"],
		"'outgoing' follows edges from this entity; 'incoming' finds entities that point to it.",
	] = "outgoing",
	target_type: Annotated[
		Optional[str],
		"Filter by the other entity's DOO class CURIE (e.g. 'dcat:Dataset', 'skos:Concept').",
	] = None,
) -> ToolResult:
	"""Traverse relationships in the knowledge graph from a given entity.

	Covers every edge: dataset relations (dcterms:isPartOf, dcterms:relation), supporting documents
	(dcterms:references), citing publications (dcterms:isReferencedBy), themes (dcat:theme), concept
	hierarchy (skos:broader), funding (doo:originatingGrant, frapo:awards), affiliations (org:memberOf)
	and contributor roles (pro:author, scoro:data-curator, ...). Use direction='incoming' for the
	inverse, e.g. all datasets sharing a theme or funded by a grant.

	Returns:
	    JSON-LD document of Relation objects in @graph.
	"""
	logger.info(f"get_relations: {uri} [{direction}, predicate={predicate}, target_type={target_type}]")
	target_label = None
	if target_type:
		target_label = resolve_label(compact_iri(target_type))
		if target_label is None:
			raise ToolError(f"Unknown target_type '{target_type}'. Valid types: {sorted(NODE_TYPES.values())}.")
	predicate = compact_iri(predicate) if predicate else None

	with neo4j_driver.session(database="neo4j") as session:
		rows = session.execute_read(get_relations_query, uri=uri, direction=direction)

	relations = []
	for row in rows:
		if row["rel_type"] in ("PART_OF", "DESCRIPTION_OF", "LINEAGE_OF", "SUPPORTING_DOC_OF"):
			continue  # text chunk plumbing, not ontology relations; use get_content
		if target_label and target_label not in row["node_labels"]:
			continue
		pred = rel_to_predicate(row["rel_type"], row["rel_props"])
		if predicate and pred != predicate:
			continue
		relations.append(Relation(predicate=pred, source=uri, target=props_to_entity(row["node_labels"], row["node_props"])))

	return _result(RelationList(graph=relations), [r.target for r in relations])


@mcp.tool(output_schema=_schema(AttributionList))
def get_contributors(
	dataset_uri: Annotated[str, "The @id (URI) of the dataset."],
	role: Annotated[
		Optional[str],
		"Filter by role individual (e.g. 'pro:author', 'scoro:data-curator') or role class "
		"(e.g. 'scoro:DataRole' for any data role). See describe_ontology.",
	] = None,
) -> ToolResult:
	"""List the persons and organisations holding a role on a dataset (DOO pro:RoleInTime pattern).

	Returns:
	    JSON-LD document of pro:RoleInTime objects (agent, role, role_type) in @graph.
	"""
	logger.info(f"get_contributors: {dataset_uri} [role={role}]")
	role = _check_role(role)
	with neo4j_driver.session(database="neo4j") as session:
		rows = session.execute_read(get_contributors_query, dataset_uri=dataset_uri)

	attributions = []
	for row in rows:
		if not _role_matches(row["role"], role):
			continue
		individual = role_individual(row["role"])
		attributions.append(Attribution(
			agent=props_to_entity(row["agent_labels"], row["agent_props"]),
			role=individual,
			role_type=role_class(individual),
			relates_to=dataset_uri,
		))
	return _result(AttributionList(graph=attributions), [a.agent for a in attributions])


@mcp.tool(output_schema=_schema(EntityList))
def find_by_contributor(
	agent_uri: Annotated[str, "The @id (URI) of the person or organisation."],
	role: Annotated[
		Optional[str],
		"Filter by role individual (e.g. 'pro:author') or role class (e.g. 'pro:PublishingRole'). "
		"Omit to return datasets for all roles.",
	] = None,
) -> ToolResult:
	"""Find all datasets a given person or organisation holds a role on.

	Returns:
	    JSON-LD document of dcat:Dataset entities in @graph.
	"""
	logger.info(f"find_by_contributor: {agent_uri} [role={role}]")
	role = _check_role(role)
	with neo4j_driver.session(database="neo4j") as session:
		rows = session.execute_read(find_by_contributor_query, agent_uri=agent_uri)

	datasets = {}
	for row in rows:
		if _role_matches(row.get("role"), role):
			entity = props_to_entity(row["labels"], row["props"])
			datasets.setdefault(entity.id, entity)
	entities = list(datasets.values())
	return _result(EntityList(graph=entities), entities)


@mcp.tool()
def get_content(
	uri: Annotated[str, "The @id (URI) of a DigitalManifestation or Dataset to retrieve text from."],
) -> str:
	"""Retrieve the full text content associated with a DigitalManifestation or Dataset URI.

	Supporting documents (fabio:DigitalManifestation) and description/lineage text
	chunks are stored separately from the main entity to keep search results lightweight.
	Call this after identifying a relevant entity via search or get_relations.

	Args:
	    uri: The entity URI (@id) — typically a DigitalManifestation
	         (dcterms:references target) or a Dataset (to get its description/lineage
	         text).

	Returns:
	    Concatenated text content.
	"""
	logger.info(f"get_content: {uri}")
	with neo4j_driver.session(database="neo4j") as session:
		chunks = session.execute_read(get_content_query, uri=uri)
	if not chunks:
		raise ToolError(f"No text content found for '{uri}'")
	return "\n\n---\n\n".join(chunks)
