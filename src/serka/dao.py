from typing import List, Optional
import logging
from serka.models import Result, RAGResponse, GroupedDocuments
from serka.pipelines import PipelineBuilder


logger = logging.getLogger(__name__)


class DAO:
	_pipeline_builder: PipelineBuilder = None

	def __init__(
		self,
		neo4j_user: str,
		neo4j_password: str,
		legilo_user: str,
		legilo_password: str,
		ollama_host: str = "localhost",
		ollama_port: int = 11434,
		neo4j_host: str = "localhost",
		neo4j_port: int = 7687,
		default_embedding_model: str = "nomic-embed-text",
		default_rag_model: str = "llama3.1",
	):
		self._pipeline_builder = PipelineBuilder(
			ollama_host=ollama_host,
			ollama_port=ollama_port,
			neo4j_host=neo4j_host,
			neo4j_port=neo4j_port,
			neo4j_user=neo4j_user,
			neo4j_password=neo4j_password,
			legilo_user=legilo_user,
			legilo_password=legilo_password,
			embedding_model=default_embedding_model,
			rag_model=default_rag_model,
			chunk_length=150,
			chunk_overlap=50,
		)

	def build_eidc_graph(self, rows=10):
		p = self._pipeline_builder.build_graph_pipeline()
		result = p.run(data={"eidc_fetcher": {"rows": rows}})
		return Result(success=True, msg=f"Created graph: {result["graph_writer"]}")

	def query(self, query: str) -> List[GroupedDocuments]:
		p = self._pipeline_builder.query_pipeline()
		result = p.run({"embedder": {"text": query}})
		return result["reader"]["grouped_docs"]

	def rag_query(
		self,
		query: str,
		hyde: bool = False,
		answer: Optional[RAGResponse] = None,
	) -> str:
		def callback(x):
			return answer.tokens.append(x.content) if answer else None

		p = self._pipeline_builder.rag_pipeline(hyde=hyde, streaming_callback=callback)
		result = p.run(
			{"embedder": {"text": query}, "prompt_builder": {"query": query}}
		)
		if answer:
			answer.complete = True
			answer.answer = result["answer_builder"]["answers"][0].data
		return result
