from haystack import component
from typing import List, Dict, Any


@component
class AuthorExtractor:
	def _extract_dataset_author(self, dataset):
		return [
			{"forename": given, "surname": family, "orcid": orcid}
			for given, family, orcid in zip(
				dataset["authorGivenName"],
				dataset["authorFamilyName"],
				dataset["authorOrcid"],
			)
		]

	@component.output_types(documents=List[Dict[str, Any]])
	def run(self, datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		authors = []
		for dataset in datasets:
			authors.extend(self._extract_dataset_author(dataset))
		authors
		unique_authors = {author["orcid"]: author for author in authors}
		return list(unique_authors.values())
