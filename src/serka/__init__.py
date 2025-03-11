import logging
import base64
import os
from dotenv import load_dotenv
from haystack.components.fetchers.link_content import REQUEST_HEADERS

# Set basic logging configuration
logging.basicConfig(
	level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Load .env and setup default credentials for using the Legilo service.
load_dotenv()
user = os.environ.get("user")
password = os.environ.get("password")
credentials = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("utf-8")
REQUEST_HEADERS["Authorization"] = f"Basic {credentials}"
