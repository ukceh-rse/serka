import chromadb.api
import haystack
from typing import List, Dict, Any, Set
import logging
import chromadb
from .models import Document
from .pipelines import PipelineBuilder


logger = logging.getLogger(__name__)


class DAO:
	_chroma_client: chromadb.api.ClientAPI = None
	_pipeline_builder: PipelineBuilder = None

	def __init__(
		self,
		ollama_host,
		ollama_port,
		chroma_host,
		chroma_port,
		default_embedding_model,
		default_rag_model,
	):
		self._chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
		self._pipeline_builder = PipelineBuilder(
			ollama_host=ollama_host,
			ollama_port=ollama_port,
			chroma_host=chroma_host,
			chroma_port=chroma_port,
			embedding_model=default_embedding_model,
			rag_model=default_rag_model,
			chunk_length=150,
			chunk_overlap=50,
		)

	def list_collections(self) -> List[str]:
		return self._chroma_client.list_collections()

	def insert(self, document: Document, collection: str):
		p = self._pipeline_builder.insert_pipeline(collection)
		sources = [haystack.Document(content=document.content, meta=document.metadata)]
		result = p.run(data={"splitter": {"documents": sources}})
		print(result)

	def scrape(
		self,
		url,
		collection_name: str,
		source_type: str = "eidc",
		unified_metadata: Set[str] = {},
	) -> Dict[str, Any]:
		p = self._pipeline_builder.scraping_pipeline(
			collection_name, source_type, unified_metadata
		)
		result = p.run(data={"fetcher": {"urls": [url]}})
		return {"status": "success", "documents": result["writer"]["documents_written"]}

	def delete(self, collection_name: str) -> Dict[str, Any]:
		self._chroma_client.delete_collection(collection_name)
		return {"status": "success"}

	def query(
		self, collection_name: str, query: str, n: int = 10
	) -> List[Dict[str, Any]]:
		p = self._pipeline_builder.query_pipeline(collection_name, n)
		results = p.run({"embedder": {"text": query}})["retriever"]["documents"]
		output = []
		for doc in results:
			d = {k: v for k, v in doc.meta.items()}
			d["score"] = doc.score
			output.append(d)
		return sorted(output, key=lambda x: x["score"])

	def peek(self, collection_name: str, n: int = 5) -> List[Dict[str, str]]:
		result = self._chroma_client.get_collection(collection_name).peek(n)
		output = []
		for doc, meta in zip(result["documents"], result["metadatas"]):
			d = {k: str(v) for k, v in meta.items()}
			d["doc"] = doc
			output.append(d)
		return output

	def rag_query(
		self, collection_name: str, collection_desc: str, query: str
	) -> Dict[str, Any]:
		p = self._pipeline_builder.rag_pipeline(collection_name)
		result = p.run(
			{
				"embedder": {"text": query},
				"prompt_builder": {"query": query, "collection_desc": collection_desc},
			}
		)
		return {
			"answer": result["answer_builder"]["answers"][0].data,
			"query": result["answer_builder"]["answers"][0].query,
		}
