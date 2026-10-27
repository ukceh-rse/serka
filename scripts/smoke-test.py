"""End-to-end smoke test for Serka.

Starts a throwaway Neo4j container, ingests the datasets listed in
tests/smoke/datasets.txt (EIDC + Legilo, via scripts/ingest-data.py), starts the
MCP server and the Serka API locally, then runs a few basic queries.

Requires podman (or docker), AWS credentials for Bedrock, and a .env file with
Legilo credentials. Your normal Neo4j data is not touched.

	uv run scripts/smoke-test.py
"""

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from fastmcp import Client
from neo4j import GraphDatabase
from pyld import jsonld

ROOT = Path(__file__).resolve().parent.parent
IDS_FILE = ROOT / "tests" / "smoke" / "datasets.txt"

CONTAINER = "serka-smoke-neo4j"
NEO4J_PASSWORD = "serka-smoke-test"
NEO4J_PORT = 17687
MCP_PORT = 8000  # hard-coded in mcp-server/src/serka-mcp/main.py
API_PORT = 19000
API = f"http://localhost:{API_PORT}"
MCP = f"http://localhost:{MCP_PORT}/mcp"

# API return_type value -> DOO @type it should yield
RETURN_TYPES = {
	"Dataset": "dcat:Dataset",
	"Person": "foaf:Person",
	"Organisation": "foaf:Organization",
	"FundingAgency": "frapo:FundingAgency",
	"Grant": "frapo:Grant",
	"Concept": "skos:Concept",
	"Document": "fabio:Expression",
	"DigitalManifestation": "fabio:DigitalManifestation",
}
ORPHAN_TOKEN = "smokeorphanquokka"

# (query, substring expected in the title of one of the top 3 datasets)
SEARCH_CASES = [
	("pike eggs in Windermere", "pike"),
	("telomere length in Seychelles warblers", "Seychelles Warbler"),
	("coral bleaching at high temperature", "Coral bleaching"),
	("radioactive contamination at Chernobyl", "Chernobyl"),
	("oak gall wasps", "galls"),
	("antibiotic resistance in cattle", "antibiotic"),
	("raspberry pollination", "raspberry"),
	("urban weather in West Africa", "Ouagadougou"),
]
CHAT_QUESTION = "Is there a dataset about pike in Windermere? Answer in one short sentence and give its title."
CHAT_EXPECTED = ["pike", "windermere"]


def log(msg: str) -> None:
	print(f"[smoke] {msg}", flush=True)


def port_free(port: int) -> bool:
	with socket.socket() as s:
		return s.connect_ex(("localhost", port)) != 0


def wait_for(check, what: str, timeout: float = 120) -> None:
	deadline = time.time() + timeout
	while time.time() < deadline:
		try:
			if check():
				return
		except Exception:
			pass
		time.sleep(2)
	raise RuntimeError(f"Timed out waiting for {what}")


def start_neo4j(runtime: str) -> None:
	subprocess.run([runtime, "rm", "-f", CONTAINER], capture_output=True)
	subprocess.run(
		[
			runtime, "run", "-d", "--rm", "--name", CONTAINER,
			"-p", f"{NEO4J_PORT}:7687",
			"-e", f"NEO4J_AUTH=neo4j/{NEO4J_PASSWORD}",
			"-e", 'NEO4J_PLUGINS=["apoc"]',
			"docker.io/library/neo4j:5.26.5",
		],
		check=True,
	)

	def ready() -> bool:
		with GraphDatabase.driver(f"bolt://localhost:{NEO4J_PORT}", auth=("neo4j", NEO4J_PASSWORD)) as d:
			d.verify_connectivity()
		return True

	wait_for(ready, "Neo4j", timeout=180)


def search(q: str, **params) -> list:
	r = search_raw(q, **{"return_type": "Dataset", **params})
	r.raise_for_status()
	return r.json()


def search_raw(q: str, **params) -> httpx.Response:
	return httpx.get(f"{API}/v1/query/semantic", params={"q": q, **params}, timeout=120)


def mcp(fn):
	"""Run `fn(client)` against the MCP server and return its result."""

	async def _run():
		async with Client(MCP) as client:
			return await fn(client)

	return asyncio.run(_run())


