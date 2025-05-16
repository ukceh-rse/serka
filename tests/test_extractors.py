from serka.graph.extractors import (
	AuthorExtractor,
	DatasetExtractor,
	OrganisationExtractor,
	RelationshipExtractor,
	TextExtractor,
)


def test_text_extractor():
	records = [
		{
			"resourceIdentifier": ["10.1234/abc123"],
			"title": "Test Title",
			"description": "test_description",
			"lineage": "test_lineage",
		}
	]
	extractor = TextExtractor(["description", "lineage"])
	result = extractor.run(records=records)
	assert len(result["documents"]) == 2
	assert result["documents"][0].content == "test_description"
	assert result["documents"][0].meta["uri"] == "https://doi.org/10.1234/abc123"
	assert result["documents"][0].meta["title"] == "Test Title"
	assert result["documents"][1].content == "test_lineage"
	assert result["documents"][1].meta["uri"] == "https://doi.org/10.1234/abc123"
	assert result["documents"][1].meta["title"] == "Test Title"


def test_relationship_extractor():
	records = [
		{
			"resourceIdentifier": ["10.1234/abc123"],
			"authorOrcid": ["1234", "5678"],
			"authorRor": ["https://ror.org/1234"],
			"ror": ["https://ror.org/1234"],
		},
	]
	extractor = RelationshipExtractor()
	result = extractor.run(records=records)
	relationships = result["relationships"]

	authorship = relationships["AUTHORED_BY"]
	assert len(authorship) == 2
	assert authorship[0][0] == "https://doi.org/10.1234/abc123"
	assert authorship[0][1] == "1234"
	assert authorship[1][0] == "https://doi.org/10.1234/abc123"
	assert authorship[1][1] == "5678"

	affiliation = relationships["AFFILIATED_WITH"]
	assert len(affiliation) == 1
	assert affiliation[0][0] == "1234"
	assert affiliation[0][1] == "https://ror.org/1234"

	contributions = relationships["CONTRIBUTED_TO"]
	assert len(contributions) == 1
	assert contributions[0][0] == "https://ror.org/1234"
	assert contributions[0][1] == "https://doi.org/10.1234/abc123"


def test_organisation_extractor():
	datasets = [
		{
			"organisation": ["org_a", "org_b"],
			"ror": ["https://ror.org/1234", "https://ror.org/5678"],
			"authorAffiliation": ["org_b", "org_c"],
			"authorRor": ["https://ror.org/5678", "https://ror.org/91011"],
		}
	]
	extractor = OrganisationExtractor()
	result = extractor.run(records=datasets)
	organisations = result["organisations"]
	assert len(organisations) == 3
	assert organisations[0]["name"] == "org_a"
	assert organisations[0]["uri"] == "https://ror.org/1234"
	assert organisations[1]["name"] == "org_b"
	assert organisations[1]["uri"] == "https://ror.org/5678"
	assert organisations[2]["name"] == "org_c"
	assert organisations[2]["uri"] == "https://ror.org/91011"


def test_author_extractor():
	datasets = [
		{
			"authorGivenName": ["Joe", "Sarah"],
			"authorFamilyName": ["Bloggs", "Smith"],
			"authorOrcid": ["1234", "5678"],
		}
	]

	extractor = AuthorExtractor()
	result = extractor.run(records=datasets)
	authors = result["authors"]
	assert len(authors) == 2
	assert authors[0]["forename"] == "Joe"
	assert authors[0]["surname"] == "Bloggs"
	assert authors[0]["uri"] == "1234"
	assert authors[1]["forename"] == "Sarah"
	assert authors[1]["surname"] == "Smith"
	assert authors[1]["uri"] == "5678"


def test_dataset_extractor():
	datasets = [
		{
			"resourceIdentifier": ["not/a/doi", "10.1234/abc123"],
			"title": "Test Dataset",
		},
		{
			"resourceIdentifier": ["10.1234/987654", "not/a/doi"],
			"title": "Another Dataset",
		},
	]
	extractor = DatasetExtractor()
	result = extractor.run(records=datasets)
	datasets = result["datasets"]
	assert len(datasets) == 2
	assert datasets[0]["uri"] == "https://doi.org/10.1234/abc123"
	assert datasets[0]["title"] == "Test Dataset"
	assert datasets[1]["uri"] == "https://doi.org/10.1234/987654"
	assert datasets[1]["title"] == "Another Dataset"
