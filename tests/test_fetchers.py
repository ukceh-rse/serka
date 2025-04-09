from serka.fetchers import EIDCFetcher
from unittest.mock import Mock
import requests


def test_eidc_fetcher(monkeypatch):
	mock_response = Mock()
	mock_response.json.return_value = {
		"results": [{"id": 1, "title": "Dataset 1"}, {"id": 2, "title": "Dataset 2"}]
	}

	def mock_get(*args, **kwargs):
		assert args[0] == "https://catalogue.ceh.ac.uk/eidc/documents"
		assert kwargs["params"]["page"] == 1
		assert kwargs["params"]["rows"] == 10000
		assert kwargs["params"]["term"] == "state:published AND recordType:Dataset"
		return mock_response

	monkeypatch.setattr(requests, "get", mock_get)

	fetcher = EIDCFetcher()
	result = fetcher.run()

	assert result == [{"id": 1, "title": "Dataset 1"}, {"id": 2, "title": "Dataset 2"}]
	assert mock_response.json.called
