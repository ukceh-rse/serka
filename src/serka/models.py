from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any


class Result(BaseModel):
	success: bool
	msg: str


class Document(BaseModel):
	content: str = Field(..., description="The content of the document.")
	metadata: Optional[Dict[str, Any]] = Field(
		None, description="Metadata associated with the document."
	)

	def __hash__(self):
		metadata_hash = tuple(sorted(self.metadata.items())) if self.metadata else None
		return hash((self.content, metadata_hash))

	def __eq__(self, other):
		if not isinstance(other, Document):
			return False
		return self.content == other.content and self.metadata == other.metadata


class ScoredDocument(BaseModel):
	document: Document
	score: float

	def __hash__(self):
		return hash((hash(self.document), self.score))

	def __eq__(self, other):
		if not isinstance(other, ScoredDocument):
			return False
		return self.document == other.document and self.score == other.score


class GroupedDocuments(BaseModel):
	docs: List[ScoredDocument]
	groupedby: str


class RAGResponse(BaseModel):
	id: str
	answer: str = ""
	thinking: bool = True
	complete: bool = False
	thinking_tokens: List[str] = []
	tokens: List[str] = []
