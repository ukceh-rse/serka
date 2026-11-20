import argparse
import logging
from tqdm.contrib.logging import logging_redirect_tqdm

from serka.pipelines import PipelineBuilder
from serka.settings import Settings

logger = logging.getLogger(__name__)


def greater_than_zero(value) -> int:
	int_value = int(value)
	if int_value <= 0:
		raise argparse.ArgumentTypeError("Value must be greater than zero.")
	return int_value


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description=(
			"Fetch EIDC records and Legilo supporting files, write them as an OKF bundle "
			"(OKF_BUNDLE_DIR, default ./bundle), then load the bundle into Redis. "
			"Each run REPLACES the whole bundle: ingesting a subset (a small n or --ids-file) "
			"leaves only that subset in the bundle and the search index."
		)
	)
	parser.add_argument(
		"n",
		help="Number of rows to process",
		default=10,
		type=greater_than_zero,
		nargs="?",
	)
	parser.add_argument(
		"--ids-file",
		help="File of EIDC dataset IDs to ingest (one per line, '#' comments allowed); overrides n",
	)
	parser.add_argument(
		"--no-load",
		action="store_true",
		help="Only write the bundle; do not load it into Redis (see scripts/load-bundle.py)",
	)
	parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
	args = parser.parse_args()

	fetcher_args = {"rows": args.n}
	if args.ids_file:
		with open(args.ids_file) as f:
			lines = (line.split("#", 1)[0].strip() for line in f)
			fetcher_args = {"ids": [line for line in lines if line]}

	logging.basicConfig(
		level=logging.DEBUG if args.debug else logging.INFO,
		format="%(asctime)s %(name)s %(levelname)s %(message)s",
	)
	file_handler = logging.FileHandler("ingest.log")
	file_handler.setLevel(logging.WARNING)
	file_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
	logging.getLogger().addHandler(file_handler)

	s = Settings()
	p = PipelineBuilder(okf_bundle_dir=s.okf_bundle_dir, legilo_pat=s.legilo_pat).build_graph_pipeline()
	with logging_redirect_tqdm():
		result = p.run(data={"eidc_fetcher": fetcher_args})
	logger.info(f"{result['okf_writer']}")

	if not args.no_load:
		from serka.okf.loader import load_from_settings

		with logging_redirect_tqdm():
			logger.info(f"{load_from_settings(s)}")
