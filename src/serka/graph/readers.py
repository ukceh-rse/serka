from typing import List, Any, Dict
from haystack import component
from neo4j import GraphDatabase


@component
class Neo4jGraphReader:
	def __init__(self, url="bolt://localhost:7687", username="neo4j", password="neo4j"):
		self.url = url
		self.username = username
		self.password = password

	@staticmethod
	def query_nodes(tx, embedding: List[float]) -> List[Dict[str, Any]]:
		query = (
			"CALL db.index.vector.queryNodes('vec_lookup', 5, $embedding) "
			"YIELD node AS start_node, score "
			"MATCH (start_node)-[r]-(connected_node) "
			"RETURN apoc.map.removeKeys(start_node, ['embedding']) as start_node, "
			"labels(start_node) as start_labels, "
			"type(r) as relationship_type, "
			"apoc.map.removeKeys(connected_node, ['embedding']) as connected_node, "
			"labels(connected_node) as connected_labels, "
			"score"
		)
		result = tx.run(query, embedding=embedding)
		data = result.data()
		return data

	@component.output_types(nodes=List[Dict[str, Any]])
	def run(self, embedding: List[float]):
		with GraphDatabase.driver(
			self.url, auth=(self.username, self.password)
		) as driver:
			with driver.session(database="neo4j") as session:
				nodes = session.execute_read(
					Neo4jGraphReader.query_nodes, embedding=embedding
				)
		return {"nodes": nodes}