def mcp_call(tool: str, args: dict | None = None):
	"""Call a tool without raising on tool errors; returns the CallToolResult."""
	return mcp(lambda c: c.call_tool(tool, args or {}, raise_on_error=False))


def mcp_data(tool: str, args: dict | None = None) -> dict:
	"""A tool's structured (JSON-LD) result; an error result yields {}."""
	result = mcp_call(tool, args)
	return {} if result.is_error else result.structured_content


def graph_query(cypher: str, **params) -> list[dict]:
	with GraphDatabase.driver(f"bolt://localhost:{NEO4J_PORT}", auth=("neo4j", NEO4J_PASSWORD)) as d:
		records, _, _ = d.execute_query(cypher, **params)
	return [r.data() for r in records]


def chat(message: str) -> str:
	text = []
	with httpx.stream("POST", f"{API}/v1/chat/stream", json={"message": message}, timeout=300) as r:
		r.raise_for_status()
		for line in r.iter_lines():
			if not line.startswith("data:"):
				continue
			event = json.loads(line[5:])
			if event.get("type") == "TEXT_MESSAGE_CONTENT":
				text.append(event.get("delta", ""))
			elif event.get("type") == "RUN_ERROR":
				raise RuntimeError(event.get("message"))
	return "".join(text)


def run_tests() -> list[str]:
	failures = []

	def check(name: str, ok: bool, detail: str = "") -> None:
		log(f"{'PASS' if ok else 'FAIL'}  {name}{'  -- ' + detail if detail and not ok else ''}")
		if not ok:
			failures.append(name)

	r = httpx.get(f"{API}/health", timeout=10)
	check("health endpoint", r.status_code == 200 and r.json().get("status") == "ok", r.text)

	with GraphDatabase.driver(f"bolt://localhost:{NEO4J_PORT}", auth=("neo4j", NEO4J_PASSWORD)) as d:
		records, _, _ = d.execute_query("MATCH (n:Dataset) RETURN count(n) AS n")
		n_datasets = records[0]["n"]
		records, _, _ = d.execute_query("MATCH (n:DigitalManifestation) RETURN count(n) AS n")
		n_docs = records[0]["n"]
	check("10 datasets ingested", n_datasets == 10, f"found {n_datasets}")
	check("Legilo supporting documents ingested", n_docs > 0, f"found {n_docs}")

	for q, expected in SEARCH_CASES:
		hits = search(q)
		titles = [h["entity"].get("label") or "" for h in hits[:3]]
		check(
			f"search '{q}' finds '{expected}'",
			any(expected.lower() in t.lower() for t in titles),
			f"top 3: {titles}",
		)

	run_doo_tests(check)
	run_ontology_tests(check)

	answer = chat(CHAT_QUESTION)
	log(f"chat answer: {answer.strip()}")
	check("chat answers pike question", all(w in answer.lower() for w in CHAT_EXPECTED), answer)

	return failures


