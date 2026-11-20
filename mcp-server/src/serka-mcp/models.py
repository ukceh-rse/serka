from typing import List

from pydantic import BaseModel, Field


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
