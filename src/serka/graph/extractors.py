from haystack import component
from typing import List, Dict, Any
import re


@component
class AuthorExtractor:
	def _extract_record_author(self, record):
		return [
			{"forename": given, "surname": family, "uri": orcid}
			for given, family, orcid in zip(
				record["authorGivenName"],
				record["authorFamilyName"],
				record["authorOrcid"],
			)
		]

	@component.output_types(authors=List[Dict[str, Any]])
	def run(self, records: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
		authors = []
		for record in records:
			authors.extend(self._extract_record_author(record))
		unique_authors = {author["uri"]: author for author in authors}
		return {"authors": list(unique_authors.values())}


@component
class DatasetExtractor:
	def _extract_doi(self, ids: List[str]) -> str:
		for id in ids:
			if re.match(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", id, re.I):
				return f"https://doi.org/{id}"
		return None

	@component.output_types(datasets=List[Dict[str, Any]])
	def run(self, records: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
		datasets = []
		for record in records:
			dataset = {
				"uri": self._extract_doi(record["resourceIdentifier"]),
				"title": record["title"],
			}
			datasets.append(dataset)
		return {"datasets": datasets}
