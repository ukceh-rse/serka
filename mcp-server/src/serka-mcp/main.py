from fastmcp import FastMCP
from typing import List, Literal, Optional, Union
from logging import Logger
import logging
from dotenv import load_dotenv
import os
from pydantic import BaseModel, Field
from neo4j import GraphDatabase, Driver
from haystack_integrations.components.embedders.amazon_bedrock import (
	AmazonBedrockTextEmbedder,
)
from geopy.geocoders.nominatim import Nominatim
from geopy.location import Location


load_dotenv()

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
	handlers=[
		logging.StreamHandler(),
		logging.FileHandler("serka_mcp.log"),
	],
)
logger: Logger = logging.getLogger("serka_mcp")

mcp: FastMCP = FastMCP("Serka")
geolocator: Nominatim = Nominatim(user_agent="serka_geocoder")


def create_neo4j_driver(
	uri: str = "<NEO4J_URI missing!!!>",
	user: str = "<NEO4J_USERNAME missing!!!>",
	password: str = "<NEO4J_PASSWORD missing!!!>",
) -> Driver:
	return GraphDatabase.driver(
		uri,
		auth=(user, password),
	)


neo4j_driver: Driver = create_neo4j_driver(
	os.getenv("NEO4J_URI"), os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")
)


class Person(BaseModel):
	"""Represents a person that has contributed to data in the EIDC catalogue."""

	name: str = Field(description="The name of the person.")
	uri: str = Field(description="A unique uri corresponding to the person's ORCID.")


class TextChunk(BaseModel):
	"""Represents a searchable chunk of text."""

	content: str = Field(description="The textual content of the chunk of text.")


class Dataset(BaseModel):
	"""Represents a dataset from the EIDC catalogue."""

	title: str = Field(description="The title of the dataset")
	uri: str = Field(description="URI of the dataset")
	citations: Optional[int] = Field(
		None, description="Number of citations for this dataset"
	)
	publication_date: Optional[str] = Field(
		None, description="Date when the dataset was published"
	)


class BoundingBox(BaseModel):
	"""Represents a bounding box of an area."""

	south: float = Field(..., description="Southern boundary (minimum latitude)")
	north: float = Field(..., description="Northern boundary (maximum latitude)")
	west: float = Field(..., description="Western boundary (minimum longitude)")
	east: float = Field(..., description="Eastern boundary (maximum longitude)")

	@classmethod
	def from_nominatim(cls, bbox_array: List[str]) -> "BoundingBox":
		"""Create BoundingBox from Nominatim's bbox array [south, north, west, east]"""
		return cls(
			south=float(bbox_array[0]),
			north=float(bbox_array[1]),
			west=float(bbox_array[2]),
			east=float(bbox_array[3]),
		)


class GeoCodedLocation(BaseModel):
	name: str = Field(
		..., description="The full display name of the geocoded location."
	)
	boundary: BoundingBox = Field(
		..., description="A bounding box representing the boundry of the location."
	)


class ResultItem(BaseModel):
	item: TextChunk | Person = Field(
		description="Contains the data for the result item."
	)
	type: Literal["TextChunk", "Person"] = Field(
		description="Specified the type of the result it."
	)


class SearchResult(BaseModel):
	"""Represents results of performing a semantic search on the Serka knowledge graph."""

	result: ResultItem = Field(
		description="The result item that matches the semantic query."
	)
	dataset: Dataset = Field(
		description="The dataset connected to the node matching the semantic search."
	)
	score: float = Field(
		description="Score showing how semantically similar the content of the node is to the query"
	)
	description: str | None = Field(
		description="Description of the contents relationship to the dataset. Could be a description, metadata, or some other kind of supporting documentation."
	)


class SupportingDocument(BaseModel):
	"""Represents a supporting document of a dataset"""

	filename: str = Field(description="The filename of the supporting document")
	content: str = Field(description="The content of the supporting document")


class Error(BaseModel):
	"""Respresents an error."""

	msg: str = Field(description="A message describing the error")


