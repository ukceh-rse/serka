import chromadb.api
import haystack
from typing import List, Dict, Optional
import logging
import chromadb
from serka.models import Document, Result, RAGResponse, GroupedDocuments, ScoredDocument
from serka.pipelines import PipelineBuilder


logger = logging.getLogger(__name__)


class DAO:
	_chroma_client: chromadb.api.ClientAPI = None
	_pipeline_builder: PipelineBuilder = None

	def __init__(
		self,
		neo4j_user: str,
		neo4j_password: str,
		ollama_host: str = "localhost",
		ollama_port: int = 11434,
		chroma_host: str = "localhost",
		chroma_port: int = 8000,
		neo4j_host: str = "localhost",
		neo4j_port: int = 7687,
		default_embedding_model: str = "nomic-embed-text",
		default_rag_model: str = "llama3.1",
	):
		self._chroma_client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
		self._pipeline_builder = PipelineBuilder(
			ollama_host=ollama_host,
			ollama_port=ollama_port,
			chroma_host=chroma_host,
			chroma_port=chroma_port,
			neo4j_host=neo4j_host,
			neo4j_port=neo4j_port,
			neo4j_user=neo4j_user,
			neo4j_password=neo4j_password,
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

	def build_eidc_graph(self, rows=3):
		p = self._pipeline_builder.eidc_graph_pipeline()
		result = p.run(data={"fetcher": {"rows": rows}})
		return Result(success=True, msg=f"Created graph: {result["graph_writer"]}")

	def scrape(
		self,
		urls,
		collection: str,
		source_type: str = "eidc",
		unified_metadata: List[str] = {},
		metadata: Dict[str, str] = {},
	) -> Result:
		p = self._pipeline_builder.scraping_pipeline(
			collection, source_type, unified_metadata, metadata
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

	def eidc_graph_search(self, query: str) -> List[Document]:
		p = self._pipeline_builder.eidc_graph_query_pipeline()
		result = p.run({"embedder": {"text": query}})
		nodes = result["reader"]["nodes"]
		docs = set()
		for node in nodes:
			score = node["score"]
			content = None
			meta = {}
			if "TextChunk" in node["start_labels"]:
				content = node["start_node"]["content"]
				meta["section"] = node["relationship_type"]
				meta["title"] = node["connected_node"]["title"]
				meta["url"] = node["connected_node"]["uri"]
			if "Dataset" in node["start_labels"]:
				content = repr(node["start_node"])
				meta["title"] = node["start_node"]["title"]
				meta["section"] = "Dataset"
				meta["url"] = node["start_node"]["uri"]
			if content:
				docs.add(
					ScoredDocument(
						document=Document(content=content, metadata=meta), score=score
					)
				)

		docs = sorted(docs, key=lambda x: x.score, reverse=True)

		groupby = "title"

		grouped: Dict[str, GroupedDocuments] = {}
		for doc in docs:
			groupby_val = doc.document.metadata.get(groupby, "unknown")
			if groupby_val not in grouped.keys():
				grouped[groupby_val] = GroupedDocuments(docs=[], groupedby=groupby)
			grouped[groupby_val].docs.append(doc)
		return list(grouped.values())

	def query(
		self, collection_name: str, query: str, n: int = 10, groupby: str = "title"
	) -> List[GroupedDocuments]:
		p = self._pipeline_builder.query_pipeline(collection_name, n)
		results = p.run({"embedder": {"text": query}})["retriever"]["documents"]

		doc_scores = [
			ScoredDocument(
				document=Document(content=doc.content, metadata=doc.meta),
				score=doc.score,
			)
			for doc in results
		]
		doc_scores = sorted(doc_scores, key=lambda x: x.score)

		grouped: Dict[str, GroupedDocuments] = {}
		for doc in doc_scores:
			groupby_val = doc.document.metadata.get(groupby, "unknown")
			if groupby_val not in grouped.keys():
				grouped[groupby_val] = GroupedDocuments(docs=[], groupedby=groupby)
			grouped[groupby_val].docs.append(doc)

		return grouped.values()

	def peek(self, collection_name: str, n: int = 5) -> List[Document]:
		result = self._chroma_client.get_collection(collection_name).peek(n)
		output = []
		for doc, meta in zip(result["documents"], result["metadatas"]):
			output.append(Document(content=doc, metadata=meta))
		return output

	def rag_query(
		self,
		collection_name: str,
		collection_desc: str,
		query: str,
		answer: RAGResponse,
	) -> None:
		p = self._pipeline_builder.rag_pipeline(
			collection_name, lambda x: answer.tokens.append(x.content)
		)
		result = p.run(
			{
				"embedder": {"text": query},
				"prompt_builder": {"query": query, "collection_desc": collection_desc},
			}
		)
		answer.complete = True
		answer.answer = result["answer_builder"]["answers"][0].data

	def eidc_graph_rag(
		self,
		query: str,
		answer: Optional[RAGResponse] = None,
	) -> str:
		def callback(x):
			return answer.tokens.append(x.content) if answer else None

		p = self._pipeline_builder.eidc_graph_rag_pipeline(callback)
		result = p.run(
			{"embedder": {"text": query}, "prompt_builder": {"query": query}}
		)
		if answer:
			answer.complete = True
			answer.answer = result["answer_builder"]["answers"][0].data
		return result
