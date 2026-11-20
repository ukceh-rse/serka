"""The chat pipeline as a pydantic-graph state machine.

Cache -> End (cached answer) | Classify; Classify -> Refuse | Route; Route -> InsightLimit | Plan;
Plan -> Execute -> Synthesize -> Evaluate; Evaluate -> Plan (data retry) | Synthesize (writing retry) | End.
See openspec specs `chat-agent` and `chat-agent-events`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent
from pydantic_ai.exceptions import IncompleteToolCall, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.usage import RunUsage, UsageLimits
from pydantic_graph import BaseNode, End, Graph, GraphBuilder, GraphRunContext

from serka import prompts
from serka.answer_cache import AnswerCache, CachedAnswer
from serka.chat.events import Emitter, ToolCaller, ToolResult, agent_event_handler, call_tool
from serka.chat.models import StageModels
from serka.catalogue import Order, SortBy, search_args

logger = logging.getLogger(__name__)

Label = Literal["keyword", "insight"]
Problem = Literal["none", "data", "writing"]
Status = Literal["accepted", "limit_reached", "refused", "insight_limit_reached", "cached"]

MAX_ATTEMPTS: dict[Label, int] = {"keyword": 1, "insight": 2}
MAX_TOKENS = {
	"classify": 300,
	"plan_keyword": 300,
	"plan_insight": 2_000,
	"execute_insight": 2_000,
	"synthesize_keyword": 2_000,
	"synthesize_insight": 3_000,
	"evaluate": 4_000,
}
"""Output limit per model response. Sonnet and Haiku thinking uses the same limit, so these include headroom."""
EXECUTE_USAGE_LIMITS = UsageLimits(request_limit=10, total_tokens_limit=200_000)
"""Per run, across attempts. Tokens need a limit too: the execute agent sees uncapped tool results (see MAX_RESULT_CHARS)."""
MAX_RESULT_CHARS = 8000
"""Cap on each tool result's size in downstream prompts (search hits and read files can be large)."""
CLASSIFY_OUTPUT_RETRIES = 2
"""Nova models occasionally return invalid structured output; a failed classify ends the run."""


# Structured stage outputs


class Classification(BaseModel):
	# Reason comes first so the model reasons before committing to a category: with category
	# first, Nova Micro refused in-scope questions and wrote the reason afterwards to fit.
	reason: str = Field(description="One sentence explaining the classification.")
	# One required enum rather than a bool plus a nullable label: small models (Nova Micro)
	# often omit nullable fields from structured output.
	category: Literal["keyword", "insight", "out_of_scope"] = Field(description="out_of_scope, or the in-scope label.")

	@property
	def in_scope(self) -> bool:
		return self.category != "out_of_scope"

	@property
	def label(self) -> Label | None:
		return None if self.category == "out_of_scope" else self.category


OKFType = Literal["dataset", "document", "person", "organisation", "grant", "theme"]


class SearchParams(BaseModel):
	# A string rather than nullable: small models often omit nullable fields from structured output.
	query: str = Field(default="", description="Subject search terms; empty for a pure ranking request.")
	type: OKFType = "dataset"
	location: str | None = Field(default=None, description="UK place name to restrict results to.")
	# Real dates, so an unusable value ("last year") is caught as an output retry, not a search failure.
	published_after: date | None = Field(default=None, description="ISO date YYYY-MM-DD.")
	published_before: date | None = Field(default=None, description="ISO date YYYY-MM-DD.")
	sort_by: SortBy | None = Field(default=None, description="Rank results by citations or publication date.")
	order: Order | None = Field(default=None, description="Sort order; descending when omitted.")


class RetrievalPlan(BaseModel):
	summary: str = Field(description="Short summary of the retrieval approach.")
	steps: list[str] = Field(description="Ordered retrieval steps.")


class Evaluation(BaseModel):
	passed: bool
	score: int = Field(ge=1, le=5)
	problem: Problem
	feedback: str

	@model_validator(mode="after")
	def _consistent(self) -> Evaluation:
		"""A pass has no problem; a failure always has one (`writing` when the model gave none)."""
		if self.passed:
			self.problem = "none"
		elif self.problem == "none":
			self.problem = "writing"
		return self


