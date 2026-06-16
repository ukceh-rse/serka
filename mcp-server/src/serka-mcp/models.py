from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Entity(BaseModel):
	"""Any node in the DOO knowledge graph, typed via @type."""

	id: str = Field(description="The @id (URI) of this entity.")
	type: List[str] = Field(description="The @type(s) of this entity as DOO class URIs.")
	label: Optional[str] = Field(None, description="Human-readable label (title/name).")
	properties: dict[str, Any] = Field(default_factory=dict, description="All other properties mapped to DOO terms.")


class Relation(BaseModel):
	"""A directed edge in the knowledge graph."""

	predicate: str = Field(description="DOO predicate URI (e.g. 'dcat:theme', 'dcterms:isPartOf').")
	source: str = Field(description="@id of the source entity.")
	target: Entity = Field(description="The target entity.")


class Attribution(BaseModel):
	"""An agent (Person/Organisation) associated with a Dataset and their role."""

	agent: Entity = Field(description="The contributing Person or Organisation.")
	role: str = Field(description="The role scoro/dcterms URI (e.g. 'scoro:AuthorshipRole').")


class SearchHit(BaseModel):
	"""A single search result with relevance score."""

	entity: Entity = Field(description="The matched entity.")
	score: float = Field(description="Relevance score.")
	matched_on: str = Field(description="Field or relationship type that produced this match.")
	excerpt: Optional[str] = Field(None, description="Matched text excerpt (populated for text_content matches).")


class Dataset(BaseModel):
	"""Represents a dataset from the EIDC catalogue (used by list_datasets)."""

	title: str = Field(description="The title of the dataset.")
	uri: str = Field(description="URI of the dataset.")
	citations: Optional[int] = Field(None, description="Number of citations for this dataset.")
	publication_date: Optional[str] = Field(None, description="Date when the dataset was published.")
	north_boundary: Optional[float] = Field(None, description="Northern most latitude of the spatial boundary.")
	south_boundary: Optional[float] = Field(None, description="Southern most latitude of the spatial boundary.")
	west_boundary: Optional[float] = Field(None, description="Western most longitude of the spatial boundary.")
	east_boundary: Optional[float] = Field(None, description="Eastern most longitude of the spatial boundary.")


class DatasetPage(BaseModel):
	"""A paginated page of datasets from the EIDC catalogue."""

	datasets: List[Dataset] = Field(description="Datasets on this page.")
	total: int = Field(description="Total number of datasets in the catalogue.")
	page: int = Field(description="Current page number (1-based).")
	page_size: int = Field(description="Number of datasets per page.")
	total_pages: int = Field(description="Total number of pages.")


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


class Error(BaseModel):
	"""Represents an error."""

	msg: str = Field(description="A message describing the error.")
