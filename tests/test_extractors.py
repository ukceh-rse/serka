from haystack import Document

from serka.graph.extractors import DocumentTruncator, EntityExtractor, TextExtractor


# ---------------------------------------------------------------------------
# TextExtractor
# ---------------------------------------------------------------------------


def test_text_extractor_returns_documents_for_each_field():
	records = [
		{
			"resourceIdentifiers": [{"codeSpace": "doi:", "code": "10.1234/abc123"}],
			"title": "Test Title",
			"description": "test_description",
			"lineage": "test_lineage",
		}
	]
	result = TextExtractor(["description", "lineage"]).run(records=records)
	docs = result["documents"]
	assert len(docs) == 2
	assert docs[0].content == "test_description"
	assert docs[0].meta["uri"] == "https://doi.org/10.1234/abc123"
	assert docs[0].meta["title"] == "Test Title"
	assert docs[1].content == "test_lineage"


def test_text_extractor_skips_missing_fields():
	records = [
		{
			"resourceIdentifiers": [{"codeSpace": "doi:", "code": "10.1234/abc"}],
			"title": "T",
			"description": "only this field present",
		}
	]
	result = TextExtractor(["description", "lineage"]).run(records=records)
	assert len(result["documents"]) == 1


# ---------------------------------------------------------------------------
# EntityExtractor
# ---------------------------------------------------------------------------

_RECORD = {
	"resourceIdentifiers": [{"codeSpace": "doi:", "code": "10.1234/abc123"}],
	"title": "Test Dataset",
	"authors": [
		{
			"fullName": "Joe Bloggs",
			"nameIdentifier": "https://orcid.org/0000-0001-2345-6789",
			"organisationName": "Test Org",
			"organisationIdentifier": "https://ror.org/abc123",
		},
		{
			"fullName": "Jane Smith",
			"nameIdentifier": "https://orcid.org/0000-0002-9876-5432",
		},
	],
	"incomingCitationCount": 5,
	"publicationDate": "2023-01-01",
}


def test_entity_extractor_datasets():
	result = EntityExtractor().run(data=[_RECORD])
	datasets = result["nodes"]["Dataset"]
	assert len(datasets) == 1
	assert datasets[0]["uri"] == "https://doi.org/10.1234/abc123"
	assert datasets[0]["title"] == "Test Dataset"
	assert datasets[0]["citations"] == 5
	assert datasets[0]["publication_date"] == "2023-01-01"


def test_entity_extractor_authors():
	result = EntityExtractor().run(data=[_RECORD])
	authors = result["nodes"]["Person"]
	uris = {a["uri"] for a in authors}
	assert "https://orcid.org/0000-0001-2345-6789" in uris
	assert "https://orcid.org/0000-0002-9876-5432" in uris


def test_entity_extractor_organisations():
	result = EntityExtractor().run(data=[_RECORD])
	orgs = result["nodes"]["Organisation"]
	assert len(orgs) == 1
	assert orgs[0]["uri"] == "https://ror.org/abc123"
	assert orgs[0]["name"] == "Test Org"


def test_entity_extractor_relationships():
	result = EntityExtractor().run(data=[_RECORD])
	rels = result["relationships"]
	authored_by_datasets = {r[0] for r in rels["AUTHORED_BY"]}
	assert "https://doi.org/10.1234/abc123" in authored_by_datasets
	affiliated_orgs = {r[1] for r in rels["AFFILIATED_WITH"]}
	assert "https://ror.org/abc123" in affiliated_orgs


def test_entity_extractor_handles_missing_fields_gracefully():
	# Records with missing keys fall back to empty strings rather than raising.
	sparse = {"title": "Sparse Dataset"}
	result = EntityExtractor().run(data=[sparse, _RECORD])
	datasets = result["nodes"]["Dataset"]
	assert len(datasets) == 2
	sparse_ds = next(d for d in datasets if d["title"] == "Sparse Dataset")
	assert sparse_ds["uri"] == ""  # extract_doi returns "" when no identifiers present


# ---------------------------------------------------------------------------
# DocumentTruncator
# ---------------------------------------------------------------------------


def test_document_truncator_truncates_long_docs():
	doc = Document(content="x" * 50_000, meta={"uri": "http://example.com"})
	result = DocumentTruncator(max_chars=45_000).run(documents=[doc])
	assert len(result["documents"][0].content) == 45_000


def test_document_truncator_passes_short_docs_unchanged():
	doc = Document(content="short content", meta={})
	result = DocumentTruncator(max_chars=45_000).run(documents=[doc])
	assert result["documents"][0].content == "short content"
