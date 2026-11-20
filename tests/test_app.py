import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace
from unittest.mock import MagicMock
from starlette.responses import StreamingResponse

from serka.main import app
from serka.routers.dependencies import get_feedback_logger, get_mcp_search, get_stream_fn


@pytest.fixture
def client():
	with TestClient(app) as c:
		yield c


# --- /query/semantic ---


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


class FakeMCPClient:
	"""Stands in for fastmcp.Client: records tool calls; geocoding fails for 'Nowhereville'."""

	calls: list[tuple[str, dict]] = []

	def __init__(self, url: str) -> None:
		pass

	async def __aenter__(self):
		return self

	async def __aexit__(self, *_):
		return False

	async def call_tool(self, name: str, args: dict):
		from fastmcp.exceptions import ToolError

		FakeMCPClient.calls.append((name, args))
		if name == "geocode_location":
			if args["location"] == "Nowhereville":
				raise ToolError("Could not geocode location 'Nowhereville'")
			return SimpleNamespace(structured_content={"boundary": {"south": 54.2, "north": 54.5, "west": -3.0, "east": -2.9}})
		return SimpleNamespace(structured_content={"hits": [HIT], "total": 240, "warnings": ["a warning"]})


@pytest.fixture
def real_search(monkeypatch):
	"""The real search dependency, talking to a fake MCP client."""
	from serka.routers import dependencies

	monkeypatch.setattr(dependencies, "Client", FakeMCPClient)
	monkeypatch.setattr(dependencies, "_mcp_search_fn", None)
	FakeMCPClient.calls = []
	app.dependency_overrides.pop(get_mcp_search, None)
	app.dependency_overrides[get_feedback_logger] = lambda: MagicMock()
	return FakeMCPClient.calls


def test_semantic_search_returns_search_hits_unchanged(client, real_search):
	response = client.get("/v1/query/semantic", params={"q": "pike windermere"})
	assert response.status_code == 200
	assert response.json() == [HIT]
	assert real_search == [("search", {"query": "pike windermere"})]


def test_semantic_search_type_filter(client, real_search):
	response = client.get("/v1/query/semantic", params={"q": "pike", "type": "dataset", "published_after": "2015-01-01"})
	assert response.status_code == 200
	assert real_search == [("search", {"query": "pike", "type": "dataset", "published_after": "2015-01-01"})]


def test_semantic_search_location_is_geocoded_to_a_bounding_box(client, real_search):
	assert client.get("/v1/query/semantic", params={"q": "pike", "location": "Windermere"}).status_code == 200
	assert real_search[1] == (
		"search",
		{"query": "pike", "bounding_box": {"south": 54.2, "north": 54.5, "west": -3.0, "east": -2.9}},
	)


def test_semantic_search_unknown_location_returns_422(client, real_search):
	response = client.get("/v1/query/semantic", params={"q": "fish", "location": "Nowhereville"})
	assert response.status_code == 422
	assert [name for name, _ in real_search] == ["geocode_location"]


def test_semantic_search_no_longer_takes_hops_or_return_type(client, real_search):
	client.get("/v1/query/semantic", params={"q": "pike", "hops": 2, "return_type": "Dataset"})
	assert real_search == [("search", {"query": "pike"})]


# --- test mode mock search ---


def test_test_mode_search_returns_okf_chunk_hits(client):
	hits = client.get("/v1/query/semantic", params={"q": "soil"}).json()
	assert all(set(h) == {"chunk_id", "text", "score", "concept"} for h in hits)
	scores = [h["score"] for h in hits]
	assert scores == sorted(scores, reverse=True)
	soil = [h for h in hits if h["concept"]["id"] == "datasets/soil-carbon-upland-1978-2019"]
	assert len(soil) == 3 and len({h["chunk_id"] for h in soil}) == 3
	[doc] = [h for h in hits if h["concept"]["type"] == "document"]
	assert doc["concept"]["id"].startswith("datasets/soil-carbon-upland-1978-2019/docs/")


def test_test_mode_search_type_filter(client):
	hits = client.get("/v1/query/semantic", params={"q": "soil", "type": "person"}).json()
	assert hits and all(h["concept"]["type"] == "person" for h in hits)


def test_semantic_search_missing_query_returns_422(client):
	response = client.get("/v1/query/semantic")
	assert response.status_code == 422


