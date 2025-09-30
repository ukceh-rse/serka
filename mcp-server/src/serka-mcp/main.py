from fastmcp import FastMCP
from typing import List, Any, Literal, Optional, Union
import requests
from logging import Logger
import logging
from dotenv import load_dotenv
import os
from pydantic import BaseModel, Field
from neo4j import GraphDatabase
from haystack_integrations.components.embedders.amazon_bedrock import (
	AmazonBedrockTextEmbedder,
)

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

EIDC_URL: str = "https://catalogue.ceh.ac.uk/eidc/documents"
DETAILS_URL: str = "https://catalogue.ceh.ac.uk/documents/{id}?format=json"
LEGILO_URL: str = "https://legilo.eds-infra.ceh.ac.uk/{id}/documents"

TIMEOUT: int = 10


class Dataset(BaseModel):
	"""Represents a dataset from the EIDC catalogue."""

	title: str = Field(description="The title of the dataset")
	id: str = Field(description="Unique identifier for the dataset")
	url: str = Field(description="URL to access the dataset")
	citations: Optional[int] = Field(
		None, description="Number of citations for this dataset"
	)
	publication_date: Optional[str] = Field(
		None, description="Date when the dataset was published"
	)


class Detail(BaseModel):
	"""Represents a specific detail field from a dataset."""

	id: str = Field(
		description="Unique identifier for the dataset this detail relates to"
	)
	field: str = Field(description="The name of this detail's field")
	value: Any = Field(description="The value of the detail")


class SupportingDocument(BaseModel):
	"""Represents a supporting document of a dataset"""

	filename: str = Field(description="The filename of the supporting document")
	content: str = Field(description="The content of the supporting document")


class Error(BaseModel):
	"""Respresents an error."""

	msg: str = Field(description="A message describing the error")


@mcp.tool()
def get_supporting_documentation(id: str) -> Union[List[SupportingDocument], Error]:
	"""Gets the supporting documentation of a dataset matching the given id.
	Supporting documentation may contain extended information about the dataset and how it was gathered.

	Args:
	    id (str): The unique identifier of the dataset. Unique identifiers can be found using the search and lisat tools.

	Returns:
	    Dict[str, str]: Supporting documentation for the dataset in a Dict where the keys are the filenames of the supporting documents and the values are the content.
	"""
	logger.info(f"Getting supporting documentation for dataset {id}")
	try:
		sso_user = os.getenv("SSO_USER")
		sso_pass = os.getenv("SSO_PASS")

		if not sso_user or not sso_pass:
			return Error(msg="Missing SSO credentials to access service")

		response = requests.get(
			LEGILO_URL.format(id=id), auth=(sso_user, sso_pass), timeout=TIMEOUT
		)
		json_data = response.json()
		if json_data["success"]:
			return [
				SupportingDocument(filename=key, content=val)
				for key, val in json_data["success"].items()
			]
		else:
			return []
	except Exception as e:
		logger.error(f"Error getting supporting documents: {str(e)}")
		return Error(f"Error getting supporting documents: {str(e)}")


@mcp.tool()
def get_details(
	id: str, field: Literal["description", "authors"]
) -> Union[Detail, Error]:
	"""Gets the details about the dataset matching the given id.

	Args:
	    id (str): The unique identifier of the dataset. Unique identifiers can be found using the search and list tools.
	    field (Literal["description", "authors"]): The specific field to retrieve.
	        Must be either "description" or "authors".

	Returns:
	    Detail: Detail containing the value of the requested field for the specified dataset
	"""
	try:
		logger.info(f"Getting {field} details for dataset {id}")
		url = DETAILS_URL.format(id=id)
		response = requests.get(url, timeout=TIMEOUT)
		json_data = response.json()
		if field in json_data:
			return Detail(field=field, value=json_data[field], id=id)
		else:
			logger.error(f'Field "{field}" not found in dataset "{id}"')
			return Error(f'Field "{field}" not found in dataset "{id}"')
	except Exception as e:
		logger.error(
			f'Could not retrieve details "{field}" about dataset "{id}": {str(e)}'
		)
		return Error(
			f'Could not retrieve details "{field}" about dataset "{id}": {str(e)}'
		)


