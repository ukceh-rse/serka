import chromadb.api
from haystack import Pipeline
from haystack.components.fetchers import LinkContentFetcher
from haystack.components.preprocessors import DocumentSplitter
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.document_stores.chroma import ChromaDocumentStore
from haystack_integrations.components.retrievers.chroma import ChromaEmbeddingRetriever
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack.components.writers import DocumentWriter
from .converters import EIDCConverter, HTMLConverter
from typing import List, Dict, Any
import logging
from dataclasses import dataclass
import chromadb
from haystack.components.builders import PromptBuilder
from haystack_integrations.components.generators.ollama.generator import OllamaGenerator
from haystack.components.builders.answer_builder import AnswerBuilder


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
		self,
		url,
		collection_name: str,
		embedding_model: str | None = None,
		source_type: str = "eidc",
	) -> Dict[str, Any]:
		p = self._insertion_pipeline(collection_name, embedding_model, source_type)
		result = p.run(data={"fetcher": {"urls": [url]}})
		return {"status": "success", "documents": result["writer"]["documents_written"]}

	def delete(self, collection_name: str) -> Dict[str, Any]:
		self._chroma_client.delete_collection(collection_name)
		return {"status": "success"}

	def query(
		self, collection_name: str, query: str, n: int = 10
	) -> List[Dict[str, Any]]:
		p = self._query_pipeline(collection_name, n)
		results = p.run({"embedder": {"text": query}})["retriever"]["documents"]
		output = []
		for doc in results:
			d = {k: v for k, v in doc.meta.items()}
			d["content"] = doc.content
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
		p = self._rag_pipeline(collection_name, collection_desc)
		result = p.run(
			{"embedder": {"text": query}, "prompt_builder": {"query": query}}
		)
		return {
			"answer": result["answer_builder"]["answers"][0].data,
			"query": result["answer_builder"]["answers"][0].query,
		}

	def _rag_pipeline(self, collection_name: str, collection_desc: str) -> Pipeline:
		logger.info(f"Creating RAG pipeline for collection: {collection_name}")
		p = self._query_pipeline(collection_name)
		template = (
			"""
			# Task Description:
			You are a helpful assistant for the UK Centre for Ecology and Hydrology (UKCEH).
			Your task is to provide an answer to a query based on a given set of retrieved documents.
			Your answer should be in markdown format.
			The retrieved documents are in JSON format and are excerpts of information from source documents.
			The following describes the source of the documents:
			"""
			+ collection_desc
			+ """
			Your answer should derived from the provided retrieved documents.
			Do not use your own knowledge to answer the query, only the information in the retrieved documents.
			If the query is not a question, but appears to be a series of keywords, simply provide a general summary of any retreived documents relevant to the keywords and include references to them.
			Provide a citation to the relevant retrieved document used to generate each part of your answer.
			Your answer should be in markdown format.

			# Examples:
			## Example 1:
			### Query:
			What is the impact of climate change on the UK's biodiversity?
			### Answer:
			The impact on bidiversity is discussed in the dataset "UK Biodiversity Indicators" [1].
			### References:
			- [1]: [ UK Biodiversity Indicators ](https://eidc.ceh.ac.uk/uk-biodiversity-indicators)

			## Example 2:
			### Query:
			farming
			### Answer:
			The following datasets are relevant to farming: "UK farming trends" [1], "UK farming statistics" [2].
			### References:
			- [1]: [ UK farming trends ](https://eidc.ceh.ac.uk/uk-farming-trends)
			- [2]: [ UK farming statistics ](https://eidc.ceh.ac.uk/uk-farming-statistics)

			# The Actual Task:
			## Query:
			{{query}}
			## Retreived Documents:
			[{% for document in documents %}
					{
						content: "{{ document.content }}",
						meta: {
							title: "{{ document.meta.title }}",
							url: "{{ document.meta.url }}",
							chunk_id: "{{ document.id }}"
						}
					}
				{% endfor %}
			]
			## Answer:
		"""
		)
		prompt_builder = PromptBuilder(template)
		logger.info(f"Creating RAG pipeline with llm: {self.default_rag_model}")
		llm = OllamaGenerator(
			model=self.default_rag_model,
			generation_kwargs={"num_ctx": 16384, "temperature": 0.0},
			url=f"http://{self.ollama_host}:{self.ollama_port}",
		)
		answer_builder = AnswerBuilder()
		p.add_component("prompt_builder", prompt_builder)
		p.add_component("llm", llm)
		p.add_component("answer_builder", answer_builder)

		p.connect("retriever.documents", "prompt_builder.documents")
		p.connect("retriever.documents", "answer_builder.documents")

		p.connect("prompt_builder", "llm")

		p.connect("llm.replies", "answer_builder.replies")
		p.connect("prompt_builder.prompt", "answer_builder.query")
		return p

	def _query_pipeline(self, collection_name: str, top_n: int = 5) -> Pipeline:
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
		p.add_component("retriever", ChromaEmbeddingRetriever(doc_store, top_k=top_n))
		p.connect("embedder.embedding", "retriever.query_embedding")
		return p

	def _create_converter(self, source_type: str):
		if source_type == "eidc":
			return EIDCConverter({"title", "description"})
		if source_type == "html":
			return HTMLConverter()
		raise ValueError(f"Unknown converter type: {source_type}")

	def _insertion_pipeline(
		self,
		collection_name: str,
		embedding_model: str | None = None,
		source_type: str = "eidc",
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
		p.add_component("converter", self._create_converter(source_type))
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
