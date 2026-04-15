from __future__ import annotations

import uuid

from ag_ui.core import RunAgentInput, UserMessage
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

from serka.routers.dependencies import StreamFn, get_stream_fn

router = APIRouter(prefix="/chat", tags=["Chat"])


class QueryRequest(BaseModel):
	message: str


@router.post(
	"/stream",
	summary="Ask the EIDC agent a question",
	description="Send a plain-text query. The agent searches the EIDC catalogue and streams back a response.",
)
async def chat_stream(
	body: QueryRequest,
	request: Request,
	stream_fn: StreamFn = Depends(get_stream_fn),
) -> Response:
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
		"for use in multi-turn conversation."
	),
)
async def chat_stream_agui(
	body: RunAgentInput,
	request: Request,
	stream_fn: StreamFn = Depends(get_stream_fn),
) -> Response:
	return stream_fn(body, request)
