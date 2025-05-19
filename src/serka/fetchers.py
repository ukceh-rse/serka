from requests import Response
from typing import List, Dict, Any
import requests

from haystack import component


@component
class EIDCFetcher:
	"""
	Haystack fetcher component for retrieving dataset infromation from the EIDC API.
	Args:
		url (str): The URL of the EIDC API endpoint.
	"""

	def __init__(self, url: str = "https://catalogue.ceh.ac.uk/eidc/documents"):
		self.url = url

	@component.output_types(records=List[Dict[Any, Any]])
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
		return {"records": eidc_data["results"]}


@component
class LegiloFetcher:
	"""
	Haystack fetcher component for retrieving supporting documentation from the Legilo API.
	Args:
		url (str): The URL of the Legilo API endpoint.
	"""

	def __init__(
		self,
		legilo_url: str = "https://legilo.eds-infra.ceh.ac.uk/{id}/documents",
		legilo_username: str = None,
		legilo_password: str = None,
	):
		self.legilo_url = legilo_url
		self.legilo_username = legilo_username
		self.legilo_password = legilo_password

	@component.output_types(records=List[Dict[Any, Any]])
	def run(self, dataset_ids: List[str]) -> List[Dict[Any, Any]]:
		for id in dataset_ids:
			url = self.legilo_url.format(id=id)
			print(url)
			res: Response = requests.get(
				url,
				auth=(self.legilo_username, self.legilo_password),
			)
			res.status_code
			if res.status_code != 200:
				print(f"Error: {res.status_code}")
				return {"records": []}
			if res.status_code == 200:
				print(f"Success: {res.status_code}")
				print(res.content)
		return {"records": "results"}
