import time
from typing import Annotated, List, Literal, Optional, Union

from app import embedder, geolocator, logger, mcp, neo4j_driver, reranker, reranking_enabled
from geopy.location import Location
from models import (
	BoundingBox,
	Dataset,
	Error,
	GeoCodedLocation,
	Organisation,
	Person,
	ResultItem,
	SearchResult,
	SupportingDocument,
	TextChunk,
)
from queries import dataset_cypher_query, escape_fts_query, fulltext_search_query, list_query, search_query

_RESULT_TYPE_LABEL: dict[str, str] = {
	"dataset": "TextChunk",
	"person": "Person",
	"organisation": "Organisation",
}


def _result_key(sr: SearchResult) -> str:
	if sr.result.type == "TextChunk":
		return f"TextChunk::{hash(sr.result.item.content)}"
	return f"{sr.result.type}::{sr.result.item.uri}"


def _rrf_merge(lists: list[list[SearchResult]], k: int = 60) -> list[SearchResult]:
	scores: dict[str, float] = {}
	items: dict[str, SearchResult] = {}
	for ranked_list in lists:
		for rank, sr in enumerate(ranked_list, start=1):
			key = _result_key(sr)
			scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
			if key not in items:
				items[key] = sr
	return [items[k] for k in sorted(scores, key=lambda k: scores[k], reverse=True)]


def _build_search_results(
	nodes: list[dict], label_filter: str | None
) -> list[SearchResult]:
	results: list[SearchResult] = []
	for n in nodes:
		labels = n["start_labels"]
		if label_filter and label_filter not in labels:
			continue
		if "TextChunk" in labels:
			results.append(
				SearchResult(
					result=ResultItem(item=TextChunk(**n["start_node"]), type="TextChunk"),
					dataset=Dataset(**n["connected_node"]),
					score=n["score"],
					description=n["relationship_type"],
				)
			)
		elif "Person" in labels and "Dataset" in n["connected_labels"]:
			results.append(
				SearchResult(
					result=ResultItem(item=Person(**n["start_node"]), type="Person"),
					dataset=Dataset(**n["connected_node"]),
					score=n["score"],
					description=n["relationship_type"],
				)
			)
		elif "Organisation" in labels and "Dataset" in n["connected_labels"]:
			results.append(
				SearchResult(
					result=ResultItem(
						item=Organisation(**n["start_node"]), type="Organisation"
					),
					dataset=Dataset(**n["connected_node"]),
					score=n["score"],
					description=n["relationship_type"],
				)
			)
	return results


@mcp.resource("dataset://{uri}")
def get_dataset(uri: str) -> Union[Dataset, Error]:
	logger.info(f"Retrieving dataset {uri}")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			result = session.execute_read(dataset_cypher_query, uri=uri)
		if result is None:
			return Error(msg=f"Dataset '{uri}' not found")
		return Dataset(**result["d"])
	except Exception as e:
		logger.error(f"Error retrieving dataset {uri}: {str(e)}")
		return Error(msg=f"Error retrieving dataset {uri}: {str(e)}")


@mcp.tool()
def geocode_location(location: str) -> Union[GeoCodedLocation, Error]:
	"""Geocode a location name to get its geographic boundaries within the UK.

	This function uses the Nominatim geocoding service to convert a place name
	into geographic coordinates and bounding box information. The search is
	biased towards UK locations using the country code "GB".

	Args:
	    location (str): The location name to geocode. Can be a city, town,
	        village, region, or other geographic feature. Examples: "London",
	        "Lake District", "Cambridge", "M25 motorway".

	Returns:
	    Union[GeoCodedLocation, Error]:
	        - GeoCodedLocation: Contains the full display name and bounding box
	          coordinates (south, north, west, east boundaries in decimal degrees)
	        - Error: Returned if the location cannot be found, has no bounding box
	          data, or if there's a network/service error
	"""
	try:
		result: Location = geolocator.geocode(location, country_codes="GB")
		if result is None:
			return Error(msg=f"Location '{location}' not found")
		boundary: BoundingBox = BoundingBox.from_nominatim(result.raw["boundingbox"])
		return GeoCodedLocation(name=result.raw["display_name"], boundary=boundary)
	except Exception as e:
		logger.error(f"Error geocoding location {location}: {str(e)}")
		return Error(msg=f"Error geocoding location {location}: {str(e)}")


