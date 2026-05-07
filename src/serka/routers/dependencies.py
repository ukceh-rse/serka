import json
from functools import lru_cache
from typing import Any, Callable

from fastapi import Depends
from fastmcp import Client
from starlette.requests import Request
from starlette.responses import Response

from serka.feedback import FeedbackLogger
from serka.settings import Settings

StreamFn = Callable[[Any, Request], Response]

_feedback_logger: FeedbackLogger | None = None
_stream_fn: StreamFn | None = None


@lru_cache
def get_settings() -> Settings:
	return Settings()


async def get_mcp_search(settings: Settings = Depends(get_settings)) -> Callable:
	async def _search(q: str) -> list:
		async with Client(f"http://{settings.mcp_host}:{settings.mcp_port}/mcp") as client:
			result = await client.call_tool("search", {"search_term": q})
		return json.loads(result.content[0].text)

	return _search


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
