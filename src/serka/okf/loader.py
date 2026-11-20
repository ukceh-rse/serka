"""Loads an OKF bundle into Redis: drops and rebuilds the chunk and relation indexes and the stored concepts.

Keys:
  concept:<id>        STRING  raw markdown of every bundle file, index files included (what read() returns)
  chunk:<id>#<n>      JSON    one chunk with its concept's fields and embedding, indexed by idx:chunks
  rel:<dataset>#<n>   JSON    one dataset and one related concept, indexed by idx:relations
  theme-label:<label> STRING  theme concept ID, for theme filters given by label
"""

import logging
from pathlib import Path
from typing import Any, Protocol

import redis
from haystack import Document
from redis.commands.search.field import Field, NumericField, TagField, TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from tqdm import tqdm  # type: ignore[import-untyped]

from serka import answer_cache
from serka.answer_cache import AnswerCache
from serka.okf.bundle import read_bundle
from serka.okf.chunks import chunk_concepts
from serka.okf.relations import relation_records
from serka.settings import Settings

logger = logging.getLogger(__name__)

INDEX = "idx:chunks"
RELATIONS_INDEX = "idx:relations"
CHUNK_PREFIX = "chunk:"
RELATION_PREFIX = "rel:"
CONCEPT_PREFIX = "concept:"
THEME_LABEL_PREFIX = "theme-label:"
TAG_SEPARATOR = "|"
_BATCH = 500


class DocumentEmbedder(Protocol):
	def run(self, documents: list[Document]) -> dict[str, Any]: ...


def index_schema(dim: int) -> list[Field]:
	def tag(name: str, path: str | None = None) -> TagField:
		return TagField(path or f"$.{name}", as_name=name, separator=TAG_SEPARATOR)

	return [
		TextField("$.text", as_name="text"),
		TextField("$.title", as_name="title", weight=2),
		tag("concept"),
		tag("type"),
		tag("tags", "$.tags[*]"),
		tag("links", "$.links[*]"),
		tag("themes", "$.themes[*]"),
		tag("dataset"),
		NumericField("$.lead", as_name="lead"),
		NumericField("$.published", as_name="published", sortable=True),
		NumericField("$.citations", as_name="citations", sortable=True),
		*(NumericField(f"$.{side}", as_name=side) for side in ("north", "south", "east", "west")),
		VectorField(
			"$.embedding",
			"HNSW",
			{"TYPE": "FLOAT32", "DIM": dim, "DISTANCE_METRIC": "COSINE"},
			as_name="embedding",
		),
	]


def relations_schema() -> list[Field]:
	def tag(name: str, path: str | None = None, sortable: bool = False) -> TagField:
		return TagField(path or f"$.{name}", as_name=name, separator=TAG_SEPARATOR, sortable=sortable)

	return [
		tag("dataset"),
		tag("kind"),
		tag("target", sortable=True),
		tag("roles", "$.roles[*]"),
		tag("themes", "$.themes[*]"),
		tag("links", "$.links[*]"),
		NumericField("$.published", as_name="published"),
		NumericField("$.citations", as_name="citations"),
		*(NumericField(f"$.{side}", as_name=side) for side in ("north", "south", "east", "west")),
	]


def _embed(chunks: list[dict[str, Any]], embedder: DocumentEmbedder) -> list[dict[str, Any]]:
	"""Chunks with their `embedding`; a chunk whose embedding fails is left out and logged."""
	docs = [Document(content=c["embed_text"], meta={"chunk": i}) for i, c in enumerate(chunks)]
	embedded = {d.meta["chunk"]: d.embedding for d in embedder.run(documents=docs)["documents"] if d.embedding}
	missing = len(chunks) - len(embedded)
	if missing:
		logger.warning("%d chunk(s) could not be embedded and are not indexed", missing)
	stored = []
	for i, chunk in enumerate(chunks):
		if i in embedded:
			record = {k: v for k, v in chunk.items() if k not in ("id", "embed_text")}
			stored.append({**record, "id": chunk["id"], "embedding": list(embedded[i])})
	return stored