def list_query(
	tx,
	type: str = "Dataset",
	limit: int = 25,
	sort_by: Literal["citations", "publication_date"] = "citations",
	order: Literal["ascending", "descending"] = "descending",
):
	cypher_order = "ASC" if order == "ascending" else "DESC"
	query = f"MATCH (n:{type}) RETURN apoc.map.removeKey(properties(n), 'embedding') AS dataset ORDER BY n.{sort_by} {cypher_order} LIMIT {limit}"
	result = tx.run(query)
	return result.data()


def dataset_cypher_query(tx, uri: str):
	query = "MATCH (d:Dataset {uri: $uri}) RETURN d"
	result = tx.run(query, uri=uri)
	return result.single()


@mcp.resource("dataset://{uri}")
def get_dataset(uri: str) -> Union[Dataset, Error]:
	logger.info(f"Retrieving dataset {uri}")
	try:
		with neo4j_driver.session(database="neo4j") as session:
			result = session.execute_read(dataset_cypher_query, uri=uri)
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
	"""Lists the datasets in the EIDC and sorts them. Only returns the first 20 datasets.

	Args:
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
			datasets: List[Dataset] = [Dataset(**n["dataset"]) for n in nodes]
			return datasets
	except Exception as e:
		logger.error(f"Error listing datasets in Serka knowledge graph: {str(e)}")
		return Error(msg=f"Error listing datasets in Serka knowledge graph: {str(e)}")


def search_query(tx, embedding: List[float], limit: int = 25):
	query = (
		"CALL db.index.vector.queryNodes('vec_lookup', 20, $embedding) "
		"YIELD node AS start_node, score "
		"MATCH (start_node)-[r]-(connected_node) "
		"WITH start_node, r, connected_node, score, "
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
	result = tx.run(query, embedding=embedding)
	data = result.data()
	return data


@mcp.tool()
def search(search_term: str) -> List[SearchResult]:
	"""Performs a semantic search on the EIDC catalogue using the given search term.

	Args:
	    search_term (str): The search term to use for the semantic search.

	Returns:
	    Any: The raw response from the semantic search API or an error message.
	"""
	logger.info(f'Performing semantic search with term: "{search_term}"')

	try:
		embedding_model: str = os.getenv(
			"AWS_EMBEDDING_MODEL", "<AWS_EMBEDDING_MODEL missing!!!>"
		)
		logger.debug(
			f"Creating embedding for {search_term} using {embedding_model} embedding model."
		)
		embedder = AmazonBedrockTextEmbedder(model=embedding_model)
		embedding = embedder.run(search_term)["embedding"]
		logger.debug(f"Created embedding for {search_term} successfully.")

		with neo4j_driver.session(database="neo4j") as session:
			nodes = session.execute_read(search_query, embedding=embedding)
			search_results: List[SearchResult] = []
			for n in nodes:
				if "TextChunk" in n["start_labels"]:
					dataset = Dataset(**n["connected_node"])
					search_results.append(
						SearchResult(
							result=ResultItem(
								item=TextChunk(**n["start_node"]),
								type="TextChunk",
							),
							dataset=dataset,
							score=n["score"],
							description=n["relationship_type"],
						)
					)
				if "Person" in n["start_labels"] and "Dataset" in n["connected_labels"]:
					dataset = Dataset(**n["connected_node"])
					search_results.append(
						SearchResult(
							result=ResultItem(
								item=Person(**n["start_node"]), type="Person"
							),
							dataset=dataset,
							score=n["score"],
							description=n["relationship_type"],
						)
					)
			return search_results
	except Exception as e:
		logger.error(f'Error performing semantic search for "{search_term}": {str(e)}')
		return Error(
			msg=f'Error performing semantic search for "{search_term}": {str(e)}'
		)


if __name__ == "__main__":
	logger.info("Starting MCP server...")
	mcp.run(transport="http", host="0.0.0.0", port=8000)
	neo4j_driver.close()
	logger.info("Stopping MCP server")