def run_doo_tests(check) -> None:
	"""Checks for the DOO search/ingestion behaviour (see CODE_REVIEW_TODO.md)."""
	with GraphDatabase.driver(f"bolt://localhost:{NEO4J_PORT}", auth=("neo4j", NEO4J_PASSWORD)) as d:
		# Supporting files are keyed on their source file id, not their (possibly shared) filename.
		records, _, _ = d.execute_query(
			"MATCH (ds:Dataset)-[:RELATION]->(m:DigitalManifestation) "
			"WHERE m.uri = ds.uri + '#' + m.title RETURN count(m) AS n"
		)
		check("supporting doc URIs not keyed on filename", records[0]["n"] == 0, f"{records[0]['n']} keyed on filename")
		records, _, _ = d.execute_query(
			"MATCH (ds:Dataset)-[:RELATION]->(:DigitalManifestation)<-[:PART_OF]-(t:TextChunk) "
			"RETURN ds.uri AS uri, t.content AS content LIMIT 1"
		)
		supp = records[0] if records else None
		# An orphan chunk (no non-TextChunk neighbour) should still be returned as a hit.
		d.execute_query(
			"MERGE (t:TextChunk:embedded {doc_id: 'smoke-orphan'}) SET t.content = $c, t.field = 'text'",
			c=f"{ORPHAN_TOKEN} orphan chunk with no parent entity",
		)

	# return_type: every API value works and yields entities of the matching DOO type
	for rt, doo_type in RETURN_TYPES.items():
		r = search_raw("pike in Windermere", return_type=rt)
		hits = r.json() if r.status_code == 200 else []
		check(
			f"return_type={rt} yields only {doo_type}",
			r.status_code == 200 and all(doo_type in h["entity"]["@type"] for h in hits),
			f"status {r.status_code}: {r.text[:200]}",
		)

	# Date filters constrain datasets without dropping other entity types
	hits = search("pike in Windermere", return_type="Person", published_after="1900-01-01")
	check("date filter keeps Person results", len(hits) > 0, "no people returned")
	hits = search("pike in Windermere", published_after="2100-01-01")
	check("date filter excludes datasets", hits == [], f"{len(hits)} datasets returned")

	# Location filter: unknown places are reported, not silently ignored
	r = search_raw("pike", return_type="Dataset", location="Xyzzyqwv Nowhereshire")
	check("unknown location returns 422", r.status_code == 422, f"status {r.status_code}")
	r = search_raw("pike", return_type="Dataset", location="Windermere")
	check("known location filters search", r.status_code == 200 and len(r.json()) > 0, f"status {r.status_code}: {r.text[:200]}")

	# Contributor roles always map to a prefixed DOO role term
	hits = search("pike in Windermere", return_type="Person")
	preds = [step["predicate"] for h in hits for step in h.get("path", [])]
	check("contributor roles are DOO terms", all(":" in p for p in preds), f"predicates: {preds}")

	res = mcp_call("search", {"query": "pike", "return_type": "foaf:Persn"})
	check("unknown return_type is a tool error", res.is_error and "Unknown return_type" in res.content[0].text, str(res)[:200])

	hits = mcp_data("search", {"query": "data", "limit": 3}).get("@graph", [])
	check("search respects limit", 0 < len(hits) <= 3, f"{len(hits)} hits")

	hits = mcp_data("search", {"query": ORPHAN_TOKEN}).get("@graph", [])
	check(
		"orphan TextChunk returned as hit",
		any(ORPHAN_TOKEN in (h.get("excerpt") or "") for h in hits),
		str(hits)[:200],
	)

	res = mcp_data("search", {"query": "data", "return_type": "dcat:Dataset", "min_citations": 10**6})
	check("min_citations excludes datasets", res.get("@graph") == [], str(res)[:200])
	hits = mcp_data("search", {"query": "data", "return_type": "dcat:Dataset", "min_citations": 1}).get("@graph")
	check(
		"min_citations keeps cited datasets",
		hits is not None and all((h["entity"].get("citations") or 0) >= 1 for h in hits),
		str(hits)[:200],
	)

	if supp is None:
		check("get_content includes supporting docs", False, "no supporting doc chunks in graph")
	else:
		res = mcp_call("get_content", {"uri": supp["uri"]})
		content = "" if res.is_error else res.content[0].text
		check("get_content includes supporting docs", supp["content"] in content, content[:200])


WINDERMERE = "https://catalogue.ceh.ac.uk/id/4b255fc4-33d3-4beb-a238-37e1a8cf32a2"
CHERNOBYL = "https://catalogue.ceh.ac.uk/id/ae02f4e8-9486-4b47-93ef-e49dd9ddecd4"
CHERNOBYL_PARENT = "https://catalogue.ceh.ac.uk/id/3124e313-7ce8-4832-98b4-2357fab9284c"
NERC = "https://ror.org/02b5d8509"
DCAT = "http://www.w3.org/ns/dcat#"
MAPPING = json.loads((ROOT / "mcp-server" / "src" / "serka-mcp" / "doo_mapping.json").read_text())


