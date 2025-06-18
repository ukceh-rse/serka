from requests import Response
from typing import List, Dict, Any
import requests
from tqdm import tqdm
from haystack import component, Document
from serka.graph.extractors import extract_doi


@component
class EIDCFetcher:
	"""
	Haystack fetcher component for retrieving dataset infromation from the EIDC API.
	Args:
		url (str): The URL of the EIDC API endpoint.
	"""

	def __init__(self, url: str = "https://catalogue.ceh.ac.uk/eidc/documents"):
		self.url = url

	def get_eidc_json(self, ids: List[str]) -> List[Dict[Any, Any]]:
		results = []
		for id in tqdm(ids, desc="Fetching EIDC JSON", unit="dataset"):
			res: Response = requests.get(
				f"https://catalogue.ceh.ac.uk/documents/{id}?format=json"
			)
			if res.status_code == 200:
				results.append(res.json())
		return results

	@component.output_types(data=List[Dict[Any, Any]])
	def run(
		self,
		rows: int = 10000,
		page: int = 1,
		term: str = "state:published AND recordType:Dataset",
		**kwargs,
	) -> List[Dict[Any, Any]]:
		res: Response = requests.get(
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
		url (str): Format string for the URL of the Legilo API endpoint.
		{id} is used as a placeholder for the dataset ID
		e.g. "https://legilo.eds-infra.ceh.ac.uk/{id}/documents"
	"""

	def __init__(
		self,
		legilo_url: str = "https://legilo.eds-infra.ceh.ac.uk/{id}/documents",
		username: str = None,
		password: str = None,
	):
		self.legilo_url = legilo_url
		self.auth = (username, password)

	def extract_docs(self, json_data, title, uri):
		extracted_docs = []
		docs = json_data.get("success", {})
		for filename, content in docs.items():
			extracted_docs.append(
				Document(
					content=content,
					meta={"title": title, "field": "SUPPORTING_DOC", "uri": uri},
				)
			)
		return extracted_docs

	@component.output_types(supporting_docs=List[Document])
	def run(self, datasets: List[Dict[Any, Any]]) -> List[Document]:
		supporting_docs = []
		for dataset in tqdm(datasets, desc="Fetching Legilo records", unit="dataset"):
			id = dataset.get("id")
			dataset_uri = extract_doi(dataset["resourceIdentifiers"])
			dataset_title = dataset.get("title", "")
			url = self.legilo_url.format(id=id)
			res: Response = requests.get(
				url,
				auth=self.auth,
			)
			if res.status_code == 200:
				json_data = res.json()
				supporting_docs.extend(
					self.extract_docs(json_data, dataset_title, dataset_uri)
				)
		return {"supporting_docs": supporting_docs}
