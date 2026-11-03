import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import fields
from typing import Any

import pytest
from fastmcp.exceptions import ToolError
from pydantic_ai.messages import (
	ModelMessage,
	ModelRequest,
	ModelResponse,
	TextPart,
	ToolCallPart,
	ToolReturnPart,
	UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_graph import End, GraphRunContext

from serka import prompts
from serka.chat.events import Emitter, ToolResult, stream_run
from serka.chat.models import StageModels
from serka.chat.pipeline import (
	Answer,
	ChatDeps,
	ChatState,
	Classification,
	Classify,
	Draft,
	Evaluate,
	Evaluation,
	Execute,
	Plan,
	RetrievalPlan,
	Refuse,
	Route,
	SearchParams,
	Synthesize,
	best_draft,
	build_graph,
	render_tool_results,
	run_chat,
)
from serka.chat.pipeline import _search_args as search_args_of
from tests.sse import answer_text, customs, decode, drain, steps, types

# --- scripted models and fakes ---


class Scripted:
	"""A FunctionModel that returns the given outputs in order: str -> text, dict -> structured output."""

	def __init__(self, *outputs: str | dict[str, Any], name: str = "scripted") -> None:
		self.outputs = list(outputs)
		self.prompts: list[list[ModelMessage]] = []
		self.model = FunctionModel(self._fn, stream_function=self._stream, model_name=name)

	def _next(self, messages: list[ModelMessage]) -> str | dict[str, Any]:
		self.prompts.append(messages)
		assert self.outputs, "scripted model called more times than scripted"
		return self.outputs.pop(0)

	def _fn(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
		out = self._next(messages)
		if isinstance(out, str):
			return ModelResponse(parts=[TextPart(out)])
		return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, out)])

	async def _stream(self, messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
		out = self._next(messages)
		if isinstance(out, str):
			for i in range(0, len(out), 5):
				yield out[i : i + 5]
		else:
			yield {0: DeltaToolCall(name=info.output_tools[0].name, json_args=json.dumps(out))}

	def user_prompt(self, call: int = -1) -> str:
		return "\n".join(
			str(p.content)
			for m in self.prompts[call]
			if isinstance(m, ModelRequest)
			for p in m.parts
			if isinstance(p, UserPromptPart)
		)


def _unused(stage: str) -> Model:
	def fail(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
		raise AssertionError(f"{stage} model should not be called")

	return FunctionModel(fail, model_name=f"unused-{stage}")


def stage_models(**overrides: Model | Scripted) -> StageModels:
	values = {f.name: _unused(f.name) for f in fields(StageModels)}
	for name, model in overrides.items():
		values[name] = model.model if isinstance(model, Scripted) else model
	return StageModels(**values)


SEARCH_RESULT = {
	"@context": {"dcat": "http://www.w3.org/ns/dcat#"},
	"@graph": [{"entity": {"@id": "https://catalogue.ceh.ac.uk/id/1", "title": "River flow data"}, "score": 0.9}],
	"meta": {"took_ms": 3},
}
BBOX = {"north": 53.4, "south": 51.4, "east": -2.6, "west": -5.3}


class FakeTools:
	def __init__(self, *, geocode_fails: bool = False) -> None:
		self.calls: list[tuple[str, dict[str, Any]]] = []
		self.geocode_fails = geocode_fails

	async def __call__(self, name: str, args: dict[str, Any]) -> Any:
		self.calls.append((name, args))
		if name == "geocode_location":
			if self.geocode_fails:
				raise ToolError("Could not geocode location 'Atlantis'")
			return {"name": "Wales", "boundary": BBOX}
		return SEARCH_RESULT


def insight_toolset() -> FunctionToolset[Any]:
	toolset: FunctionToolset[Any] = FunctionToolset()

	@toolset.tool_plain
	def search(query: str) -> dict[str, Any]:
		return SEARCH_RESULT

	@toolset.tool_plain
	def get_contributors(id: str) -> dict[str, Any]:
		return {"@graph": [{"name": "Dr. Alice Whitfield", "role": "author"}]}

	return toolset


def tool_calling_model(name: str = "haiku") -> FunctionModel:
	"""Calls search, then get_contributors with the id it found, then replies 'done'."""

	def step(messages: list[ModelMessage]) -> list[str]:
		return [p.tool_name for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]

	async def stream(messages: list[ModelMessage], info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
		done = step(messages)
		if not done:
			yield {0: DeltaToolCall(name="search", json_args='{"query": "river wye invertebrates"}')}
		elif done == ["search"]:
			yield {0: DeltaToolCall(name="get_contributors", json_args='{"id": "https://catalogue.ceh.ac.uk/id/1"}')}
		else:
			yield "done"

	def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
		raise AssertionError("execute agent should be streamed")

	return FunctionModel(fn, stream_function=stream, model_name=name)


def make_deps(models: StageModels, tools: FakeTools | None = None) -> ChatDeps:
	return ChatDeps(models=models, call_tool=tools or FakeTools(), toolset=insight_toolset(), emitter=Emitter())


def ctx(state: ChatState, deps: ChatDeps) -> GraphRunContext[ChatState, ChatDeps]:
	return GraphRunContext(state=state, deps=deps)


def run_node(node: Any, state: ChatState, deps: ChatDeps) -> Any:
	return asyncio.run(node.run(ctx(state, deps)))


IN_SCOPE_KEYWORD = {"category": "keyword", "reason": "dataset search"}
IN_SCOPE_INSIGHT = {"category": "insight", "reason": "needs reasoning"}
OUT_OF_SCOPE = {"category": "out_of_scope", "reason": "coding request"}
KEYWORD = Classification.model_validate(IN_SCOPE_KEYWORD)
INSIGHT = Classification.model_validate(IN_SCOPE_INSIGHT)
PARAMS = {"query": "river flow", "return_type": "Dataset", "location": None}
PLAN = {"summary": "Find datasets then contributors.", "steps": ["search", "get_contributors"]}
ANSWER = "Daily flows are in [River flow data](https://catalogue.ceh.ac.uk/id/1)."


def ev(passed: bool, score: int, problem: str = "none", feedback: str = "ok") -> dict[str, Any]:
	return {"passed": passed, "score": score, "problem": problem, "feedback": feedback}


# --- 4.3 Classify / Route / Refuse ---


def test_classify_in_scope_routes() -> None:
	deps = make_deps(stage_models(classify=Scripted(IN_SCOPE_KEYWORD)))
	state = ChatState(query="what datasets cover soil carbon in UK uplands?")
	assert isinstance(run_node(Classify(), state, deps), Route)
	events = drain(deps.emitter.queue)
	assert steps(events) == ["classify"]
	assert customs(events, "serka.classification") == [{"inScope": True, "label": "keyword", "reason": "dataset search"}]
	assert customs(events, "serka.step")[0]["maxAttempts"] is None


def test_classify_survives_two_invalid_outputs() -> None:
	invalid = {"category": "out-of-scope", "reason": "bad enum value"}
	classifier = Scripted(invalid, invalid, IN_SCOPE_KEYWORD)
	deps = make_deps(stage_models(classify=classifier))
	assert isinstance(run_node(Classify(), ChatState(query="river flow"), deps), Route)
	assert not classifier.outputs  # all three responses were used


def test_classify_out_of_scope_refuses() -> None:
	deps = make_deps(stage_models(classify=Scripted(OUT_OF_SCOPE)))
	state = ChatState(query="write me a Python function to sort a list")
	assert isinstance(run_node(Classify(), state, deps), Refuse)
	assert customs(drain(deps.emitter.queue), "serka.classification")[0]["label"] is None


def test_classify_uses_history_for_follow_up() -> None:
	classify = Scripted(IN_SCOPE_KEYWORD)
	deps = make_deps(stage_models(classify=classify))
	history: list[ModelMessage] = [
		ModelRequest(parts=[UserPromptPart("which datasets cover river flow?")]),
		ModelResponse(parts=[TextPart("The [River flow data](https://x) dataset...")]),
	]
	state = ChatState(query="what about in Wales?", history=history)
	assert isinstance(run_node(Classify(), state, deps), Route)
	seen = classify.user_prompt()
	assert "which datasets cover river flow?" in seen and "what about in Wales?" in seen


@pytest.mark.parametrize(("label", "max_attempts", "answer_model"), [("keyword", 1, "nova-lite"), ("insight", 3, "sonnet")])
def test_route_emits_attempts_and_metadata(label: str, max_attempts: int, answer_model: str) -> None:
	models = stage_models(synthesize_keyword=TestModel(model_name="nova-lite"), synthesize_insight=TestModel(model_name="sonnet"))
	deps = make_deps(models)
	state = ChatState(query="q", classification=Classification(category=label, reason="r"))  # type: ignore[arg-type]
	assert isinstance(run_node(Route(), state, deps), Plan)
	assert (state.label, state.max_attempts, state.attempt) == (label, max_attempts, 1)
	events = drain(deps.emitter.queue)
	meta = next(e for e in events if e["type"] == "RUN_METADATA")
	assert meta["model"] == answer_model and meta["models"] == models.ids()
	assert customs(events, "serka.step")[0]["maxAttempts"] == max_attempts


def test_refuse_emits_fixed_text_and_outcome() -> None:
	deps = make_deps(stage_models(classify=TestModel(model_name="nova-micro")))
	result = run_node(Refuse(), ChatState(query="q"), deps)
	assert result == End(Answer(text=prompts.REFUSAL_MESSAGE, status="refused"))
	events = drain(deps.emitter.queue)
	assert answer_text(events) == prompts.REFUSAL_MESSAGE
	assert next(e for e in events if e["type"] == "RUN_METADATA")["model"] == "nova-micro"
	assert types(events)[-1] == "CUSTOM"
	assert customs(events, "serka.outcome") == [
		{"status": "refused", "path": None, "attemptsUsed": 0, "maxAttempts": None, "score": None, "feedback": None}
	]


# --- 4.4 Plan ---


def test_plan_keyword_yields_search_params() -> None:
	deps = make_deps(stage_models(plan_keyword=TestModel(custom_output_args={"query": "bats", "location": "Wales"})))
	state = ChatState(query="bat habitat in Wales", classification=KEYWORD)
	assert isinstance(run_node(Plan(), state, deps), Execute)
	assert state.plan == SearchParams(query="bats", location="Wales")
	plan_event = customs(drain(deps.emitter.queue), "serka.plan")[0]
	assert set(plan_event) == {"summary", "steps"}
	assert plan_event["steps"][0].startswith("geocode_location")


def test_plan_insight_yields_summary_and_steps() -> None:
	deps = make_deps(stage_models(plan_insight=TestModel(custom_output_args=PLAN)))
	state = ChatState(query="who funded Wye monitoring?", classification=INSIGHT)
	run_node(Plan(), state, deps)
	assert state.plan == RetrievalPlan.model_validate(PLAN)
	assert customs(drain(deps.emitter.queue), "serka.plan") == [PLAN]


def test_plan_insight_data_retry_gets_previous_plan_and_feedback() -> None:
	planner = Scripted(PLAN)
	deps = make_deps(stage_models(plan_insight=planner))
	state = ChatState(
		query="q", classification=INSIGHT, attempt=2, plan=RetrievalPlan(summary="old plan", steps=["a"]),
		drafts=[Draft(1, "d", Evaluation(**ev(False, 2, "data", "No funder data was retrieved.")))],
	)
	run_node(Plan(), state, deps)
	prompt = planner.user_prompt()
	assert "old plan" in prompt and "No funder data was retrieved." in prompt


# --- 4.5 Execute ---


def test_execute_keyword_geocodes_then_searches_without_a_model() -> None:
	tools = FakeTools()
	deps = make_deps(stage_models(), tools)
	state = ChatState(query="river flow Wales", classification=KEYWORD, plan=SearchParams(query="river flow", location="Wales"))
	assert isinstance(run_node(Execute(), state, deps), Synthesize)
	assert [name for name, _ in tools.calls] == ["geocode_location", "search"]
	assert tools.calls[1][1] == {"query": "river flow", "return_type": "dcat:Dataset", "bounding_box": BBOX}
	events = drain(deps.emitter.queue)
	tool_events = [e for e in events if e["type"].startswith("TOOL_CALL")]
	assert [e["type"] for e in tool_events] == ["TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END", "TOOL_CALL_RESULT"] * 2
	assert [e["toolCallName"] for e in tool_events if e["type"] == "TOOL_CALL_START"] == ["geocode_location", "search"]
	assert customs(events, "serka.step")[0]["model"] is None
	assert state.tool_results == [ToolResult(tool="search", args=tools.calls[1][1], result=SEARCH_RESULT)]


def test_render_tool_results_keeps_only_graph_hits() -> None:
	rendered = render_tool_results([ToolResult("search", {"query": "q"}, SEARCH_RESULT)])
	assert "River flow data" in rendered
	assert "@context" not in rendered and "took_ms" not in rendered


def test_execute_keyword_without_location_searches_once() -> None:
	tools = FakeTools()
	deps = make_deps(stage_models(), tools)
	state = ChatState(query="nitrogen deposition uplands", classification=KEYWORD, plan=SearchParams(query="nitrogen deposition uplands"))
	run_node(Execute(), state, deps)
	assert [name for name, _ in tools.calls] == ["search"]


def test_execute_keyword_unknown_location_still_searches() -> None:
	tools = FakeTools(geocode_fails=True)
	deps = make_deps(stage_models(), tools)
	state = ChatState(query="q", classification=KEYWORD, plan=SearchParams(query="q", location="Atlantis"))
	run_node(Execute(), state, deps)
	assert [name for name, _ in tools.calls] == ["geocode_location", "search"]
	assert "bounding_box" not in tools.calls[1][1]
	assert types(drain(deps.emitter.queue)).count("TOOL_CALL_RESULT") == 2
	assert "NOT filtered by location" in render_tool_results(state.tool_results)


def test_execute_keyword_search_error_fails_run() -> None:
	class FailingSearch(FakeTools):
		async def __call__(self, name: str, args: dict[str, Any]) -> Any:
			raise RuntimeError("MCP down")

	deps = make_deps(stage_models(), FailingSearch())
	state = ChatState(query="q", classification=KEYWORD, plan=SearchParams(query="q"))
	with pytest.raises(RuntimeError):
		run_node(Execute(), state, deps)


def test_plan_keyword_rejects_non_iso_dates() -> None:
	planner = Scripted({"query": "soil", "published_after": "last year"}, {"query": "soil", "published_after": "2020-01-01"})
	deps = make_deps(stage_models(plan_keyword=planner))
	state = ChatState(query="soil datasets since 2020", classification=KEYWORD)
	run_node(Plan(), state, deps)
	assert isinstance(state.plan, SearchParams)
	assert search_args_of(state.plan)["published_after"] == "2020-01-01"


def test_execute_insight_collects_model_chosen_tool_results() -> None:
	tools = FakeTools()
	deps = make_deps(stage_models(execute_insight=tool_calling_model()), tools)
	state = ChatState(query="q", classification=INSIGHT, plan=RetrievalPlan.model_validate(PLAN), tool_results=[ToolResult("old", {}, 1)])
	run_node(Execute(), state, deps)
	assert tools.calls == []
	assert [r.tool for r in state.tool_results] == ["search", "get_contributors"]
	assert state.tool_results[0].result == SEARCH_RESULT
	assert state.tool_results[1].args == {"id": "https://catalogue.ceh.ac.uk/id/1"}
	events = drain(deps.emitter.queue)
	assert [e["toolCallName"] for e in events if e["type"] == "TOOL_CALL_START"] == ["search", "get_contributors"]
	assert "TEXT_MESSAGE_CONTENT" not in types(events)


# --- 4.6 Synthesize ---


def test_synthesize_keyword_streams_live_and_leaves_message_open() -> None:
	deps = make_deps(stage_models(synthesize_keyword=Scripted(ANSWER)))
	state = ChatState(query="q", classification=KEYWORD, tool_results=[ToolResult("search", {}, SEARCH_RESULT["@graph"])])
	assert isinstance(run_node(Synthesize(), state, deps), Evaluate)
	events = drain(deps.emitter.queue)
	assert answer_text(events) == ANSWER
	assert "TEXT_MESSAGE_END" not in types(events)
	assert deps.emitter.message_open
	assert state.drafts == [Draft(attempt=1, text=ANSWER)]


def test_synthesize_insight_emits_draft_only() -> None:
	deps = make_deps(stage_models(synthesize_insight=Scripted(ANSWER)))
	state = ChatState(query="q", classification=INSIGHT)
	run_node(Synthesize(), state, deps)
	events = drain(deps.emitter.queue)
	assert "TEXT_MESSAGE_CONTENT" not in types(events)
	assert customs(events, "serka.draft") == [{"attempt": 1, "text": ANSWER}]


def test_synthesize_writing_retry_reuses_results_and_gets_feedback() -> None:
	writer = Scripted("better answer")
	tools = FakeTools()
	deps = make_deps(stage_models(synthesize_insight=writer), tools)
	state = ChatState(
		query="q", classification=INSIGHT, attempt=2,
		tool_results=[ToolResult("search", {}, SEARCH_RESULT)],
		drafts=[Draft(1, "first draft", Evaluation(**ev(False, 3, "writing", "Cite the dataset title exactly.")))],
	)
	run_node(Synthesize(), state, deps)
	prompt = writer.user_prompt()
	assert "first draft" in prompt and "Cite the dataset title exactly." in prompt and "River flow data" in prompt
	assert tools.calls == []
	assert state.drafts[-1] == Draft(attempt=2, text="better answer")


# --- 4.7 Evaluate (whole-graph scenarios with scripted models) ---


def run_graph(query: str, models: StageModels, tools: FakeTools | None = None) -> tuple[Answer, list[dict[str, Any]], ChatState]:
	deps = make_deps(models, tools)
	state = ChatState(query=query)
	answer = asyncio.run(run_chat(build_graph(), state, deps))
	return answer, drain(deps.emitter.queue), state


def keyword_models(*evaluations: dict[str, Any]) -> StageModels:
	return stage_models(
		classify=Scripted(IN_SCOPE_KEYWORD),
		plan_keyword=Scripted(PARAMS),
		synthesize_keyword=Scripted(ANSWER),
		evaluate=Scripted(*evaluations),
	)


def insight_models(*, plans: int, drafts: list[str], evaluations: list[dict[str, Any]], executes: int) -> StageModels:
	return stage_models(
		classify=Scripted(IN_SCOPE_INSIGHT),
		plan_insight=Scripted(*([PLAN] * plans)),
		execute_insight=tool_calling_model() if executes else _unused("execute_insight"),
		synthesize_insight=Scripted(*drafts),
		evaluate=Scripted(*evaluations),
	)


def test_accepted_on_attempt_1() -> None:
	answer, events, _ = run_graph("river flow", keyword_models(ev(True, 5)))
	assert answer == Answer(text=ANSWER, status="accepted")
	assert answer_text(events) == ANSWER
	assert customs(events, "serka.evaluation") == [{"attempt": 1, "passed": True, "score": 5, "problem": "none", "feedback": "ok"}]
	assert customs(events, "serka.outcome") == [
		{"status": "accepted", "path": "keyword", "attemptsUsed": 1, "maxAttempts": 1, "score": 5, "feedback": "ok"}
	]


def test_keyword_limit_reached_appends_note() -> None:
	answer, events, _ = run_graph("river flow", keyword_models(ev(False, 2, "data", "Too few results.")))
	note = f"\n\n{prompts.INCOMPLETE_ANSWER_NOTE}"
	assert answer == Answer(text=ANSWER + note, status="limit_reached")
	assert answer_text(events) == ANSWER + note
	assert types(events).count("TEXT_MESSAGE_START") == 1 and types(events).count("TEXT_MESSAGE_END") == 1
	assert steps(events).count("plan") == 1
	assert customs(events, "serka.outcome")[0] == {
		"status": "limit_reached", "path": "keyword", "attemptsUsed": 1, "maxAttempts": 1, "score": 2, "feedback": "Too few results."
	}


def test_insight_data_retry_replans_and_re_executes() -> None:
	models = insight_models(
		plans=2, drafts=["draft 1", "draft 2"], evaluations=[ev(False, 2, "data", "No funders."), ev(True, 4)], executes=2
	)
	answer, events, state = run_graph("who funded Wye monitoring?", models)
	assert steps(events) == [
		"classify", "route", "plan", "execute", "synthesize", "evaluate",
		"plan", "execute", "synthesize", "evaluate",
	]
	second_plan = [s for s in customs(events, "serka.step") if s["step"] == "plan"][1]
	assert (second_plan["attempt"], second_plan["maxAttempts"]) == (2, 3)
	assert answer_text(events) == "draft 2"
	assert len(state.tool_results) == 2  # replaced, not accumulated
	assert customs(events, "serka.outcome")[0]["status"] == "accepted"
	assert customs(events, "serka.outcome")[0]["attemptsUsed"] == 2


def test_insight_writing_retry_skips_retrieval() -> None:
	models = insight_models(
		plans=1, drafts=["draft 1", "draft 2"], evaluations=[ev(False, 3, "writing", "Fix links."), ev(True, 5)], executes=1
	)
	answer, events, _ = run_graph("q", models)
	assert steps(events) == ["classify", "route", "plan", "execute", "synthesize", "evaluate", "synthesize", "evaluate"]
	assert answer_text(events) == "draft 2"
	assert customs(events, "serka.draft") == [{"attempt": 1, "text": "draft 1"}, {"attempt": 2, "text": "draft 2"}]


def test_three_failed_attempts_return_best_draft() -> None:
	models = insight_models(
		plans=1,
		drafts=["draft 1", "draft 2", "draft 3"],
		evaluations=[ev(False, 3, "writing", "f1"), ev(False, 2, "writing", "f2"), ev(False, 2, "writing", "f3")],
		executes=1,
	)
	answer, events, _ = run_graph("q", models)
	note = f"\n\n{prompts.INCOMPLETE_ANSWER_NOTE}"
	assert answer == Answer(text="draft 1" + note, status="limit_reached")
	assert answer_text(events) == "draft 1" + note
	assert steps(events).count("evaluate") == 3
	assert customs(events, "serka.outcome")[0] == {
		"status": "limit_reached", "path": "insight", "attemptsUsed": 3, "maxAttempts": 3, "score": 3, "feedback": "f1"
	}


def test_evaluate_sees_history() -> None:
	evaluator = Scripted(ev(True, 5))
	deps = make_deps(stage_models(evaluate=evaluator))
	history: list[ModelMessage] = [ModelRequest(parts=[UserPromptPart("which datasets cover river flow?")])]
	state = ChatState(query="what about in Wales?", history=history, classification=KEYWORD, drafts=[Draft(1, ANSWER)])
	deps.emitter.text_delta(ANSWER)
	run_node(Evaluate(), state, deps)
	assert "which datasets cover river flow?" in evaluator.user_prompt()


def test_evaluation_passed_and_problem_are_consistent() -> None:
	assert Evaluation(**ev(True, 4, "writing")).problem == "none"
	assert Evaluation(**ev(False, 2, "none")).problem == "writing"


def test_best_draft_ties_go_to_earliest() -> None:
	drafts = [Draft(1, "a", Evaluation(**ev(False, 2))), Draft(2, "b", Evaluation(**ev(False, 2)))]
	assert best_draft(drafts).attempt == 1


# --- 4.8 End-to-end event contract ---


async def _stream(query: str, models: StageModels) -> list[dict[str, Any]]:
	deps = make_deps(models)
	graph = build_graph()

	async def run() -> None:
		await run_chat(graph, ChatState(query=query), deps)

	return decode([c async for c in stream_run(deps.emitter, run, thread_id="t", run_id="r")])


def _assert_framing(events: list[dict[str, Any]]) -> None:
	t = types(events)
	assert t[0] == "RUN_STARTED" and t[-1] == "RUN_FINISHED"
	assert events[-2]["type"] == "CUSTOM" and events[-2]["name"] == "serka.outcome"
	assert t.index("RUN_METADATA") < t.index("TEXT_MESSAGE_CONTENT")
	assert t.count("TEXT_MESSAGE_START") == 1
	assert t.count("STEP_STARTED") == t.count("STEP_FINISHED")
	for i, e in enumerate(events):
		if e["type"] == "STEP_STARTED":
			assert events[i + 1]["name"] == "serka.step" and events[i + 1]["value"]["step"] == e["stepName"]


def test_keyword_run_event_sequence() -> None:
	events = asyncio.run(_stream("river flow", keyword_models(ev(True, 5))))
	_assert_framing(events)
	assert steps(events) == ["classify", "route", "plan", "execute", "synthesize", "evaluate"]
	assert {s["attempt"] for s in customs(events, "serka.step")} == {1}
	execute = events[[i for i, e in enumerate(events) if e.get("stepName") == "execute"][0] :]
	assert [e["toolCallName"] for e in execute if e["type"] == "TOOL_CALL_START"] == ["search"]


def test_refusal_event_sequence() -> None:
	events = asyncio.run(_stream("write me a Python function", stage_models(classify=Scripted(OUT_OF_SCOPE))))
	_assert_framing(events)
	assert steps(events) == ["classify", "refuse"]
	assert answer_text(events) == prompts.REFUSAL_MESSAGE
	assert "TOOL_CALL_START" not in types(events)
	assert customs(events, "serka.outcome")[0]["status"] == "refused"