def run_ontology_tests(check) -> None:
	"""Checks for DOO conformance of ingestion and the MCP tools (doo_review_and_mcp_recommendations.md)."""
	count = lambda cypher, **kw: graph_query(cypher, **kw)[0]["n"]

	# --- ingestion: fields that were previously dropped -------------------------------------
	n = count(
		"MATCH (:Dataset {uri: $uri})-[r:RELATION {predicate: 'dcterms:isPartOf'}]->({uri: $parent}) RETURN count(r) AS n",
		uri=CHERNOBYL, parent=CHERNOBYL_PARENT,
	)
	check("dataset relationships ingested as CURIE predicates", n == 1, f"{n} isPartOf edges")
	n = count("MATCH ()-[r:RELATION]->() WHERE r.predicate STARTS WITH 'http' RETURN count(r) AS n")
	check("no full-IRI relation predicates", n == 0, f"{n} edges")
	for role in ("pointOfContact", "rightsHolder"):
		n = count("MATCH (:Dataset)-[r:ASSOCIATED_WITH {role: $role}]->() RETURN count(r) AS n", role=role)
		check(f"{role} associations ingested", n > 0, "none")
	n = count(
		"MATCH (:Dataset {uri: $uri})-[:HAS_THEME]->(c:Concept {label: 'Radioecology'}) RETURN count(c) AS n", uri=CHERNOBYL
	)
	check("keywordsTheme concepts ingested", n == 1, f"{n} Radioecology themes")
	n = count(
		"MATCH (d:Dataset)-[:ASSOCIATED_WITH {role: 'author'}]->(p:Person)-[:AFFILIATED_WITH]->(o:Organisation), "
		"(d)-[:ASSOCIATED_WITH {role: 'author'}]->(o) RETURN count(o) AS n"
	)
	check("organisations don't inherit their members' author role", n == 0, f"{n} organisations credited as author")

	# --- ingestion: funding (frapo) and concept hierarchy (skos:broader) ---------------------
	n = count("MATCH (d:Dataset)-[:RELATION {predicate: 'doo:originatingGrant'}]->(:Grant) RETURN count(DISTINCT d) AS n")
	check("datasets linked to their grants", n == 6, f"{n} datasets with grants")
	n = count(
		"MATCH (f:Organisation:FundingAgency {uri: $nerc})-[:RELATION {predicate: 'frapo:awards'}]->(g:Grant) "
		"RETURN count(g) AS n",
		nerc=NERC,
	)
	check("NERC is a FundingAgency awarding the grants", n == 7, f"{n} grants awarded by NERC")
	n = count("MATCH (:Concept)-[r:BROADER]->(:Concept) RETURN count(r) AS n")
	check("GEMET broader hierarchy ingested", n > 0, "no BROADER edges")

	# --- MCP: server metadata and schemas ----------------------------------------------------
	init = mcp(lambda c: asyncio.sleep(0, c.initialize_result))
	check("server instructions describe DOO", "Digital Objects Ontology" in (init.instructions or ""), str(init.instructions)[:200])
	tools = {t.name: t for t in mcp(lambda c: c.list_tools())}
	jsonld_tools = ["search", "get_entity", "get_relations", "get_contributors", "find_by_contributor", "list_datasets"]
	check(
		"JSON-LD tools declare @context/@graph output schemas",
		all({"@context", "@graph"} <= set((tools[t].outputSchema or {}).get("properties", {})) for t in jsonld_tools),
		str({t: list((tools[t].outputSchema or {}).get("properties", {})) for t in jsonld_tools}),
	)
	entity_schemas = tools["search"].outputSchema["properties"]["@graph"]["items"]["properties"]["entity"]["anyOf"]
	check(
		"output schema annotates entity classes",
		{"dcat:Dataset", "foaf:Person", "frapo:Grant"} <= {o.get("x-rdf-type") for o in entity_schemas},
		str([o.get("x-rdf-type") for o in entity_schemas]),
	)

	# --- MCP: search output is JSON-LD with resource links ------------------------------------
	res = mcp_call("search", {"query": "pike in Windermere", "return_type": "dcat:Dataset", "limit": 5})
	data = res.structured_content or {}
	hits = data.get("@graph", [])
	check("search returns @context and typed @graph", bool(hits) and "@context" in data and all(
		h["entity"].get("@id") and h["entity"].get("@type") == ["dcat:Dataset"] for h in hits
	), str(data)[:300])
	check("search text content mirrors structured content", json.loads(res.content[0].text) == data)
	links = {str(c.uri) for c in res.content if c.type == "resource_link"}
	check("search links each hit as a doo://entity resource", {f"doo://entity/{h['entity']['@id']}" for h in hits} <= links, str(links))
	try:
		expanded = jsonld.expand(data)
		types = {t for hit in expanded[0]["@graph"] for t in hit["urn:serka:entity"][0]["@type"]}
		check("search output expands to DOO IRIs", types == {f"{DCAT}Dataset"}, str(types))
	except Exception as e:
		check("search output expands to DOO IRIs", False, repr(e))

	contents = mcp(lambda c: c.read_resource(f"doo://entity/{WINDERMERE}"))
	doc = json.loads(contents[0].text)
	check(
		"doo://entity resource is a JSON-LD document",
		doc.get("@id") == WINDERMERE and "@context" in doc and contents[0].mimeType == "application/ld+json",
		f"{contents[0].mimeType}: {contents[0].text[:200]}",
	)

	# --- MCP: discovery ------------------------------------------------------------------------
	desc = mcp_data("describe_ontology")
	types = {t["curie"]: t["count"] for t in desc.get("types", [])}
	predicates = {t["curie"]: t["count"] for t in desc.get("predicates", [])}
	roles = {t["curie"]: t["count"] for t in desc.get("roles", [])}
	check("describe_ontology counts datasets", types.get("dcat:Dataset") == 10, str(types))
	check(
		"describe_ontology counts grants, hierarchy and roles",
		types.get("frapo:Grant", 0) > 0 and predicates.get("skos:broader", 0) > 0 and roles.get("pro:author", 0) > 0,
		f"{types} {predicates} {roles}",
	)

	# --- MCP: DOO role pattern -----------------------------------------------------------------
	attributions = mcp_data("get_contributors", {"dataset_uri": WINDERMERE}).get("@graph", [])
	check(
		"contributor roles are DOO role individuals with their class",
		bool(attributions) and all(
			a["@type"] == "pro:RoleInTime" and MAPPING["role_classes"].get(a["role"]) == a["role_type"] for a in attributions
		),
		str([(a["role"], a["role_type"]) for a in attributions]),
	)
	check(
		"Windermere roles include author, curator and contact",
		{"pro:author", "scoro:data-curator", "scoro:contact-person"} <= {a["role"] for a in attributions},
		str({a["role"] for a in attributions}),
	)
	data_roles = mcp_data("get_contributors", {"dataset_uri": WINDERMERE, "role": "scoro:DataRole"}).get("@graph", [])
	check(
		"role class filter returns only roles of that class",
		bool(data_roles) and all(a["role_type"] == "scoro:DataRole" for a in data_roles),
		str([a["role"] for a in data_roles]),
	)
	author = next((a["agent"]["@id"] for a in attributions if a["role"] == "pro:author"), None)
	found = mcp_data("find_by_contributor", {"agent_uri": author or "", "role": "pro:PublishingRole"}).get("@graph", [])
	check("find_by_contributor filters by role class", WINDERMERE in {e["@id"] for e in found}, str(found)[:200])

	# --- MCP: relations, funding and theme expansion -------------------------------------------
	rels = mcp_data("get_relations", {"uri": CHERNOBYL, "predicate": "dcterms:isPartOf"}).get("@graph", [])
	check("get_relations follows dcterms:isPartOf", [r["target"]["@id"] for r in rels] == [CHERNOBYL_PARENT], str(rels)[:200])
	[grant] = graph_query("MATCH (d:Dataset)-[:RELATION {predicate: 'doo:originatingGrant'}]->(g:Grant) RETURN g.uri AS uri LIMIT 1")
	funded = mcp_data("get_relations", {"uri": grant["uri"], "direction": "incoming", "predicate": "doo:originatingGrant"})
	check(
		"grants lead back to the datasets they funded",
		any("dcat:Dataset" in r["target"]["@type"] for r in funded.get("@graph", [])),
		str(funded)[:200],
	)
	hits = mcp_data("search", {"query": "South Asian Nitrogen Hub", "return_type": "frapo:Grant"}).get("@graph", [])
	check(
		"search finds grants by award title",
		any("Nitrogen" in (h["entity"].get("title") or "") for h in hits),
		str([h["entity"].get("title") for h in hits]),
	)

	rows = graph_query(
		"MATCH (d:Dataset)-[:HAS_THEME]->(c:Concept)-[:BROADER]->(p:Concept) "
		"RETURN d.uri AS dataset, d.title AS title, p.uri AS broader LIMIT 1"
	)
	if not rows:
		check("theme filter expands broader concepts", False, "no dataset theme with a broader concept")
	else:
		row = rows[0]
		res = mcp_data("search", {"query": row["title"], "return_type": "dcat:Dataset", "theme": row["broader"]})
		expansion = (res.get("meta") or {}).get("theme_expansion") or {}
		check(
			"theme filter expands broader concepts",
			row["dataset"] in {h["entity"]["@id"] for h in res.get("@graph", [])} and expansion.get(row["broader"], 0) > 1,
			f"expansion {expansion}, hits {[h['entity']['@id'] for h in res.get('@graph', [])]}",
		)
	res = mcp_call("search", {"query": "pike", "theme": "no such theme zzz"})
	check("unknown theme is a tool error", res.is_error and "Unknown theme" in res.content[0].text, str(res)[:200])

	res = mcp_data("search", {
		"query": "pike", "return_type": "foaf:Person",
		"bounding_box": {"south": 54.0, "north": 54.6, "west": -3.2, "east": -2.7},
	})
	check("search meta warns about dataset-only filters", any("bounding_box" in w for w in res["meta"]["warnings"]), str(res.get("meta")))

	# --- API: new return types --------------------------------------------------------------------
	r = search_raw("South Asian Nitrogen Hub", return_type="Grant")
	check(
		"API return_type=Grant yields grants",
		r.status_code == 200 and len(r.json()) > 0 and all("frapo:Grant" in h["entity"]["@type"] for h in r.json()),
		f"status {r.status_code}: {r.text[:200]}",
	)