# State, deps and output


@dataclass
class Draft:
	attempt: int
	text: str
	evaluation: Evaluation | None = None


@dataclass
class ChatState:
	query: str
	history: list[ModelMessage] = field(default_factory=list)
	classification: Classification | None = None
	attempt: int = 1
	plan: SearchParams | RetrievalPlan | None = None
	tool_results: list[ToolResult] = field(default_factory=list)
	drafts: list[Draft] = field(default_factory=list)
	execute_usage: RunUsage = field(default_factory=RunUsage)
	"""Shared by the run's retrievals, so EXECUTE_USAGE_LIMITS covers all its attempts."""
	retrieval_stopped: bool = False
	"""A retrieval limit stopped retrieval, so another attempt is not expected to gather more."""

	@property
	def label(self) -> Label | None:
		return self.classification.label if self.classification else None

	@property
	def max_attempts(self) -> int | None:
		"""None before routing (out of scope, or not yet classified)."""
		return MAX_ATTEMPTS[self.label] if self.label else None

	@property
	def last_evaluation(self) -> Evaluation | None:
		"""The evaluation that triggered the current retry; None on the first attempt."""
		return self.drafts[-1].evaluation if self.drafts else None


@dataclass
class ChatDeps:
	models: StageModels
	call_tool: ToolCaller
	"""Calls a catalogue tool directly (keyword path)."""
	toolset: AbstractToolset[Any]
	"""Catalogue tools offered to the insight execute agent."""
	emitter: Emitter
	claim_insight: Callable[[], bool]
	"""Takes one of today's insight slots; False when none is left."""
	answer_cache: AnswerCache = field(default_factory=lambda: AnswerCache(None))
	"""Accepted first-turn answers; disabled by default."""
	count_run: Callable[[], None] = lambda: None
	"""Counts the run towards the daily caps; called once the run needs the models."""


@dataclass
class Answer:
	text: str
	status: Status


Ctx = GraphRunContext[ChatState, ChatDeps]


# Helpers


def _step(ctx: Ctx, name: str, model: Model | None) -> Any:
	return ctx.deps.emitter.step(
		name,
		attempt=ctx.state.attempt,
		max_attempts=ctx.state.max_attempts,
		model=model.model_name if model else None,
	)


def _render_hit(hit: dict[str, Any]) -> str:
	"""`title (resource): text`, with the concept's type and ID, and citations and date when known."""
	c = hit.get("concept") or {}
	details = [f"{c.get('type')} {c.get('id')}"]
	if c.get("citations") is not None:
		details.append(f"{c['citations']} citations")
	if c.get("published"):
		details.append(f"published {c['published']}")
	resource = f" ({c['resource']})" if c.get("resource") else ""
	text = " ".join(str(hit.get("text") or "").split())
	return f"- {c.get('title')}{resource} [{', '.join(details)}]: {text}"


def _render_result(result: Any) -> str:
	if isinstance(result, dict) and "hits" in result:
		lines = [_render_hit(h) for h in result["hits"]]
		lines.append(f"({result.get('total', len(result['hits']))} matches in total)")
		lines += [f"Warning: {w}" for w in result.get("warnings") or []]
		return "\n".join(lines) if result["hits"] else "(no matches)\n" + "\n".join(lines[1:])
	if isinstance(result, str):
		return result
	return json.dumps(result, default=str, ensure_ascii=False)


_FILTER_ARGS = ("theme", "linked", "bounding_box", "published_after", "published_before", "min_citations")


def _counted(args: dict[str, Any]) -> str:
	"""What an aggregate call counted, in words, so answers can say it."""
	group_by = args.get("group_by")
	noun = f"{args.get('type') or 'dataset'}s"
	if group_by in (None, "year") and args.get("query"):
		noun += f" that mention any of: {args['query']}"
	if any(args.get(k) is not None for k in _FILTER_ARGS):
		noun += " matching the filters"
	if group_by is None:
		return f"Number of {noun}"
	if group_by == "year":
		return f"Number of {noun} per publication year"
	if group_by == "type":
		return "Number of catalogue concepts of each type"
	role = f" with the role {args['role']}" if args.get("role") else ""
	order = "summed citations" if args.get("sort_by") == "citations" else "number of datasets"
	return f"{group_by.capitalize()}s{role}, ranked by {order}, with the datasets they are related to and those datasets' summed citations"