@mcp.tool()
def list_datasets(
	limit: int = 25,
	sort_by: Literal["citations", "publication_date"] = "citations",
	order: Literal["ascending", "descending"] = "descending",
) -> Union[List[Dataset], Error]:
	"""Lists the datasets in the EIDC and sorts them.

	Args:
	    limit: List up to n datasets, n defaults to 25. Increase to return more.
	    sort_by (Literal["citations", "publication_date"]): The field to sort the list on.
	        Must be either "citations" or "publication_date".
	    order (Literal["ascending", "descending"]): Whether the sorting order is "ascending" or "descending".
	        Default is "descending"

	Returns:
	    Union[List[Dataset], Error]: A list of datasets sorted appropriately or an error.
	"""
	logger.info("Listing datasets in Serka knowledge graph.")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			nodes = session.execute_read(
				list_query, limit=limit, sort_by=sort_by, order=order
			)
			return [Dataset(**n["dataset"]) for n in nodes]
	except Exception as e:
		logger.error(f"Error listing datasets in Serka knowledge graph: {str(e)}")
		return Error(msg=f"Error listing datasets in Serka knowledge graph: {str(e)}")


@mcp.tool()
def search(
	search_term: Annotated[str, "A term to use to search the EIDC catalogue."],
	result_type: Annotated[
		Optional[Literal["dataset", "person", "organisation"]],
		"Restrict results to a specific kind of match. 'dataset' returns text chunks from dataset documentation. "
		"'person' returns matching authors/contributors — use this to find a person's URI before calling find_datasets_by_author. "
		"'organisation' returns matching organisations. Omit to return all types.",
	] = None,
	bounding_box: Annotated[
		Optional[BoundingBox],
		"A bounding box representing the geographic boundaries to filter the search on. This bounding box will be expanded by ~20% to ensure capturing of data.",
	] = None,
	published_after: Annotated[
		Optional[str],
		"ISO date string (YYYY-MM-DD). Only return datasets published on or after this date.",
	] = None,
	published_before: Annotated[
		Optional[str],
		"ISO date string (YYYY-MM-DD). Only return datasets published on or before this date.",
	] = None,
	min_citations: Annotated[
		Optional[int], "Minimum number of citations a dataset must have to be included."
	] = None,
	result_limit: Annotated[int, "How many result to return."] = 25,
) -> Union[List[SearchResult], Error]:
	"""Performs a semantic search on the EIDC catalogue using the given search term.

	The search matches against embedded text in the knowledge graph and returns the most
	semantically similar results along with their connected dataset. Use result_type to target
	a specific kind of entity — in particular, set result_type='person' when you need to
	identify an author by name so you can obtain their URI for use with find_datasets_by_author.

	Args:
	    search_term (str): The search term to use for the semantic search.
	    result_type (Optional[Literal]): Restrict results to 'dataset', 'person', or 'organisation'.
	        Defaults to None (all types returned).
	    bounding_box (Optional[BoundingBox]): Geographic boundaries to filter search results.
	    published_after (Optional[str]): Exclude datasets published before this ISO date.
	    published_before (Optional[str]): Exclude datasets published after this ISO date.
	    min_citations (Optional[int]): Exclude datasets with fewer than this many citations.

	Returns:
	    Union[List[SearchResult], Error]: A list of search results ranked by semantic similarity, or an Error.
	"""
	logger.info(
		f'Search: "{search_term}" [type={result_type}, bounding_box={bounding_box}, '
		f"after={published_after}, before={published_before}, min_citations={min_citations}]"
	)
	try:
		t0 = time.perf_counter()

		label_filter = _RESULT_TYPE_LABEL.get(result_type) if result_type else None
		embedding = embedder.run(search_term)["embedding"]
		logger.info(f"  embed:    {(time.perf_counter() - t0) * 1000:.0f}ms")

		with neo4j_driver.session(database="neo4j") as session:
			t1 = time.perf_counter()
			vector_nodes = session.execute_read(
				search_query,
				embedding=embedding,
				limit=result_limit * 4,
				bounding_box=bounding_box,
				published_after=published_after,
				published_before=published_before,
				min_citations=min_citations,
			)
			logger.info(f"  vector:   {(time.perf_counter() - t1) * 1000:.0f}ms ({len(vector_nodes)} rows)")

			t2 = time.perf_counter()
			try:
				ft_nodes = session.execute_read(
					fulltext_search_query,
					search_term=escape_fts_query(search_term),
					limit=result_limit * 4,
					bounding_box=bounding_box,
					published_after=published_after,
					published_before=published_before,
					min_citations=min_citations,
				)
				logger.info(f"  fts:      {(time.perf_counter() - t2) * 1000:.0f}ms ({len(ft_nodes)} rows)")
			except Exception as fts_err:
				logger.warning(f"FTS query failed, falling back to vector-only: {fts_err}")
				ft_nodes = []

			vector_results = _build_search_results(vector_nodes, label_filter)
			ft_results = _build_search_results(ft_nodes, label_filter)
			search_results = _rrf_merge([vector_results, ft_results])

		if reranking_enabled and len(search_results) > 1:
			t3 = time.perf_counter()
			pairs = [
				(
					search_term,
					sr.result.item.content
					if sr.result.type == "TextChunk"
					else f"{sr.result.item.name} {sr.dataset.title}",
				)
				for sr in search_results
			]
			ce_scores = reranker.predict(pairs, batch_size=128, show_progress_bar=False)
			for sr, score in zip(search_results, ce_scores):
				sr.score = float(score)
			search_results.sort(key=lambda sr: sr.score, reverse=True)
			search_results = search_results[:result_limit]
			logger.info(f"  rerank:   {(time.perf_counter() - t3) * 1000:.0f}ms ({len(pairs)} pairs → {len(search_results)} results)")

		logger.info(f"  total:    {(time.perf_counter() - t0) * 1000:.0f}ms")
		return search_results
	except Exception as e:
		logger.error(f'Error performing semantic search for "{search_term}": {str(e)}')
		return Error(
			msg=f'Error performing semantic search for "{search_term}": {str(e)}'
		)


