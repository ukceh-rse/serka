from haystack import component, Document
from typing import List, Dict, Tuple, Any
import re


def extract_doi(ids: List[str], default="") -> str:
	for id in ids:
		if re.match(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", id, re.I):
			return f"https://doi.org/{id}"
	return default


@component
class TextExtractor:
	def __init__(self, fields: str):
		self.fields = fields

	def extract_text_fields(self, record) -> List[Document]:
		uri = extract_doi(record["resourceIdentifier"])
		title = record.get("title", "")
		docs = [
			Document(content=record[field], meta={"uri": uri, "title": title})
			for field in self.fields
			if field in record
		]
		return docs

	@component.output_types(documents=List[Document])
	def run(self, records: List[Dict[Any, Any]]) -> Dict[str, List[Document]]:
		docs = []
		for record in records:
			docs.extend(self.extract_text_fields(record))
		return {"documents": docs}


@component
class RelationshipExtractor:
	def _extract_authorship(self, record) -> List[Tuple[str, str]]:
		if not all(field in record for field in ["authorRor", "authorOrcid"]):
			return []
		doi = extract_doi(record["resourceIdentifier"])
		return [(doi, orcid) for orcid in record["authorOrcid"]]

	def _extract_author_affiliations(self, record) -> List[Tuple[str, str]]:
		if not all(field in record for field in ["authorRor", "authorOrcid"]):
			return []
		return [
			(orcid, ror)
			for orcid, ror in zip(record["authorOrcid"], record["authorRor"])
		]

	def _extract_contributors(self, record) -> List[Tuple[str, str]]:
		if not all(field in record for field in ["ror", "resourceIdentifier"]):
			return []
		doi = extract_doi(record["resourceIdentifier"])
		return [(ror, doi) for ror in record["ror"]]

	@component.output_types(relationships=Dict[str, List[Tuple[str, str]]])
	def run(
		self, records: List[Dict[Any, Any]]
	) -> Dict[str, Dict[str, List[Tuple[str, str]]]]:
		authorships = []
		affiliations = []
		contributors = []
		for record in records:
			authorships.extend(self._extract_authorship(record))
			affiliations.extend(self._extract_author_affiliations(record))
			contributors.extend(self._extract_contributors(record))
		return {
			"relationships": {
				"AUTHORED_BY": authorships,
				"AFFILIATED_WITH": affiliations,
				"CONTRIBUTED_TO": contributors,
			}
		}


@component
class OrganisationExtractor:
	def _extract_record_organisations(self, record) -> List[Dict[str, str]]:
		return [
			{"name": org, "uri": ror}
			for org, ror in zip(record["organisation"], record["ror"])
		]

	def _extract_record_author_organisations(self, record) -> List[Dict[str, str]]:
		fields = ["authorAffiliation", "authorRor"]
		if not all(field in record for field in fields):
			return []
		return [
			{"name": org, "uri": ror}
			for org, ror in zip(record["authorAffiliation"], record["authorRor"])
		]

	@component.output_types(organisations=List[Dict[str, Any]])
	def run(self, records: List[Dict[Any, Any]]) -> Dict[str, List[Dict[str, str]]]:
		orgs = []
		for record in records:
			orgs.extend(self._extract_record_organisations(record))
			orgs.extend(self._extract_record_author_organisations(record))
		unique_orgs = {org["uri"]: org for org in orgs}
		return {"organisations": list(unique_orgs.values())}


@component
class AuthorExtractor:
	def _extract_record_authors(self, record) -> List[Dict[str, str]]:
		fields = ["authorGivenName", "authorFamilyName", "authorOrcid"]
		if not all(field in record for field in fields):
			return []
		return [
			{"forename": given, "surname": family, "uri": orcid}
			for given, family, orcid in zip(
				record["authorGivenName"],
				record["authorFamilyName"],
				record["authorOrcid"],
			)
		]

	@component.output_types(authors=List[Dict[str, Any]])
	def run(self, records: List[Dict[Any, Any]]) -> Dict[str, List[Dict[str, Any]]]:
		authors = []
		for record in records:
			authors.extend(self._extract_record_authors(record))
		unique_authors = {author["uri"]: author for author in authors}
		return {"authors": list(unique_authors.values())}


@component
class DatasetExtractor:
	@component.output_types(datasets=List[Dict[str, Any]])
	def run(self, records: List[Dict[Any, Any]]) -> Dict[str, List[Dict[str, Any]]]:
		datasets = []
		for record in records:
			dataset = {
				"uri": extract_doi(record["resourceIdentifier"]),
				"title": record["title"],
			}
			datasets.append(dataset)
		return {"datasets": datasets}
