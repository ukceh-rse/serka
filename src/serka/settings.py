from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	# Neo4j
	neo4j_host: str = "localhost"
	neo4j_port: int = 7687
	neo4j_username: Optional[str] = None
	neo4j_password: Optional[str] = None

	# Feedback
	feedback_log_path: str = "feedback.jsonl"

	# MCP server
	mcp_host: str = "localhost"
	mcp_port: int = 8000

	# Models (Bedrock). All chat model calls go to Bedrock in aws_region.
	aws_region: str = "eu-west-2"
	models_embedding: str = "amazon.titan-embed-text-v2:0"
	# Chat pipeline stage models
	models_classify: str = "amazon.nova-lite-v1:0"
	models_plan_keyword: str = "amazon.nova-micro-v1:0"
	models_plan_insight: str = "eu.anthropic.claude-sonnet-5-5"
	models_execute_insight: str = "eu.anthropic.claude-haiku-5-5"
	models_synthesize_keyword: str = "amazon.nova-lite-v1:0"
	models_synthesize_insight: str = "eu.anthropic.claude-sonnet-5-5"
	models_evaluate: str = "eu.anthropic.claude-haiku-5-5"

	# External services
	legilo_username: Optional[str] = None
	legilo_password: Optional[str] = None

	# App
	test_mode: bool = False

	model_config = SettingsConfigDict(
		env_file=".env", env_file_encoding="utf-8", extra="ignore"
	)
