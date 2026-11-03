"""AG-UI event emission for the chat pipeline.

Pipeline nodes push events onto an `Emitter` queue; `stream_run` runs the pipeline in a
task and drains the queue as SSE. See openspec `chat-agent-events` for the contract.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from ag_ui.core import (
	BaseEvent,
	CustomEvent,
	RunErrorEvent,
	RunFinishedEvent,
	RunStartedEvent,
	StepFinishedEvent,
	StepStartedEvent,
	TextMessageContentEvent,
	TextMessageEndEvent,
	TextMessageStartEvent,
	ToolCallArgsEvent,
	ToolCallEndEvent,
	ToolCallResultEvent,
	ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from pydantic_ai import RunContext
from pydantic_ai.messages import (
	AgentStreamEvent,
	FunctionToolCallEvent,
	FunctionToolResultEvent,
	PartDeltaEvent,
	PartStartEvent,
	TextPart,
	TextPartDelta,
)
from pydantic_ai.ui import SSE_CONTENT_TYPE
from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)

ToolCaller = Callable[[str, dict[str, Any]], Awaitable[Any]]
"""Calls a catalogue tool by name with arguments, returning its structured result."""


@dataclass
class ToolResult:
	tool: str
	args: dict[str, Any]
	result: Any


class Emitter:
	"""Queue of encoded SSE lines with typed helpers for every event the pipeline emits."""

	def __init__(self) -> None:
		self.queue: asyncio.Queue[str | None] = asyncio.Queue()
		self._encoder = EventEncoder()
		self._message_id: str | None = None

	def _put(self, event: BaseEvent) -> None:
		self.queue.put_nowait(self._encoder.encode(event))

	def close(self) -> None:
		self.queue.put_nowait(None)

	# Run lifecycle

	def run_started(self, thread_id: str, run_id: str) -> None:
		self._put(RunStartedEvent(thread_id=thread_id, run_id=run_id))

	def run_finished(self, thread_id: str, run_id: str) -> None:
		self._put(RunFinishedEvent(thread_id=thread_id, run_id=run_id))

	def run_error(self, message: str) -> None:
		self._put(RunErrorEvent(message=message))

	def metadata(self, model: str, models: dict[str, str]) -> None:
		"""RUN_METADATA is not an AG-UI type, so it is written as a raw SSE event."""
		payload = json.dumps({"type": "RUN_METADATA", "model": model, "models": models})
		self.queue.put_nowait(f"event: RUN_METADATA\ndata: {payload}\n\n")

	# Steps and custom events

	@contextmanager
	def step(self, name: str, *, attempt: int, max_attempts: int | None, model: str | None) -> Iterator[None]:
		"""Brackets a stage in STEP_STARTED/STEP_FINISHED. A stage that raises gets no STEP_FINISHED."""
		self._put(StepStartedEvent(step_name=name))
		self.custom("serka.step", {"step": name, "attempt": attempt, "maxAttempts": max_attempts, "model": model})
		yield
		self._put(StepFinishedEvent(step_name=name))

	def custom(self, name: str, value: Any) -> None:
		self._put(CustomEvent(name=name, value=value))

	# Tool calls

	def tool_call_start(self, tool_call_id: str, name: str, args_json: str) -> None:
		self._put(ToolCallStartEvent(tool_call_id=tool_call_id, tool_call_name=name))
		self._put(ToolCallArgsEvent(tool_call_id=tool_call_id, delta=args_json))
		self._put(ToolCallEndEvent(tool_call_id=tool_call_id))

	def tool_call_result(self, tool_call_id: str, content: str) -> None:
		self._put(ToolCallResultEvent(message_id=str(uuid.uuid4()), tool_call_id=tool_call_id, content=content, role="tool"))

	# Text (one answer message per run)

	@property
	def message_open(self) -> bool:
		return self._message_id is not None

	def text_delta(self, delta: str) -> None:
		"""Appends to the answer message, opening it on the first delta."""
		if not delta:
			return
		if self._message_id is None:
			self._message_id = str(uuid.uuid4())
			self._put(TextMessageStartEvent(message_id=self._message_id, role="assistant"))
		self._put(TextMessageContentEvent(message_id=self._message_id, delta=delta))

	def text_end(self) -> None:
		if self._message_id is not None:
			self._put(TextMessageEndEvent(message_id=self._message_id))
			self._message_id = None

	def text(self, text: str) -> None:
		"""Emits a complete answer message."""
		self.text_delta(text)
		self.text_end()


def _json(value: Any) -> str:
	return value if isinstance(value, str) else json.dumps(value, default=str)


async def call_tool(emitter: Emitter, call: ToolCaller, name: str, args: dict[str, Any]) -> ToolResult:
	"""Runs a directly executed tool call, streaming it as a tool call event sequence."""
	tool_call_id = str(uuid.uuid4())
	emitter.tool_call_start(tool_call_id, name, json.dumps(args))
	try:
		result = await call(name, args)
	except Exception as e:
		emitter.tool_call_result(tool_call_id, f"Error: {e}")
		raise
	emitter.tool_call_result(tool_call_id, _json(result))
	return ToolResult(tool=name, args=args, result=result)


def agent_event_handler(
	emitter: Emitter, *, stream_text: bool = False, tool_results: list[ToolResult] | None = None
) -> Callable[[RunContext[Any], AsyncIterable[AgentStreamEvent]], Awaitable[None]]:
	"""Maps an inner agent run's events onto the emitter.

	Tool calls become TOOL_CALL_START/ARGS/END/RESULT; a result that is not a success is
	prefixed `Error: `, as in `call_tool`. Text deltas are forwarded only when
	`stream_text` is set. Successful tool results are appended to `tool_results` when given.
	"""

	async def handler(ctx: RunContext[Any], events: AsyncIterable[AgentStreamEvent]) -> None:
		calls: dict[str, tuple[str, dict[str, Any]]] = {}
		async for event in events:
			if isinstance(event, FunctionToolCallEvent):
				part = event.part
				calls[part.tool_call_id] = (part.tool_name, part.args_as_dict())
				emitter.tool_call_start(part.tool_call_id, part.tool_name, part.args_as_json_str())
			elif isinstance(event, FunctionToolResultEvent):
				result = event.part
				content = result.model_response_str()
				emitter.tool_call_result(
					result.tool_call_id, content if result.outcome == "success" else f"Error: {content}"
				)
				if tool_results is not None and result.outcome == "success":
					name, args = calls.get(result.tool_call_id, (result.tool_name, {}))
					tool_results.append(ToolResult(tool=name, args=args, result=result.content))
			elif stream_text and isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
				emitter.text_delta(event.part.content)
			elif stream_text and isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
				emitter.text_delta(event.delta.content_delta)

	return handler


async def stream_run(
	emitter: Emitter, run: Callable[[], Awaitable[None]], *, thread_id: str, run_id: str
) -> AsyncIterator[str]:
	"""Runs the pipeline in a task and yields its events, ending with RUN_FINISHED or RUN_ERROR."""
	emitter.run_started(thread_id, run_id)

	async def runner() -> None:
		try:
			await run()
		except Exception:
			# Details stay in the server log; clients get a generic message.
			logger.exception("Chat pipeline failed")
			emitter.text_end()  # close a live-streamed answer so the event sequence stays valid
			emitter.run_error("Sorry, something went wrong while answering. Please try again.")
		else:
			emitter.run_finished(thread_id, run_id)
		finally:
			emitter.close()

	task = asyncio.create_task(runner())
	try:
		while (item := await emitter.queue.get()) is not None:
			yield item
	finally:
		if not task.done():
			task.cancel()


def streaming_response(
	emitter: Emitter, run: Callable[[], Awaitable[None]], *, thread_id: str, run_id: str
) -> StreamingResponse:
	return StreamingResponse(stream_run(emitter, run, thread_id=thread_id, run_id=run_id), media_type=SSE_CONTENT_TYPE)
