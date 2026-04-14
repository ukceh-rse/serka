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
	uri: str = "<NEO4J_URI missing!!!>",
	user: str = "<NEO4J_USERNAME missing!!!>",
	password: str = "<NEO4J_PASSWORD missing!!!>",
) -> Driver:
	return GraphDatabase.driver(uri, auth=(user, password))


neo4j_driver: Driver = create_neo4j_driver(
	os.getenv("NEO4J_URI"), os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")
)

embedder = AmazonBedrockTextEmbedder(
	model=os.getenv("AWS_EMBEDDING_MODEL", "<AWS_EMBEDDING_MODEL missing!!!>")
)
embedder.warm_up()
