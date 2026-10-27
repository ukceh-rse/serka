"""End-to-end smoke test for Serka.

Starts a throwaway Neo4j container, ingests the datasets listed in
tests/smoke/datasets.txt (EIDC + Legilo, via scripts/ingest-data.py), starts the
MCP server and the Serka API locally, then runs a few basic queries.

Requires podman (or docker), AWS credentials for Bedrock, and a .env file with
Legilo credentials. Your normal Neo4j data is not touched.

	uv run scripts/smoke-test.py
"""

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
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent.parent
IDS_FILE = ROOT / "tests" / "smoke" / "datasets.txt"

CONTAINER = "serka-smoke-neo4j"
NEO4J_PASSWORD = "serka-smoke-test"
NEO4J_PORT = 17687
MCP_PORT = 8000  # hard-coded in mcp-server/src/serka-mcp/main.py
API_PORT = 19000
API = f"http://localhost:{API_PORT}"

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


def search(q: str) -> list:
	r = httpx.get(f"{API}/v1/query/semantic", params={"q": q, "return_type": "Dataset"}, timeout=120)
	r.raise_for_status()
	return r.json()


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

	answer = chat(CHAT_QUESTION)
	log(f"chat answer: {answer.strip()}")
	check("chat answers pike question", all(w in answer.lower() for w in CHAT_EXPECTED), answer)

	return failures


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
