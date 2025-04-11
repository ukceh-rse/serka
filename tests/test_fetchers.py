from serka.fetchers import EIDCFetcher
from unittest.mock import Mock
import requests


def test_eidc_fetcher(monkeypatch):
	dataset_list = [{"id": 1, "title": "Dataset 1"}, {"id": 2, "title": "Dataset 2"}]
	test_url = "http://test.com/documents"

	mock_response = Mock()
	mock_response.json.return_value = {"results": dataset_list}

	def mock_get(*args, **kwargs):
		assert args[0] == test_url
		assert kwargs["params"]["page"] == 1
		assert kwargs["params"]["rows"] == 10000
		assert kwargs["params"]["term"] == "state:published AND recordType:Dataset"
		return mock_response

	monkeypatch.setattr(requests, "get", mock_get)

	fetcher = EIDCFetcher(test_url)
	result = fetcher.run()

	assert result == {"records": dataset_list}
	assert mock_response.json.called