def _delete_prefix(client: redis.Redis, prefix: str) -> int:
	deleted = 0
	batch: list[Any] = []
	for key in client.scan_iter(match=f"{prefix}*", count=1000):
		batch.append(key)
		if len(batch) >= _BATCH:
			deleted += client.unlink(*batch)
			batch = []
	if batch:
		deleted += client.unlink(*batch)
	return deleted


def load_bundle(
	root: Path,
	client: redis.Redis,
	embedder: DocumentEmbedder,
	cache: AnswerCache | None = None,
	default_dim: int = 1024,
) -> dict[str, int]:
	"""Replaces the index and stored concepts with the bundle's contents, then clears the answer cache."""
	if not (root / "index.md").is_file():
		raise FileNotFoundError(f"{root} is not an OKF bundle (no index.md)")
	files = read_bundle(root)
	chunks = _embed(chunk_concepts(files), embedder)
	relations = relation_records(files)
	dim = len(chunks[0]["embedding"]) if chunks else default_dim

	for index in (INDEX, RELATIONS_INDEX):
		try:
			client.ft(index).dropindex(delete_documents=True)
		except redis.ResponseError:
			pass
	for prefix in (CHUNK_PREFIX, RELATION_PREFIX, CONCEPT_PREFIX, THEME_LABEL_PREFIX):
		_delete_prefix(client, prefix)
	client.ft(INDEX).create_index(
		index_schema(dim), definition=IndexDefinition(prefix=[CHUNK_PREFIX], index_type=IndexType.JSON)
	)
	client.ft(RELATIONS_INDEX).create_index(
		relations_schema(), definition=IndexDefinition(prefix=[RELATION_PREFIX], index_type=IndexType.JSON)
	)

	pipe = client.pipeline(transaction=False)
	pending = 0

	def flush(force: bool = False) -> None:
		nonlocal pipe, pending
		if pending and (force or pending >= _BATCH):
			pipe.execute()
			pipe = client.pipeline(transaction=False)
			pending = 0

	for chunk in tqdm(chunks, desc="Writing chunks", unit="chunk"):
		record = {k: v for k, v in chunk.items() if k != "id"}
		pipe.json().set(f"{CHUNK_PREFIX}{chunk['id']}", "$", record)
		pending += 1
		flush()
	for rel in relations:
		pipe.json().set(f"{RELATION_PREFIX}{rel['id']}", "$", {k: v for k, v in rel.items() if k != "id"})
		pending += 1
		flush()
	for f in files:
		pipe.set(f"{CONCEPT_PREFIX}{f.id}", f.raw)
		pending += 1
		flush()
	labels: dict[str, str] = {}
	for f in sorted(files, key=lambda f: f.id):
		if f.is_concept and f.meta.get("type") == "theme" and f.meta.get("title"):
			labels.setdefault(str(f.meta["title"]).strip().lower(), f.id)
	for label, theme_id in labels.items():
		pipe.set(f"{THEME_LABEL_PREFIX}{label}", theme_id)
		pending += 1
		flush()
	flush(force=True)

	if cache is not None:
		cache.clear()
	counts = {
		"files": len(files),
		"concepts": sum(1 for f in files if f.is_concept),
		"chunks": len(chunks),
		"relations": len(relations),
		"theme_labels": len(labels),
	}
	logger.info("Loaded %s into Redis: %s", root, counts)
	return counts


def load_from_settings(settings: Settings) -> dict[str, int]:
	from serka.graph.embedders import CachedDocumentEmbedder

	client = redis.Redis.from_url(settings.redis_url)
	# Cleared whether or not lookups are enabled, so re-enabling never serves answers from an old index
	cache = AnswerCache(lambda: answer_cache._semantic_cache(settings))
	return load_bundle(
		Path(settings.okf_bundle_dir),
		client,
		CachedDocumentEmbedder(model=settings.models_embedding),
		cache,
	)
