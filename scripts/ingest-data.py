"""Download, build and load N EIDC datasets in one step.

Runs scripts/download.py, scripts/build-bundle.py and scripts/load-bundle.py in order: datasets go
into the raw store (RAW_DIR), the bundle into BUNDLES_DIR/<N> (or BUNDLES_DIR/full), and that bundle
into Redis. Supporting files need the local Legilo: `docker compose --profile ingest up -d legilo`.

	uv run scripts/ingest-data.py 100
	uv run scripts/ingest-data.py 10 --ids-file tests/smoke/datasets.txt
"""

import argparse
import logging
from datetime import timedelta
from pathlib import Path

import requests
from tqdm.contrib.logging import logging_redirect_tqdm

from serka.build import BuildSummary, build_bundle
from serka.download import DownloadRequest, download
from serka.legilo import LegiloConverter
from serka.okf.loader import load_from_settings
from serka.raw import RawStore, parse_size, read_ids_file, size_name
from serka.settings import Settings

logger = logging.getLogger(__name__)


def main() -> None:
	"""Parse arguments and run the download, build and load stages."""
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("size", type=parse_size, nargs="?", default=10, help="number of datasets, or 'all'")
	parser.add_argument("--ids-file", type=Path, help="IDs to put first in a new order (one per line, '#' comments)")
	parser.add_argument("--no-load", action="store_true", help="download and build only; do not load into Redis")
	parser.add_argument("--debug", action="store_true", help="enable DEBUG logging")
	args: argparse.Namespace = parser.parse_args()
	logging.basicConfig(
		level=logging.DEBUG if args.debug else logging.INFO,
		format="%(asctime)s %(name)s %(levelname)s %(message)s",
	)
	file_handler: logging.FileHandler = logging.FileHandler("ingest.log")
	file_handler.setLevel(logging.WARNING)
	file_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
	logging.getLogger().addHandler(file_handler)

	settings: Settings = Settings()
	store: RawStore = RawStore(Path(settings.raw_dir))
	head: list[str] = read_ids_file(args.ids_file) if args.ids_file else []
	converter: LegiloConverter = LegiloConverter(settings.legilo_url, timedelta(seconds=settings.legilo_timeout))
	with requests.Session() as session, logging_redirect_tqdm():
		download(session, store, DownloadRequest(n=args.size, head=head))
		out: Path = Path(settings.bundles_dir) / size_name(args.size)
		summary: BuildSummary = build_bundle(store, args.size, out, converter)
		if not args.no_load:
			logger.info("Loaded: %s", load_from_settings(settings, summary.bundle_dir))


if __name__ == "__main__":
	main()
