from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from ontology import JSONLD_CONTEXT, MAPPING

_TERMS: dict[str, Any] = MAPPING["terms"]


def _term(key: str, description: str, default: Any = None) -> Any:
	"""A field whose JSON key is mapped to an ontology term in the JSON-LD @context."""
	term = _TERMS[key]
	curie = term if isinstance(term, str) else term.get("@id") or f"^{term['@reverse']}"
	return Field(default, description=description, json_schema_extra={"x-rdf-property": curie})


class JsonLd(BaseModel):
	model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

	def dump(self) -> dict[str, Any]:
		return self.model_dump(mode="json", by_alias=True, exclude_none=True)


# ---------------------------------------------------------------------------
# Entities — one model per DOO class, so the output schema documents each field.
# ---------------------------------------------------------------------------


class BaseEntity(JsonLd):
	"""A node in the knowledge graph. Untyped when only known as a relationship target."""

	id: Optional[str] = Field(None, alias="@id", description="The entity's URI.")
	type: List[str] = Field(default_factory=list, alias="@type", description="DOO class CURIEs, e.g. ['dcat:Dataset'].")
	label: Optional[str] = _term("label", "Human-readable label (title or name).")


class PeriodOfTime(JsonLd):
	type: Literal["dcterms:PeriodOfTime"] = Field("dcterms:PeriodOfTime", alias="@type")
	start_date: Optional[str] = _term("start_date", "Start of the temporal extent (ISO date).")
	end_date: Optional[str] = _term("end_date", "End of the temporal extent (ISO date).")


class DatasetEntity(BaseEntity):
	model_config = ConfigDict(json_schema_extra={"x-rdf-type": "dcat:Dataset"})

	title: Optional[str] = _term("title", "Dataset title.")
	publication_date: Optional[str] = _term("publication_date", "Publication date (ISO date).")
	identifiers: Optional[List[str]] = _term("identifiers", "All identifiers, e.g. the DOI as https://doi.org/...")
	resource_type: Optional[str] = _term("resource_type", "EIDC resource type, e.g. 'dataset'.")
	access_rights: Optional[str] = _term("access_rights", "Access limitation statement.")
	licence: Optional[str] = _term("licence", "Licence URI.")
	temporal: Optional[PeriodOfTime] = _term("temporal", "Temporal extent covered by the data.")
	bbox: Optional[str] = _term("bbox", "Spatial extent as a WKT polygon (lon lat, EPSG:4326).")
	citations: Optional[int] = _term("citations", "Number of publications citing the dataset.")


class PersonEntity(BaseEntity):
	model_config = ConfigDict(json_schema_extra={"x-rdf-type": "foaf:Person"})

	name: Optional[str] = _term("name", "Full name.")


class OrganisationEntity(BaseEntity):
	model_config = ConfigDict(json_schema_extra={"x-rdf-type": "foaf:Organization"})

	name: Optional[str] = _term("name", "Organisation name.")


class GrantEntity(BaseEntity):
	model_config = ConfigDict(json_schema_extra={"x-rdf-type": "frapo:Grant"})

	title: Optional[str] = _term("title", "Award title.")
	grant_number: Optional[str] = _term("grant_number", "Funder's award number, e.g. NE/V010603/1.")
	see_also: Optional[str] = _term("see_also", "Web page for the award, when known.")


class ConceptEntity(BaseEntity):
	model_config = ConfigDict(json_schema_extra={"x-rdf-type": "skos:Concept"})

	scheme: Optional[str] = _term("scheme", "Vocabulary the concept comes from, e.g. 'gemet'.")


class ExpressionEntity(BaseEntity):
	model_config = ConfigDict(json_schema_extra={"x-rdf-type": "fabio:Expression"})

	bibliographic_citation: Optional[str] = _term("bibliographic_citation", "Full citation of the publication.")


class ManifestationEntity(BaseEntity):
	model_config = ConfigDict(json_schema_extra={"x-rdf-type": "fabio:DigitalManifestation"})

	title: Optional[str] = _term("title", "File name.")
	format: Optional[str] = _term("format", "MIME type of the file.")


Entity = Union[
	DatasetEntity,
	PersonEntity,
	OrganisationEntity,
	GrantEntity,
	ConceptEntity,
	ExpressionEntity,
	ManifestationEntity,
	BaseEntity,
]


# ---------------------------------------------------------------------------
# Tool results — each a JSON-LD document: one @context, results in @graph.
# ---------------------------------------------------------------------------


class Graph(JsonLd):
	context: dict[str, Any] = Field(
		default_factory=lambda: JSONLD_CONTEXT,
		alias="@context",
		description="JSON-LD context mapping keys and CURIEs to ontology IRIs.",
	)


class PathStep(JsonLd):
	"""One hop on the path connecting a returned entity to the node bearing the matched text."""

	predicate: str = _term("predicate", "DOO predicate or role CURIE of this hop (e.g. 'pro:author', 'dcat:theme').", ...)
	entity: Entity = _term("entity", "The entity reached by this hop.", ...)


