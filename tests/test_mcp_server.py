"""MCP server tests: the real FastMCP server in memory, with a stub `app` module standing in
for Neo4j, Bedrock and Nominatim. Checks the JSON-LD/DOO contract of every tool."""

import asyncio
import json
import logging
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from pyld import jsonld

MCP_SRC = Path(__file__).resolve().parent.parent / "mcp-server" / "src" / "serka-mcp"
sys.path.insert(0, str(MCP_SRC))

from ontology import INSTRUCTIONS  # noqa: E402

DCAT = "http://www.w3.org/ns/dcat#"
DCTERMS = "http://purl.org/dc/terms/"
DATASET_URI = "https://catalogue.ceh.ac.uk/id/ds-1"
PERSON_URI = "https://orcid.org/0000-0000-0000-0001"
ORG_URI = "https://ror.org/00pggkr55"


class FakeDriver:
	"""Answers session.execute_read(query_fn, **kwargs) from canned responses keyed by query name."""

	def __init__(self) -> None:
		self.responses: dict[str, Any] = {}
		self.calls: list[tuple[str, dict]] = []

	def session(self, **_):
		return self

	def __enter__(self):
		return self

	def __exit__(self, *_):
		return False

	def execute_read(self, fn, **kwargs):
		self.calls.append((fn.__name__, kwargs))
		response = self.responses.get(fn.__name__, [])
		return response(**kwargs) if callable(response) else response


class FakeGeolocator:
	def geocode(self, location, **_):
		return None


driver = FakeDriver()
fake_app = types.ModuleType("app")
fake_app.mcp = FastMCP("Serka", instructions=INSTRUCTIONS)
fake_app.logger = logging.getLogger("serka_mcp_test")
fake_app.neo4j_driver = driver
fake_app.embedder = types.SimpleNamespace(run=lambda text: {"embedding": [0.0]})
fake_app.geolocator = FakeGeolocator()
fake_app.reranker = None
fake_app.reranking_enabled = False
sys.modules["app"] = fake_app

import prompts  # noqa: E402, F401
import tools  # noqa: E402, F401

mcp = fake_app.mcp

DATASET_PROPS = {
	"uri": DATASET_URI,
	"title": "Pike in Windermere",
	"publication_date": "2020-05-01",
	"citations": 4,
	"south_boundary": 54.2,
	"north_boundary": 54.5,
	"west_boundary": -3.0,
	"east_boundary": -2.9,
	"temporal_start": "1963-01-01",
	"temporal_end": "2003-12-31",
}
PERSON_PROPS = {"uri": PERSON_URI, "name": "Ada Angler"}


def _search_rows(**kwargs) -> list[dict]:
	# A description chunk resolving to its dataset, and a person reached through that dataset.
	chunk = {"content": "pike eggs", "field": "description", "doc_id": "c1"}
	return [
		{
			"matched_props": chunk, "matched_labels": ["TextChunk", "embedded"], "score": 0.9,
			"target_props": DATASET_PROPS, "target_labels": ["Dataset", "embedded"],
			"via": [], "rels": [],
		},
		{
			"matched_props": chunk, "matched_labels": ["TextChunk", "embedded"], "score": 0.8,
			"target_props": PERSON_PROPS, "target_labels": ["Person", "embedded"],
			"via": [{"props": DATASET_PROPS, "labels": ["Dataset", "embedded"]}],
			"rels": [{"type": "DESCRIPTION_OF", "props": {}}, {"type": "ASSOCIATED_WITH", "props": {"role": "author"}}],
		},
	]


@pytest.fixture(autouse=True)
def reset_driver():
	driver.responses = {
		"search_query": _search_rows,
		"fulltext_search_query": [],
		"expand_theme_query": ["gemet:1", "gemet:2", "gemet:3"],
		"get_contributors_query": [
			{"role": "author", "agent_labels": ["Person", "embedded"], "agent_props": PERSON_PROPS},
			{"role": "custodian", "agent_labels": ["Organisation", "embedded"], "agent_props": {"uri": ORG_URI, "name": "UKCEH"}},
		],
		"get_relations_query": [
			{"rel_type": "RELATION", "rel_props": {"predicate": "http://purl.org/dc/terms/isPartOf"},
			 "node_labels": ["Dataset", "embedded"], "node_props": {"uri": "https://catalogue.ceh.ac.uk/id/parent", "title": "Parent"}},
			{"rel_type": "HAS_THEME", "rel_props": {},
			 "node_labels": ["Concept", "embedded"], "node_props": {"uri": "gemet:1", "label": "fish", "scheme": "gemet"}},
			{"rel_type": "DESCRIPTION_OF", "rel_props": {}, "node_labels": ["TextChunk"], "node_props": {"content": "x"}},
		],
		"get_entity_query": {"labels": ["Dataset", "embedded"], "props": DATASET_PROPS},
		"ontology_counts_query": {
			"labels": {"Dataset": 10, "Person": 30, "Organisation": 5, "FundingAgency": 1},
			"rel_types": {"HAS_THEME": 40, "BROADER": 12},
			"predicates": {"dcterms:isPartOf": 5, "doo:originatingGrant": 6},
			"roles": {"author": 30, "coAuthor": 2, "custodian": 10},
		},
	}
	driver.calls = []