def _render_aggregate(result: dict[str, Any], args: dict[str, Any]) -> str:
	lines = [f"{_counted(args)}:"]
	if "groups" not in result:
		total = f"{result.get('total', 0)}"
		if result.get("citations") is not None:
			total += f" (cited {result['citations']} times in total)"
		lines.append(total)
	else:
		for g in result["groups"]:
			if "concepts" in g:
				lines.append(f"- {g['title']}: {g['concepts']}")
			else:
				ident = "" if g["id"] == g["title"] else f" ({g['id']})"
				lines.append(f"- {g['title']}{ident}: {g['datasets']} datasets, {g['citations']} citations")
		if not result["groups"]:
			lines.append("(no groups)")
		covered = "concepts" if args.get("group_by") == "type" else "matching datasets"
		lines.append(f"({result.get('total_groups', len(result['groups']))} groups in total, covering {result.get('total', 0)} {covered})")
	lines += [f"Warning: {w}" for w in result.get("warnings") or []]
	return "\n".join(lines)


def render_tool_results(tool_results: Sequence[ToolResult]) -> str:
	if not tool_results:
		return "(no data was retrieved)"
	parts = []
	for r in tool_results:
		if r.tool == "aggregate" and isinstance(r.result, dict):
			body = _render_aggregate(r.result, r.args)
		else:
			body = _render_result(r.result)
		if len(body) > MAX_RESULT_CHARS:
			body = body[:MAX_RESULT_CHARS] + " ...[truncated]"
		parts.append(f"## {r.tool}({json.dumps(r.args, default=str)})\n{body}")
	return "\n\n".join(parts)


def _plan_text(plan: SearchParams | RetrievalPlan | None) -> str:
	return plan.model_dump_json() if plan is not None else "(none)"


async def _run(
	model: Model,
	instructions: str,
	prompt: str,
	output_type: Any = str,
	*,
	stage: str,
	history: Sequence[ModelMessage] | None = None,
	toolsets: Sequence[AbstractToolset[Any]] | None = None,
	event_stream_handler: Callable[..., Awaitable[None]] | None = None,
	output_retries: int | None = None,
	usage_limits: UsageLimits | None = None,
	usage: RunUsage | None = None,
) -> Any:
	agent: Agent[None, Any] = Agent(
		model,
		instructions=instructions,
		output_type=output_type,
		toolsets=toolsets,
		retries={"output": output_retries} if output_retries is not None else None,
	)
	usage = RunUsage() if usage is None else usage
	max_tokens = MAX_TOKENS[stage]
	try:
		result = await agent.run(
			prompt,
			message_history=history,
			event_stream_handler=event_stream_handler,
			model_settings={"max_tokens": max_tokens},
			usage_limits=usage_limits,
			usage=usage,
		)
	finally:
		# In `finally` because reaching a usage limit or failing a call still spends tokens.
		# With shared usage, as in execute_insight, these are the totals so far.
		logger.info(
			"model usage stage=%s model=%s requests=%d input_tokens=%d output_tokens=%d max_tokens=%d",
			stage, model.model_name, usage.requests, usage.input_tokens, usage.output_tokens, max_tokens,
		)
	return result.output


def _fixed_answer(ctx: Ctx, step: str, message: str, status: Status, path: Label | None) -> End[Answer]:
	"""Ends a run with a fixed message and no attempts."""
	emitter = ctx.deps.emitter
	with _step(ctx, step, None):
		emitter.text(message)
	emitter.custom(
		"serka.outcome",
		{
			"status": status,
			"path": path,
			"attemptsUsed": 0,
			"maxAttempts": ctx.state.max_attempts,
			"score": None,
			"feedback": None,
		},
	)
	return End(Answer(text=message, status=status))


