import json
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any, Callable

from fastapi import Depends, HTTPException
from fastmcp import Client
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import Response

from serka.feedback import FeedbackLogger
from serka.ontology import NODE_TYPES
from serka.settings import Settings

StreamFn = Callable[[Any, Request], Response]


_feedback_logger: FeedbackLogger | None = None
_stream_fn: StreamFn | None = None
_mcp_search_fn: Callable | None = None


@lru_cache
def get_settings() -> Settings:
	return Settings()


async def get_mcp_search(settings: Settings = Depends(get_settings)) -> Callable:
	global _mcp_search_fn
	if _mcp_search_fn is not None:
		return _mcp_search_fn

	mcp_url = f"http://{settings.mcp_host}:{settings.mcp_port}/mcp"

	async def _search(
		q: str,
		return_type: str | None = None,
		hops: int = 1,
		location: str | None = None,
		published_after: str | None = None,
		published_before: str | None = None,
	) -> list:
		args: dict[str, Any] = {"query": q, "hops": hops}
		if return_type:
			args["return_type"] = NODE_TYPES[return_type]
		if published_after:
			args["published_after"] = published_after
		if published_before:
			args["published_before"] = published_before
		async with Client(mcp_url) as client:
			if location:
				try:
					geo = await client.call_tool("geocode_location", {"location": location})
				except ToolError as e:
					raise HTTPException(status_code=422, detail=str(e)) from e
				args["bounding_box"] = geo.structured_content["boundary"]
			try:
				result = await client.call_tool("search", args)
			except ToolError as e:
				raise HTTPException(status_code=422, detail=str(e)) from e
		# The search result is a JSON-LD document; the UI consumes the hits in its @graph.
		return result.structured_content["@graph"]

	_mcp_search_fn = _search
	return _mcp_search_fn


def get_feedback_logger(settings: Settings = Depends(get_settings)) -> FeedbackLogger:
	global _feedback_logger
	if _feedback_logger is None:
		_feedback_logger = FeedbackLogger(settings.feedback_log_path)
	return _feedback_logger


async def _prepend_metadata(stream: AsyncGenerator[bytes, None], model_id: str) -> AsyncGenerator[bytes, None]:
	yield f'event: RUN_METADATA\ndata: {json.dumps({"type": "RUN_METADATA", "model": model_id})}\n\n'.encode()
	async for chunk in stream:
		yield chunk


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
		encoded = adapter.encode_stream(adapter.run_stream())
		return StreamingResponse(_prepend_metadata(encoded, settings.models_llm), media_type=accept)

	_stream_fn = stream
	return _stream_fn
