import logging
from dotenv import load_dotenv


# Set basic logging configuration
logging.basicConfig(
	level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
load_dotenv()
