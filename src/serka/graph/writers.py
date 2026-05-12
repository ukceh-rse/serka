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

	@staticmethod
	def _write_nodes(tx, node_type: str, batch: List[Dict[str, Any]]) -> int:
		result = tx.run(
			"UNWIND $nodes as node "
			f"CREATE (n:{node_type}:embedded) "
			"SET n = node "
			"RETURN n",
			nodes=batch,
		)
		return len(result.data())

	@staticmethod
	def _write_doc_nodes(tx, batch: List[Dict[str, Any]]) -> int:
		result = tx.run(
			"UNWIND $docs as doc "
			"CREATE (d:TextChunk:embedded {doc_id: doc.id, content: doc.content, embedding: doc.embedding}) "
			"RETURN d",
			docs=batch,
		)
		return len(result.data())

	@staticmethod
	def _write_relations(tx, relation_type: str, batch: List[Tuple[str, str]]) -> int:
		result = tx.run(
			"UNWIND $relations as relation "
			f"MATCH (a:embedded {{uri: relation[0]}}), (b:embedded {{uri: relation[1]}}) "
			f"CREATE (a)-[:{relation_type}]->(b) "
			"RETURN count(*) AS created",
			relations=batch,
		)
		return result.data()[0]["created"]

	@staticmethod
	def _write_doc_relations(tx, relation_type: str, batch: List[Tuple[str, str]]) -> int:
		result = tx.run(
			"UNWIND $relations as relation "
			f"MATCH (a:TextChunk {{doc_id: relation[0]}}), (b:embedded {{uri: relation[1]}}) "
			f"CREATE (a)-[:{relation_type}]->(b) "
			"RETURN count(*) AS created",
			relations=batch,
		)
		return result.data()[0]["created"]

	@staticmethod
	def _unpack_doc_relations(docs: List[Dict[str, Any]]) -> Dict[str, List[Tuple[str, str]]]:
		relations: Dict[str, List[Tuple[str, str]]] = {}
		for doc in docs:
			rel_type = str(doc.get("field", "")).upper() + "_OF"
			relations.setdefault(rel_type, []).append((doc["id"], doc["uri"]))
		return relations

	@staticmethod
	def _create_lookup_indexes(tx) -> None:
		tx.run("CREATE CONSTRAINT embedded_uri IF NOT EXISTS FOR (n:embedded) REQUIRE n.uri IS UNIQUE")
		tx.run("CREATE INDEX textchunk_doc_id IF NOT EXISTS FOR (n:TextChunk) ON (n.doc_id)")

	@staticmethod
	def _create_search_indexes(tx) -> None:
		tx.run("CREATE VECTOR INDEX vec_lookup IF NOT EXISTS FOR (n:embedded) ON n.embedding")
		tx.run(
			"CREATE FULLTEXT INDEX ft_search IF NOT EXISTS "
			"FOR (n:Dataset|TextChunk|Person|Organisation) ON EACH [n.title, n.content, n.name] "
			"OPTIONS {indexConfig: {`fulltext.analyzer`: 'english'}}"
		)

	@staticmethod
	def doc_to_dict(doc: Document) -> Dict[str, Any]:
		return {
			"id": doc.id,
			"content": doc.content,
			"field": doc.meta.get("field", ""),
			"uri": doc.meta.get("uri", ""),
			"embedding": doc.embedding,
		}

	@component.output_types(
		nodes_created=Dict[str, int], relations_created=Dict[str, int]
	)
	def run(
		self,
		nodes: Dict[str, List[Dict[str, Any]]],
		relations: Dict[str, List[Tuple[str, str]]],
		docs: List[Document],
	) -> Dict[str, Any]:
		docs_as_dicts = [self.doc_to_dict(doc) for doc in docs]

		with GraphDatabase.driver(self.url, auth=(self.username, self.password)) as driver:
			with driver.session(database="neo4j") as session:

				# Phase 1: bulk-create nodes in batches
				node_result: Dict[str, int] = {}
				for node_type, node_list in nodes.items():
					unique = list({n["uri"]: n for n in node_list}.values())
					node_result[node_type] = sum(
						session.execute_write(Neo4jGraphWriter._write_nodes, node_type, batch)
						for batch in _batched(unique, _BATCH_SIZE)
					)

				unique_docs = list({d["id"]: d for d in docs_as_dicts}.values())
				node_result["Document"] = sum(
					session.execute_write(Neo4jGraphWriter._write_doc_nodes, batch)
					for batch in _batched(unique_docs, _BATCH_SIZE)
				)

				# Phase 2: lookup indexes before relationship MATCH
				session.execute_write(Neo4jGraphWriter._create_lookup_indexes)

				# Phase 3: create relationships in batches
				relation_result: Dict[str, int] = {}
				for relation_type, relation_list in relations.items():
					unique = list({(r[0], r[1]): r for r in relation_list}.values())
					relation_result[relation_type] = sum(
						session.execute_write(Neo4jGraphWriter._write_relations, relation_type, batch)
						for batch in _batched(unique, _BATCH_SIZE)
					)

				for rel_type, rel_list in Neo4jGraphWriter._unpack_doc_relations(docs_as_dicts).items():
					unique = list({(r[0], r[1]): r for r in rel_list}.values())
					relation_result[rel_type] = sum(
						session.execute_write(Neo4jGraphWriter._write_doc_relations, rel_type, batch)
						for batch in _batched(unique, _BATCH_SIZE)
					)

				# Phase 4: build search indexes over the completed dataset
				session.execute_write(Neo4jGraphWriter._create_search_indexes)

		return {"nodes_created": node_result, "relations_created": relation_result}
