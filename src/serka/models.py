from pydantic import BaseModel
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


class TaskStatus(BaseModel):
	id: str
	status: Literal["pending", "running", "complete", "failed"] = "pending"
	result: Optional[Dict[str, Any]] = {}
