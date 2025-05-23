from serka.models import Config
import yaml
from functools import lru_cache
from serka.dao import DAO
from fastapi import Depends
from serka.feedback import FeedbackLogger
import os


@lru_cache
def get_config() -> Config:
	with open("config.yaml", "r") as f:
		config_data = yaml.safe_load(f)
	return Config(**config_data)


@lru_cache
def get_dao(config: Config = Depends(get_config)) -> DAO:
	return DAO(
		ollama_host=config.ollama.host,
		ollama_port=config.ollama.port,
		neo4j_host=config.neo4j.host,
		neo4j_port=config.neo4j.port,
		neo4j_user=os.getenv("NEO4J_USERNAME"),
		neo4j_password=os.getenv("NEO4J_PASSWORD"),
		legilo_user=os.getenv("LEGILO_USERNAME"),
		legilo_password=os.getenv("LEGILO_PASSWORD"),
		default_embedding_model=config.embedding_models[0],
		default_rag_model=config.rag_models[0],
	)


@lru_cache
def get_feedback_logger(config: Config = Depends(get_config)) -> FeedbackLogger:
	return FeedbackLogger(config.mongo.host, config.mongo.port)
