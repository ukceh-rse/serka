from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from serka.main import app

client = TestClient(app)


def test_list() -> None:
	mock_db = MagicMock()
	mock_db.list_collections.return_value = ["eidc"]
	with patch("serka.main.get_db", return_value=mock_db):
		response = client.get("/list")
		assert response.status_code == 200
		assert response.json() == {"collections": ["eidc"]}
