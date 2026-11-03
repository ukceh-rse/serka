from types import SimpleNamespace
from unittest.mock import Mock

import requests

import serka.fetchers
from serka.fetchers import EIDCFetcher, LegiloFetcher


class FakeSession:
	"""Stands in for the cached requests session: canned JSON by URL, nothing cached."""

	def __init__(self, responses: dict):
		self.responses = responses
		self.calls = []
		self.cache = SimpleNamespace(contains=lambda url: False)

	def get(self, url, params=None):
		self.calls.append((url, params))
		return Mock(status_code=200, json=Mock(return_value=self.responses[url]))


def _record_url(id: str) -> str:
	return f"https://catalogue.ceh.ac.uk/documents/{id}?format=json"


def test_eidc_fetcher_lists_then_fetches_each_record(monkeypatch):
	list_url = "http://test.com/documents"
	records = {"a": {"id": "a", "title": "Dataset A"}, "b": {"id": "b", "title": "Dataset B"}}
	session = FakeSession({
		list_url: {"results": [{"identifier": "a"}, {"identifier": "b"}]},
		**{_record_url(id): r for id, r in records.items()},
	})
	monkeypatch.setattr(serka.fetchers, "_session", session)

	result = EIDCFetcher(list_url).run()

	assert result == {"data": [records["a"], records["b"]]}
	assert session.calls[0] == (
		list_url,
		{"rows": 10000, "page": 1, "term": "state:published AND recordType:Dataset"},
	)


def test_eidc_fetcher_with_ids_skips_listing(monkeypatch):
	session = FakeSession({_record_url("a"): {"id": "a"}})
	monkeypatch.setattr(serka.fetchers, "_session", session)

	assert EIDCFetcher().run(ids=["a"]) == {"data": [{"id": "a"}]}
	assert [url for url, _ in session.calls] == [_record_url("a")]


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


class FakeLegiloSession:
	"""Records each request's headers and returns one canned Legilo response."""

	def __init__(self, body: dict):
		self.body = body
		self.headers = []
		self.cache = SimpleNamespace(contains=lambda url: False)

	def get(self, url, headers=None):
		self.headers.append(headers)
		return Mock(status_code=200, json=Mock(return_value=self.body))


def test_legilo_fetcher_sends_token_as_bearer(monkeypatch):
	session = FakeLegiloSession({"success": {"guide.pdf": "some supporting documentation text"}})
	monkeypatch.setattr(serka.fetchers, "_session", session)

	result = LegiloFetcher(token="pat-123").run([{"id": "a", "title": "Dataset A", "uri": "https://x/a"}])

	assert session.headers and all(h == {"Authorization": "Bearer pat-123"} for h in session.headers)
	[doc] = result["documents"]
	assert doc.meta["filename"] == "guide.pdf"
	assert doc.meta["uri"] == "https://x/a"


def test_legilo_fetcher_without_token_skips_requests(monkeypatch):
	session = FakeLegiloSession({})
	monkeypatch.setattr(serka.fetchers, "_session", session)

	assert LegiloFetcher().run([{"id": "a"}]) == {"documents": []}
	assert session.headers == []


def test_legilo_fetcher_survives_timeout_on_credential_check(monkeypatch):
	session = FakeLegiloSession({"success": {"guide.pdf": "some supporting documentation text"}})
	real_get = session.get

	def flaky_get(url, headers=None):
		if not session.headers:
			session.headers.append(headers)
			raise requests.exceptions.ReadTimeout("Read timed out")
		return real_get(url, headers=headers)

	session.get = flaky_get
	monkeypatch.setattr(serka.fetchers, "_session", session)

	result = LegiloFetcher(token="pat-123").run([{"id": "a", "title": "Dataset A", "uri": "https://x/a"}])

	assert len(result["documents"]) == 1
