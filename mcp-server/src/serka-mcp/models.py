from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Person(BaseModel):
	"""Represents a person that has contributed to data in the EIDC catalogue."""

	name: str = Field(description="The name of the person.")
	uri: str = Field(description="A unique uri corresponding to the person's ORCID.")


class Organisation(BaseModel):
	"""Represents an organisation that has contributed to data in the EIDC catalogue."""

	name: str = Field(description="The name of the organisation.")
	uri: str = Field(description="A unique URI identifying the organisation.")


class TextChunk(BaseModel):
	"""Represents a searchable chunk of text."""

	content: str = Field(description="The textual content of the chunk of text.")


class Dataset(BaseModel):
	"""Represents a dataset from the EIDC catalogue."""

	title: str = Field(description="The title of the dataset")
	uri: str = Field(description="URI of the dataset")
	citations: Optional[int] = Field(
		None, description="Number of citations for this dataset"
	)
	publication_date: Optional[str] = Field(
		None, description="Date when the dataset was published"
	)
	north_boundary: Optional[float] = Field(
		description="The northern most latitude of the datasets spatial boundary."
	)
	south_boundary: Optional[float] = Field(
		description="The southern most latitude of the datasets spatial boundary."
	)
	west_boundary: Optional[float] = Field(
		description="The western most longitude of the datasets spatial boundary."
	)
	east_boundary: Optional[float] = Field(
		description="The eastern most longitude of the datasets spatial boundary."
	)


class BoundingBox(BaseModel):
	"""Represents a bounding box of an area."""

	south: float = Field(..., description="Southern boundary (minimum latitude)")
	north: float = Field(..., description="Northern boundary (maximum latitude)")
	west: float = Field(..., description="Western boundary (minimum longitude)")
	east: float = Field(..., description="Eastern boundary (maximum longitude)")

	@classmethod
	def from_nominatim(cls, bbox_array: List[str]) -> "BoundingBox":
		"""Create BoundingBox from Nominatim's bbox array [south, north, west, east]"""
		return cls(
			south=float(bbox_array[0]),
			north=float(bbox_array[1]),
			west=float(bbox_array[2]),
			east=float(bbox_array[3]),
		)

	def expand(self, percentage: float = 10.0) -> "BoundingBox":
		"""Expand the bounding box by a given percentage.

		Args:
		    percentage: The percentage to expand by (default 10.0 for 10%)

		Returns:
		    A new BoundingBox that is expanded by the specified percentage
		"""
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
	name: str = Field(
		..., description="The full display name of the geocoded location."
	)
	boundary: BoundingBox = Field(
		..., description="A bounding box representing the boundry of the location."
	)


class ResultItem(BaseModel):
	item: TextChunk | Person | Organisation = Field(
		description="Contains the data for the result item."
	)
	type: Literal["TextChunk", "Person", "Organisation"] = Field(
		description="Specifies the type of the result item."
	)


class SearchResult(BaseModel):
	"""Represents results of performing a semantic search on the Serka knowledge graph."""

	result: ResultItem = Field(
		description="The result item that matches the semantic query."
	)
	dataset: Dataset = Field(
		description="The dataset connected to the node matching the semantic search."
	)
	score: float = Field(
		description="Score showing how semantically similar the content of the node is to the query"
	)
	description: str | None = Field(
		description="Description of the contents relationship to the dataset. Could be a description, metadata, or some other kind of supporting documentation."
	)


class SupportingDocument(BaseModel):
	"""Represents a supporting document of a dataset"""

	filename: str = Field(description="The filename of the supporting document")
	content: str = Field(description="The content of the supporting document")


class Error(BaseModel):
	"""Respresents an error."""

	msg: str = Field(description="A message describing the error")
