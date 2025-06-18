from haystack import component, Document
from typing import Dict, List, Any, Tuple
from neo4j import GraphDatabase


@component
class Neo4jGraphWriter:
	def __init__(
		self, host: str, port: int, username: str = "neo4j", password: str = "neo4j"
	):
		self.url = f"bolt://{host}:{port}"
		self.username = username
		self.password = password

	@staticmethod
	def create_nodes(tx, nodes_and_types) -> Dict[str, int]:
		nodes_created: Dict[str, int] = dict()
		for node_type, node_list in nodes_and_types.items():
			props = ", ".join(f"{key}: node.{key}" for key in node_list[0].keys())
			query = (
				"UNWIND $nodes as node "
				f"MERGE (n:{node_type}:embedded {{{props}}}) "
				"RETURN n"
			)
			result = tx.run(query, nodes=node_list)
			nodes_created[node_type] = len(result.data())
		return nodes_created

	@staticmethod
	def create_relations(tx, relations_and_types) -> Dict[str, int]:
		relations_created: Dict[str, int] = dict()
		for relation_type, relation_list in relations_and_types.items():
			query = (
				"UNWIND $relations as relation "
				"MATCH (a {uri: relation[0]}) "
				"MATCH (b {uri: relation[1]}) "
				f"MERGE (a)-[:{relation_type}]->(b) "
				"RETURN COUNT(*)"
			)
			result = tx.run(query, relations=relation_list)
			relations_created[relation_type] = result.data()[0]["COUNT(*)"]
		return relations_created

	@staticmethod
	def create_doc_nodes(tx, docs: List[Dict[str, Any]]) -> int:
		query = (
			"UNWIND $docs as doc "
			"MERGE (d:TextChunk:embedded {doc_id: doc.id, content: doc.content, embedding: doc.embedding}) "
			"RETURN d"
		)
		result = tx.run(query, docs=docs)
		docs_created = len(result.data())
		return docs_created

	@staticmethod
	def unpack_doc_relations(
		docs: List[Dict[str, Any]],
	) -> Dict[str, List[Tuple[str, str]]]:
		relations: Dict[str, List[Tuple[str, str]]] = {}
		for doc in docs:
			field = str(doc.get("field", "")).upper() + "_OF"
			if field not in relations:
				relations[field] = []
			relations[field].append((doc["id"], doc["uri"]))
		return relations

	@staticmethod
	def create_doc_relations(tx, docs: List[Dict[str, Any]]) -> Dict[str, int]:
		relations = Neo4jGraphWriter.unpack_doc_relations(docs)
		relations_created: Dict[str, int] = dict()
		for relation_type, relation_list in relations.items():
			query = (
				"UNWIND $relations as relation "
				"MATCH (a:TextChunk {doc_id: relation[0]}) "
				"MATCH (b {uri: relation[1]}) "
				f"MERGE (a)-[:{relation_type}]->(b) "
				"RETURN COUNT(*)"
			)
			result = tx.run(query, relations=relation_list)
			relations_created[relation_type] = result.data()[0]["COUNT(*)"]
		return relations_created

	@staticmethod
	def doc_to_dict(doc: Document) -> Dict[str, Any]:
		return {
			"id": doc.id,
			"content": doc.content,
			"field": doc.meta.get("field", ""),
			"uri": doc.meta.get("uri", ""),
			"embedding": doc.embedding,
		}

	@staticmethod
	def create_indexes(tx):
		tx.run(
			"CREATE VECTOR INDEX vec_lookup IF NOT EXISTS FOR (n:embedded) ON n.embedding;"
		)
		tx.run("CREATE INDEX doc_id_idx IF NOT EXISTS FOR (c:TextChunk) ON (c.doc_id);")
		tx.run("CREATE INDEX uri_idx IF NOT EXISTS FOR (n:embedded) ON (n.uri);")
		return {"message": "Indexes created successfully"}

	@staticmethod
	def create_graph(
		tx,
		nodes_and_types: Dict[str, List[Dict[str, Any]]],
		relations_and_types: Dict[str, List[Tuple[str, str]]],
		docs: List[Document],
	) -> Tuple[Dict[str, int], Dict[str, int]]:
		nodes_created = Neo4jGraphWriter.create_nodes(tx, nodes_and_types)
		relations_created = Neo4jGraphWriter.create_relations(tx, relations_and_types)

		docs_as_dicts = [Neo4jGraphWriter.doc_to_dict(doc) for doc in docs]
		nodes_created["Document"] = Neo4jGraphWriter.create_doc_nodes(tx, docs_as_dicts)
		doc_relations_created = Neo4jGraphWriter.create_doc_relations(tx, docs_as_dicts)

		return nodes_created, relations_created | doc_relations_created

	@component.output_types(
		nodes_created=Dict[str, int], relations_created=Dict[str, int]
	)
	def run(
		self,
		nodes: Dict[str, List[Dict[str, Any]]],
		relations: Dict[str, List[Tuple[str, str]]],
		docs: List[Document],
	) -> Dict[str, Any]:
		with GraphDatabase.driver(
			self.url, auth=(self.username, self.password)
		) as driver:
			with driver.session(database="neo4j") as session:
				session.execute_write(Neo4jGraphWriter.create_indexes)
				node_result, relation_result = session.execute_write(
					Neo4jGraphWriter.create_graph, nodes, relations, docs
				)
		return {"nodes_created": node_result, "relations_created": relation_result}
