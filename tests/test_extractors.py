from serka.graph.extractors import AuthorExtractor, DatasetExtractor


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
