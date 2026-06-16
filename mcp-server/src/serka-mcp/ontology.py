from typing import Any

JSONLD_CONTEXT: dict[str, str] = {
	"dcat": "https://www.w3.org/ns/dcat#",
	"dcterms": "http://purl.org/dc/terms/",
	"doo": "https://digital.ceh.ac.uk/ontology/doo/",
	"fabio": "http://purl.org/spar/fabio/",
	"foaf": "http://xmlns.com/foaf/0.1/",
	"frapo": "http://purl.org/cerif/frapo/",
	"geo": "http://www.opengis.net/ont/geosparql#",
	"org": "http://www.w3.org/ns/org#",
	"pro": "http://purl.org/spar/pro/",
	"prov": "http://www.w3.org/ns/prov#",
	"scoro": "http://purl.org/spar/scoro/",
	"skos": "http://www.w3.org/2004/02/skos/core#",
}

NODE_TYPES: dict[str, str] = {
	"Dataset": "dcat:Dataset",
	"Person": "foaf:Person",
	"Organisation": "foaf:Organization",
	"Concept": "skos:Concept",
	"Document": "fabio:Expression",
}

PROPERTY_TERMS: dict[str, str] = {
	"title": "dcterms:title",
	"description": "dcterms:description",
	"lineage": "dcterms:provenance",
	"publication_date": "dcterms:issued",
	"identifiers": "dcterms:identifier",
	"licence": "dcterms:license",
	"resource_type": "dcterms:type",
	"temporal_start": "dcterms:temporal",
	"temporal_end": "dcterms:temporal",
	"access_rights": "dcterms:accessRights",
	"citations": "dcterms:relation",
	"south_boundary": "geo:hasBoundingBox",
	"north_boundary": "geo:hasBoundingBox",
	"west_boundary": "geo:hasBoundingBox",
	"east_boundary": "geo:hasBoundingBox",
	"name": "foaf:name",
	"label": "skos:prefLabel",
	"scheme": "skos:inScheme",
	"format": "dcterms:format",
	"bibliographic_citation": "dcterms:bibliographicCitation",
}

ROLE_TERMS: dict[str, str] = {
	"author": "scoro:AuthorshipRole",
	"coAuthor": "scoro:AuthorshipRole",
	"custodian": "scoro:DataRole",
	"distributor": "scoro:DataRole",
	"distributorContact": "scoro:DataRole",
	"originator": "scoro:AuthorshipRole",
	"pointOfContact": "pro:RoleInTime",
	"principalInvestigator": "scoro:InvestigationRole",
	"publisher": "dcterms:publisher",
	"rightsHolder": "dcterms:rightsHolder",
}
