from pydantic import BaseModel, Field
from typing import List, Dict, Set, Optional, Any, Literal


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
	embedding_models: List[str]
	rag_models: List[str]
	collections: Dict[str, CollectionConfig]
	default_collection: str
	rag_enabled: bool
	unified_metadata: Set[str]


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


class RAGResponse(BaseModel):
	result: Result
	query: Optional[str]
	answer: Optional[str]
