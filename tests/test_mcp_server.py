"""MCP server tests: the real FastMCP server in memory, with a stub `app` module whose catalogue
records calls and returns canned results instead of querying Redis and Bedrock."""

import asyncio
import json
import logging
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP

MCP_SRC = Path(__file__).resolve().parent.parent / "mcp-server" / "src" / "serka-mcp"
sys.path.insert(0, str(MCP_SRC))

from catalogue import AggregateResult, CatalogueError, Filters, SearchResult  # noqa: E402
from instructions import INSTRUCTIONS  # noqa: E402

HIT = {
	"chunk_id": "datasets/abc#0",
	"text": "Annual counts of pike in Windermere.",
	"score": 0.033,
	"concept": {
		"id": "datasets/abc",
		"type": "dataset",
		"title": "Pike in Windermere",
		"description": "Pike counts.",
		"resource": "https://catalogue.ceh.ac.uk/id/abc",
		"tags": ["pike"],
		"citations": 4,
		"published": "2020-05-01",
	},
}


GROUP = {"id": "people/x", "title": "Morton, R.D.", "datasets": 20, "citations": 234}


class FakeCatalogue:
	def __init__(self) -> None:
		self.searches: list[dict[str, Any]] = []
		self.aggregates: list[dict[str, Any]] = []
		self.themes = {"freshwater fish": "themes/fish"}

	def resolve_theme(self, theme: str) -> str:
		if "/" in theme:
			return theme
		if theme.lower() not in self.themes:
			raise CatalogueError(f"Unknown theme '{theme}'.")
		return self.themes[theme.lower()]

	def search(self, query, sort_by, order, filters: Filters, limit) -> SearchResult:
		self.searches.append({"query": query, "sort_by": sort_by, "order": order, "filters": filters, "limit": limit})
		if not query and not sort_by:
			raise CatalogueError("search needs a query, a sort_by, or both.")
		return SearchResult([HIT], 240, [])

	def aggregate(self, group_by, role, sort_by, query, filters: Filters, limit) -> AggregateResult:
		self.aggregates.append(
			{"group_by": group_by, "role": role, "sort_by": sort_by, "query": query, "filters": filters, "limit": limit}
		)
		if role == "editor":
			raise CatalogueError("Unknown role 'editor'. Roles in use: author.")
		return AggregateResult(total=87, groups=[GROUP], total_groups=145)

	def read(self, concept_id: str) -> str:
		if concept_id.strip("/") == "datasets/abc":
			return "---\ntype: dataset\ntitle: Pike in Windermere\n---\n\nBody."
		raise CatalogueError(f"No concept '{concept_id}' in the catalogue.")


class FakeGeolocator:
	def geocode(self, location, **_):
		return None


catalogue = FakeCatalogue()
fake_app = types.ModuleType("app")
fake_app.__dict__.update(
	mcp=FastMCP("Serka", instructions=INSTRUCTIONS),
	logger=logging.getLogger("serka_mcp_test"),
	catalogue=catalogue,
	geolocator=FakeGeolocator(),
)
sys.modules["app"] = fake_app

import prompts  # noqa: E402, F401
import tools  # noqa: E402, F401

mcp = fake_app.mcp  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def reset_catalogue():
	catalogue.searches.clear()
	catalogue.aggregates.clear()


def call(tool: str, args: dict | None = None):
	async def _call():
		async with Client(mcp) as client:
			return await client.call_tool(tool, args or {}, raise_on_error=False)

	return asyncio.run(_call())


def _with_client(fn):
	async def _run():
		async with Client(mcp) as client:
			return await fn(client)

	return asyncio.run(_run())


def test_tools_are_exactly_search_read_aggregate_and_geocode() -> None:
	names = {t.name for t in _with_client(lambda c: c.list_tools())}
	assert names == {"search", "read", "aggregate", "geocode_location"}


def test_no_resources() -> None:
	assert _with_client(lambda c: c.list_resources()) == []
	assert _with_client(lambda c: c.list_resource_templates()) == []


def test_instructions_describe_the_tools_and_ontology_index() -> None:
	result = _with_client(lambda c: asyncio.sleep(0, c.initialize_result))
	for word in ("search", "read", "aggregate", "geocode_location", 'read("ontology/index")'):
		assert word in result.instructions
	assert "JSON-LD" not in result.instructions