def main() -> int:
	runtime = shutil.which("podman") or shutil.which("docker")
	if not runtime:
		log("podman or docker is required")
		return 1
	for port in (NEO4J_PORT, MCP_PORT, API_PORT):
		if not port_free(port):
			log(f"port {port} is already in use; stop whatever is using it and retry")
			return 1

	logs = Path(tempfile.mkdtemp(prefix="serka-smoke-"))
	env = {
		**os.environ,
		"NEO4J_HOST": "localhost",
		"NEO4J_PORT": str(NEO4J_PORT),
		"NEO4J_USERNAME": "neo4j",
		"NEO4J_PASSWORD": NEO4J_PASSWORD,
		"MCP_HOST": "localhost",
		"MCP_PORT": str(MCP_PORT),
		"FEEDBACK_LOG_PATH": str(logs / "feedback.jsonl"),
	}
	procs: list[subprocess.Popen] = []
	try:
		log(f"starting Neo4j container ({runtime})")
		start_neo4j(runtime)

		log(f"ingesting datasets from {IDS_FILE.relative_to(ROOT)}")
		subprocess.run(
			["uv", "run", "scripts/ingest-data.py", "--ids-file", str(IDS_FILE)],
			cwd=ROOT, env=env, check=True,
		)

		log(f"starting MCP server and Serka API (logs in {logs})")
		procs.append(subprocess.Popen(
			["uv", "run", "python", "mcp-server/src/serka-mcp/main.py"],
			cwd=ROOT, env=env, stdout=open(logs / "mcp.log", "w"), stderr=subprocess.STDOUT,
		))
		procs.append(subprocess.Popen(
			["uv", "run", "fastapi", "run", "src/serka/main.py", "--port", str(API_PORT)],
			cwd=ROOT, env=env, stdout=open(logs / "serka.log", "w"), stderr=subprocess.STDOUT,
		))
		wait_for(lambda: not port_free(MCP_PORT), "MCP server", timeout=180)
		wait_for(lambda: httpx.get(f"{API}/health").status_code == 200, "Serka API")

		failures = run_tests()
	finally:
		for p in procs:
			p.terminate()
			try:
				p.wait(timeout=10)
			except subprocess.TimeoutExpired:
				p.kill()
		subprocess.run([runtime, "rm", "-f", CONTAINER], capture_output=True)

	if failures:
		log(f"{len(failures)} check(s) failed; logs in {logs}")
		return 1
	log("all checks passed")
	return 0


if __name__ == "__main__":
	sys.exit(main())
