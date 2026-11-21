"""Loads small bundles into a real Redis (see the `test_redis` fixture) with a fake embedder."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
from haystack import Document

from serka.answer_cache import AnswerCache
from serka.okf import loader
from serka.okf.bundle import read_bundle
from serka.okf.chunks import chunk_concepts
from serka.okf.loader import (
	CHUNK_PREFIX,
	CONCEPT_PREFIX,
	INDEX,
	RELATION_PREFIX,
	RELATIONS_INDEX,
	THEME_LABEL_PREFIX,
	load_bundle,
)
from serka.okf.relations import relation_records

pytestmark = pytest.mark.integration


class FakeEmbedder:
	"""A deterministic 8-dimensional embedding of each document's text."""

	def run(self, documents: list[Document]) -> dict[str, Any]:
		out = []
		for d in documents:
			digest = hashlib.sha256((d.content or "").encode()).digest()
			out.append(Document(content=d.content, meta=d.meta, embedding=[b / 255 for b in digest[:8]]))
		return {"documents": out}


class RecordingCache(AnswerCache):
	def __init__(self) -> None:
		super().__init__(None)
		self.cleared = 0

	def clear(self) -> None:
		self.cleared += 1


def _write(root: Path, rel: str, text: str) -> None:
	path = root / rel
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(text)


def _bundle(root: Path, datasets: list[str]) -> Path:
	_write(root, "index.md", '---\nokf_version: "0.2"\n---\n\n- [Datasets](/datasets/index)\n')
	_write(root, "datasets/index.md", "# Datasets\n\n" + "\n".join(f"- [{d}](/datasets/{d})" for d in datasets))
	for d in datasets:
		body = " ".join(f"word{i}" for i in range(200)) + " [Jane](/people/jane) [Fish](/themes/fish)"
		meta = (
			f"---\ntype: dataset\ntitle: Dataset {d}\npublished: '2020-01-01'\ncitations: 3\nthemes:\n- themes/fish\n"
			"contributors:\n- id: people/jane\n  roles: [author, contact-person]\n---\n\n"
		)
		_write(root, f"datasets/{d}.md", meta + body)
		_write(root, f"datasets/{d}/docs/s1.md", f"---\ntype: document\ntitle: readme.txt\n---\n\nAbout [{d}](/datasets/{d}).")
	_write(root, "people/jane.md", "---\ntype: person\ntitle: Jane Smith\n---\n")
	_write(root, "themes/fish.md", "---\ntype: theme\ntitle: Freshwater fish\n---\n")
	return root


def _counts(client) -> dict[str, int]:
	prefixes = (CHUNK_PREFIX, RELATION_PREFIX, CONCEPT_PREFIX, THEME_LABEL_PREFIX)
	return {p: len(list(client.scan_iter(match=f"{p}*"))) for p in prefixes}


def test_loading_twice_gives_identical_keys(tmp_path: Path, test_redis) -> None:
	bundle = _bundle(tmp_path / "bundle", ["a", "b"])
	first = load_bundle(bundle, test_redis, FakeEmbedder())
	keys_first = sorted(test_redis.keys("*"))
	second = load_bundle(bundle, test_redis, FakeEmbedder())
	assert first == second
	assert sorted(test_redis.keys("*")) == keys_first
	n_chunks = len(chunk_concepts(read_bundle(bundle)))
	assert first["chunks"] == n_chunks
	n_relations = len(relation_records(read_bundle(bundle)))
	assert first["relations"] == n_relations == 4  # jane and fish, for each dataset
	assert _counts(test_redis) == {CHUNK_PREFIX: n_chunks, RELATION_PREFIX: 4, CONCEPT_PREFIX: 8, THEME_LABEL_PREFIX: 1}
	assert int(test_redis.ft(INDEX).info()["num_docs"]) == n_chunks
	assert int(test_redis.ft(RELATIONS_INDEX).info()["num_docs"]) == n_relations


