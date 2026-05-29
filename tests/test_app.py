import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from starlette.responses import StreamingResponse

from serka.main import app
from serka.routers.dependencies import get_feedback_logger, get_mcp_search, get_stream_fn


@pytest.fixture
def client():
	with TestClient(app) as c:
		yield c


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
	"""Reset dependency overrides after every test to prevent state leaking between tests."""
	yield
	app.dependency_overrides.clear()


# --- /query/semantic ---


def test_semantic_search_returns_results(client):
	mock_results = [
		{
			"result": {"item": {"doc_id": "1", "content": "Test content"}, "type": "TextChunk"},
			"dataset": {"uri": "http://example.com", "title": "Test Dataset"},
			"score": 0.9,
			"description": "HAS_CHUNK",
		}
	]

	async def mock_search_fn():
		async def _search(q: str) -> list:
			return mock_results

		return _search

	app.dependency_overrides[get_mcp_search] = mock_search_fn
	app.dependency_overrides[get_feedback_logger] = lambda: MagicMock()

	response = client.get("/v1/query/semantic?q=wetlands")

	assert response.status_code == 200
	results = response.json()
	assert len(results) == 1
	assert results[0]["dataset"]["title"] == "Test Dataset"
	assert results[0]["score"] == 0.9


def test_semantic_search_missing_query_returns_422(client):
	response = client.get("/v1/query/semantic")
	assert response.status_code == 422


# --- /feedback ---


def test_feedback_submit_logs_and_returns_success(client):
	mock_logger = MagicMock()
	app.dependency_overrides[get_feedback_logger] = lambda: mock_logger

	payload = {"query": "test query", "feedback": "UP", "type": "VOTE"}
	response = client.post("/v1/feedback/submit", json=payload)

	assert response.status_code == 200
	assert response.json()["success"] is True
	mock_logger.log_feedback.assert_called_once_with(payload)


def test_feedback_submit_rejects_unknown_fields(client):
	app.dependency_overrides[get_feedback_logger] = lambda: MagicMock()
	response = client.post(
		"/v1/feedback/submit", json={"query": "q", "type": "VOTE", "injected": "bad"}
	)
	assert response.status_code == 422


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
		lambda run_input, request: StreamingResponse(
			_fake_events(), media_type="text/event-stream"
		)
	)

	response = client.post(
		"/v1/chat/stream", json={"message": "what datasets cover wetlands?"}
	)

	assert response.status_code == 200
	assert "text/event-stream" in response.headers["content-type"]


def test_chat_stream_missing_body_returns_422(client):
	app.dependency_overrides[get_stream_fn] = lambda: (lambda run_input, request: None)

	response = client.post("/v1/chat/stream")
	assert response.status_code == 422
