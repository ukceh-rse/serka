from neomodel import StructuredNode, StringProperty, RelationshipTo, DateProperty


class Organisation(StructuredNode):
	uri = StringProperty(unique_index=True, required=True)
	name = StringProperty()


class Dataset(StructuredNode):
	uri = StringProperty(unique_index=True, required=True)
	title = StringProperty()
	description = StringProperty()
	lineage = StringProperty()
	publicationDate = DateProperty()
	authors = RelationshipTo("Person", "AUTHORED_BY")


class Person(StructuredNode):
	uri = StringProperty(unique_index=True, required=True)
	surname = StringProperty()
	forename = StringProperty()
	affiliation = RelationshipTo(Organisation, "AFFILIATED_TO")
