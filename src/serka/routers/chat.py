from __future__ import annotations

import uuid

from ag_ui.core import RunAgentInput, UserMessage
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import Response

from serka.routers.dependencies import StreamFn, get_settings, get_stream_fn, get_usage_limiter, require_chat_enabled
from serka.settings import Settings
from serka.usage import LIMIT_MESSAGES, MAX_QUERY_CHARS, UsageLimiter, client_address

router = APIRouter(prefix="/chat", tags=["Chat"])


class QueryRequest(BaseModel):
	message: str = Field(max_length=MAX_QUERY_CHARS, pattern=r"\S")


def _admit(limiter: UsageLimiter, request: Request, settings: Settings) -> None:
	"""Counts this run, or raises 429 over a daily cap.

	Called from handler bodies, not as a dependency: FastAPI resolves dependencies before it
	reports validation errors, so a dependency would count queries that are then rejected.
	"""
	rejected = limiter.admit(client_address(request, settings.trusted_proxy_hops))
	if rejected:
		raise HTTPException(
			status_code=429,
			detail={"code": rejected, "message": LIMIT_MESSAGES[rejected]},
			headers={"Retry-After": str(limiter.seconds_until_reset())},
		)


@router.post(
	"/stream",
	summary="Ask the EIDC agent a question",
	description="Send a plain-text query. The agent searches the EIDC catalogue and streams back a response.",
)
async def chat_stream(
	body: QueryRequest,
	request: Request,
	stream_fn: StreamFn = Depends(get_stream_fn),
	limiter: UsageLimiter = Depends(get_usage_limiter),
	settings: Settings = Depends(get_settings),
) -> Response:
	_admit(limiter, request, settings)
	run_input = RunAgentInput(
		threadId=str(uuid.uuid4()),
		runId=str(uuid.uuid4()),
		state=None,
		messages=[UserMessage(id=str(uuid.uuid4()), content=body.message)],
		tools=[],
		context=[],
		forwardedProps=None,
	)
	return stream_fn(run_input, request)


@router.post(
	"/stream/agui",
	summary="AG-UI streaming chat (multi-turn)",
	description=(
		"Full AG-UI protocol endpoint. Accepts a complete RunAgentInput including message history, "
		"for use in multi-turn conversation. Returns 404 unless chat is enabled."
	),
	dependencies=[Depends(require_chat_enabled)],
)
async def chat_stream_agui(
	body: RunAgentInput,
	request: Request,
	stream_fn: StreamFn = Depends(get_stream_fn),
	limiter: UsageLimiter = Depends(get_usage_limiter),
	settings: Settings = Depends(get_settings),
) -> Response:
	# Deferred so pydantic-ai/bedrock are not required at module load time.
	from serka.chat.service import split_messages

	query, _ = split_messages(body.messages)
	if not query.strip():
		raise HTTPException(status_code=422, detail="The request has no user message to answer.")
	if len(query) > MAX_QUERY_CHARS:
		raise HTTPException(status_code=422, detail=f"The latest message is longer than {MAX_QUERY_CHARS} characters.")
	_admit(limiter, request, settings)
	return stream_fn(body, request)
