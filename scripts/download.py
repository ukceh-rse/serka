"""Download EIDC datasets into the raw store at RAW_DIR (default ./raw).

Stores each dataset's EIDC metadata JSON, its original supporting files from data-package and the
GEMET lookups its themes need. Datasets already stored are skipped, so the command can be rerun to
grow the store (20, then 100, then all) or to resume after an interruption.

	uv run scripts/download.py 20
	uv run scripts/download.py all --ids-file tests/smoke/datasets.txt
"""

import argparse
import logging
from pathlib import Path

import requests
from tqdm.contrib.logging import logging_redirect_tqdm

from serka.download import DownloadRequest, download
from serka.raw import DEFAULT_SEED, RawStore, parse_size, read_ids_file
from serka.settings import Settings


def main() -> None:
	"""Parse arguments and run the download stage."""
	parser = argparse.ArgumentParser(
		description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
	)
	parser.add_argument("size", type=parse_size, help="number of datasets, or 'all'")
	parser.add_argument(
		"--ids-file",
		type=Path,
		help="IDs to put first in the order (one per line, '#' comments)",
	)
	parser.add_argument(
		"--seed", type=int, default=DEFAULT_SEED, help="shuffle seed for a new order"
	)
	parser.add_argument(
		"--refresh",
		action="store_true",
		help="fetch selected datasets again even if stored",
	)
	parser.add_argument(
		"--reorder",
		action="store_true",
		help="rebuild the order from the ids file and seed",
	)
	parser.add_argument("--debug", action="store_true", help="enable DEBUG logging")
	args: argparse.Namespace = parser.parse_args()
	logging.basicConfig(
		level=logging.DEBUG if args.debug else logging.INFO,
		format="%(asctime)s %(name)s %(levelname)s %(message)s",
	)
	request: DownloadRequest = DownloadRequest(
		n=args.size,
		head=read_ids_file(args.ids_file) if args.ids_file else [],
		seed=args.seed,
		refresh=args.refresh,
		reorder=args.reorder,
	)
	with requests.Session() as session, logging_redirect_tqdm():
		download(session, RawStore(Path(Settings().raw_dir)), request)


if __name__ == "__main__":
	main()