def _use_search(results: list) -> tuple[MagicMock, MagicMock]:
	search, logger = MagicMock(return_value=results), MagicMock()

	async def mock_search_fn():
		async def _search(q: str, **kwargs) -> list:
			return search(q)

		return _search

	app.dependency_overrides[get_mcp_search] = mock_search_fn
	app.dependency_overrides[get_feedback_logger] = lambda: logger
	return search, logger


def test_semantic_search_accepts_query_at_the_limit(client):
	search, logger = _use_search([])
	response = client.get("/v1/query/semantic", params={"q": "x" * 500})
	assert response.status_code == 200
	search.assert_called_once()
	logger.log_feedback.assert_called_once()


def test_semantic_search_rejects_query_over_the_limit(client):
	search, logger = _use_search([])
	response = client.get("/v1/query/semantic", params={"q": "x" * 501})
	assert response.status_code == 422
	search.assert_not_called()
	logger.log_feedback.assert_not_called()


# --- /feedback ---


def test_feedback_submit_logs_and_returns_success(client):
	mock_logger = MagicMock()
	app.dependency_overrides[get_feedback_logger] = lambda: mock_logger

	payload = {"query": "test query", "feedback": "UP", "type": "VOTE"}
	response = client.post("/v1/feedback/submit", json=payload)

	assert response.status_code == 200
	assert response.json()["success"] is True
	mock_logger.log_feedback.assert_called_once_with(payload)


def test_feedback_submit_logs_extra_context_fields(client):
	# The UI sends per-result context (vote, comment, dataset_uri, ...) alongside the core fields.
	mock_logger = MagicMock()
	app.dependency_overrides[get_feedback_logger] = lambda: mock_logger
	payload = {"type": "VOTE", "vote": "up", "dataset_uri": "https://example.com/d"}
	response = client.post("/v1/feedback/submit", json=payload)
	assert response.status_code == 200
	mock_logger.log_feedback.assert_called_once_with(payload)


def test_feedback_submit_rejects_oversized_query(client):
	app.dependency_overrides[get_feedback_logger] = lambda: MagicMock()
	response = client.post(
		"/v1/feedback/submit", json={"query": "x" * 2001, "type": "VOTE"}
	)
	assert response.status_code == 422



# --- /chat/stream ---


def test_chat_stream_returns_sse_response(client):
	async def _fake_events():
		yield b'data: {"type": "RUN_FINISHED"}\n\n'

	app.dependency_overrides[get_stream_fn] = lambda: (
		lambda run_input, request, count_run: StreamingResponse(
			_fake_events(), media_type="text/event-stream"
		)
	)

	response = client.post(
		"/v1/chat/stream", json={"message": "what datasets cover wetlands?"}
	)

	assert response.status_code == 200
	assert "text/event-stream" in response.headers["content-type"]


def test_chat_stream_missing_body_returns_422(client):
	app.dependency_overrides[get_stream_fn] = lambda: (lambda run_input, request, count_run: None)

	response = client.post("/v1/chat/stream")
	assert response.status_code == 422


@pytest.mark.usefixtures("no_mock_delays")
def test_test_mode_enforces_no_caps(client):
	for _ in range(35):
		response = client.post("/v1/chat/stream", json={"message": "soil carbon"})
		assert response.status_code == 200
		assert "text/event-stream" in response.headers["content-type"]


def test_test_mode_still_limits_query_length(client):
	assert client.post("/v1/chat/stream", json={"message": "x" * 501}).status_code == 422


@pytest.mark.usefixtures("no_mock_delays")
def test_test_mode_cached_run(client):
	from tests.sse import answer_text, customs, decode, steps

	events = decode([client.post("/v1/chat/stream", json={"message": "soil carbon (cached)"}).text])
	assert steps(events) == ["cache"]
	assert [e["type"] for e in events].count("TEXT_MESSAGE_START") == 1
	assert answer_text(events).startswith("Soil carbon measurements for UK uplands")
	assert customs(events, "serka.outcome") == [
		{"status": "cached", "path": "keyword", "attemptsUsed": 0, "maxAttempts": None, "score": 5, "feedback": None}
	]
	assert events[0]["type"] == "RUN_STARTED" and events[-1]["type"] == "RUN_FINISHED"
