import logging
import os
from logging import Logger

import redis
from dotenv import load_dotenv
from fastmcp import FastMCP
from geopy.geocoders.nominatim import Nominatim
from haystack_integrations.components.embedders.amazon_bedrock import (
	AmazonBedrockTextEmbedder,
)

from catalogue import Catalogue
from instructions import INSTRUCTIONS

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

mcp: FastMCP = FastMCP("Serka", instructions=INSTRUCTIONS)
geolocator: Nominatim = Nominatim(user_agent="serka_geocoder")

redis_client: redis.Redis = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
embedder = AmazonBedrockTextEmbedder(model=os.getenv("MODELS_EMBEDDING", "amazon.titan-embed-text-v2:0"))


def embed(text: str) -> list[float]:
	return list(embedder.run(text=text)["embedding"])


catalogue = Catalogue(redis_client, embed)