@mcp.tool()
def get_dataset_documents(uri: str) -> Union[List[SupportingDocument], Error]:
	"""Retrieves the full text content of all supporting documents attached to a dataset.

	Use this after identifying a dataset of interest (e.g. from search or list_datasets) to
	read the underlying documentation — field methods, data collection protocols, metadata
	descriptions, or other supporting material stored as text chunks in the knowledge graph.
	Each returned SupportingDocument has a filename identifying the source document and a
	content field containing its text. Call this when you need to answer detailed questions
	about how a dataset was collected, what it covers, or what its limitations are.

	Args:
	    uri (str): The URI of the dataset (obtained from a Dataset object's uri field).

	Returns:
	    Union[List[SupportingDocument], Error]: List of supporting documents, or an Error if
	        the dataset URI is not found or the query fails. An empty list means the dataset
	        exists but has no attached text chunks.
	"""
	logger.info(f"Fetching documents for dataset {uri}")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			results = session.execute_read(
				lambda tx: tx.run(
					"MATCH (d:Dataset {uri: $uri})-[r]-(t:TextChunk) "
					"RETURN coalesce(t.filename, type(r)) AS filename, t.content AS content",
					uri=uri,
				).data()
			)
			return [
				SupportingDocument(filename=r["filename"], content=r["content"])
				for r in results
			]
	except Exception as e:
		logger.error(f"Error fetching documents for {uri}: {str(e)}")
		return Error(msg=f"Error fetching documents for {uri}: {str(e)}")


