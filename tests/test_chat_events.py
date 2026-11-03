import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

from serka.chat.events import Emitter, ToolResult, agent_event_handler, call_tool, stream_run
from tests.sse import customs, decode, drain, types


def test_step_brackets_stage_with_serka_step() -> None:
	emitter = Emitter()
	with emitter.step("plan", attempt=2, max_attempts=3, model="m1"):
		emitter.custom("serka.plan", {"summary": "s", "steps": []})
	events = drain(emitter.queue)
	assert types(events) == ["STEP_STARTED", "CUSTOM", "CUSTOM", "STEP_FINISHED"]
	assert events[0]["stepName"] == "plan"
	assert events[1] == {
		"type": "CUSTOM",
		"name": "serka.step",
		"value": {"step": "plan", "attempt": 2, "maxAttempts": 3, "model": "m1"},
	}
	assert events[3]["stepName"] == "plan"


def test_step_serka_step_keeps_null_fields() -> None:
	emitter = Emitter()
	with emitter.step("classify", attempt=1, max_attempts=None, model=None):
		pass
	value = customs(drain(emitter.queue), "serka.step")[0]
	assert value["maxAttempts"] is None and value["model"] is None


def test_run_lifecycle_and_metadata() -> None:
	emitter = Emitter()
	emitter.run_started("t", "r")
	emitter.metadata("answer-model", {"classify": "c"})
	emitter.run_finished("t", "r")
	emitter.run_error("boom")
	events = drain(emitter.queue)
	assert events[0] == {"type": "RUN_STARTED", "threadId": "t", "runId": "r"}
	assert events[1] == {"type": "RUN_METADATA", "model": "answer-model", "models": {"classify": "c"}}
	assert events[2] == {"type": "RUN_FINISHED", "threadId": "t", "runId": "r"}
	assert events[3] == {"type": "RUN_ERROR", "message": "boom"}


def test_raw_metadata_line_has_event_name() -> None:
	emitter = Emitter()
	emitter.metadata("m", {})
	line = emitter.queue.get_nowait()
	assert line is not None and line.startswith("event: RUN_METADATA\ndata: ")


def test_text_is_one_message() -> None:
	emitter = Emitter()
	emitter.text_delta("Hello ")
	emitter.text_delta("")
	emitter.text_delta("world")
	assert emitter.message_open
	emitter.text_end()
	assert not emitter.message_open
	events = drain(emitter.queue)
	assert types(events) == ["TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END"]
	assert events[0]["role"] == "assistant"
	assert len({e["messageId"] for e in events}) == 1


def test_call_tool_emits_sequence_with_shared_id() -> None:
	emitter = Emitter()

	async def caller(name: str, args: dict[str, Any]) -> Any:
		return {"@graph": [name, args["query"]]}

	result = asyncio.run(call_tool(emitter, caller, "search", {"query": "bats"}))
	assert result == ToolResult(tool="search", args={"query": "bats"}, result={"@graph": ["search", "bats"]})
	events = drain(emitter.queue)
	assert types(events) == ["TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END", "TOOL_CALL_RESULT"]
	assert len({e["toolCallId"] for e in events}) == 1
	assert events[0]["toolCallName"] == "search"
	assert json.loads(events[1]["delta"]) == {"query": "bats"}
	assert json.loads(events[3]["content"]) == {"@graph": ["search", "bats"]}


def _tool_then_text(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
	if any(isinstance(p, ToolReturnPart) for m in messages for p in m.parts):
		return ModelResponse(parts=[TextPart("done")])
	return ModelResponse(parts=[ToolCallPart("fake_search", {"query": "otters"})])


async def _stream_tool_then_text(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
	if any(isinstance(p, ToolReturnPart) for m in messages for p in m.parts):
		yield "do"
		yield "ne"
	else:
		yield {0: DeltaToolCall(name="fake_search", json_args='{"query": "otters"}')}


def _agent() -> Agent[None, str]:
	agent: Agent[None, str] = Agent(FunctionModel(_tool_then_text, stream_function=_stream_tool_then_text))

	@agent.tool_plain
	def fake_search(query: str) -> dict[str, Any]:
		return {"hits": [query]}

	return agent


def test_agent_tool_call_maps_to_one_sequence() -> None:
	emitter = Emitter()
	collected: list[ToolResult] = []
	asyncio.run(_agent().run("q", event_stream_handler=agent_event_handler(emitter, tool_results=collected)))
	events = drain(emitter.queue)
	assert types(events) == ["TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END", "TOOL_CALL_RESULT"]
	assert len({e["toolCallId"] for e in events}) == 1
	assert events[0]["toolCallName"] == "fake_search"
	assert json.loads(events[3]["content"]) == {"hits": ["otters"]}
	assert collected == [ToolResult(tool="fake_search", args={"query": "otters"}, result={"hits": ["otters"]})]


def test_agent_failed_tool_call_result_is_marked_error() -> None:
	agent: Agent[None, str] = Agent(FunctionModel(_tool_then_text, stream_function=_stream_tool_then_text))

	@agent.tool_plain
	def fake_search(query: str) -> dict[str, Any]:
		raise ModelRetry("catalogue unavailable")

	emitter = Emitter()
	collected: list[ToolResult] = []
	asyncio.run(agent.run("q", event_stream_handler=agent_event_handler(emitter, tool_results=collected)))
	results = [e for e in drain(emitter.queue) if e["type"] == "TOOL_CALL_RESULT"]
	assert len(results) == 1
	assert results[0]["content"].startswith("Error: ") and "catalogue unavailable" in results[0]["content"]
	assert collected == []


def test_agent_text_streamed_only_when_requested() -> None:
	emitter = Emitter()
	asyncio.run(_agent().run("q", event_stream_handler=agent_event_handler(emitter, stream_text=True)))
	events = drain(emitter.queue)
	assert "TEXT_MESSAGE_CONTENT" in types(events)
	assert emitter.message_open


async def _collect(emitter: Emitter, run: Any) -> list[dict[str, Any]]:
	return decode([chunk async for chunk in stream_run(emitter, run, thread_id="t", run_id="r")])


def test_stream_run_finishes() -> None:
	emitter = Emitter()

	async def run() -> None:
		with emitter.step("classify", attempt=1, max_attempts=None, model=None):
			pass
		emitter.custom("serka.outcome", {"status": "accepted"})

	events = asyncio.run(_collect(emitter, run))
	assert types(events) == ["RUN_STARTED", "STEP_STARTED", "CUSTOM", "STEP_FINISHED", "CUSTOM", "RUN_FINISHED"]


def test_stream_run_errors_when_stage_raises() -> None:
	emitter = Emitter()

	async def run() -> None:
		with emitter.step("execute", attempt=1, max_attempts=1, model=None):
			raise RuntimeError("MCP server unavailable")

	events = asyncio.run(_collect(emitter, run))
	assert types(events) == ["RUN_STARTED", "STEP_STARTED", "CUSTOM", "RUN_ERROR"]
	assert events[-1]["message"] == "Sorry, something went wrong while answering. Please try again."


def test_stream_run_error_closes_open_answer_message() -> None:
	emitter = Emitter()

	async def run() -> None:
		emitter.text_delta("partial answer")
		raise RuntimeError("evaluate model throttled")

	events = asyncio.run(_collect(emitter, run))
	assert types(events)[-3:] == ["TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END", "RUN_ERROR"]
	assert "throttled" not in events[-1]["message"]
