from serka.models import Config
import yaml
from functools import lru_cache
from serka.dao import DAO
from fastapi import Depends
from serka.feedback import FeedbackLogger


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
		chroma_host=config.chroma.host,
		chroma_port=config.chroma.port,
		default_embedding_model=config.embedding_models[0],
		default_rag_model=config.rag_models[0],
	)


@lru_cache
def get_feedback_logger(config: Config = Depends(get_config)) -> FeedbackLogger:
	return FeedbackLogger(config.mongo.host, config.mongo.port)
