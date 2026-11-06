"""Turns an AG-UI request into a streamed chat pipeline run."""

from collections.abc import Sequence
from typing import Any, Callable

from ag_ui.core import AssistantMessage, Message, RunAgentInput, UserMessage
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.toolsets import AbstractToolset
from starlette.requests import Request
from starlette.responses import Response

from serka.chat.events import Emitter, ToolCaller, streaming_response
from serka.chat.models import StageModels
from serka.chat.pipeline import ChatDeps, ChatState, build_graph, run_chat


def _text(message: Message) -> str:
	content = message.content
	if isinstance(content, str):
		return content
	if isinstance(content, list):
		return "".join(getattr(part, "text", "") for part in content)
	return ""


def split_messages(messages: Sequence[Message]) -> tuple[str, list[ModelMessage]]:
	"""Returns (latest user message, earlier user/assistant turns as model history).

	Only user and assistant text is kept: client-supplied history is untrusted, so system,
	tool and other message types never reach the models.
	"""
	last_user = max((i for i, m in enumerate(messages) if isinstance(m, UserMessage)), default=None)
	if last_user is None:
		return "", []
	history: list[ModelMessage] = []
	for m in messages[:last_user]:
		text = _text(m)
		if not text:
			continue
		if isinstance(m, UserMessage):
			history.append(ModelRequest(parts=[UserPromptPart(text)]))
		elif isinstance(m, AssistantMessage):
			history.append(ModelResponse(parts=[TextPart(text)]))
	return _text(messages[last_user]), history


def make_stream_fn(
	models: StageModels, call_tool: ToolCaller, toolset: AbstractToolset[Any], claim_insight: Callable[[], bool]
) -> Callable[[RunAgentInput, Request], Response]:
	graph = build_graph()

	def stream(run_input: RunAgentInput, request: Request) -> Response:
		query, history = split_messages(run_input.messages)
		deps = ChatDeps(
			models=models, call_tool=call_tool, toolset=toolset, emitter=Emitter(), claim_insight=claim_insight
		)
		state = ChatState(query=query, history=history)

		async def run() -> None:
			await run_chat(graph, state, deps)

		return streaming_response(deps.emitter, run, thread_id=run_input.thread_id, run_id=run_input.run_id)

	return stream
