
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	# Redis (search index and answer cache)
	redis_url: str = "redis://localhost:6379"

	# OKF bundle loaded by default when no bundle directory is given
	okf_bundle_dir: str = "./bundle"
	# Raw store of downloaded EIDC metadata, original supporting files and converted Markdown
	raw_dir: str = "./raw"
	# Parent directory of built bundles, one subdirectory per size (20, 100, full)
	bundles_dir: str = "./bundles"

	# Answer cache (forced off in test mode)
	answer_cache_enabled: bool = True
	# Cosine distance below which a stored query counts as the same question.
	answer_cache_distance_threshold: float = 0.05
	answer_cache_ttl_seconds: int = 7 * 24 * 60 * 60

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
	# Local Legilo service (compose profile "ingest") that converts supporting files to Markdown
	legilo_url: str = "http://localhost:8100"
	legilo_timeout: int = 600

	# Usage limits (per UTC day)
	usage_ip_daily_limit: int = 30
	usage_global_daily_limit: int = 500
	usage_insight_daily_limit: int = 100
	# Rightmost X-Forwarded-For entries to skip to reach the client: appending proxies minus one.
	# 0 ignores the header.
	trusted_proxy_hops: int = 0

	# App
	test_mode: bool = False
	# Limits on chat history are required before enabling this in production.
	chat_enabled: bool = False

	model_config = SettingsConfigDict(
		env_file=".env", env_file_encoding="utf-8", extra="ignore"
	)