# Nodes


@dataclass
class Cache(BaseNode[ChatState, ChatDeps, Answer]):
	"""Answers a first-turn query from the answer cache, or counts the run and classifies it."""

	async def run(self, ctx: Ctx) -> Classify | End[Answer]:
		state, deps = ctx.state, ctx.deps
		if not state.history and deps.answer_cache.enabled:
			emitter = deps.emitter
			with _step(ctx, "cache", None):
				hit = await asyncio.to_thread(deps.answer_cache.lookup, state.query)
				if hit is not None:
					emitter.metadata(hit.model, deps.models.ids())
					emitter.text(hit.text)
			if hit is not None:
				emitter.custom(
					"serka.outcome",
					{"status": "cached", "path": hit.path, "attemptsUsed": 0, "maxAttempts": None, "score": hit.score, "feedback": None},
				)
				return End(Answer(text=hit.text, status="cached"))
		deps.count_run()
		return Classify()


@dataclass
class Classify(BaseNode[ChatState, ChatDeps, Answer]):
	async def run(self, ctx: Ctx) -> Refuse | Route:
		model = ctx.deps.models.classify
		with _step(ctx, "classify", model):
			c: Classification = await _run(
				model,
				prompts.CLASSIFY_PROMPT,
				ctx.state.query,
				Classification,
				stage="classify",
				history=ctx.state.history,
				output_retries=CLASSIFY_OUTPUT_RETRIES,
			)
			ctx.state.classification = c
			ctx.deps.emitter.custom("serka.classification", {"inScope": c.in_scope, "label": c.label, "reason": c.reason})
		return Route() if c.in_scope else Refuse()


@dataclass
class Route(BaseNode[ChatState, ChatDeps, Answer]):
	async def run(self, ctx: Ctx) -> InsightLimit | Plan:
		models = ctx.deps.models
		with _step(ctx, "route", None):
			answer_model = models.synthesize_keyword if ctx.state.label == "keyword" else models.synthesize_insight
			ctx.deps.emitter.metadata(answer_model.model_name, models.ids())
			# Claimed here so a run takes one slot however many attempts it uses.
			if ctx.state.label == "insight" and not ctx.deps.claim_insight():
				return InsightLimit()
		return Plan()


@dataclass
class InsightLimit(BaseNode[ChatState, ChatDeps, Answer]):
	async def run(self, ctx: Ctx) -> End[Answer]:
		return _fixed_answer(ctx, "limit", prompts.INSIGHT_LIMIT_MESSAGE, "insight_limit_reached", "insight")


@dataclass
class Refuse(BaseNode[ChatState, ChatDeps, Answer]):
	async def run(self, ctx: Ctx) -> End[Answer]:
		ctx.deps.emitter.metadata(ctx.deps.models.classify.model_name, ctx.deps.models.ids())
		return _fixed_answer(ctx, "refuse", prompts.REFUSAL_MESSAGE, "refused", None)


@dataclass
class Plan(BaseNode[ChatState, ChatDeps, Answer]):
	async def run(self, ctx: Ctx) -> Execute:
		state, emitter = ctx.state, ctx.deps.emitter
		if state.label == "keyword":
			model = ctx.deps.models.plan_keyword
			with _step(ctx, "plan", model):
				params: SearchParams = await _run(
					model,
					prompts.PLAN_KEYWORD_PROMPT,
					state.query,
					SearchParams,
					stage="plan_keyword",
					history=state.history,
				)
				state.plan = params
				emitter.custom("serka.plan", _keyword_plan_event(params, state.query))
		else:
			model = ctx.deps.models.plan_insight
			prompt = f"Question: {state.query}"
			retry = state.last_evaluation
			if retry and retry.problem == "data":
				prompt += f"\n\nPrevious plan: {_plan_text(state.plan)}\n\nEvaluator feedback: {retry.feedback}"
			with _step(ctx, "plan", model):
				plan: RetrievalPlan = await _run(
					model,
					prompts.PLAN_INSIGHT_PROMPT,
					prompt,
					RetrievalPlan,
					stage="plan_insight",
					history=state.history,
				)
				state.plan = plan
				emitter.custom("serka.plan", {"summary": plan.summary, "steps": plan.steps})
		return Execute()


