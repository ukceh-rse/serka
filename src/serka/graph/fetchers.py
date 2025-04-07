from requests import Response
from typing import List, Dict, Any
import requests

from haystack import component


@component
class EIDCFetcher:
	@component.output_types(datasets=List[Dict[Any, Any]])
	def run(
		self,
		limit: int = 10000,
		page: int = 1,
		filter: str = "state:published AND recordType:Dataset",
	) -> List[Dict[Any, Any]]:
		res: Response = requests.get(
			"https://catalogue.ceh.ac.uk/eidc/documents",
			params={
				"page": page,
				"rows": limit,
				"term": filter,
			},
		)
		eidc_data = res.json()
		return eidc_data["results"]
