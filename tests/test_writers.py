from haystack import Document
from haystack.components.preprocessors import DocumentSplitter

from serka.graph.writers import Neo4jGraphWriter

DATASET_URI = "https://catalogue.ceh.ac.uk/id/test-uuid-abc"


def _supporting_docs(*contents: str) -> list[Document]:
	return [
		Document(content=c, meta={"field": "SUPPORTING_DOC", "uri": DATASET_URI, "filename": "readme.pdf"})
		for c in contents
	]


def test_same_named_supporting_docs_get_distinct_uris():
	a, b = (Neo4jGraphWriter.doc_to_dict(d) for d in _supporting_docs("first file", "second file"))
	assert Neo4jGraphWriter._supporting_doc_uri(a) != Neo4jGraphWriter._supporting_doc_uri(b)
	assert Neo4jGraphWriter._supporting_doc_node(a)["title"] == "readme.pdf"


def test_chunks_of_one_supporting_doc_share_a_uri():
	splitter = DocumentSplitter(split_by="word", split_length=2, split_overlap=0)
	chunks = splitter.run(documents=_supporting_docs("one two three four five"))["documents"]
	assert len(chunks) > 1
	uris = {Neo4jGraphWriter._supporting_doc_uri(Neo4jGraphWriter.doc_to_dict(c)) for c in chunks}
	assert len(uris) == 1
	assert uris.pop().startswith(f"{DATASET_URI}#")
