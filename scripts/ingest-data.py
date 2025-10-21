import argparse
import os
import yaml
import logging
from dotenv import load_dotenv
from serka.models import Config
from serka.pipelines import PipelineBuilder

logger = logging.getLogger(__name__)


def load_config() -> Config:
	with open("config.yml", "r") as f:
		config_data = yaml.safe_load(f)
	return Config(**config_data)


def create_pipeline_builder() -> PipelineBuilder:
	load_dotenv()
	config = load_config()
	return PipelineBuilder(
		neo4j_host=config.neo4j.host,
		neo4j_port=config.neo4j.port,
		neo4j_user=os.getenv("NEO4J_USERNAME"),
		neo4j_password=os.getenv("NEO4J_PASSWORD"),
		legilo_user=os.getenv("LEGILO_USERNAME"),
		legilo_password=os.getenv("LEGILO_PASSWORD"),
		mcp_host=config.mcp.host,
		mcp_port=config.mcp.port,
		models=config.models,
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

	args = parser.parse_args()

	pb = create_pipeline_builder()

	p = pb.build_graph_pipeline()
	result = p.run(data={"eidc_fetcher": {"rows": args.n}})

	logger.info(f"{result['graph_writer']}")
