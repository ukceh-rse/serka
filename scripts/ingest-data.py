import argparse
import logging

from serka.pipelines import PipelineBuilder
from serka.settings import Settings

logger = logging.getLogger(__name__)


def create_pipeline_builder() -> PipelineBuilder:
	s = Settings()
	return PipelineBuilder(
		neo4j_host=s.neo4j_host,
		neo4j_port=s.neo4j_port,
		neo4j_user=s.neo4j_username,
		neo4j_password=s.neo4j_password,
		legilo_user=s.legilo_username,
		legilo_password=s.legilo_password,
		mcp_host=s.mcp_host,
		mcp_port=s.mcp_port,
		models_embedding=s.models_embedding,
		models_llm=s.models_llm,
		chunk_length=150,
		chunk_overlap=50,
	)


def greater_than_zero(value) -> int:
	int_value = int(value)
	if int_value <= 0:
		raise argparse.ArgumentTypeError("Value must be greater than zero.")
	return int_value


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Run ingest-data script")
	parser.add_argument(
		"n",
		help="Number of rows to process",
		default=10,
		type=greater_than_zero,
		nargs="?",
	)
	parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
	args = parser.parse_args()

	logging.basicConfig(
		level=logging.DEBUG if args.debug else logging.INFO,
		format="%(asctime)s %(name)s %(levelname)s %(message)s",
	)

	pb = create_pipeline_builder()
	p = pb.build_graph_pipeline()
	result = p.run(data={"eidc_fetcher": {"rows": args.n}})
	logger.info(f"{result['graph_writer']}")
