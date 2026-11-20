from haystack import Document

from serka.okf import ids

DATASET_URI = "https://catalogue.ceh.ac.uk/id/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"


def test_dataset_id_is_the_eidc_id() -> None:
	assert ids.dataset_id(DATASET_URI) == "datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d"


def test_person_id_uses_orcid() -> None:
	assert ids.person_id("https://orcid.org/0000-0002-1825-009X") == "people/0000-0002-1825-009X"


def test_organisation_id_uses_ror() -> None:
	assert ids.organisation_id("https://ror.org/00pggkr55") == "organisations/00pggkr55"


def test_other_identifiers_are_hashed_stably() -> None:
	uri = "https://example.org/people/jane"
	assert ids.person_id(uri) == ids.person_id(uri)
	assert ids.person_id(uri).startswith("people/")
	assert len(ids.person_id(uri).split("/")[1]) == 12
	assert ids.theme_id(uri) != ids.theme_id(uri + "x")
	assert "jane" not in ids.person_id(uri)


def test_same_named_supporting_files_get_distinct_ids() -> None:
	a = Document(content="first", meta={"uri": DATASET_URI, "filename": "readme.txt"})
	b = Document(content="second", meta={"uri": DATASET_URI, "filename": "readme.txt"})
	a_id, b_id = ids.document_id(DATASET_URI, a.id), ids.document_id(DATASET_URI, b.id)
	assert a_id != b_id
	assert a_id.startswith("datasets/1c2fe14e-0aa4-4f4a-b827-57b96deeda0d/docs/")


def test_document_id_is_stable() -> None:
	doc = Document(content="same", meta={"uri": DATASET_URI, "filename": "readme.txt"})
	again = Document(content="same", meta={"uri": DATASET_URI, "filename": "readme.txt"})
	assert ids.document_id(DATASET_URI, doc.id) == ids.document_id(DATASET_URI, again.id)
