from typing import List, Dict, Any
import logging
import requests_cache
from tqdm import tqdm
from haystack import component, Document
from serka.graph.extractors import extract_doi

logger = logging.getLogger(__name__)

class _TimeoutSession(requests_cache.CachedSession):
	def request(self, method, url, **kwargs):
		kwargs.setdefault("timeout", 5)
		return super().request(method, url, **kwargs)


_session = _TimeoutSession(".cache/http", backend="filesystem")


def _eidc_url(id: str) -> str:
	return f"https://catalogue.ceh.ac.uk/documents/{id}?format=json"


@component
class EIDCFetcher:
	"""
	Haystack fetcher component for retrieving dataset information from the EIDC API.
	Args:
		url (str): The URL of the EIDC API endpoint.
	"""

	def __init__(self, url: str = "https://catalogue.ceh.ac.uk/eidc/documents"):
		self.url = url

	def get_eidc_json(self, ids: List[str]) -> List[Dict[Any, Any]]:
		cached_ids = [id for id in ids if _session.cache.contains(url=_eidc_url(id))]
		to_fetch = [id for id in ids if not _session.cache.contains(url=_eidc_url(id))]

		results = []
		for id in tqdm(cached_ids, desc="Loading cached EIDC data", unit="dataset"):
			results.append(_session.get(_eidc_url(id)).json())

		for id in tqdm(to_fetch, desc="Fetching EIDC data", unit="dataset"):
			try:
				res = _session.get(_eidc_url(id))
				if res.status_code != 200:
					logger.warning("EIDC: HTTP %d for dataset %s", res.status_code, id)
					continue
				results.append(res.json())
			except Exception as e:
				logger.error("EIDC: error fetching dataset %s: %s", id, e, exc_info=True)

		return results

	@component.output_types(data=List[Dict[Any, Any]])
	def run(
		self,
		rows: int = 10000,
		page: int = 1,
		term: str = "state:published AND recordType:Dataset",
		**kwargs,
	) -> List[Dict[Any, Any]]:
		res = _session.get(
			self.url,
			params={"rows": rows, "page": page, "term": term, **kwargs},
		)
		eidc_data = res.json()
		ids = [record["identifier"] for record in eidc_data["results"]]
		data = self.get_eidc_json(ids)
		return {"data": data}


@component
class LegiloFetcher:
	"""
	Haystack fetcher component for retrieving supporting documentation from the Legilo API.
	Args:
		legilo_url (str): Format string for the Legilo API endpoint; {id} is the dataset ID.
	"""

	def __init__(
		self,
		legilo_url: str = "https://legilo.eds-infra.ceh.ac.uk/{id}/documents",
		username: str = None,
		password: str = None,
	):
		self.legilo_url = legilo_url
		self.auth = (username, password)

	@staticmethod
	def _is_prose(content: str, min_whitespace_ratio: float = 0.05) -> bool:
		if not content:
			return False
		return sum(c.isspace() for c in content) / len(content) >= min_whitespace_ratio

	def extract_docs(self, json_data, title, uri):
		extracted_docs = []
		for filename, content in json_data.get("success", {}).items():
			if not self._is_prose(content):
				logger.warning(
					"Skipping non-prose supporting document '%s' for '%s' (insufficient whitespace)",
					filename,
					uri,
				)
				continue
			extracted_docs.append(
				Document(
					content=content,
					meta={"title": title, "field": "SUPPORTING_DOC", "uri": uri, "filename": filename},
				)
			)
		return extracted_docs

	def _docs_from_response(self, dataset: Dict[Any, Any], res) -> List[Document]:
		return self.extract_docs(
			res.json(),
			dataset.get("title", ""),
			extract_doi(dataset["resourceIdentifiers"]),
		)

	@component.output_types(documents=List[Document])
	def run(self, datasets: List[Dict[Any, Any]]) -> List[Document]:
		cached = [d for d in datasets if _session.cache.contains(url=self.legilo_url.format(id=d.get("id")))]
		to_fetch = [d for d in datasets if not _session.cache.contains(url=self.legilo_url.format(id=d.get("id")))]

		if to_fetch:
			test_res = _session.get(self.legilo_url.format(id=to_fetch[0].get("id")), auth=self.auth)
			if test_res.status_code == 401:
				logger.error(
					"Legilo authentication failed (401 Unauthorized). "
					"Check LEGILO_USERNAME and LEGILO_PASSWORD environment variables."
				)
				return {"documents": []}
			logger.debug(
				"Legilo credential check passed (status %d) for dataset %s",
				test_res.status_code,
				to_fetch[0].get("id"),
			)

		supporting_docs = []

		for dataset in tqdm(cached, desc="Loading cached Legilo data", unit="dataset"):
			dataset_id = dataset.get("id")
			try:
				res = _session.get(self.legilo_url.format(id=dataset_id), auth=self.auth)
				supporting_docs.extend(self._docs_from_response(dataset, res))
			except Exception as e:
				logger.error("Legilo: error for dataset %s: %s", dataset_id, e, exc_info=True)

		for dataset in tqdm(to_fetch, desc="Fetching Legilo data", unit="dataset"):
			dataset_id = dataset.get("id")
			try:
				res = _session.get(self.legilo_url.format(id=dataset_id), auth=self.auth)
				if res.status_code != 200:
					logger.warning("Legilo request failed for dataset %s: HTTP %d", dataset_id, res.status_code)
					continue
				supporting_docs.extend(self._docs_from_response(dataset, res))
			except Exception as e:
				logger.error("Legilo: error for dataset %s: %s", dataset_id, e, exc_info=True)

		logger.info("Legilo: %d supporting document(s) fetched in total", len(supporting_docs))
		return {"documents": supporting_docs}
