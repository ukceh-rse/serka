from functools import lru_cache
from typing import Any, Callable

from fastapi import Depends, HTTPException
from fastmcp import Client
from fastmcp.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import Response

from serka.feedback import FeedbackLogger
from serka.catalogue import search_args
from serka.settings import Settings
from serka.usage import UsageLimiter

StreamFn = Callable[[Any, Request, Callable[[], None]], Response]
"""(run input, request, count_run): count_run counts the run towards the daily caps."""


_feedback_logger: FeedbackLogger | None = None
_stream_fn: StreamFn | None = None
_mcp_search_fn: Callable | None = None
_usage_limiter: UsageLimiter | None = None


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
		type: str | None = None,
		location: str | None = None,
		published_after: str | None = None,
		published_before: str | None = None,
	) -> list:
		args = search_args(q, type, published_after, published_before)
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
		# The UI consumes the hits unchanged; warnings are not passed on.
		return result.structured_content["hits"]

	_mcp_search_fn = _search
	return _mcp_search_fn


def get_feedback_logger(settings: Settings = Depends(get_settings)) -> FeedbackLogger:
	global _feedback_logger
	if _feedback_logger is None:
		_feedback_logger = FeedbackLogger(settings.feedback_log_path)
	return _feedback_logger


def get_usage_limiter(settings: Settings = Depends(get_settings)) -> UsageLimiter:
	"""Provides the limiter without using it, so a rejected request counts nothing."""
	global _usage_limiter
	if _usage_limiter is None:
		_usage_limiter = UsageLimiter(
			client_limit=settings.usage_ip_daily_limit,
			overall_limit=settings.usage_global_daily_limit,
			insight_limit=settings.usage_insight_daily_limit,
		)
	return _usage_limiter


def require_chat_enabled(settings: Settings = Depends(get_settings)) -> None:
	if not settings.chat_enabled:
		raise HTTPException(status_code=404, detail="Not Found")


def get_stream_fn(
	settings: Settings = Depends(get_settings), usage_limiter: UsageLimiter = Depends(get_usage_limiter)
) -> StreamFn:
	"""Builds and returns the chat pipeline stream handler for the current config.
	Override this dependency to swap in a mock stream without touching the chat router."""
	global _stream_fn
	if _stream_fn is not None:
		return _stream_fn

	# Deferred imports so pydantic-ai/bedrock are not required at module load time.
	from pydantic_ai.mcp import MCPToolset

	from serka.chat.models import build_stage_models
	from serka.chat.service import make_stream_fn

	mcp_url = f"http://{settings.mcp_host}:{settings.mcp_port}/mcp"

	async def call_tool(name: str, args: dict[str, Any]) -> Any:
		async with Client(mcp_url) as client:
			result = await client.call_tool(name, args)
		return result.structured_content

	from serka import answer_cache

	_stream_fn = make_stream_fn(
		build_stage_models(settings),
		call_tool,
		MCPToolset(mcp_url),
		usage_limiter.claim_insight,
		answer_cache.from_settings(settings),
	)
	return _stream_fn
