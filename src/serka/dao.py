import chromadb.api
import haystack
from typing import List, Set
import logging
import chromadb
from serka.models import Document, Result, RAGResponse
from serka.pipelines import PipelineBuilder


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
		p = self._pipeline_builder.insertion_pipeline(collection)
		sources = [haystack.Document(content=document.content, meta=document.metadata)]
		result = p.run(data={"splitter": {"documents": sources}})
		insertions = result["writer"]["documents_written"]
		return Result(
			success=True, msg=f"Inserted {insertions} document(s) into {collection}"
		)

	def scrape(
		self,
		urls,
		collection: str,
		source_type: str = "eidc",
		unified_metadata: Set[str] = {},
	) -> Result:
		p = self._pipeline_builder.scraping_pipeline(
			collection, source_type, unified_metadata
		)
		result = p.run(data={"fetcher": {"urls": urls}})
		insertions = result["writer"]["documents_written"]
		return Result(
			success=True, msg=f"Inserted {insertions} document(s) into {collection}"
		)

	def delete(self, collection_name: str) -> Result:
		try:
			self._chroma_client.delete_collection(collection_name)
			return Result(success=True, msg=f"Collection '{collection_name}' deleted.")
		except chromadb.errors.InvalidArgumentError as e:
			return Result(success=False, msg=str(e))

	def query(self, collection_name: str, query: str, n: int = 10) -> List[Document]:
		p = self._pipeline_builder.query_pipeline(collection_name, n)
		results = p.run({"embedder": {"text": query}})["retriever"]["documents"]
		output = []
		for doc in results:
			d = Document(content=doc.content, metadata=doc.meta)
			d.metadata["score"] = doc.score
			output.append(d)
		return sorted(output, key=lambda x: x.metadata["score"])

	def peek(self, collection_name: str, n: int = 5) -> List[Document]:
		result = self._chroma_client.get_collection(collection_name).peek(n)
		output = []
		for doc, meta in zip(result["documents"], result["metadatas"]):
			output.append(Document(content=doc, metadata=meta))
		return output

	def rag_query(
		self, collection_name: str, collection_desc: str, query: str
	) -> RAGResponse:
		p = self._pipeline_builder.rag_pipeline(collection_name)
		result = p.run(
			{
				"embedder": {"text": query},
				"prompt_builder": {"query": query, "collection_desc": collection_desc},
			}
		)
		return RAGResponse(
			result=Result(success=True, msg="RAG query successful"),
			query=result["answer_builder"]["answers"][0].query,
			answer=result["answer_builder"]["answers"][0].data,
		)
