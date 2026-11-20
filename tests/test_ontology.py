"""The DOO mapping is ingest's vocabulary for the bundle's ontology concepts, and must conform to DOO itself."""

import json
from pathlib import Path

import pytest
import rdflib
from rdflib.namespace import OWL, RDF

from serka.ontology import compact_iri

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "src" / "serka" / "doo_mapping.json"
MAPPING = json.loads(CANONICAL.read_text())
PREFIXES = MAPPING["prefixes"]


def _iri(curie: str) -> rdflib.URIRef:
	prefix, _, local = curie.partition(":")
	return rdflib.URIRef(PREFIXES[prefix] + local)


@pytest.fixture(scope="module")
def doo() -> rdflib.Graph:
	return rdflib.Graph().parse(ROOT / "tests" / "data" / "doo-0.3.3.ttl")


def test_mapping_targets_vendored_doo_version(doo):
	versions = {str(v) for v in doo.objects(None, OWL.versionInfo)}
	assert MAPPING["doo_version"] in versions


def test_prefix_namespaces_match_doo(doo):
	iris = {str(t) for triple in doo for t in triple if isinstance(t, rdflib.URIRef)}
	unused = [p for p, ns in PREFIXES.items() if p != "serka" and not any(i.startswith(ns) for i in iris)]
	assert unused == [], "namespace differs from the one DOO uses (http vs https?)"


def test_role_individuals_are_doo_individuals_of_their_class(doo):
	for individual, role_class in MAPPING["role_classes"].items():
		types = set(doo.objects(_iri(individual), RDF.type))
		assert OWL.NamedIndividual in types, f"{individual} is not a DOO named individual"
		assert _iri(role_class) in types, f"{individual} is not a {role_class} in DOO"


def test_every_eidc_role_maps_to_a_known_individual():
	individuals = set(MAPPING["role_classes"])
	assert set(MAPPING["roles"].values()) <= individuals
	assert MAPPING["default_role"] in individuals


@pytest.mark.parametrize("kind", ["node_types", "predicates"])
def test_terms_are_declared_in_doo_or_listed_as_extensions(doo, kind):
	terms = MAPPING[kind].values() if isinstance(MAPPING[kind], dict) else MAPPING[kind]
	undeclared = [t for t in terms if not set(doo.objects(_iri(t), RDF.type)) and t not in MAPPING["not_in_doo"]]
	assert undeclared == []


def test_extensions_really_are_missing_from_doo(doo):
	declared = [t for t in MAPPING["not_in_doo"] if set(doo.objects(_iri(t), RDF.type))]
	assert declared == [], "now declared in DOO; remove from not_in_doo"


def test_compact_iri():
	assert compact_iri("http://purl.org/dc/terms/isPartOf") == "dcterms:isPartOf"
	assert compact_iri("https://example.org/unknown") == "https://example.org/unknown"