def _search_args(params: SearchParams, fallback_query: str) -> dict[str, Any]:
	"""The direct search call. With neither terms nor a sort, the user's own text is the query."""
	query = params.query.strip() or (None if params.sort_by else fallback_query)
	return search_args(
		query,
		params.type,
		params.published_after.isoformat() if params.published_after else None,
		params.published_before.isoformat() if params.published_before else None,
		params.sort_by,
		params.order,
	)


def _keyword_plan_event(params: SearchParams, fallback_query: str) -> dict[str, Any]:
	steps = []
	if params.location:
		steps.append(f"geocode_location {json.dumps({'location': params.location})}")
	args = _search_args(params, fallback_query)
	steps.append(f"search {json.dumps(args)}" + (" within the location's bounding box" if params.location else ""))
	if params.sort_by:
		ranking = "most cited" if params.sort_by == "citations" else "most recently published"
		if params.order == "ascending":
			ranking = "least cited" if params.sort_by == "citations" else "earliest published"
		about = f" matching '{args['query']}'" if args.get("query") else ""
		summary = f"Find the {ranking} {params.type}s{about} in the catalogue."
	else:
		summary = f"Search the catalogue for {params.type}s matching '{args['query']}'."
	return {"summary": summary, "steps": steps}


@dataclass
class Execute(BaseNode[ChatState, ChatDeps, Answer]):
	async def run(self, ctx: Ctx) -> Synthesize:
		state, deps = ctx.state, ctx.deps
		previous_results = state.tool_results
		state.tool_results = []
		if state.label == "keyword":
			assert isinstance(state.plan, SearchParams)
			with _step(ctx, "execute", None):
				args = _search_args(state.plan, state.query)
				if state.plan.location:
					try:
						geo = await call_tool(deps.emitter, deps.call_tool, "geocode_location", {"location": state.plan.location})
						args["bounding_box"] = geo.result["boundary"]
					except ToolError:
						# Search without the location filter, and tell Synthesize/Evaluate so the answer says so.
						state.tool_results.append(
							ToolResult(
								tool="geocode_location",
								args={"location": state.plan.location},
								result=f"Location '{state.plan.location}' could not be found. "
								"The search results below are NOT filtered by location.",
							)
						)
				state.tool_results.append(await call_tool(deps.emitter, deps.call_tool, "search", args))
		else:
			model = deps.models.execute_insight
			with _step(ctx, "execute", model):
				try:
					await _run(
						model,
						prompts.EXECUTE_INSIGHT_PROMPT,
						f"Question: {state.query}\n\nPlan: {_plan_text(state.plan)}",
						stage="execute_insight",
						toolsets=[deps.toolset],
						event_stream_handler=agent_event_handler(deps.emitter, tool_results=state.tool_results),
						usage_limits=EXECUTE_USAGE_LIMITS,
						usage=state.execute_usage,
					)
				except (UsageLimitExceeded, IncompleteToolCall):
					# A partial answer is more useful than an error: compose from what was gathered,
					# or from the last attempt's data if the limit left this one with nothing.
					state.retrieval_stopped = True
					state.tool_results = state.tool_results or previous_results
		return Synthesize()


@dataclass
class Synthesize(BaseNode[ChatState, ChatDeps, Answer]):
	async def run(self, ctx: Ctx) -> Evaluate:
		state, emitter = ctx.state, ctx.deps.emitter
		keyword = state.label == "keyword"
		model = ctx.deps.models.synthesize_keyword if keyword else ctx.deps.models.synthesize_insight
		prompt = f"Query: {state.query}\n\nRetrieved catalogue data:\n{render_tool_results(state.tool_results)}"
		retry = state.last_evaluation
		if retry and retry.problem == "writing":
			prompt += f"\n\nPrevious draft:\n{state.drafts[-1].text}\n\nEvaluator feedback: {retry.feedback}"
		with _step(ctx, "synthesize", model):
			# Keyword answers (single attempt) stream live; Evaluate closes the message.
			text: str = await _run(
				model,
				prompts.SYNTHESIZE_PROMPT,
				prompt,
				stage="synthesize_keyword" if keyword else "synthesize_insight",
				history=state.history,
				event_stream_handler=agent_event_handler(emitter, stream_text=True) if keyword else None,
			)
			if not keyword:
				emitter.custom("serka.draft", {"attempt": state.attempt, "text": text})
			state.drafts.append(Draft(attempt=state.attempt, text=text))
		return Evaluate()


