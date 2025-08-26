from typing import List, Dict, Optional
import logging
from serka.models import (
	Document,
	Result,
	RAGResponse,
	GroupedDocuments,
	ScoredDocument,
	ModelServerConfig,
)
from serka.pipelines import PipelineBuilder
from haystack.dataclasses import ChatMessage
from haystack.components.agents import Agent
from serka.prompts import AGENT_PROMPT


logger = logging.getLogger(__name__)


class DAO:
	_pipeline_builder: PipelineBuilder = None

	def __init__(
		self,
		neo4j_user: str,
		neo4j_password: str,
		legilo_user: str,
		legilo_password: str,
		model_server_config: ModelServerConfig,
		neo4j_host: str = "localhost",
		neo4j_port: int = 7687,
		mcp_host: str = "localhost",
		mcp_port: int = 8000,
	):
		self._pipeline_builder = PipelineBuilder(
			neo4j_host=neo4j_host,
			neo4j_port=neo4j_port,
			neo4j_user=neo4j_user,
			neo4j_password=neo4j_password,
			mcp_host=mcp_host,
			mcp_port=mcp_port,
			legilo_user=legilo_user,
			legilo_password=legilo_password,
			models=model_server_config,
			chunk_length=150,
			chunk_overlap=50,
		)

	def build_eidc_graph(self, rows=10):
		p = self._pipeline_builder.build_graph_pipeline()
		result = p.run(data={"eidc_fetcher": {"rows": rows}})
		return Result(success=True, msg=f"Created graph: {result["graph_writer"]}")

	def query(self, query: str) -> List[Document]:
		p = self._pipeline_builder.query_pipeline()
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

	def rag_query(
		self,
		query: str,
		answer: Optional[RAGResponse] = None,
	) -> str:
		def callback(x):
			return answer.tokens.append(x.content) if answer else None

		agent: Agent = self._pipeline_builder.agent()

		agent.warm_up()
		messages = [
			ChatMessage.from_system(AGENT_PROMPT),
			ChatMessage.from_user(query),
		]
		result = agent.run(messages=messages, streaming_callback=callback)

		if answer:
			answer.complete = True
			answer.answer = result["messages"][-1].text
		return result