def _graph_nodes(doc: dict) -> list[dict]:
	"""Expanded @graph nodes. A document with only @context/@graph expands to the bare node list;
	one with other keys too (e.g. meta) expands to a single node holding @graph."""
	expanded = jsonld.expand(doc)
	return expanded[0]["@graph"] if len(expanded) == 1 and "@graph" in expanded[0] else expanded


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


# --- tool listing & server metadata ------------------------------------------------------


def test_instructions_describe_doo_types_and_predicates():
	result = _with_client(lambda c: asyncio.sleep(0, c.initialize_result))
	assert "Digital Objects Ontology" in result.instructions
	assert "dcat:Dataset" in result.instructions and "skos:broader" in result.instructions


def test_tool_output_schemas_carry_ontology_annotations():
	tools_list = {t.name: t for t in _with_client(lambda c: c.list_tools())}
	assert "describe_ontology" in tools_list
	schema = tools_list["search"].outputSchema
	assert set(schema["properties"]) >= {"@context", "@graph", "meta"}
	# FastMCP inlines $defs: find the entity schema annotated as a dcat:Dataset
	entity_options = schema["properties"]["@graph"]["items"]["properties"]["entity"]["anyOf"]
	dataset = next(o for o in entity_options if o.get("x-rdf-type") == "dcat:Dataset")
	assert dataset["properties"]["publication_date"]["x-rdf-property"] == "dcterms:issued"
	assert "@id" in dataset["properties"]


# --- search -------------------------------------------------------------------------------


def test_search_returns_jsonld_with_structured_content_and_links():
	result = call("search", {"query": "pike"})
	assert not result.is_error
	data = result.structured_content
	assert json.loads(result.content[0].text) == data
	assert data["@context"]["dcat"] == DCAT
	hit = data["@graph"][0]
	assert hit["entity"]["@id"] == DATASET_URI
	assert hit["entity"]["@type"] == ["dcat:Dataset"]
	assert hit["entity"]["bbox"].startswith("POLYGON((")
	assert hit["entity"]["temporal"] == {"@type": "dcterms:PeriodOfTime", "start_date": "1963-01-01", "end_date": "2003-12-31"}
	links = [c for c in result.content if c.type == "resource_link"]
	assert {str(link.uri) for link in links} == {f"doo://entity/{DATASET_URI}", f"doo://entity/{PERSON_URI}"}


def test_search_output_expands_to_ontology_iris():
	data = call("search", {"query": "pike"}).structured_content
	entities = [hit["urn:serka:entity"][0] for hit in _graph_nodes(data)]
	dataset = next(e for e in entities if e["@id"] == DATASET_URI)
	assert dataset["@type"] == [f"{DCAT}Dataset"]
	assert dataset[f"{DCTERMS}title"] == [{"@value": "Pike in Windermere"}]
	assert f"{DCAT}bbox" in dataset


def test_search_path_uses_doo_role_individuals():
	data = call("search", {"query": "pike"}).structured_content
	person_hit = next(h for h in data["@graph"] if h["entity"]["@id"] == PERSON_URI)
	assert [s["predicate"] for s in person_hit["path"]] == ["pro:author"]


def test_unknown_return_type_is_a_tool_error():
	result = call("search", {"query": "pike", "return_type": "foaf:Persn"})
	assert result.is_error
	assert "Unknown return_type" in result.content[0].text


def test_return_type_accepts_full_iri():
	result = call("search", {"query": "pike", "return_type": f"{DCAT}Dataset"})
	assert not result.is_error
	assert result.structured_content["meta"]["return_type"] == "dcat:Dataset"


def test_theme_is_expanded_and_reported():
	result = call("search", {"query": "pike", "theme": "fish", "return_type": "dcat:Dataset"})
	meta = result.structured_content["meta"]
	assert meta["theme_expansion"] == {"fish": 3}
	assert meta["filters"]["theme"] == "fish"
	search_kwargs = next(kw for name, kw in driver.calls if name == "search_query")
	assert search_kwargs["theme_uris"] == ["gemet:1", "gemet:2", "gemet:3"]


def test_unknown_theme_is_a_tool_error():
	driver.responses["expand_theme_query"] = []
	result = call("search", {"query": "pike", "theme": "nonsense"})
	assert result.is_error and "Unknown theme" in result.content[0].text


