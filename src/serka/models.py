from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal


class ServiceConfig(BaseModel):
	host: str
	port: int


class CollectionConfig(BaseModel):
	source_name: str
	description: str
	organisation: str
	url: str


class Config(BaseModel):
	chroma: ServiceConfig
	ollama: ServiceConfig
	mongo: ServiceConfig
	neo4j: ServiceConfig
	embedding_models: List[str]
	rag_models: List[str]
	collections: Dict[str, CollectionConfig]
	default_collection: str
	rag_enabled: bool
	unified_metadata: List[str]

	def __hash__(self):
		return hash(self.model_dump_json())


class Result(BaseModel):
	success: bool
	msg: str


class TaskStatus(BaseModel):
	id: str
	status: Literal["pending", "running", "complete", "failed"] = "pending"
	result: Result = None


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
	complete: bool = False
	tokens: List[str] = []
