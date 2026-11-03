from haystack import Document

import serka.cache
from serka.graph.embedders import CachedDocumentEmbedder


class FakeBedrockEmbedder:
	"""Embeds documents with a fixed vector; rejects any call containing a 'too long' document."""

	def __init__(self):
		self.calls = 0

	def run(self, documents):
		self.calls += 1
		if any(d.content == "too long" for d in documents):
			raise RuntimeError("Too many input tokens")
		return {"documents": [Document(content=d.content, meta=d.meta, embedding=[1.0]) for d in documents]}


def test_one_bad_document_does_not_drop_the_rest(monkeypatch, tmp_path):
	monkeypatch.setattr(serka.cache, "root", tmp_path)
	embedder = CachedDocumentEmbedder(batch_size=2)
	embedder.embedder = FakeBedrockEmbedder()
	docs = [Document(content=c) for c in ["a", "b", "too long", "c", "d"]]

	result = embedder.run(documents=docs)

	assert [d.content for d in result["documents"]] == ["a", "b", "c", "d"]
	assert all(d.embedding == [1.0] for d in result["documents"])
	assert serka.cache.get_embedding("a") == [1.0]
	assert serka.cache.get_embedding("d") == [1.0]
