import mimetypes
from haystack import component, Document
from typing import Dict, List, Any, Tuple
from neo4j import GraphDatabase

_BATCH_SIZE = 500

# Extractor node type -> Neo4j labels, where a type adds to another (a funder is an Organisation)
_NODE_LABELS: Dict[str, str] = {"FundingAgency": "Organisation:FundingAgency"}


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
		# MERGE on uri alone: the node may already exist as an unlabelled RELATION target
		# or under another type (an Organisation that is also a FundingAgency).
		labels = _NODE_LABELS.get(node_type, node_type)
		result = tx.run(
			"UNWIND $nodes as node "
			"MERGE (n:embedded {uri: node.uri}) "
			f"SET n:{labels} "
			"SET n += node "
			"RETURN count(*) AS written",
			nodes=batch,
		)
		return result.single()["written"]

	@staticmethod
	def _write_text_chunk_nodes(tx, batch: List[Dict[str, Any]]) -> int:
		result = tx.run(
			"UNWIND $docs as doc "
			"MERGE (d:TextChunk:embedded {doc_id: doc.id}) "
			"SET d.content = doc.content, d.embedding = doc.embedding, d.field = doc.field "
			"RETURN count(*) AS written",
			docs=batch,
		)
		return result.single()["written"]

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
	def _write_pair_relations(tx, rel_type: str, src: str, batch: List[Tuple]) -> int:
		# src matches rel[0], e.g. "embedded {uri: rel[0]}" or "TextChunk {doc_id: rel[0]}"
		result = tx.run(
			"UNWIND $relations as rel "
			f"MATCH (a:{src}), (b:embedded {{uri: rel[1]}}) "
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
			"FOR (n:Dataset|TextChunk|Person|Organisation|Concept|Grant) ON EACH [n.title, n.content, n.name, n.label] "
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
			"source_id": doc.meta.get("source_id", doc.id),
			"embedding": doc.embedding,
		}

	@staticmethod
	def _supporting_doc_uri(doc_dict: Dict[str, Any]) -> str:
		# Key on the splitter's source_id (parent file id, shared across a file's chunks)
		# so a file's chunks dedup to one DigitalManifestation node and same-named files stay distinct.
		return f"{doc_dict['uri']}#{doc_dict['source_id']}"

	@staticmethod
	def _supporting_doc_node(doc_dict: Dict[str, Any]) -> Dict[str, Any] | None:
		filename = doc_dict.get("filename", "")
		if not filename:
			return None
		mime_type, _ = mimetypes.guess_type(filename)
		return {
			"uri": Neo4jGraphWriter._supporting_doc_uri(doc_dict),
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

		# Supporting files without a filename get a TextChunk but no DigitalManifestation
		named_supporting_docs = [d for d in docs_as_dicts if d["field"] == "SUPPORTING_DOC" and d["filename"]]
		field_docs = [d for d in docs_as_dicts if d["field"] != "SUPPORTING_DOC"]

		# Supporting files have no bibliographic identity — DigitalManifestation (FRBR
		# embodiment level), not Document/fabio:Expression which is for citable works.
		all_nodes = {
			**nodes,
			"DigitalManifestation": [self._supporting_doc_node(d) for d in named_supporting_docs],
		}

		pair_relations: Dict[str, Tuple[str, List[Tuple]]] = {
			rel_type: ("embedded {uri: rel[0]}", relations.get(rel_type, []))
			for rel_type in ("AFFILIATED_WITH", "HAS_THEME", "BROADER")
		}
		# TextChunk → DigitalManifestation for supporting docs
		pair_relations["PART_OF"] = (
			"TextChunk {doc_id: rel[0]}",
			[(d["id"], self._supporting_doc_uri(d)) for d in named_supporting_docs],
		)
		# TextChunk → Dataset field relations (DESCRIPTION_OF, LINEAGE_OF, etc.)
		for d in field_docs:
			rel_type = d["field"].upper() + "_OF"
			pair_relations.setdefault(rel_type, ("TextChunk {doc_id: rel[0]}", []))[1].append((d["id"], d["uri"]))

		# RELATION — from extractor (dataset↔dataset, citations) + supporting docs
		predicate_rels = list(relations.get("RELATION", [])) + [
			(d["uri"], "dcterms:references", self._supporting_doc_uri(d)) for d in named_supporting_docs
		]

		with self._driver.session(database="neo4j") as session:
			def write_all(fn, items: list, *args) -> int:
				return sum(session.execute_write(fn, *args, batch) for batch in _batched(items, _BATCH_SIZE))

			# Phase 1: create lookup indexes before MERGE (idempotent)
			session.execute_write(Neo4jGraphWriter._create_lookup_indexes)

			# Phase 2: upsert nodes
			node_result: Dict[str, int] = {
				node_type: write_all(
					Neo4jGraphWriter._write_nodes, list({n["uri"]: n for n in node_list}.values()), node_type
				)
				for node_type, node_list in all_nodes.items()
			}
			# TextChunk nodes (field docs + supporting docs)
			node_result["TextChunk"] = write_all(
				Neo4jGraphWriter._write_text_chunk_nodes, list({d["id"]: d for d in docs_as_dicts}.values())
			)

			# Phase 3: relationships
			relation_result: Dict[str, int] = {}
			if assoc := relations.get("ASSOCIATED_WITH"):
				relation_result["ASSOCIATED_WITH"] = write_all(
					Neo4jGraphWriter._write_assoc_relations, list({tuple(r[:3]) for r in assoc})
				)
			if predicate_rels:
				relation_result["RELATION"] = write_all(
					Neo4jGraphWriter._write_predicate_relations, list({tuple(r[:3]) for r in predicate_rels})
				)
			for rel_type, (src, rels) in pair_relations.items():
				if rels:
					relation_result[rel_type] = write_all(
						Neo4jGraphWriter._write_pair_relations, list(set(rels)), rel_type, src
					)

			# Phase 4: build search indexes
			session.execute_write(Neo4jGraphWriter._create_search_indexes)

		return {"nodes_created": node_result, "relations_created": relation_result}
