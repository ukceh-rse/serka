"""Splits concept bodies into overlapping chunks carrying their concept's (and dataset's) fields."""

from datetime import date
from typing import Any

from haystack import Document
from haystack.components.preprocessors import DocumentSplitter

from serka.okf.bundle import BundleFile

CHUNK_WORDS = 150
CHUNK_OVERLAP = 50
_EPOCH = date(1970, 1, 1)


def epoch_days(iso_date: str) -> int:
	return (date.fromisoformat(str(iso_date)[:10]) - _EPOCH).days


def dataset_fields(meta: dict[str, Any]) -> dict[str, Any]:
	"""Filter fields of a dataset, copied onto its own and its documents' chunks."""
	fields: dict[str, Any] = {"themes": list(meta.get("themes") or [])}
	if meta.get("published"):
		fields["published"] = epoch_days(meta["published"])
	if meta.get("citations") is not None:
		fields["citations"] = int(meta["citations"])
	if isinstance(bbox := meta.get("bbox"), dict) and all(k in bbox for k in ("north", "south", "east", "west")):
		fields.update({k: float(bbox[k]) for k in ("north", "south", "east", "west")})
	return fields


def _concept_fields(f: BundleFile) -> dict[str, Any]:
	meta = f.meta
	fields: dict[str, Any] = {
		"concept": f.id,
		"type": str(meta["type"]),
		"title": str(meta.get("title") or f.id),
		"tags": [str(t) for t in meta.get("tags") or []],
		"links": f.links,
	}
	for key in ("description", "resource"):
		if meta.get(key):
			fields[key] = str(meta[key])
	if meta.get("published"):
		# Kept as the ISO date for hits; `published` itself becomes epoch days below
		fields["published_date"] = str(meta["published"])[:10]
	return fields


def dataset_of(concept_id: str) -> str | None:
	"""`datasets/<id>/docs/...` -> `datasets/<id>`."""
	head, sep, _ = concept_id.partition("/docs/")
	return head if sep and head.startswith("datasets/") else None


def chunk_concepts(files: list[BundleFile]) -> list[dict[str, Any]]:
	"""One record per chunk: `id`, `embed_text` (title-prefixed, for the embedder) and the
	fields stored and indexed in Redis. Only concept files are chunked."""
	concepts = [f for f in files if f.is_concept]
	datasets = {f.id: f.meta for f in concepts if f.meta.get("type") == "dataset"}
	splitter = DocumentSplitter(split_by="word", split_length=CHUNK_WORDS, split_overlap=CHUNK_OVERLAP)

	chunks = []
	for f in concepts:
		fields = _concept_fields(f)
		dataset_id = f.id if f.meta["type"] == "dataset" else dataset_of(f.id)
		dataset_meta = datasets.get(dataset_id or "")
		if dataset_meta is not None:
			fields["dataset"] = dataset_id
			fields.update(dataset_fields(dataset_meta))
			if "published_date" not in fields and dataset_meta.get("published"):
				fields["published_date"] = str(dataset_meta["published"])[:10]
		title = fields["title"]

		body = f.body.strip()
		if body:
			texts = [d.content for d in splitter.run(documents=[Document(content=body)])["documents"] if d.content]
			pieces = [(t.strip(), f"{title}\n\n{t.strip()}") for t in texts if t.strip()]
		else:
			text = "\n\n".join(p for p in (title, fields.get("description", "")) if p)
			pieces = [(text, text)]

		for n, (text, embed_text) in enumerate(pieces):
			chunks.append({
				"id": f"{f.id}#{n}",
				"embed_text": embed_text,
				**fields,
				"text": text,
				"lead": 1 if n == 0 else 0,
			})
	return chunks
