from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	# Neo4j
	neo4j_host: str = "localhost"
	neo4j_port: int = 7687
	neo4j_username: str
	neo4j_password: str

	# MongoDB
	mongo_host: str = "localhost"
	mongo_port: int = 27017

	# MCP server
	mcp_host: str = "localhost"
	mcp_port: int = 8000

	# Models (Bedrock)
	models_embedding: str
	models_llm: str

	# External services
	legilo_username: str
	legilo_password: str

	# App
	test_mode: bool = False

	model_config = SettingsConfigDict(
		env_file=".env", env_file_encoding="utf-8", extra="ignore"
	)
