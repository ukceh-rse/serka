"""Rebuild the Redis search index from the OKF bundle at OKF_BUNDLE_DIR (default ./bundle).

Needs only Redis and the Bedrock embedding model, not EIDC or Legilo. Search is empty or
partial while it runs, and every cached AI Summary answer is cleared.

	uv run scripts/load-bundle.py
"""

import argparse
import logging

from tqdm.contrib.logging import logging_redirect_tqdm

from serka.okf.loader import load_from_settings
from serka.settings import Settings

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
	args = parser.parse_args()
	logging.basicConfig(
		level=logging.DEBUG if args.debug else logging.INFO,
		format="%(asctime)s %(name)s %(levelname)s %(message)s",
	)
	with logging_redirect_tqdm():
		print(load_from_settings(Settings()))
