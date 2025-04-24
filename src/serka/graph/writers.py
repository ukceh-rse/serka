from haystack import component
from typing import Dict, List, Any, Tuple
from neo4j import GraphDatabase


@component
class Neo4jGraphWriter:
	def __init__(self, url="bolt://localhost:7687", username="neo4j", password="neo4j"):
		self.url = url
		self.username = username
		self.password = password

	@staticmethod
	def create_nodes(tx, nodes_and_types):
		nodes_created: Dict[str, int] = dict()
		for node_type, node_list in nodes_and_types.items():
			props = ", ".join(f"{key}: node.{key}" for key in node_list[0].keys())
			query = (
				"UNWIND $nodes as node "
				f"MERGE (n:{node_type} {{{props}}}) "
				"RETURN n"
			)
			result = tx.run(query, nodes=node_list)
			nodes_created[node_type] = len(result.data())
		return nodes_created

	@staticmethod
	def create_relations(tx, relations_and_types):
		relations_created: Dict[str, int] = dict()
		for relation_type, relation_list in relations_and_types.items():
			query = (
				"UNWIND $relations as relation "
				f"MATCH (a), (b) "
				"WHERE a.uri = relation[0] AND b.uri = relation[1] "
				f"MERGE (a)-[:{relation_type}]->(b) "
				"RETURN COUNT(*)"
			)
			result = tx.run(query, relations=relation_list)
			relations_created[relation_type] = result.data()[0]["COUNT(*)"]
		return relations_created

	@staticmethod
	def create_nodes_and_relations(tx, nodes_and_types, relations_and_types):
		nodes_created = Neo4jGraphWriter.create_nodes(tx, nodes_and_types)
		relations_created = Neo4jGraphWriter.create_relations(tx, relations_and_types)
		return nodes_created, relations_created

	@component.output_types(
		nodes_created=Dict[str, int], relations_created=Dict[str, int]
	)
	def run(
		self,
		nodes: Dict[str, List[Dict[str, Any]]],
		relations: Dict[str, List[Tuple[str, str]]],
	) -> Dict[str, Any]:
		with GraphDatabase.driver(
			self.url, auth=(self.username, self.password)
		) as driver:
			with driver.session(database="neo4j") as session:
				node_result, relation_result = session.execute_write(
					Neo4jGraphWriter.create_nodes_and_relations, nodes, relations
				)
		return {"nodes_created": node_result, "relations_created": relation_result}
