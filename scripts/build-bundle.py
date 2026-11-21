"""Build an OKF bundle of the first N datasets in the raw store (RAW_DIR, default ./raw).

Writes BUNDLES_DIR/<N> (or BUNDLES_DIR/full for 'all') unless --out is given, replacing only that
directory. Supporting files not converted yet go to the local Legilo at LEGILO_URL; start it with
`docker compose --profile ingest up -d legilo`. Nothing else is fetched.

	uv run scripts/build-bundle.py 20
	uv run scripts/load-bundle.py bundles/20
"""

import argparse
import logging
from datetime import timedelta
from pathlib import Path

from tqdm.contrib.logging import logging_redirect_tqdm

from serka.build import BuildSummary, build_bundle
from serka.legilo import LegiloConverter
from serka.raw import RawStore, parse_size, size_name
from serka.settings import Settings


def main() -> None:
	"""Parse arguments, build the bundle and print what was written."""
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("size", type=parse_size, help="number of datasets, or 'all'")
	parser.add_argument("--out", type=Path, help="bundle directory (default: BUNDLES_DIR/<size>)")
	parser.add_argument("--refresh", action="store_true", help="convert supporting files again with Legilo")
	parser.add_argument("--debug", action="store_true", help="enable DEBUG logging")
	args: argparse.Namespace = parser.parse_args()
	logging.basicConfig(
		level=logging.DEBUG if args.debug else logging.INFO,
		format="%(asctime)s %(name)s %(levelname)s %(message)s",
	)
	settings: Settings = Settings()
	out: Path = args.out or Path(settings.bundles_dir) / size_name(args.size)
	converter: LegiloConverter = LegiloConverter(settings.legilo_url, timedelta(seconds=settings.legilo_timeout))
	with logging_redirect_tqdm():
		summary: BuildSummary = build_bundle(RawStore(Path(settings.raw_dir)), args.size, out, converter, args.refresh)
	conv = summary.conversion
	print(f"Bundle: {summary.bundle_dir}")
	print(f"Concepts: {summary.concepts}")
	print(
		f"Conversion: {conv.converted} converted, {conv.cached} cached, "
		f"{conv.file_errors} file errors, {len(conv.failed)} datasets failed"
	)


if __name__ == "__main__":
	main()
