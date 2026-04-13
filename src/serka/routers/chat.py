from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models.bedrock import BedrockConverseModel

from serka.models import Config
from serka.routers.dependencies import get_config
from serka.prompts import AGENT_PROMPT


router = APIRouter(prefix="/chat", tags=["Chat"])

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_DONE = object()  # sentinel to signal the queue is exhausted


def _strip_thinking(text: str) -> str:
	return _THINK_RE.sub("", text)


class _TrackedMCPServer(MCPServerStreamableHTTP):
	"""MCP server that emits a status event whenever a tool is called."""

	def __init__(self, url: str, queue: asyncio.Queue) -> None:
		super().__init__(url)
		self._queue = queue

	async def call_tool(
		self,
		tool_name: str,
		arguments: dict[str, Any],
		metadata: dict[str, Any] | None = None,
	) -> Any:
		await self._queue.put({"type": "tool", "name": tool_name})
		return await super().call_tool(tool_name, arguments, metadata)


class ChatRequest(BaseModel):
	message: str
	history: list[dict] = []


@router.post("/stream", summary="Streaming chat via pydantic-ai agent with MCP tools")
async def chat_stream(
	req: ChatRequest,
	config: Config = Depends(get_config),
) -> StreamingResponse:
	mcp_url = f"http://{config.mcp.host}:{config.mcp.port}/mcp"

	async def event_stream():
		queue: asyncio.Queue = asyncio.Queue()

		mcp_server = _TrackedMCPServer(mcp_url, queue)
		model = BedrockConverseModel(config.models.llm)
		agent = Agent(model, instructions=AGENT_PROMPT, mcp_servers=[mcp_server])

		async def run_agent() -> None:
			try:
				async with agent.run_mcp_servers():
					# Tool calls from _TrackedMCPServer are enqueued synchronously
					# during the agent loop before the final turn begins streaming,
					# so tool events always arrive in the queue before text events.
					async with agent.run_stream(req.message) as result:
						async for chunk in result.stream_text(delta=True):
							clean = _strip_thinking(chunk)
							if clean:
								await queue.put({"type": "text", "delta": clean})
			finally:
				await queue.put(_DONE)

		task = asyncio.create_task(run_agent())
		try:
			while True:
				event = await queue.get()
				if event is _DONE:
					break
				data = json.dumps(event)
				yield f"data: {data}\n\n"
		except Exception:
			task.cancel()
			raise

		yield 'data: {"type": "done"}\n\n'

	return StreamingResponse(event_stream(), media_type="text/event-stream")
