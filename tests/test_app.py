import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from starlette.responses import StreamingResponse

from serka.main import app
from serka.models import Document, GroupedDocuments, ScoredDocument
from serka.routers.dependencies import get_dao, get_feedback_logger, get_stream_fn


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


def test_semantic_search_returns_grouped_results(client):
	mock_dao = MagicMock()
	mock_dao.query.return_value = [
		GroupedDocuments(
			groupedby="Test Dataset",
			docs=[
				ScoredDocument(
					score=0.9,
					document=Document(
						content="Test content",
						metadata={
							"title": "Test Dataset",
							"url": "http://example.com",
							"section": "Abstract",
						},
					),
				)
			],
		)
	]
	app.dependency_overrides[get_dao] = lambda: mock_dao
	app.dependency_overrides[get_feedback_logger] = lambda: MagicMock()

	response = client.get("/query/semantic?q=wetlands")

	assert response.status_code == 200
	results = response.json()
	assert len(results) == 1
	assert results[0]["groupedby"] == "Test Dataset"
	assert results[0]["docs"][0]["score"] == 0.9
	mock_dao.query.assert_called_once_with("wetlands")


def test_semantic_search_missing_query_returns_422(client):
	response = client.get("/query/semantic")
	assert response.status_code == 422


# --- /feedback ---


def test_feedback_submit_logs_and_returns_success(client):
	mock_logger = MagicMock()
	app.dependency_overrides[get_feedback_logger] = lambda: mock_logger

	payload = {"query": "test query", "feedback": "UP", "type": "VOTE"}
	response = client.post("/feedback/submit", json=payload)

	assert response.status_code == 200
	assert response.json()["success"] is True
	mock_logger.log_feedback.assert_called_once_with(payload)


def test_feedback_list_returns_logged_items(client):
	mock_logger = MagicMock()
	mock_logger.get_feedback.return_value = [{"query": "test", "feedback": "UP"}]
	app.dependency_overrides[get_feedback_logger] = lambda: mock_logger

	response = client.get("/feedback/list")

	assert response.status_code == 200
	assert response.json() == [{"query": "test", "feedback": "UP"}]


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
		"/chat/stream", json={"message": "what datasets cover wetlands?"}
	)

	assert response.status_code == 200
	assert "text/event-stream" in response.headers["content-type"]


def test_chat_stream_missing_body_returns_422(client):
	app.dependency_overrides[get_stream_fn] = lambda: (lambda run_input, request: None)

	response = client.post("/chat/stream")
	assert response.status_code == 422
