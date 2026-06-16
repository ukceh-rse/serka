import mimetypes
from haystack import component, Document
from typing import Dict, List, Any, Tuple
from neo4j import GraphDatabase

_BATCH_SIZE = 500


def _batched(lst: list, n: int):
	for i in range(0, len(lst), n):
		yield lst[i : i + n]


@component
class Neo4jGraphWriter:
	def __init__(
		self, host: str, port: int, username: str = "neo4j", password: str = "neo4j"
	):
		self.url = f"bolt://{host}:{port}"
		self.username = username
		self.password = password
		self._driver = GraphDatabase.driver(self.url, auth=(username, password))

	@staticmethod
	def _write_nodes(tx, node_type: str, batch: List[Dict[str, Any]]) -> int:
		result = tx.run(
			"UNWIND $nodes as node "
			f"MERGE (n:{node_type}:embedded {{uri: node.uri}}) "
			"SET n += node "
			"RETURN n",
			nodes=batch,
		)
		return len(result.data())

	@staticmethod
	def _write_text_chunk_nodes(tx, batch: List[Dict[str, Any]]) -> int:
		result = tx.run(
			"UNWIND $docs as doc "
			"MERGE (d:TextChunk:embedded {doc_id: doc.id}) "
			"SET d.content = doc.content, d.embedding = doc.embedding, d.field = doc.field "
			"RETURN d",
			docs=batch,
		)
		return len(result.data())

	@staticmethod
	def _write_assoc_relations(tx, batch: List[Tuple]) -> int:
		result = tx.run(
			"UNWIND $relations as rel "
			"MATCH (a:embedded {uri: rel[0]}), (b:embedded {uri: rel[1]}) "
			"MERGE (a)-[:ASSOCIATED_WITH {role: rel[2]}]->(b) "
			"RETURN count(*) AS created",
			relations=batch,
		)
		return result.data()[0]["created"]

	@staticmethod
	def _write_affiliated_relations(tx, batch: List[Tuple]) -> int:
		result = tx.run(
			"UNWIND $relations as rel "
			"MATCH (a:embedded {uri: rel[0]}), (b:embedded {uri: rel[1]}) "
			"MERGE (a)-[:AFFILIATED_WITH]->(b) "
			"RETURN count(*) AS created",
			relations=batch,
		)
		return result.data()[0]["created"]

	@staticmethod
	def _write_theme_relations(tx, batch: List[Tuple]) -> int:
		result = tx.run(
			"UNWIND $relations as rel "
			"MATCH (a:embedded {uri: rel[0]}), (b:embedded {uri: rel[1]}) "
			"MERGE (a)-[:HAS_THEME]->(b) "
			"RETURN count(*) AS created",
			relations=batch,
		)
		return result.data()[0]["created"]

	@staticmethod
	def _write_predicate_relations(tx, batch: List[Tuple]) -> int:
		# 3-tuples: (src_uri, predicate, tgt_uri). Target may not exist → MERGE placeholder.
		result = tx.run(
			"UNWIND $relations as rel "
			"MATCH (a:embedded {uri: rel[0]}) "
			"MERGE (b:embedded {uri: rel[2]}) "
			"MERGE (a)-[:RELATION {predicate: rel[1]}]->(b) "
			"RETURN count(*) AS created",
			relations=batch,
		)
		return result.data()[0]["created"]

	@staticmethod
	def _write_part_of_relations(tx, batch: List[Tuple]) -> int:
		result = tx.run(
			"UNWIND $relations as rel "
			"MATCH (a:TextChunk {doc_id: rel[0]}), (b:embedded {uri: rel[1]}) "
			"MERGE (a)-[:PART_OF]->(b) "
			"RETURN count(*) AS created",
			relations=batch,
		)
		return result.data()[0]["created"]

	@staticmethod
	def _write_field_relations(tx, rel_type: str, batch: List[Tuple]) -> int:
		result = tx.run(
			"UNWIND $relations as rel "
			f"MATCH (a:TextChunk {{doc_id: rel[0]}}), (b:embedded {{uri: rel[1]}}) "
			f"MERGE (a)-[:{rel_type}]->(b) "
			"RETURN count(*) AS created",
			relations=batch,
		)
		return result.data()[0]["created"]

	@staticmethod
	def _create_lookup_indexes(tx) -> None:
		tx.run("CREATE CONSTRAINT embedded_uri IF NOT EXISTS FOR (n:embedded) REQUIRE n.uri IS UNIQUE")
		tx.run("CREATE INDEX textchunk_doc_id IF NOT EXISTS FOR (n:TextChunk) ON (n.doc_id)")

	@staticmethod
	def _create_search_indexes(tx) -> None:
		tx.run("CREATE VECTOR INDEX vec_lookup IF NOT EXISTS FOR (n:embedded) ON n.embedding")
		tx.run(
			"CREATE FULLTEXT INDEX ft_search IF NOT EXISTS "
			"FOR (n:Dataset|TextChunk|Person|Organisation|Concept) ON EACH [n.title, n.content, n.name, n.label] "
			"OPTIONS {indexConfig: {`fulltext.analyzer`: 'english'}}"
		)

	@staticmethod
	def doc_to_dict(doc: Document) -> Dict[str, Any]:
		return {
			"id": doc.id,
			"content": doc.content,
			"field": doc.meta.get("field", ""),
			"uri": doc.meta.get("uri", ""),
			"filename": doc.meta.get("filename", ""),
			"embedding": doc.embedding,
		}

	@staticmethod
	def _supporting_doc_node(doc_dict: Dict[str, Any]) -> Dict[str, Any] | None:
		filename = doc_dict.get("filename", "")
		if not filename:
			return None
		mime_type, _ = mimetypes.guess_type(filename)
		return {
			"uri": f"{doc_dict['uri']}#{filename}",
			"title": filename,
			"format": mime_type or "application/octet-stream",
		}

	@component.output_types(
		nodes_created=Dict[str, int], relations_created=Dict[str, int]
	)
	def run(
		self,
		nodes: Dict[str, List[Dict[str, Any]]],
		relations: Dict[str, List[Tuple]],
		docs: List[Document],
	) -> Dict[str, Any]:
		docs_as_dicts = [self.doc_to_dict(doc) for doc in docs]

		supporting_docs = [d for d in docs_as_dicts if d["field"] == "SUPPORTING_DOC"]
		field_docs = [d for d in docs_as_dicts if d["field"] != "SUPPORTING_DOC"]

		# Document nodes from supporting file metadata (synthetic URIs)
		supp_doc_nodes = [n for d in supporting_docs if (n := self._supporting_doc_node(d))]
		# Citation Document nodes come through nodes["Document"] from extractors
		all_doc_nodes = list(
			{n["uri"]: n for n in supp_doc_nodes + nodes.get("Document", [])}.values()
		)

		with self._driver.session(database="neo4j") as session:
			# Phase 1: create lookup indexes before MERGE (idempotent)
			session.execute_write(Neo4jGraphWriter._create_lookup_indexes)

			# Phase 2: upsert nodes
			node_result: Dict[str, int] = {}
			for node_type, node_list in nodes.items():
				if node_type == "Document":
					continue  # handled below with supp_doc_nodes merged in
				unique = list({n["uri"]: n for n in node_list}.values())
				node_result[node_type] = sum(
					session.execute_write(Neo4jGraphWriter._write_nodes, node_type, batch)
					for batch in _batched(unique, _BATCH_SIZE)
				) if unique else 0

			node_result["Document"] = sum(
				session.execute_write(Neo4jGraphWriter._write_nodes, "Document", batch)
				for batch in _batched(all_doc_nodes, _BATCH_SIZE)
			) if all_doc_nodes else 0

			# TextChunk nodes (field docs + supporting docs)
			all_chunks = list({d["id"]: d for d in field_docs + supporting_docs}.values())
			node_result["TextChunk"] = sum(
				session.execute_write(Neo4jGraphWriter._write_text_chunk_nodes, batch)
				for batch in _batched(all_chunks, _BATCH_SIZE)
			) if all_chunks else 0

			# Phase 3: relationships
			relation_result: Dict[str, int] = {}

			if assoc := relations.get("ASSOCIATED_WITH"):
				unique = list({(r[0], r[1], r[2]): r for r in assoc}.values())
				relation_result["ASSOCIATED_WITH"] = sum(
					session.execute_write(Neo4jGraphWriter._write_assoc_relations, batch)
					for batch in _batched(unique, _BATCH_SIZE)
				)

			if affil := relations.get("AFFILIATED_WITH"):
				unique = list(set(affil))
				relation_result["AFFILIATED_WITH"] = sum(
					session.execute_write(Neo4jGraphWriter._write_affiliated_relations, batch)
					for batch in _batched(unique, _BATCH_SIZE)
				)

			if themes := relations.get("HAS_THEME"):
				unique = list(set(themes))
				relation_result["HAS_THEME"] = sum(
					session.execute_write(Neo4jGraphWriter._write_theme_relations, batch)
					for batch in _batched(unique, _BATCH_SIZE)
				)

			# RELATION — from extractor (dataset↔dataset, citations) + supporting docs
			supp_rels = [
				(d["uri"], "dcterms:references", f"{d['uri']}#{d['filename']}")
				for d in supporting_docs
				if d.get("filename")
			]
			all_predicate_rels = list(relations.get("RELATION", [])) + supp_rels
			if all_predicate_rels:
				unique = list({(r[0], r[1], r[2]): r for r in all_predicate_rels}.values())
				relation_result["RELATION"] = sum(
					session.execute_write(Neo4jGraphWriter._write_predicate_relations, batch)
					for batch in _batched(unique, _BATCH_SIZE)
				)

			# TextChunk → Document (PART_OF) for supporting docs
			part_of = [
				(d["id"], f"{d['uri']}#{d['filename']}")
				for d in supporting_docs
				if d.get("filename")
			]
			if part_of:
				unique = list(set(part_of))
				relation_result["PART_OF"] = sum(
					session.execute_write(Neo4jGraphWriter._write_part_of_relations, batch)
					for batch in _batched(unique, _BATCH_SIZE)
				)

			# TextChunk → Dataset field relations (DESCRIPTION_OF, LINEAGE_OF, etc.)
			field_rel_map: Dict[str, List[Tuple]] = {}
			for d in field_docs:
				rel_type = d["field"].upper() + "_OF"
				field_rel_map.setdefault(rel_type, []).append((d["id"], d["uri"]))
			for rel_type, rel_list in field_rel_map.items():
				unique = list(set(rel_list))
				relation_result[rel_type] = sum(
					session.execute_write(Neo4jGraphWriter._write_field_relations, rel_type, batch)
					for batch in _batched(unique, _BATCH_SIZE)
				)

			# Phase 4: build search indexes
			session.execute_write(Neo4jGraphWriter._create_search_indexes)

		return {"nodes_created": node_result, "relations_created": relation_result}
