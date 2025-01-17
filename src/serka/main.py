import chromadb.api
from fastapi import FastAPI, Query
import chromadb
import ollama
from typing import Dict, Sequence
from dotenv import load_dotenv
import os


load_dotenv()

app = FastAPI(
	title="Serka", description="An API for expose advanced search functionality"
)

_db_instance: chromadb.api.ClientAPI | None = None
_ollama_isntance: ollama.Client | None = None


def get_db() -> chromadb.api.ClientAPI:
	global _db_instance
	if _db_instance is None:
		host = os.getenv("CHROMADB_HOST", "chromadb-container")
		port = int(os.getenv("CHROMADB_PORT", "8000"))
		_db_instance = chromadb.HttpClient(host=host, port=port)
	return _db_instance


def get_ollama_client() -> ollama.Client:
	global _ollama_isntance
	if _ollama_isntance is None:
		host = os.getenv("OLLAMA_HOST", "ollama-container")
		port = os.getenv("OLLAMA_PORT", "11434")
		_ollama_isntance = ollama.Client(host=f"http://{host}:{port}")
	return _ollama_isntance


@app.get("/list", summary="List collections in the vector database")
def list() -> Dict[str, Sequence[str]]:
	return {"collections": get_db().list_collections()}


@app.get("/query", summary="Query an LLM")
def query(
	q: str = Query(
		description="Prompt to query the LLM",
		examples=["Tell me an interesting fact about the environment."],
	),
	m: str = Query(
		description="LLM model to query",
		examples=["tinyllama"],
		default=os.getenv("OLLAMA_MODEL", "tinyllama"),
	),
) -> Dict[str, str]:
	response = get_ollama_client().generate(model=m, prompt=q)
	return {"query": q, "response": response.response}
