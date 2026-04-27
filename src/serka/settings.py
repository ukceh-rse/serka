from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	# Neo4j
	neo4j_host: str = "localhost"
	neo4j_port: int = 7687
	neo4j_username: str
	neo4j_password: str

	# Feedback
	feedback_log_path: str = "feedback.jsonl"

	# MCP server
	mcp_host: str = "localhost"
	mcp_port: int = 8000

	# Models (Bedrock)
	models_embedding: str = "amazon.titan-embed-text-v2:0"
	models_llm: str = "anthropic.claude-sonnet-4-6"

	# External services
	legilo_username: Optional[str] = None
	legilo_password: Optional[str] = None

	# App
	test_mode: bool = False

	model_config = SettingsConfigDict(
		env_file=".env", env_file_encoding="utf-8", extra="ignore"
	)
