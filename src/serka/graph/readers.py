from typing import List, Any, Dict
from haystack import component
from neo4j import GraphDatabase
from serka.models import Document, GroupedDocuments, ScoredDocument


@component
class Neo4jGraphReader:
	def __init__(self, url="bolt://localhost:7687", username="neo4j", password="neo4j"):
		self.url = url
		self.username = username
		self.password = password

	@staticmethod
	def query_nodes(tx, embedding: List[float]) -> List[Dict[str, Any]]:
		query = (
			"CALL db.index.vector.queryNodes('vec_lookup', 20, $embedding) "
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
			markdown += f" - {key}: {value.replace("\n", " ")}\n"
		markdown += "\n"
		return markdown, markdown_id

	def extract_node(self, labels, id, node):
		labels.remove("embedded")
		label = labels[0]
		markdown, markdown_id = self.node_to_markdown(label, id, node)
		return label, markdown, markdown_id

	def group_nodes(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		group_by = "Dataset"
		grouped_nodes = {}
		for row in rows:
			if group_by not in [*row["start_labels"], *row["connected_labels"]]:
				continue
			dataset_prefix = "start" if group_by in row["start_labels"] else "connected"
			nondataset_prefix = "connected" if dataset_prefix == "start" else "start"
			uri = row[f"{dataset_prefix}_node"]["uri"]
			title = row[f"{dataset_prefix}_node"]["title"]
			if uri not in grouped_nodes:
				grouped_nodes[uri] = {
					"uri": uri,
					"title": title,
				}

			if (
				"TextChunk" in row["connected_labels"]
				and row["relationship_type"] == "SUPPORTING_DOC_OF"
			):
				continue

			relationship = row["relationship_type"]
			if relationship not in grouped_nodes[uri]:
				grouped_nodes[uri][relationship] = []

			if "TextChunk" in row[f"{nondataset_prefix}_labels"]:
				content = row[f"{nondataset_prefix}_node"].get("content", "")
				if content:
					grouped_nodes[uri][relationship].append(content)

			if (
				"Person" in row[f"{nondataset_prefix}_labels"]
				or "Organisation" in row[f"{nondataset_prefix}_labels"]
			):
				name = row[f"{nondataset_prefix}_node"].get("name", "")
				if name:
					grouped_nodes[uri][relationship].append(content)

		return list(grouped_nodes.values())

	def escape_markdown(text):
		"""Basic escaping of markdown special characters"""
		if not text:
			return ""
		# Escape characters that have special meaning in Markdown
		text = text.replace("\n", " ")
		escapes = [
			("\\", "\\\\"),
			("*", "\\*"),
			("_", "\\_"),
			("`", "\\`"),
			("#", "\\#"),
			("+", "\\+"),
			("-", "\\-"),
			(".", "\\."),
			("!", "\\!"),
			("(", "\\("),
			(")", "\\)"),
			("[", "\\["),
			("]", "\\]"),
		]
		result = text
		for char, escaped in escapes:
			result = result.replace(char, escaped)
		return result

	def nodes_to_markdown(self, grouped_nodes: List[Dict[str, Any]]) -> str:
		markdown = ""
		for dataset in grouped_nodes:
			markdown += f"# {dataset["title"]}\n"
			markdown += f"## URL\n{dataset["uri"]}\n"
			if "DESCRIPTION_OF" in dataset:
				markdown += "\n## Description (excerpts)\n- "
				markdown += "\n- ".join(
					[
						Neo4jGraphReader.escape_markdown(item)
						for item in dataset["DESCRIPTION_OF"]
					]
				)

			if "SUPPORTING_DOC_OF" in dataset:
				markdown += "\n## Supporting Documentation (excerpts)\n- "
				markdown += "\n- ".join(
					[
						Neo4jGraphReader.escape_markdown(item)
						for item in dataset["SUPPORTING_DOC_OF"]
					]
				)
		return markdown

	def group_and_sort_nodes(self, nodes) -> List[GroupedDocuments]:
		docs = set()
		for node in nodes:
			score = node["score"]
			content = None
			meta = {}
			if "TextChunk" in node["start_labels"]:
				content = node["start_node"]["content"]
				meta["section"] = node["relationship_type"]
				meta["title"] = node["connected_node"]["title"]
				meta["url"] = node["connected_node"]["uri"]
			if "Dataset" in node["start_labels"]:
				content = repr(node["start_node"])
				meta["title"] = node["start_node"]["title"]
				meta["section"] = "Dataset"
				meta["url"] = node["start_node"]["uri"]

			if content:
				docs.add(
					ScoredDocument(
						document=Document(content=content, metadata=meta), score=score
					)
				)

		docs = sorted(docs, key=lambda x: x.score, reverse=True)

		groupby = "title"

		grouped: Dict[str, GroupedDocuments] = {}
		for doc in docs:
			groupby_val = doc.document.metadata.get(groupby, "unknown")
			if groupby_val not in grouped.keys():
				grouped[groupby_val] = GroupedDocuments(docs=[], groupedby=groupby)
			grouped[groupby_val].docs.append(doc)
		return list(grouped.values())

	@component.output_types(nodes=List[GroupedDocuments], markdown_nodes=str)
	def run(self, embedding: List[float]):
		with GraphDatabase.driver(
			self.url, auth=(self.username, self.password)
		) as driver:
			with driver.session(database="neo4j") as session:
				nodes = session.execute_read(
					Neo4jGraphReader.query_nodes, embedding=embedding
				)
		grouped_docs = self.group_and_sort_nodes(nodes)

		grouped_nodes = Neo4jGraphReader.group_nodes(nodes)
		md_nodes = self.nodes_to_markdown(grouped_nodes)

		return {"grouped_docs": grouped_docs, "markdown_nodes": md_nodes}
