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


def get_db() -> chromadb.api.ClientAPI:
	host = os.getenv("CHROMADB_HOST", "chromadb-container")
	port = int(os.getenv("CHROMADB_PORT", "8000"))
	return chromadb.HttpClient(host=host, port=port)


def get_ollama_client() -> ollama.Client:
	host = os.getenv("OLLAMA_HOST", "ollama-container")
	port = os.getenv("OLLAMA_PORT", "11434")
	return ollama.Client(host=f"http://{host}:{port}")


@app.get("/list", summary="List collections in the vector database")
def list() -> Dict[str, Sequence[str]]:
	return {"collections": get_db().list_collections()}


@app.get("/query", summary="Query an LLM")
def query(
	q: str = Query(
		description="Prompt to query the LLM", example="Tell me an interesting fact"
	),
	m: str = Query(
		description="LLM model to query", example="tinyllama", default="tinyllama"
	),
) -> Dict[str, str]:
	response = get_ollama_client().generate(model=m, prompt=q)
	return {"query": q, "response": response.response}
