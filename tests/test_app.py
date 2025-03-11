from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from serka.main import app
from serka.routers.dependencies import get_dao
from serka.models import Document
import pytest


client = TestClient(app)


@pytest.mark.integration
def test_list() -> None:
	mock_dao = MagicMock()
	test_name = "test_collection"
	mock_dao.list_collections.return_value = [test_name]

	app.dependency_overrides.update({get_dao: lambda: mock_dao})

	response = client.get("/collections/list")
	assert response.status_code == 200
	assert response.json() == [test_name]


@pytest.mark.integration
def test_peek() -> None:
	mock_dao = MagicMock()
	test_content = "test_content"
	test_doc = Document(content=test_content)
	mock_dao.peek.return_value = [test_doc]

	app.dependency_overrides.update({get_dao: lambda: mock_dao})

	test_collection = "test_collection"
	response = client.get(f"/collections/peek?collection={test_collection}")
	assert response.status_code == 200
	assert response.json() == [{"content": test_content, "metadata": None}]
	mock_dao.peek.assert_called_once_with(test_collection)
