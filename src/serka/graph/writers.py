from haystack import component
from typing import Dict, List, Any
from neo4j import GraphDatabase


@component
class Neo4jGraphWriter:
	def __init__(self, url="bolt://localhost:7687", username="neo4j", password="neo4j"):
		self.url = url
		self.username = username
		self.password = password

	@component.output_types(nodes_created=Dict[str, int])
	def run(
		self,
		nodes: Dict[str, List[Dict[str, Any]]],
	) -> Dict[str, Any]:
		result = {}
		with GraphDatabase.driver(
			self.url, auth=(self.username, self.password)
		) as driver:
			with driver.session(database="neo4j") as session:

				def create_nodes(tx, nodes_and_types):
					nodes_created: Dict[str, int] = dict()
					for node_type, node_list in nodes_and_types.items():
						props = ", ".join(
							f"{key}: node.{key}" for key in node_list[0].keys()
						)
						query = (
							"UNWIND $nodes as node "
							f"MERGE (n:{node_type} {{{props}}}) "
							"RETURN n"
						)
						result = tx.run(query, nodes=node_list)
						nodes_created[node_type] = len(result.data())
					return nodes_created

				result = session.execute_write(create_nodes, nodes)
		return {"nodes_created": result}
