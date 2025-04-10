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

	@component.output_types(datasets=List[Dict[Any, Any]])
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
		return {"datasets": eidc_data["results"]}