@mcp.tool()
def find_datasets_by_author(orcid_uri: str) -> Union[List[Dataset], Error]:
	"""Find all datasets in the EIDC catalogue contributed to by a specific person, identified by their ORCID URI.

	Requires an exact ORCID URI to unambiguously identify a person — name-based lookup is
	intentionally not supported since names may be shared across multiple individuals. To find
	a person's URI first, use search with result_type='person' and their name as the search
	term, then extract the uri field from the returned Person result before calling this tool.
	Results are deduplicated — a dataset appears once even if the person has multiple roles on it.

	Args:
	    orcid_uri (str): The person's full ORCID URI (e.g. "https://orcid.org/0000-0001-2345-6789").
	        Obtain this from a Person result returned by search.

	Returns:
	    Union[List[Dataset], Error]: All datasets linked to the person, or an Error if the
	        query fails. An empty list means no datasets are linked to that URI.
	"""
	logger.info(f"Finding datasets by author URI: {orcid_uri}")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			results = session.execute_read(
				lambda tx: tx.run(
					"MATCH (p:Person {uri: $uri})-[]-(d:Dataset) "
					"RETURN DISTINCT apoc.map.removeKey(properties(d), 'embedding') AS dataset",
					uri=orcid_uri,
				).data()
			)
			return [Dataset(**r["dataset"]) for r in results]
	except Exception as e:
		logger.error(f"Error finding datasets by author URI '{orcid_uri}': {str(e)}")
		return Error(
			msg=f"Error finding datasets by author URI '{orcid_uri}': {str(e)}"
		)


@mcp.tool()
def find_related_datasets(uri: str) -> Union[List[Dataset], Error]:
	"""Find datasets that are related to a given dataset through shared graph connections.

	Uses a two-hop traversal of the knowledge graph, so it surfaces datasets that share
	authors, organisations, keywords, or any other intermediate node with the source dataset.
	Use this for discovery — e.g. after finding a relevant dataset via search, call this to
	broaden the results to thematically or institutionally connected work. Results are
	deduplicated and exclude the source dataset itself.

	Args:
	    uri (str): The URI of the source dataset (obtained from a Dataset object's uri field).

	Returns:
	    Union[List[Dataset], Error]: Datasets reachable within two hops of the source, or an
	        Error if the query fails. An empty list means the dataset has no graph neighbours
	        that are also connected to another dataset.
	"""
	logger.info(f"Finding datasets related to {uri}")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			results = session.execute_read(
				lambda tx: tx.run(
					"MATCH (d:Dataset {uri: $uri})-[]-(mid)-[]-(related:Dataset) "
					"WHERE related.uri <> $uri "
					"RETURN DISTINCT apoc.map.removeKey(properties(related), 'embedding') AS dataset",
					uri=uri,
				).data()
			)
			return [Dataset(**r["dataset"]) for r in results]
	except Exception as e:
		logger.error(f"Error finding related datasets for {uri}: {str(e)}")
		return Error(msg=f"Error finding related datasets for {uri}: {str(e)}")


@mcp.tool()
def get_graph_schema() -> Union[dict, Error]:
	"""Returns the live schema of the knowledge graph to support query planning and capability discovery.

	Call this when you are unsure what node types, relationship types, or properties exist in
	the graph — for example, before deciding which tool to use or whether a particular filter
	is meaningful. The returned dict has three keys: 'node_labels' (list of node type names
	such as Dataset, Person, TextChunk), 'relationship_types' (list of edge type names between
	nodes), and 'property_keys' (list of all property names used across the graph). This
	reflects the current state of the database, so it will include any new node types or
	relationships added since the server was deployed.

	Returns:
	    Union[dict, Error]: Schema dict with keys 'node_labels', 'relationship_types', and
	        'property_keys', or an Error if the schema query fails.
	"""
	logger.info("Fetching graph schema")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			labels = session.execute_read(
				lambda tx: [
					r["label"] for r in tx.run("CALL db.labels() YIELD label").data()
				]
			)
			rel_types = session.execute_read(
				lambda tx: [
					r["relationshipType"]
					for r in tx.run(
						"CALL db.relationshipTypes() YIELD relationshipType"
					).data()
				]
			)
			prop_keys = session.execute_read(
				lambda tx: [
					r["propertyKey"]
					for r in tx.run("CALL db.propertyKeys() YIELD propertyKey").data()
				]
			)
			return {
				"node_labels": labels,
				"relationship_types": rel_types,
				"property_keys": prop_keys,
			}
	except Exception as e:
		logger.error(f"Error fetching graph schema: {str(e)}")
		return Error(msg=f"Error fetching graph schema: {str(e)}")
