from functools import lru_cache
from typing import Any, Callable

from fastapi import Depends
from starlette.requests import Request
from starlette.responses import Response

from serka.dao import DAO
from serka.feedback import FeedbackLogger
from serka.settings import Settings

StreamFn = Callable[[Any, Request], Response]

_dao: DAO | None = None
_feedback_logger: FeedbackLogger | None = None
_stream_fn: StreamFn | None = None


@lru_cache
def get_settings() -> Settings:
	return Settings()


def get_dao(settings: Settings = Depends(get_settings)) -> DAO:
	global _dao
	if _dao is None:
		_dao = DAO(
			neo4j_host=settings.neo4j_host,
			neo4j_port=settings.neo4j_port,
			neo4j_user=settings.neo4j_username,
			neo4j_password=settings.neo4j_password,
			mcp_host=settings.mcp_host,
			mcp_port=settings.mcp_port,
			legilo_user=settings.legilo_username,
			legilo_password=settings.legilo_password,
			models_embedding=settings.models_embedding,
			models_llm=settings.models_llm,
		)
	return _dao


def get_feedback_logger(settings: Settings = Depends(get_settings)) -> FeedbackLogger:
	global _feedback_logger
	if _feedback_logger is None:
		_feedback_logger = FeedbackLogger(settings.feedback_log_path)
	return _feedback_logger


def get_stream_fn(settings: Settings = Depends(get_settings)) -> StreamFn:
	"""Builds and returns the chat stream handler for the current config.
	Override this dependency to swap in a mock stream without touching the chat router."""
	global _stream_fn
	if _stream_fn is not None:
		return _stream_fn

	# Deferred imports so pydantic-ai/bedrock are not required at module load time.
	from pydantic_ai import Agent
	from pydantic_ai.mcp import MCPServerStreamableHTTP
	from pydantic_ai.models.bedrock import BedrockConverseModel
	from pydantic_ai.ui import SSE_CONTENT_TYPE
	from pydantic_ai.ui.ag_ui import AGUIAdapter
	from starlette.responses import StreamingResponse

	from serka.prompts import AGENT_PROMPT

	mcp_url = f"http://{settings.mcp_host}:{settings.mcp_port}/mcp"
	agent = Agent(
		BedrockConverseModel(settings.models_llm),
		instructions=AGENT_PROMPT,
		toolsets=[MCPServerStreamableHTTP(mcp_url)],
	)

	def stream(run_input: Any, request: Request) -> Response:
		accept = request.headers.get("accept", SSE_CONTENT_TYPE)
		adapter = AGUIAdapter(agent=agent, run_input=run_input, accept=accept)
		return StreamingResponse(
			adapter.encode_stream(adapter.run_stream()), media_type=accept
		)

	_stream_fn = stream
	return _stream_fn