def test_loading_in_small_embedding_batches_stores_every_chunk(
	tmp_path: Path, test_redis, monkeypatch: pytest.MonkeyPatch
) -> None:
	bundle = _bundle(tmp_path / "bundle", ["a", "b"])
	whole = load_bundle(bundle, test_redis, FakeEmbedder())
	keys_whole = sorted(test_redis.keys("*"))
	monkeypatch.setattr(loader, "_EMBED_BATCH", 2)
	batched = load_bundle(bundle, test_redis, FakeEmbedder())
	assert batched == whole
	assert sorted(test_redis.keys("*")) == keys_whole
	assert int(test_redis.ft(INDEX).info()["num_docs"]) == whole["chunks"] > 2


def test_stored_concepts_chunks_and_labels(tmp_path: Path, test_redis) -> None:
	bundle = _bundle(tmp_path / "bundle", ["a"])
	load_bundle(bundle, test_redis, FakeEmbedder())
	assert test_redis.get("concept:datasets/a").decode() == (bundle / "datasets" / "a.md").read_text()
	assert test_redis.get("concept:datasets/index") is not None
	assert test_redis.get("theme-label:freshwater fish") == b"themes/fish"
	chunk = test_redis.json().get("chunk:datasets/a#0")
	assert chunk["concept"] == "datasets/a"
	assert chunk["lead"] == 1
	assert chunk["links"] == ["people/jane", "themes/fish"]
	assert chunk["themes"] == ["themes/fish"]
	assert len(chunk["embedding"]) == 8
	doc_chunk = test_redis.json().get("chunk:datasets/a/docs/s1#0")
	assert doc_chunk["citations"] == 3
	assert doc_chunk["dataset"] == "datasets/a"


def test_two_role_contributor_has_one_relation_record(tmp_path: Path, test_redis) -> None:
	load_bundle(_bundle(tmp_path / "bundle", ["a"]), test_redis, FakeEmbedder())
	people = test_redis.ft(RELATIONS_INDEX).search("@kind:{person}")
	assert people.total == 1
	record = test_redis.json().get(people.docs[0].id)
	assert record["target"] == "people/jane"
	assert record["target_title"] == "Jane Smith"
	assert record["roles"] == ["author", "contact-person"]
	assert record["citations"] == 3 and record["themes"] == ["themes/fish"]
	assert test_redis.ft(RELATIONS_INDEX).search("@kind:{person} @roles:{contact\\-person}").total == 1


def test_removed_dataset_is_gone_after_reload(tmp_path: Path, test_redis) -> None:
	load_bundle(_bundle(tmp_path / "one", ["a", "b"]), test_redis, FakeEmbedder())
	load_bundle(_bundle(tmp_path / "two", ["a"]), test_redis, FakeEmbedder())
	assert test_redis.get("concept:datasets/b") is None
	assert not list(test_redis.scan_iter(match="chunk:datasets/b*"))
	assert test_redis.ft(INDEX).search("@concept:{datasets\\/b}").total == 0
	assert test_redis.ft(INDEX).search("@concept:{datasets\\/a}").total > 0
	assert not list(test_redis.scan_iter(match="rel:datasets/b*"))
	assert test_redis.ft(RELATIONS_INDEX).search("@dataset:{datasets\\/b}").total == 0
	assert test_redis.ft(RELATIONS_INDEX).search("@dataset:{datasets\\/a}").total == 2


def test_loading_clears_the_answer_cache(tmp_path: Path, test_redis) -> None:
	cache = RecordingCache()
	load_bundle(_bundle(tmp_path / "bundle", ["a"]), test_redis, FakeEmbedder(), cache)
	assert cache.cleared == 1


def test_not_a_bundle(tmp_path: Path, test_redis) -> None:
	with pytest.raises(FileNotFoundError):
		load_bundle(tmp_path, test_redis, FakeEmbedder())
