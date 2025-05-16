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
			"WITH start_node, r, connected_node, score, "
			"CASE WHEN startNode(r) = start_node THEN 'outgoing' ELSE 'incoming' END as direction "
			"RETURN apoc.map.removeKeys(start_node, ['embedding']) as start_node, "
			"id(start_node) as start_node_id, "
			"labels(start_node) as start_labels, "
			"type(r) as relationship_type, "
			"direction as relationship_direction, "
			"apoc.map.removeKeys(connected_node, ['embedding']) as connected_node, "
			"id(connected_node) as connected_node_id, "
			"labels(connected_node) as connected_labels, "
			"score"
		)
		result = tx.run(query, embedding=embedding)
		data = result.data()
		return data

	def node_to_markdown(self, label: str, node_id: int, node: Dict[str, Any]) -> str:
		markdown_id = f"{label.lower()}_{node_id:04d}"
		markdown = f"[{label}:{markdown_id}]\n"
		for key, value in node.items():
			if key == "doc_id":
				continue
			markdown += f" - {key}: {value}\n"
		markdown += "\n"
		return markdown, markdown_id

	def extract_node(self, labels, id, node):
		labels.remove("embedded")
		label = labels[0]
		markdown, markdown_id = self.node_to_markdown(label, id, node)
		return label, markdown, markdown_id

	def nodes_to_markdown(self, rows: List[Dict[str, Any]]) -> str:
		nodes_sets = {
			"Person": set(),
			"Dataset": set(),
			"Organisation": set(),
			"TextChunk": set(),
		}
		relationships = set()

		# Take all nodes returned from the query and create a label for them
		# and add them to the corresponding set
		for row in rows:
			s_label, s_md, s_id = self.extract_node(
				row["start_labels"], row["start_node_id"], row["start_node"]
			)
			nodes_sets[s_label].add(s_md)
			c_label, c_md, c_id = self.extract_node(
				row["connected_labels"], row["connected_node_id"], row["connected_node"]
			)
			nodes_sets[c_label].add(c_md)

			a = s_id if row["relationship_direction"] == "outgoing" else c_id
			b = c_id if row["relationship_direction"] == "outgoing" else s_id
			relationships.add(f"{a} -> {row['relationship_type']} -> {b}")

		markdown = "## Nodes\n"
		for node_set in nodes_sets.values():
			for node in node_set:
				markdown += node
		markdown += "\n## Relationships\n"
		for rel in relationships:
			markdown += f" - {rel}\n"
		return markdown

	@component.output_types(nodes=List[Dict[str, Any]], markdown_nodes=str)
	def run(self, embedding: List[float]):
		with GraphDatabase.driver(
			self.url, auth=(self.username, self.password)
		) as driver:
			with driver.session(database="neo4j") as session:
				nodes = session.execute_read(
					Neo4jGraphReader.query_nodes, embedding=embedding
				)
		return {"nodes": nodes, "markdown_nodes": self.nodes_to_markdown(nodes)}
