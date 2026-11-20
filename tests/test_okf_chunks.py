from serka.okf.bundle import BundleFile
from serka.okf.chunks import CHUNK_OVERLAP, CHUNK_WORDS, chunk_concepts, dataset_of, epoch_days

DATASET_META = {
	"type": "dataset",
	"title": "Pike in Windermere",
	"description": "Pike counts.",
	"resource": "https://catalogue.ceh.ac.uk/id/abc",
	"tags": ["pike"],
	"published": "2020-01-02",
	"citations": 7,
	"bbox": {"north": 54.5, "south": 54.2, "east": -2.9, "west": -3.0},
	"themes": ["themes/fish", "themes/biodiversity"],
}


def _words(n: int, word: str = "w") -> str:
	return " ".join(f"{word}{i}" for i in range(n))


def test_long_body_is_split_into_overlapping_title_prefixed_chunks() -> None:
	f = BundleFile("datasets/abc", "", DATASET_META, _words(300), links=["people/x"])
	chunks = chunk_concepts([f])
	assert [c["id"] for c in chunks] == ["datasets/abc#0", "datasets/abc#1", "datasets/abc#2"]
	assert [c["lead"] for c in chunks] == [1, 0, 0]
	first, second = chunks[0]["text"].split(), chunks[1]["text"].split()
	assert len(first) == CHUNK_WORDS
	assert first[-CHUNK_OVERLAP:] == second[:CHUNK_OVERLAP]
	assert chunks[0]["embed_text"] == f"Pike in Windermere\n\n{chunks[0]['text']}"
	assert not chunks[0]["text"].startswith("Pike in Windermere")


def test_concept_and_dataset_fields_on_every_chunk() -> None:
	f = BundleFile("datasets/abc", "", DATASET_META, _words(300), links=["people/x"])
	for c in chunk_concepts([f]):
		assert c["concept"] == "datasets/abc"
		assert c["type"] == "dataset"
		assert c["title"] == "Pike in Windermere"
		assert c["description"] == "Pike counts."
		assert c["resource"] == "https://catalogue.ceh.ac.uk/id/abc"
		assert c["tags"] == ["pike"]
		assert c["links"] == ["people/x"]
		assert c["themes"] == ["themes/fish", "themes/biodiversity"]
		assert c["published"] == epoch_days("2020-01-02") == 18263
		assert c["published_date"] == "2020-01-02"
		assert c["citations"] == 7
		assert (c["north"], c["south"], c["east"], c["west"]) == (54.5, 54.2, -2.9, -3.0)


def test_document_chunks_carry_their_dataset_fields() -> None:
	dataset = BundleFile("datasets/abc", "", DATASET_META, "Body.")
	doc = BundleFile(
		"datasets/abc/docs/s1",
		"",
		{"type": "document", "title": "methods.pdf", "media_type": "application/pdf"},
		"Supporting document of [Pike](/datasets/abc).\n\nNets were set at dawn.",
		links=["datasets/abc"],
	)
	chunks = chunk_concepts([dataset, doc])
	[doc_chunk] = [c for c in chunks if c["concept"] == doc.id]
	assert doc_chunk["type"] == "document"
	assert doc_chunk["dataset"] == "datasets/abc"
	assert {c["dataset"] for c in chunks if c["concept"] == dataset.id} == {"datasets/abc"}
	assert doc_chunk["title"] == "methods.pdf"
	assert doc_chunk["themes"] == ["themes/fish", "themes/biodiversity"]
	assert doc_chunk["citations"] == 7
	assert doc_chunk["north"] == 54.5
	assert doc_chunk["published_date"] == "2020-01-02"


def test_non_dataset_chunks_have_no_dataset_fields() -> None:
	person = BundleFile("people/x", "", {"type": "person", "title": "Jane"}, "## Affiliations\n\n- [O](/o)")
	[chunk] = chunk_concepts([person])
	for key in ("dataset", "themes", "published", "citations", "north", "south", "east", "west"):
		assert key not in chunk


def test_empty_body_gives_one_title_and_description_chunk() -> None:
	org = BundleFile("organisations/o", "", {"type": "organisation", "title": "UKCEH", "description": "A centre."}, "")
	[chunk] = chunk_concepts([org])
	assert chunk["id"] == "organisations/o#0"
	assert chunk["text"] == "UKCEH\n\nA centre."
	assert chunk["embed_text"] == chunk["text"]
	assert chunk["lead"] == 1


def test_index_files_are_not_chunked() -> None:
	index = BundleFile("ontology/index", "", {}, "# Ontology\n\n- [a](/ontology/roles/a)")
	assert chunk_concepts([index]) == []


def test_dataset_of() -> None:
	assert dataset_of("datasets/abc/docs/s1") == "datasets/abc"
	assert dataset_of("datasets/abc") is None
	assert dataset_of("people/x") is None
