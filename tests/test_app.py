from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from serka.main import app

client = TestClient(app)


def test_list() -> None:
	mock_dao = MagicMock()
	test_name = "test_collection"
	mock_dao.list_collections.return_value = [test_name]
	with patch("serka.main.get_dao", return_value=mock_dao):
		response = client.get("/list")
		assert response.status_code == 200
		assert response.json() == {"collections": [test_name]}


def test_peek() -> None:
	mock_dao = MagicMock()
	test_doc = {"doc": "test_conent", "meta": "some_meta_value"}
	mock_dao.peek.return_value = [test_doc]
	with patch("serka.main.get_dao", return_value=mock_dao):
		test_collection = "test_collection"
		response = client.get(f"/peek?collection={test_collection}")
		assert response.status_code == 200
		assert response.json() == {"documents": [test_doc]}
		mock_dao.peek.assert_called_once_with(test_collection)
