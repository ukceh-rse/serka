from neomodel import (
	ArrayProperty,
	DateProperty,
	RelationshipTo,
	StringProperty,
	StructuredNode,
	StructuredRel,
)


class AssociationRel(StructuredRel):
	role = StringProperty()


class RelationRel(StructuredRel):
	predicate = StringProperty()


class Organisation(StructuredNode):
	uri = StringProperty(unique_index=True, required=True)
	name = StringProperty()


class Concept(StructuredNode):
	uri = StringProperty(unique_index=True, required=True)
	label = StringProperty()
	scheme = StringProperty()


class Document(StructuredNode):
	"""A citable published work (e.g. an external paper citing a Dataset) — fabio:Expression."""

	uri = StringProperty(unique_index=True, required=True)
	bibliographic_citation = StringProperty()


class DigitalManifestation(StructuredNode):
	"""An arbitrary uploaded file with no bibliographic identity (e.g. a supporting-doc
	PDF) — fabio:DigitalManifestation, the FRBR embodiment level, not fabio:Expression."""

	uri = StringProperty(unique_index=True, required=True)
	title = StringProperty()
	format = StringProperty()


class Person(StructuredNode):
	uri = StringProperty(unique_index=True, required=True)
	name = StringProperty()
	affiliation = RelationshipTo(Organisation, "AFFILIATED_WITH")


class Dataset(StructuredNode):
	uri = StringProperty(unique_index=True, required=True)
	title = StringProperty()
	description = StringProperty()
	lineage = StringProperty()
	publication_date = DateProperty()
	identifiers = ArrayProperty(StringProperty())
	resource_type = StringProperty()
	access_rights = StringProperty()
	licence = StringProperty()
	temporal_start = DateProperty()
	temporal_end = DateProperty()
	associated_with = RelationshipTo(Person, "ASSOCIATED_WITH", model=AssociationRel)
	has_theme = RelationshipTo(Concept, "HAS_THEME")
	relation = RelationshipTo("Dataset", "RELATION", model=RelationRel)
