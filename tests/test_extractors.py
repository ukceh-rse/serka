import json
from pathlib import Path

from haystack import Document

from serka.graph.extractors import DocumentTruncator, EntityExtractor, TextExtractor


# ---------------------------------------------------------------------------
# TextExtractor
# ---------------------------------------------------------------------------


def test_text_extractor_returns_documents_for_each_field():
	records = [
		{
			"uri": "https://catalogue.ceh.ac.uk/id/test-uuid-abc",
			"title": "Test Title",
			"description": "test_description",
			"lineage": "test_lineage",
		}
	]
	result = TextExtractor(["description", "lineage"]).run(records=records)
	docs = result["documents"]
	assert len(docs) == 2
	assert docs[0].content == "test_description"
	assert docs[0].meta["uri"] == "https://catalogue.ceh.ac.uk/id/test-uuid-abc"
	assert docs[0].meta["title"] == "Test Title"
	assert docs[1].content == "test_lineage"


def test_text_extractor_skips_missing_fields():
	records = [
		{
			"uri": "https://catalogue.ceh.ac.uk/id/test-uuid-xyz",
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
	"uri": "https://catalogue.ceh.ac.uk/id/test-uuid-1234",
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
	assert datasets[0]["uri"] == "https://catalogue.ceh.ac.uk/id/test-uuid-1234"
	assert datasets[0]["title"] == "Test Dataset"
	assert datasets[0]["citations"] == 5
	assert datasets[0]["publication_date"] == "2023-01-01"
	assert "https://doi.org/10.1234/abc123" in datasets[0]["identifiers"]


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
	assoc_datasets = {r[0] for r in rels["ASSOCIATED_WITH"]}
	assert "https://catalogue.ceh.ac.uk/id/test-uuid-1234" in assoc_datasets
	affiliated_orgs = {r[1] for r in rels["AFFILIATED_WITH"]}
	assert "https://ror.org/abc123" in affiliated_orgs


def test_entity_extractor_handles_missing_fields_gracefully():
	sparse = {"title": "Sparse Dataset"}
	result = EntityExtractor().run(data=[sparse, _RECORD])
	datasets = result["nodes"]["Dataset"]
	assert len(datasets) == 2
	sparse_ds = next(d for d in datasets if d["title"] == "Sparse Dataset")
	assert sparse_ds["uri"] == ""


# Real EIDC records (tests/data): 1c2fe14e has relationships, funding, a rights holder and
# a contact point; ae02f4e8 has an isPartOf relationship and keywordsTheme concepts.
_DATA = Path(__file__).parent / "data"
_REAL = [json.loads((_DATA / f).read_text()) for f in ("eidc-1c2fe14e.json", "eidc-ae02f4e8.json")]
_URI_1C2 = "https://catalogue.ceh.ac.uk/id/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"
_URI_AE0 = "https://catalogue.ceh.ac.uk/id/ae02f4e8-9486-4b47-93ef-e49dd9ddecd4"


def test_real_records_relationships_use_eidc_keys_and_curies():
	rels = EntityExtractor().run(data=_REAL)["relationships"]["RELATION"]
	dataset_rels = {r for r in rels if r[2].startswith("https://catalogue.ceh.ac.uk/id/")}
	assert (_URI_AE0, "dcterms:isPartOf", "https://catalogue.ceh.ac.uk/id/3124e313-7ce8-4832-98b4-2357fab9284c") in dataset_rels
	assert (_URI_1C2, "dcterms:relation", "https://catalogue.ceh.ac.uk/id/cfcc0e31-e2ce-450b-a292-3427de06a687") in dataset_rels
	assert all(":" in p and not p.startswith("http") for _, p, _ in rels)


def test_real_records_contact_points_and_rights_holders():
	assoc = EntityExtractor().run(data=_REAL)["relationships"]["ASSOCIATED_WITH"]
	roles = {(d, a, r) for d, a, r in assoc}
	assert (_URI_1C2, "https://ror.org/00n3w3b69", "rightsHolder") in roles
	# A named contact with an ORCID holds the role personally...
	assert (_URI_AE0, "https://orcid.org/0000-0002-8722-0238", "pointOfContact") in roles
	# ...and one without an ORCID is dropped rather than credited to their organisation
	assert (_URI_1C2, "https://ror.org/00n3w3b69", "pointOfContact") not in roles


def test_legacy_points_of_contact_key_still_read():
	# Records cached before EIDC renamed the field use pointsOfContact
	legacy = {**_RECORD, "pointsOfContact": [{"organisationIdentifier": "https://ror.org/poc", "role": "pointOfContact"}]}
	assoc = EntityExtractor().run(data=[legacy])["relationships"]["ASSOCIATED_WITH"]
	assert (_RECORD["uri"], "https://ror.org/poc", "pointOfContact") in assoc


def test_real_records_organisation_does_not_inherit_person_role():
	assoc = EntityExtractor().run(data=_REAL)["relationships"]["ASSOCIATED_WITH"]
	# Both authors of 1c2fe14e are people at ror.org/00n3w3b69: the org is no author
	assert (_URI_1C2, "https://ror.org/00n3w3b69", "author") not in set(assoc)
	assert (_URI_1C2, "https://orcid.org/0000-0003-4460-5178", "author") in set(assoc)


def test_real_records_theme_keywords():
	result = EntityExtractor().run(data=_REAL)
	themes = set(result["relationships"]["HAS_THEME"])
	assert (_URI_AE0, "http://onto.nerc.ac.uk/CEHMD/topic/8") in themes
	labels = {c["uri"]: c["label"] for c in result["nodes"]["Concept"]}
	assert labels["http://onto.nerc.ac.uk/CEHMD/topic/8"] == "Radioecology"


def test_real_records_funding():
	result = EntityExtractor().run(data=_REAL)
	nerc = "https://ror.org/02b5d8509"
	grant_uri = f"{nerc}#NE%2FV010603%2F1"
	assert result["nodes"]["FundingAgency"] == [{"uri": nerc, "name": "Natural Environment Research Council"}]
	assert result["nodes"]["Grant"] == [{"uri": grant_uri, "grant_number": "NE/V010603/1"}]
	rels = set(result["relationships"]["RELATION"])
	assert (_URI_1C2, "doo:originatingGrant", grant_uri) in rels
	assert (nerc, "frapo:awards", grant_uri) in rels


def test_missing_bounding_box_is_not_an_error(caplog):
	EntityExtractor().run(data=[_RECORD])
	assert "boundingBoxes" not in caplog.text


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
