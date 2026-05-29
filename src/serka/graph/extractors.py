import logging
from typing import Any, Dict, List, Tuple

from haystack import Document, component

logger = logging.getLogger(__name__)


def extract_doi(resource_identifiers, default="") -> str:
	for id in resource_identifiers:
		if "codeSpace" in id and id["codeSpace"] == "doi:":
			return f"https://doi.org/{id['code']}"
	return default


@component
class EntityExtractor:
	def _extract_boundary(self, record):
		try:
			bb = record["boundingBoxes"][0]
			boundary = {
				"south_boundary": bb["southBoundLatitude"],
				"north_boundary": bb["northBoundLatitude"],
				"west_boundary": bb["westBoundLongitude"],
				"east_boundary": bb["eastBoundLongitude"],
			}
			# Drop any keys whose value is None — Neo4j forbids MERGE on null properties
			return {k: v for k, v in boundary.items() if v is not None}
		except Exception as e:
			logger.error(f"Error extracting boundary: {e}")
			return {}

	def _extract_dataset(self, record) -> Dict[str, str]:
		dataset = {
			"uri": extract_doi(record.get("resourceIdentifiers", [])),
			"title": record.get("title", ""),
			**self._extract_boundary(record),
		}
		if (citations := record.get("incomingCitationCount")) is not None:
			dataset["citations"] = citations
		if pub_date := record.get("publicationDate"):
			dataset["publication_date"] = pub_date
		return dataset

	def _extract_authors(self, record):
		author_list = record.get("authors", [])
		authors = [
			{"name": author.get("fullName", ""), "uri": author["nameIdentifier"]}
			for author in author_list
			if "nameIdentifier" in author
		]
		doi = extract_doi(record.get("resourceIdentifiers", []))
		authorship = [(doi, author["uri"]) for author in authors]
		return authors, authorship

	def _extract_organisations(self, author_list):
		orgs = [
			{
				"name": author["organisationName"],
				"uri": author["organisationIdentifier"],
			}
			for author in author_list
			if "organisationIdentifier" in author
		]
		affiliations = [
			(author["nameIdentifier"], author["organisationIdentifier"])
			for author in author_list
			if all(
				key in author for key in ["organisationIdentifier", "nameIdentifier"]
			)
		]
		return orgs, affiliations

	@component.output_types(
		nodes=Dict[str, List[Dict[str, Any]]],
		relationships=Dict[str, List[Tuple[str, str]]],
	)
	def run(self, data: List[Dict[Any, Any]]):
		datasets = []
		authors = []
		orgs = []
		authored_by = []
		affiliated_with = []
		for record in data:
			try:
				author_list = record.get("authors", [])
				record_authors, authorship = self._extract_authors(record)
				authors.extend(record_authors)
				authored_by.extend(authorship)

				record_orgs, affiliations = self._extract_organisations(author_list)
				orgs.extend(record_orgs)
				affiliated_with.extend(affiliations)

				datasets.append(self._extract_dataset(record))
			except Exception as e:
				logger.warning(
					f"Skipping record due to extraction error: {e} — record keys: {list(record.keys())}"
				)

		authors = list({author["uri"]: author for author in authors}.values())
		orgs = list({org["uri"]: org for org in orgs}.values())

		authored_by = list(set(authored_by))
		affiliated_with = list(set(affiliated_with))

		return {
			"nodes": {"Dataset": datasets, "Person": authors, "Organisation": orgs},
			"relationships": {
				"AUTHORED_BY": authored_by,
				"AFFILIATED_WITH": affiliated_with,
			},
		}


@component
class DocumentTruncator:
	def __init__(self, max_chars: int = 45_000):
		self.max_chars = max_chars

	@component.output_types(documents=List[Document])
	def run(self, documents: List[Document]) -> Dict[str, List[Document]]:
		truncated = []
		for doc in documents:
			if doc.content and len(doc.content) > self.max_chars:
				logger.warning(
					"Truncating document '%s' from %d to %d characters",
					doc.meta.get("uri", "unknown"),
					len(doc.content),
					self.max_chars,
				)
				doc = Document(content=doc.content[: self.max_chars], meta=doc.meta)
			truncated.append(doc)
		return {"documents": truncated}


@component
class TextExtractor:
	def __init__(self, fields: str):
		self.fields = fields

	def extract_text_fields(self, record) -> List[Document]:
		uri = extract_doi(record.get("resourceIdentifiers", []))
		title = record.get("title", "")
		docs = [
			Document(
				content=record[field], meta={"uri": uri, "title": title, "field": field}
			)
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
