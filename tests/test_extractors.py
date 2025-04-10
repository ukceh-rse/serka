from serka.graph.extractors import AuthorExtractor


def test_author_extractor():
	datasets = [
		{
			"authorGivenName": ["Joe", "Sarah"],
			"authorFamilyName": ["Bloggs", "Smith"],
			"authorOrcid": ["1234", "5678"],
		}
	]

	extractor = AuthorExtractor()
	authors = extractor.run(datasets=datasets)
	assert len(authors) == 2
	assert authors[0]["forename"] == "Joe"
	assert authors[0]["surname"] == "Bloggs"
	assert authors[0]["orcid"] == "1234"
	assert authors[1]["forename"] == "Sarah"
	assert authors[1]["surname"] == "Smith"
	assert authors[1]["orcid"] == "5678"