def test_search_description_explains_totals_and_the_relevance_window() -> None:
	[search] = [t for t in _with_client(lambda c: c.list_tools()) if t.name == "search"]
	assert "`total` counts candidate passages" in search.description
	assert "use `aggregate` to count" in search.description
	assert "`total` counts those concepts" in search.description
	assert "theme=<theme> with no query" in search.description
	assert set(search.inputSchema["properties"]) == {
		"query", "sort_by", "order", "type", "theme", "linked", "bounding_box",
		"published_after", "published_before", "min_citations", "limit",
	}


def test_search_returns_plain_json_hits() -> None:
	result = call("search", {"query": "pike", "type": "dataset", "limit": 5})
	assert not result.is_error
	data = json.loads(result.content[0].text)
	assert data == {"hits": [HIT], "total": 240, "warnings": []}
	assert result.structured_content == data
	assert set(data["hits"][0]) == {"chunk_id", "text", "score", "concept"}
	assert "@context" not in result.content[0].text
	[args] = catalogue.searches
	assert args["filters"].type == "dataset" and args["limit"] == 5


def test_search_passes_sort_and_filters() -> None:
	call(
		"search",
		{
			"sort_by": "citations",
			"order": "ascending",
			"theme": "Freshwater fish",
			"linked": "/people/x",
			"bounding_box": {"south": 54.2, "north": 54.5, "west": -3.0, "east": -2.9},
			"published_after": "2015-01-01",
			"min_citations": 2,
		},
	)
	[args] = catalogue.searches
	assert args["query"] is None and args["sort_by"] == "citations" and args["order"] == "ascending"
	filters = args["filters"]
	assert filters.theme == "themes/fish"
	assert filters.linked == "/people/x"
	assert filters.bounding_box.north == 54.5
	assert (filters.published_after, filters.min_citations) == ("2015-01-01", 2)


def test_unknown_theme_is_a_tool_error() -> None:
	result = call("search", {"query": "pike", "theme": "Volcanoes"})
	assert result.is_error and "Unknown theme 'Volcanoes'" in result.content[0].text


def test_search_without_query_or_sort_is_a_tool_error() -> None:
	result = call("search", {"type": "dataset"})
	assert result.is_error and "query, a sort_by" in result.content[0].text


def test_aggregate_description_explains_what_is_counted() -> None:
	[tool] = [t for t in _with_client(lambda c: c.list_tools()) if t.name == "aggregate"]
	for phrase in ("distinct matching datasets", "narrower themes", "full-text", "Never count search hits"):
		assert phrase in tool.description
	assert set(tool.inputSchema["properties"]) == {
		"group_by", "role", "sort_by", "query", "type", "theme", "linked", "bounding_box",
		"published_after", "published_before", "min_citations", "limit",
	}


def test_aggregate_returns_plain_json_groups() -> None:
	result = call("aggregate", {"group_by": "person", "role": "author", "theme": "Freshwater fish", "limit": 3})
	assert not result.is_error
	data = json.loads(result.content[0].text)
	assert data == {"total": 87, "groups": [GROUP], "total_groups": 145, "warnings": []}
	[args] = catalogue.aggregates
	assert (args["group_by"], args["role"], args["sort_by"], args["limit"]) == ("person", "author", "datasets", 3)
	assert args["filters"].theme == "themes/fish"


def test_aggregate_with_no_arguments_counts_datasets() -> None:
	assert not call("aggregate").is_error
	[args] = catalogue.aggregates
	assert args["group_by"] is None and args["query"] is None and args["filters"].type is None


def test_aggregate_unknown_role_is_a_tool_error() -> None:
	result = call("aggregate", {"group_by": "person", "role": "editor"})
	assert result.is_error and "Roles in use: author" in result.content[0].text


def test_read_returns_markdown() -> None:
	result = call("read", {"id": "/datasets/abc"})
	assert not result.is_error
	assert result.content[0].text.startswith("---\ntype: dataset")


def test_read_unknown_is_a_tool_error_naming_the_id() -> None:
	result = call("read", {"id": "datasets/does-not-exist"})
	assert result.is_error and "datasets/does-not-exist" in result.content[0].text


def test_geocode_failure_is_a_tool_error() -> None:
	result = call("geocode_location", {"location": "Nowhereville"})
	assert result.is_error and "Nowhereville" in result.content[0].text


def test_prompts_name_only_current_tools() -> None:
	removed = ("get_entity", "get_relations", "get_contributors", "find_by_contributor", "list_datasets", "get_content", "describe_ontology")
	for prompt in _with_client(lambda c: c.list_prompts()):
		args = {a.name: "x" for a in prompt.arguments or []}
		text = _with_client(lambda c, p=prompt, a=args: c.get_prompt(p.name, a)).messages[0].content.text
		assert not any(name in text for name in removed), prompt.name
