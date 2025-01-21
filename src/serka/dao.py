import chromadb.api
from haystack import Pipeline
from haystack.components.fetchers import LinkContentFetcher
from haystack.components.converters import JSONConverter
from haystack.components.preprocessors import DocumentSplitter
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack_integrations.components.retrievers.chroma import ChromaEmbeddingRetriever
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack.components.writers import DocumentWriter
from typing import List, Dict, Any, Set
import logging
from dataclasses import dataclass
import chromadb


logger = logging.getLogger(__name__)


@dataclass
class DAO:
	ollama_host: str
	ollama_port: int
	chroma_host: str
	chroma_port: int
	default_embedding_model: str
	default_rag_model: str
	_chroma_client: chromadb.api.ClientAPI = None

	def __post_init__(self):
		logger.info(f"Creating DAO with [{self.chroma_host}:{self.chroma_port}]")
		self._chroma_client = chromadb.HttpClient(
			host=self.chroma_host, port=self.chroma_port
		)

	def list_collections(self) -> List[str]:
		return self._chroma_client.list_collections()

	def insert(
		self, url, collection_name: str, embedding_model: str | None = None
	) -> Dict[str, Any]:
		p = self._eidc_metadata_insertion_pipeline(collection_name, embedding_model)
		result = p.run(data={"fetcher": {"urls": [url]}})
		return {"status": "success", "documents": result["writer"]["documents_written"]}

	def delete(self, collection_name: str) -> Dict[str, Any]:
		self._chroma_client.delete_collection(collection_name)
		return {"status": "success"}

	def query(
		self, collection_name: str, query: str, n: int = 5
	) -> List[Dict[str, Any]]:
		p = self._eidc_metadata_query_pipeline(collection_name)
		results = p.run({"embedder": {"text": query}})
		sorted_results = sorted(
			results["retriever"]["documents"], key=lambda x: x.score, reverse=False
		)[:n]
		return [
			{
				"doc": doc.content,
				"dataset": doc.meta["title"],
				"identifier": doc.meta["identifier"],
				"score": doc.score,
			}
			for doc in sorted_results
		]

	def peek(self, collection_name: str, n: int = 5) -> List[Dict[str, Any]]:
		result = self._chroma_client.get_collection(collection_name).peek(n)
		return [
			{"doc": doc, "dataset": meta["title"], "identifier": meta["identifier"]}
			for doc, meta in zip(result["documents"], result["metadatas"])
		]

	def _eidc_metadata_query_pipeline(self, collection_name: str) -> Pipeline:
		doc_store = ChromaDocumentStore(
			host=self.chroma_host,
			port=self.chroma_port,
			collection_name=collection_name,
		)
		p = Pipeline()
		p.add_component(
			"embedder",
			OllamaTextEmbedder(
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				model=self.default_embedding_model,
			),
		)
		p.add_component("retriever", ChromaEmbeddingRetriever(doc_store))
		p.connect("embedder.embedding", "retriever.query_embedding")
		return p

	def _eidc_metadata_insertion_pipeline(
		self,
		collection_name: str,
		embedding_model: str | None = None,
		content_field: str = "description",
		meta_fields: Set[str] = {"identifier", "title"},
		chunk_length: int = 150,
		chunk_overlap: int = 50,
	) -> Pipeline:
		model = embedding_model or self.default_embedding_model
		logger.info(
			f"Creating EIDC metadata insertion pipeline["
			f"ollama({self.ollama_host}:{self.ollama_port}), "
			f"chroma({self.chroma_host}:{self.chroma_port}), "
			f"[model({model})]"
		)
		doc_store = ChromaDocumentStore(
			host=self.chroma_host,
			port=self.chroma_port,
			collection_name=collection_name,
		)
		p = Pipeline()
		p.add_component("fetcher", LinkContentFetcher())
		p.add_component(
			"converter",
			JSONConverter(
				jq_schema=".results[]",
				content_key=content_field,
				extra_meta_fields=meta_fields,
			),
		)
		p.add_component(
			"splitter",
			DocumentSplitter(
				split_by="word", split_length=chunk_length, split_overlap=chunk_overlap
			),
		)
		p.add_component(
			"embedder",
			OllamaDocumentEmbedder(
				url=f"http://{self.ollama_host}:{self.ollama_port}",
				model=model,
			),
		)
		p.add_component("writer", DocumentWriter(doc_store))
		p.connect("fetcher.streams", "converter.sources")
		p.connect("converter.documents", "splitter.documents")
		p.connect("splitter.documents", "embedder.documents")
		p.connect("embedder.documents", "writer.documents")
		return p