@mcp.tool()
def list(
	sort_by: Literal["citations", "publication_date"],
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
	try:
		logger.info(f"Listing datasets, sorted by {sort_by} in {order} order")

		sort_params = {
			"citations": "incomingCitationCount",
			"publication_date": "publicationDate",
		}
		order_params = {"ascending": "asc", "descending": "desc"}

		url = f"{EIDC_URL}?sortField={sort_params[sort_by]}&order={order_params[order]}"
		response = requests.get(url, timeout=TIMEOUT)
		json_data = response.json()
		if "results" in json_data:
			return [
				Dataset(
					title=result["title"],
					id=result["identifier"],
					url=f"https://catalogue.ceh.ac.uk/id/{result['identifier']}",
					**{sort_by: result[sort_params[sort_by]]},
				)
				for result in json_data["results"]
			]
		else:
			logger.warning("No datasets found!")
			return []
	except Exception as e:
		logger.error(f"Error listing datasets: {str(e)}")
		return Error(msg=f"Error listing datasets: {str(e)}")


def list_query(tx, type: str = "Dataset", limit: int = 25):
	query = f"MATCH (n:{type}) RETURN apoc.map.removeKey(properties(n), 'embedding') AS datasets LIMIT {limit}"
	result = tx.run(query)
	return result.data()


@mcp.tool()
def list_datasets() -> Any:
	"""Lists the datasets held in Serka's EIDC knowledge graph.

	Return:
		Any: The raw response from the knowledge graph.
	"""
	logger.info("Listing datasets in Serka knowledge graph.")
	try:
		with GraphDatabase.driver(
			os.getenv("NEO4J_URI"),
			auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
		) as driver:
			with driver.session(database="neo4j") as session:
				nodes = session.execute_read(list_query)
				return nodes
	except Exception as e:
		logger.error(f"Error listing datasets in Serka knowledge graph: {str(e)}")
		return Error(f"Error listing datasets in Serka knowledge graph: {str(e)}")


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
def semantic_search(search_term: str) -> Any:
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

		db_uri: str = os.getenv("NEO4J_URI", "<NEO4J_URI missing!!!>")
		db_user = os.getenv("NEO4J_USERNAME", "<NEO4J_USERNAME missing!!!>")
		db_password = os.getenv("NEO4J_PASSWORD", "<NEO4J_PASSWORD missing!!!>")
		logger.debug(f"Querying graph at {db_uri}.")
		with GraphDatabase.driver(
			db_uri,
			auth=(db_user, db_password),
		) as driver:
			with driver.session(database="neo4j") as session:
				datasets = session.execute_read(search_query, embedding=embedding)
				return datasets
	except Exception as e:
		logger.error(f'Error performing semantic search for "{search_term}": {str(e)}')
		return Error(f'Error performing semantic search for "{search_term}": {str(e)}')


@mcp.tool()
def search(search_term: str) -> Union[List[Dataset], Error]:
	"""Searches the EIDC catalogue for datasets most relevant to the search term. Returns the title and url of the 20 most relevant datasets

	Args:
	    search_term (str): Search term or terms to search for in the EIDC

	Returns:
	    Union[List[Dataset], Error]: A list of datasets matching the search term or an error
	"""
	logger.info(f'Searching EIDC with search term: "{search_term}"')
	try:
		response = requests.get(f"{EIDC_URL}?term={search_term}", timeout=TIMEOUT)
		json_data = response.json()
		if "results" in json_data:
			return [
				Dataset(
					title=result["title"],
					id=result["identifier"],
					url=f"https://catalogue.ceh.ac.uk/id/{result['identifier']}",
				)
				for result in json_data["results"]
			]
		else:
			return []
	except Exception as e:
		logger.error(f'Error searching for "{search_term}": {str(e)}')
		return Error(f'Error searching for "{search_term}": {str(e)}')


if __name__ == "__main__":
	logger.info("Starting MCP server...")
	mcp.run(transport="http", host="0.0.0.0", port=8000)
	logger.info("Stopping MCP server")
