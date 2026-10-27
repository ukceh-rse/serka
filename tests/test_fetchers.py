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


def test_concept_hierarchy_fetcher_walks_gemet_broader(monkeypatch):
	from serka.fetchers import ConceptHierarchyFetcher

	gemet = "http://www.eionet.europa.eu/gemet/concept/"
	parents = {
		f"{gemet}1225": [{"uri": f"{gemet}4862", "preferredLabel": {"string": "livestock"}}],
		f"{gemet}4862": [{"uri": f"{gemet}299", "preferredLabel": {"string": "animal"}}],
	}
	fetcher = ConceptHierarchyFetcher()
	monkeypatch.setattr(fetcher, "_broader", lambda uri: parents.get(uri, []))
	nodes = {
		"Concept": [
			{"uri": f"{gemet}1225", "label": "cattle", "scheme": "gemet"},
			{"uri": "http://onto.nerc.ac.uk/CEHMD/topic/8", "label": "Radioecology", "scheme": "keywordsTheme"},
		],
		"Dataset": [{"uri": "d"}],
	}
	result = fetcher.run(nodes=nodes, relationships={"HAS_THEME": [("d", f"{gemet}1225")]})

	assert set(result["relationships"]["BROADER"]) == {(f"{gemet}1225", f"{gemet}4862"), (f"{gemet}4862", f"{gemet}299")}
	assert result["relationships"]["HAS_THEME"] == [("d", f"{gemet}1225")]
	labels = {c["uri"]: c["label"] for c in result["nodes"]["Concept"]}
	assert labels[f"{gemet}299"] == "animal"
	assert result["nodes"]["Dataset"] == [{"uri": "d"}]
