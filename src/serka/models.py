from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal, Union


class ServiceConfig(BaseModel):
	host: str
	port: int


class BasModelServerConfig(BaseModel):
	provider: Literal["ollama", "bedrock"]
	embedding: str
	llm: str


class OllamaModelServerConfig(BasModelServerConfig):
	provider: Literal["ollama"] = "ollama"
	host: str
	port: int


class BedrockModelServerConfig(BasModelServerConfig):
	provider: Literal["bedrock"] = "bedrock"
	region: Literal["eu-west-2"] = "eu-west-2"


ModelServerConfig = Union[OllamaModelServerConfig, BedrockModelServerConfig]


class Config(BaseModel):
	mongo: ServiceConfig
	neo4j: ServiceConfig
	mcp: ServiceConfig
	models: ModelServerConfig
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
	thinking: bool = True
	complete: bool = False
	thinking_tokens: List[str] = []
	tokens: List[str] = []
