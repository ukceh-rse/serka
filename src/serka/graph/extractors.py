import logging
from typing import Any, Dict, List, Tuple

from haystack import Document, component

logger = logging.getLogger(__name__)

_PARTY_FIELDS: dict[str, str] = {
	"authors": "author",
	"custodians": "custodian",
	"publishers": "publisher",
	"distributorContacts": "distributorContact",
	"pointsOfContact": "pointOfContact",
}


def extract_doi(resource_identifiers, default="") -> str:
	for id in resource_identifiers:
		if "codeSpace" in id and id["codeSpace"] == "doi:":
			return f"https://doi.org/{id['code']}"
	return default


def _collect_identifiers(resource_identifiers: list) -> list[str]:
	ids = []
	for rid in resource_identifiers:
		if "code" not in rid:
			continue
		if rid.get("codeSpace") == "doi:":
			ids.append(f"https://doi.org/{rid['code']}")
		else:
			ids.append(rid["code"])
	return ids


def _infer_concept_scheme(uri: str, field: str) -> str:
	if "gemet" in uri or "eionet.europa.eu" in uri:
		return "gemet"
	if "geonames.org" in uri:
		return "geonames"
	if "inspire.ec.europa.eu" in uri:
		return "inspire-topic"
	return field


@component
class EntityExtractor:
	def _extract_boundary(self, record: dict) -> dict:
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

	def _extract_dataset(self, record: dict) -> Dict[str, Any]:
		dataset: Dict[str, Any] = {
			"uri": record.get("uri", ""),
			"title": record.get("title", ""),
			"identifiers": _collect_identifiers(record.get("resourceIdentifiers", [])),
			**self._extract_boundary(record),
		}
		if (citations := record.get("incomingCitationCount")) is not None:
			dataset["citations"] = citations
		if pub_date := record.get("publicationDate"):
			dataset["publication_date"] = pub_date
		if rt := record.get("resourceType"):
			dataset["resource_type"] = rt.get("value", "") if isinstance(rt, dict) else rt
		if al := record.get("accessLimitation"):
			dataset["access_rights"] = al.get("value", "") if isinstance(al, dict) else al
		licences = record.get("licences", [])
		if licences and "uri" in licences[0]:
			dataset["licence"] = licences[0]["uri"]
		extents = record.get("temporalExtents", [])
		if extents:
			if begin := extents[0].get("begin"):
				dataset["temporal_start"] = begin
			if end := extents[0].get("end"):
				dataset["temporal_end"] = end
		return dataset

	def _extract_parties(
		self, record: dict, dataset_uri: str
	) -> tuple[list, list, list, list]:
		persons: Dict[str, dict] = {}
		orgs: Dict[str, dict] = {}
		associations: List[Tuple] = []
		affiliations: List[Tuple] = []

		for field, default_role in _PARTY_FIELDS.items():
			for entry in record.get(field, []):
				role = entry.get("role", default_role)
				person_uri = entry.get("nameIdentifier")
				org_uri = entry.get("organisationIdentifier")

				if person_uri:
					persons[person_uri] = {
						"uri": person_uri,
						"name": entry.get("fullName", ""),
					}
					associations.append((dataset_uri, person_uri, role))

				if org_uri:
					orgs[org_uri] = {
						"uri": org_uri,
						"name": entry.get("organisationName", ""),
					}
					associations.append((dataset_uri, org_uri, role))

					if person_uri:
						affiliations.append((person_uri, org_uri))

		return list(persons.values()), list(orgs.values()), associations, affiliations

	def _extract_concepts(
		self, record: dict, dataset_uri: str
	) -> tuple[list, list]:
		concepts: Dict[str, dict] = {}
		themes: List[Tuple] = []

		for field in ("topicCategories", "keywordsOther", "keywordsPlace"):
			for kw in record.get(field, []):
				uri = kw.get("uri")
				if not uri:
					continue
				concepts[uri] = {
					"uri": uri,
					"label": kw.get("value", ""),
					"scheme": _infer_concept_scheme(uri, field),
				}
				themes.append((dataset_uri, uri))

		return list(concepts.values()), themes

	def _extract_relations(self, record: dict, dataset_uri: str) -> List[Tuple]:
		relations = []
		for rel in record.get("relationships", []):
			target_id = rel.get("identifier")
			predicate = rel.get("associationType", "dcterms:relation")
			if target_id:
				target_uri = f"https://catalogue.ceh.ac.uk/id/{target_id}"
				relations.append((dataset_uri, predicate, target_uri))
		return relations

	def _extract_citations(
		self, record: dict, dataset_uri: str
	) -> tuple[list, list]:
		docs = []
		relations: List[Tuple] = []
		for citation in record.get("incomingCitations", []):
			url = citation.get("url")
			if not url:
				continue
			docs.append({
				"uri": url,
				"bibliographic_citation": citation.get("description", ""),
			})
			relations.append((dataset_uri, "dcterms:isReferencedBy", url))
		return docs, relations

	@component.output_types(
		nodes=Dict[str, List[Dict[str, Any]]],
		relationships=Dict[str, List[Tuple]],
	)
	def run(self, data: List[Dict[Any, Any]]):
		datasets = []
		persons: Dict[str, dict] = {}
		orgs: Dict[str, dict] = {}
		concepts: Dict[str, dict] = {}
		documents: Dict[str, dict] = {}
		associations: List[Tuple] = []
		affiliations: List[Tuple] = []
		themes: List[Tuple] = []
		relations: List[Tuple] = []

		for record in data:
			try:
				dataset_uri = record.get("uri", "")
				datasets.append(self._extract_dataset(record))

				rec_persons, rec_orgs, rec_assoc, rec_affil = self._extract_parties(
					record, dataset_uri
				)
				for p in rec_persons:
					persons[p["uri"]] = p
				for o in rec_orgs:
					orgs[o["uri"]] = o
				associations.extend(rec_assoc)
				affiliations.extend(rec_affil)

				rec_concepts, rec_themes = self._extract_concepts(record, dataset_uri)
				for c in rec_concepts:
					concepts[c["uri"]] = c
				themes.extend(rec_themes)

				relations.extend(self._extract_relations(record, dataset_uri))

				rec_docs, rec_cite_rels = self._extract_citations(record, dataset_uri)
				for d in rec_docs:
					documents[d["uri"]] = d
				relations.extend(rec_cite_rels)

			except Exception as e:
				logger.warning(
					f"Skipping record due to extraction error: {e} — record keys: {list(record.keys())}"
				)

		associations = list({(a[0], a[1], a[2]): a for a in associations}.values())
		affiliations = list(set(affiliations))
		themes = list(set(themes))
		relations = list({(r[0], r[1], r[2]): r for r in relations}.values())

		return {
			"nodes": {
				"Dataset": datasets,
				"Person": list(persons.values()),
				"Organisation": list(orgs.values()),
				"Concept": list(concepts.values()),
				"Document": list(documents.values()),
			},
			"relationships": {
				"ASSOCIATED_WITH": associations,
				"AFFILIATED_WITH": affiliations,
				"HAS_THEME": themes,
				"RELATION": relations,
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

	def extract_text_fields(self, record: dict) -> List[Document]:
		uri = record.get("uri", "")
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
