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
			"CALL db.index.vector.queryNodes('vec_lookup', 100, $embedding) "
			"YIELD node AS start_node, score "
			"MATCH (start_node)-[r]-(connected_node) "
			"RETURN apoc.map.removeKeys(start_node, ['embedding']) as start_node, "
			"id(start_node) as start_node_id, "
			"labels(start_node) as start_labels, "
			"type(r) as relationship_type, "
			"apoc.map.removeKeys(connected_node, ['embedding']) as connected_node, "
			"id(connected_node) as connected_node_id, "
			"labels(connected_node) as connected_labels, "
			"score"
		)
		result = tx.run(query, embedding=embedding)
		data = result.data()
		return data

	def node_to_markdown(self, label: str, node_id: int, node: Dict[str, Any]) -> str:
		markdown = f"[{label}:{label.lower()}_{node_id:04d}]\n"
		for key, value in node.items():
			markdown += f" - {key}: {value}\n"
		markdown += "\n"
		return markdown

	def nodes_to_markdown(self, nodes: List[Dict[str, Any]]) -> str:
		nodes_sets = {
			"Person": set(),
			"Dataset": set(),
			"Organisation": set(),
			"TextChunk": set(),
		}

		for node in nodes:
			labels = node["start_labels"]
			labels.remove("embedded")
			label = labels[0]
			node_id: int = node["start_node_id"]
			node_markdown = self.node_to_markdown(label, node_id, node["start_node"])
			nodes_sets[label].add(node_markdown)

		markdown = ""
		for label, node_set in nodes_sets.items():
			print(node_set)
			for node in node_set:
				markdown += node
		return markdown

		markdown_nodes = ""
		for node in nodes:
			start_node = node["start_node"]
			start_labels = node["start_labels"]
			relationship_type = node["relationship_type"]
			connected_node = node["connected_node"]
			connected_labels = node["connected_labels"]
			score = node["score"]

			markdown_nodes += f"### Node: {start_node}\n"
			markdown_nodes += f"Labels: {start_labels}\n"
			markdown_nodes += f"Relationship Type: {relationship_type}\n"
			markdown_nodes += f"Connected Node: {connected_node}\n"
			markdown_nodes += f"Connected Labels: {connected_labels}\n"
			markdown_nodes += f"Score: {score}\n\n"

		return markdown_nodes

	@component.output_types(nodes=List[Dict[str, Any]])
	def run(self, embedding: List[float]):
		with GraphDatabase.driver(
			self.url, auth=(self.username, self.password)
		) as driver:
			with driver.session(database="neo4j") as session:
				nodes = session.execute_read(
					Neo4jGraphReader.query_nodes, embedding=embedding
				)
		return {"nodes": nodes, "markdown_nodes": self.nodes_to_markdown(nodes)}
