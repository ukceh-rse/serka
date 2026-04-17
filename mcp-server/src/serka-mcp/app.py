import logging
import os
from logging import Logger

from dotenv import load_dotenv
from fastmcp import FastMCP
from geopy.geocoders.nominatim import Nominatim
from haystack_integrations.components.embedders.amazon_bedrock import (
	AmazonBedrockTextEmbedder,
)
from neo4j import Driver, GraphDatabase

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
	uri: str,
	user: str,
	password: str,
) -> Driver:
	return GraphDatabase.driver(uri, auth=(user, password))


neo4j_driver: Driver = create_neo4j_driver(
	f"bolt://{os.getenv('NEO4J_HOST')}:{os.getenv('NEO4J_PORT')}",
	f"{os.getenv('NEO4J_USERNAME')}",
	f"{os.getenv('NEO4J_PASSWORD')}",
)

embedder = AmazonBedrockTextEmbedder(model=f"{os.getenv('MODELS_EMBEDDING')}")