class SearchHit(JsonLd):
	"""A single search result with relevance score."""

	entity: Entity = _term("entity", "The returned entity (of the requested return_type, or the matched node itself).", ...)
	score: float = _term("score", "Relevance score.", ...)
	matched_on: str = _term("matched_on", "Field or section bearing the matched text (e.g. 'description', 'metadata').", ...)
	excerpt: Optional[str] = _term("excerpt", "Matched text excerpt (populated for text matches).")
	path: List[PathStep] = Field(
		default_factory=list,
		description="Ordered hops FROM the returned entity TO the node bearing the matched text. Empty when the entity itself matched.",
		json_schema_extra={"x-rdf-property": "serka:path"},
	)


class SearchMeta(BaseModel):
	return_type: Optional[str] = Field(None, description="The DOO class searched for, if any.")
	hops: int = Field(description="Maximum hops used from the matched node to the returned entity.")
	filters: dict[str, Any] = Field(default_factory=dict, description="Filters applied.")
	theme_expansion: Optional[dict[str, int]] = Field(
		None, description="Theme concept -> number of concepts (itself plus narrower) it was expanded to."
	)
	reranked: bool = Field(False, description="Whether results were re-scored by the cross-encoder.")
	warnings: List[str] = Field(default_factory=list, description="Notes on how the query was interpreted.")


class SearchResults(Graph):
	graph: List[SearchHit] = Field(alias="@graph", description="Search hits, best first.")
	meta: SearchMeta = _term("meta", "How the search was run.", ...)


class Relation(JsonLd):
	"""A directed edge in the knowledge graph."""

	predicate: str = _term("predicate", "DOO predicate CURIE (e.g. 'dcat:theme', 'dcterms:isPartOf').", ...)
	source: str = _term("source", "@id of the source entity.", ...)
	target: Entity = _term("target", "The entity at the other end of the edge.", ...)


class RelationList(Graph):
	graph: List[Relation] = Field(alias="@graph")


class Attribution(JsonLd):
	"""DOO's reified role: an agent holds a role (pro:RoleInTime) in relation to a dataset."""

	type: Literal["pro:RoleInTime"] = Field("pro:RoleInTime", alias="@type")
	agent: Entity = _term("agent", "The Person or Organisation holding the role.", ...)
	role: str = _term("role", "Role individual (pro:withRole), e.g. 'pro:author', 'scoro:data-curator'.", ...)
	role_type: str = _term("role_type", "Class of the role, e.g. 'pro:PublishingRole', 'scoro:DataRole'.", ...)
	relates_to: str = _term("relates_to", "@id of the dataset the role relates to.", ...)


class AttributionList(Graph):
	graph: List[Attribution] = Field(alias="@graph")


class EntityList(Graph):
	graph: List[Entity] = Field(alias="@graph")


class PageMeta(BaseModel):
	total: int = Field(description="Total number of datasets in the catalogue.")
	page: int = Field(description="Current page number (1-based).")
	page_size: int = Field(description="Number of datasets per page.")
	total_pages: int = Field(description="Total number of pages.")


class DatasetPage(Graph):
	graph: List[DatasetEntity] = Field(alias="@graph", description="Datasets on this page.")
	meta: PageMeta = _term("meta", "Pagination.", ...)


# ---------------------------------------------------------------------------
# Ontology description (describe_ontology tool)
# ---------------------------------------------------------------------------


class TermInfo(BaseModel):
	curie: str
	iri: str
	definition: Optional[str] = None
	count: int = Field(0, description="Number of nodes/edges in the graph using this term.")


class RoleInfo(TermInfo):
	role_class: str = Field(description="The role's DOO class.")
	eidc_roles: List[str] = Field(description="EIDC role names mapped to this role.")


class OntologyDescription(BaseModel):
	doo_version: str
	prefixes: dict[str, str]
	types: List[TermInfo] = Field(description="Entity classes (use as search return_type / get_relations target_type).")
	predicates: List[TermInfo] = Field(description="Relationship predicates (use with get_relations).")
	role_classes: List[TermInfo] = Field(description="Role classes (use as a role filter to match any role of that class).")
	roles: List[RoleInfo] = Field(description="Role individuals (use as a role filter for an exact role).")


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------


class BoundingBox(BaseModel):
	"""Represents a bounding box of an area."""

	south: float = Field(..., description="Southern boundary (minimum latitude)")
	north: float = Field(..., description="Northern boundary (maximum latitude)")
	west: float = Field(..., description="Western boundary (minimum longitude)")
	east: float = Field(..., description="Eastern boundary (maximum longitude)")

	@classmethod
	def from_nominatim(cls, bbox_array: List[str]) -> "BoundingBox":
		return cls(
			south=float(bbox_array[0]),
			north=float(bbox_array[1]),
			west=float(bbox_array[2]),
			east=float(bbox_array[3]),
		)

	def expand(self, percentage: float = 10.0) -> "BoundingBox":
		width = self.east - self.west
		height = self.north - self.south
		width_expansion = (width * percentage) / 200.0
		height_expansion = (height * percentage) / 200.0
		return BoundingBox(
			south=self.south - height_expansion,
			north=self.north + height_expansion,
			west=self.west - width_expansion,
			east=self.east + width_expansion,
		)


class GeoCodedLocation(BaseModel):
	name: str = Field(..., description="The full display name of the geocoded location.")
	boundary: BoundingBox = Field(..., description="A bounding box representing the boundary of the location.")
