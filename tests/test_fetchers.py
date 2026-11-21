from serka.fetchers import ConceptHierarchyFetcher


def test_concept_hierarchy_fetcher_walks_gemet_broader():
	gemet = "http://www.eionet.europa.eu/gemet/concept/"
	parents = {
		f"{gemet}1225": [{"uri": f"{gemet}4862", "preferredLabel": {"string": "livestock"}}],
		f"{gemet}4862": [{"uri": f"{gemet}299", "preferredLabel": {"string": "animal"}}],
	}
	fetcher = ConceptHierarchyFetcher(broader=lambda uri: parents.get(uri, []))
	nodes = {
		"Concept": [
			{"uri": f"{gemet}1225", "label": "cattle", "scheme": "gemet"},
			{"uri": "http://onto.nerc.ac.uk/CEHMD/topic/8", "label": "Radioecology", "scheme": "keywordsTheme"},
		],
		"Dataset": [{"uri": "d"}],
	}
	result = fetcher.run(nodes=nodes, relationships={"HAS_THEME": [("d", f"{gemet}1225")]})

	assert set(result["relationships"]["BROADER"]) == {(f"{gemet}1225", f"{gemet}4862"), (f"{gemet}4862", f"{gemet}299")}
	assert result["relationships"]["HAS_THEME"] == [("d", f"{gemet}1225")]
	labels = {c["uri"]: c["label"] for c in result["nodes"]["Concept"]}
	assert labels[f"{gemet}299"] == "animal"
	assert result["nodes"]["Dataset"] == [{"uri": "d"}]
