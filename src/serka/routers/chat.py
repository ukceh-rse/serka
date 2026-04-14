from __future__ import annotations

import uuid

from ag_ui.core import RunAgentInput, UserMessage
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models.bedrock import BedrockConverseModel
from pydantic_ai.ui import SSE_CONTENT_TYPE
from pydantic_ai.ui.ag_ui import AGUIAdapter
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from serka.models import Config
from serka.prompts import AGENT_PROMPT
from serka.routers.dependencies import get_config

router = APIRouter(prefix="/chat", tags=["Chat"])


def _build_agent(config: Config) -> Agent:
	mcp_url = f"http://{config.mcp.host}:{config.mcp.port}/mcp"
	return Agent(
		BedrockConverseModel(config.models.llm),
		instructions=AGENT_PROMPT,
		toolsets=[MCPServerStreamableHTTP(mcp_url)],
	)


def _ag_ui_response(
	agent: Agent, run_input: RunAgentInput, request: Request
) -> StreamingResponse:
	accept = request.headers.get("accept", SSE_CONTENT_TYPE)
	adapter = AGUIAdapter(agent=agent, run_input=run_input, accept=accept)
	return StreamingResponse(
		adapter.encode_stream(adapter.run_stream()), media_type=accept
	)


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
	config: Config = Depends(get_config),
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
	return _ag_ui_response(_build_agent(config), run_input, request)


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
	config: Config = Depends(get_config),
) -> Response:
	return _ag_ui_response(_build_agent(config), body, request)