def best_draft(drafts: Sequence[Draft]) -> Draft:
	"""Highest-scoring draft; `max` keeps the first, so ties go to the earliest attempt."""
	return max(drafts, key=lambda d: d.evaluation.score if d.evaluation else 0)


@dataclass
class Evaluate(BaseNode[ChatState, ChatDeps, Answer]):
	async def run(self, ctx: Ctx) -> Plan | Synthesize | End[Answer]:
		state, emitter = ctx.state, ctx.deps.emitter
		draft = state.drafts[-1]
		model = ctx.deps.models.evaluate
		prompt = (
			f"Query: {state.query}\n\nRetrieved catalogue data:\n{render_tool_results(state.tool_results)}"
			f"\n\nDraft answer:\n{draft.text}"
		)
		with _step(ctx, "evaluate", model):
			ev: Evaluation = await _run(
				model, prompts.EVALUATE_PROMPT, prompt, Evaluation, stage="evaluate", history=state.history
			)
			draft.evaluation = ev
			emitter.custom(
				"serka.evaluation",
				{"attempt": state.attempt, "passed": ev.passed, "score": ev.score, "problem": ev.problem, "feedback": ev.feedback},
			)

		assert state.max_attempts is not None
		more_data_impossible = ev.problem == "data" and state.retrieval_stopped
		if not ev.passed and state.attempt < state.max_attempts and not more_data_impossible:
			state.attempt += 1
			return Plan() if ev.problem == "data" else Synthesize()

		chosen = draft if ev.passed else best_draft(state.drafts)
		status: Status = "accepted" if ev.passed else "limit_reached"
		note = f"\n\n{prompts.INCOMPLETE_ANSWER_NOTE}" if status == "limit_reached" else ""
		final = chosen.text + note
		if state.label == "keyword":
			# The only draft was streamed live by Synthesize; append the note and close it.
			emitter.text_delta(note)
			emitter.text_end()
		else:
			emitter.text(final)
		assert chosen.evaluation is not None
		emitter.custom(
			"serka.outcome",
			{
				"status": status,
				"path": state.label,
				"attemptsUsed": state.attempt,
				"maxAttempts": state.max_attempts,
				"score": chosen.evaluation.score,
				"feedback": chosen.evaluation.feedback,
			},
		)
		if status == "accepted" and not state.history and ctx.deps.answer_cache.enabled:
			models = ctx.deps.models
			answer_model = models.synthesize_keyword if state.label == "keyword" else models.synthesize_insight
			cached = CachedAnswer(text=final, path=state.label, score=chosen.evaluation.score, model=answer_model.model_name)
			await asyncio.to_thread(ctx.deps.answer_cache.store, state.query, cached)
		return End(Answer(text=final, status=status))


def build_graph() -> Graph:
	g = GraphBuilder(name="chat", state_type=ChatState, deps_type=ChatDeps, input_type=Cache, output_type=Answer)
	g.add(
		g.edge_from(g.start_node).to(Cache),
		g.node(Cache),
		g.node(Classify),
		g.node(Route),
		g.node(InsightLimit),
		g.node(Refuse),
		g.node(Plan),
		g.node(Execute),
		g.node(Synthesize),
		g.node(Evaluate),
	)
	return g.build()


async def run_chat(graph: Graph, state: ChatState, deps: ChatDeps) -> Answer:
	answer = await graph.run(inputs=Cache(), state=state, deps=deps)
	assert isinstance(answer, Answer)
	return answer
