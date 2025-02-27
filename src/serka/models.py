from pydantic import BaseModel, Field
from typing import List, Dict, Set, Optional, Any


class ChromaConfig(BaseModel):
	host: str
	port: int


class OllamaConfig(BaseModel):
	host: str
	port: int


class MongoConfig(BaseModel):
	host: str
	port: int


class CollectionConfig(BaseModel):
	source_name: str
	description: str
	organisation: str
	url: str


class Config(BaseModel):
	chroma: ChromaConfig
	ollama: OllamaConfig
	mongo: MongoConfig
	embedding_models: List[str]
	rag_models: List[str]
	collections: Dict[str, CollectionConfig]
	default_collection: str
	rag_enabled: bool
	unified_metadata: Set[str]


class TaskStatus(BaseModel):
	id: str
	status: str
	result: Optional[Dict[str, Any]] = Field(default=None, exclude=None)

	class Config:
		json_encoders = {}
		exclude_none = True