def test_search_meta_warns_about_dataset_only_filters():
	result = call("search", {
		"query": "pike", "return_type": "foaf:Person",
		"bounding_box": {"south": 54, "north": 55, "west": -3, "east": -2},
		"published_after": "2000-01-01",
	})
	warnings = result.structured_content["meta"]["warnings"]
	assert any("bounding_box" in w for w in warnings)
	assert any("published_after" in w for w in warnings)


# --- contributors & relations ---------------------------------------------------------------


def test_get_contributors_returns_role_in_time():
	data = call("get_contributors", {"dataset_uri": DATASET_URI}).structured_content
	roles = {(a["agent"]["@id"], a["role"], a["role_type"]) for a in data["@graph"]}
	assert roles == {
		(PERSON_URI, "pro:author", "pro:PublishingRole"),
		(ORG_URI, "scoro:data-curator", "scoro:DataRole"),
	}
	assert all(a["@type"] == "pro:RoleInTime" and a["relates_to"] == DATASET_URI for a in data["@graph"])
	# agent is the reverse of pro:holdsRoleInTime, as in DOO's role pattern
	[role] = [n for n in _graph_nodes(data) if PERSON_URI in json.dumps(n)]
	assert role["@reverse"]["http://purl.org/spar/pro/holdsRoleInTime"][0]["@id"] == PERSON_URI


@pytest.mark.parametrize("role, expected", [("scoro:DataRole", {ORG_URI}), ("pro:author", {PERSON_URI})])
def test_get_contributors_filters_by_role_class_or_individual(role, expected):
	data = call("get_contributors", {"dataset_uri": DATASET_URI, "role": role}).structured_content
	assert {a["agent"]["@id"] for a in data["@graph"]} == expected


def test_unknown_role_is_a_tool_error():
	result = call("get_contributors", {"dataset_uri": DATASET_URI, "role": "scoro:AuthorshipRole"})
	assert result.is_error and "Unknown role" in result.content[0].text


def test_get_relations_compacts_predicates_and_skips_text_chunks():
	data = call("get_relations", {"uri": DATASET_URI}).structured_content
	assert [(r["predicate"], r["target"]["@id"]) for r in data["@graph"]] == [
		("dcterms:isPartOf", "https://catalogue.ceh.ac.uk/id/parent"),
		("dcat:theme", "gemet:1"),
	]
	filtered = call("get_relations", {"uri": DATASET_URI, "predicate": f"{DCTERMS}isPartOf"}).structured_content
	assert len(filtered["@graph"]) == 1


# --- discovery -----------------------------------------------------------------------------


def test_describe_ontology_reports_definitions_and_counts():
	data = call("describe_ontology").structured_content
	types = {t["curie"]: t for t in data["types"]}
	assert types["dcat:Dataset"]["count"] == 10
	assert types["dcat:Dataset"]["iri"] == f"{DCAT}Dataset"
	assert types["frapo:FundingAgency"]["count"] == 1
	predicates = {p["curie"]: p["count"] for p in data["predicates"]}
	assert predicates["dcat:theme"] == 40 and predicates["skos:broader"] == 12
	assert predicates["doo:originatingGrant"] == 6
	roles = {r["curie"]: r for r in data["roles"]}
	assert roles["pro:author"]["count"] == 32  # author + coAuthor
	assert roles["pro:author"]["role_class"] == "pro:PublishingRole"
	classes = {c["curie"]: c["count"] for c in data["role_classes"]}
	assert classes["scoro:DataRole"] == 10


def test_entity_resource_is_jsonld():
	contents = _with_client(lambda c: c.read_resource(f"doo://entity/{DATASET_URI}"))
	doc = json.loads(contents[0].text)
	assert doc["@id"] == DATASET_URI and doc["@context"]["dcat"] == DCAT
	assert contents[0].mimeType == "application/ld+json"
	get_entity_kwargs = next(kw for name, kw in driver.calls if name == "get_entity_query")
	assert get_entity_kwargs["uri"] == DATASET_URI


def test_get_entity_tool_and_not_found_error():
	data = call("get_entity", {"uri": DATASET_URI}).structured_content
	assert [e["@id"] for e in data["@graph"]] == [DATASET_URI]
	driver.responses["get_entity_query"] = None
	result = call("get_entity", {"uri": "https://example.org/missing"})
	assert result.is_error and "not found" in result.content[0].text


def test_context_resource_is_a_jsonld_context():
	contents = _with_client(lambda c: c.read_resource("doo://context"))
	assert json.loads(contents[0].text)["@context"]["role"] == {"@id": "pro:withRole", "@type": "@vocab"}


def test_geocode_failure_is_a_tool_error():
	result = call("geocode_location", {"location": "Nowhereshire"})
	assert result.is_error and "Could not geocode" in result.content[0].text
