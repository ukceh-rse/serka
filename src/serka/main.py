from fastapi import FastAPI, Query
from typing import Dict, Sequence, Any, List, Literal
from .dao import DAO
import yaml
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


def load_config():
	with open("config.yaml", "r") as f:
		return yaml.safe_load(f)


config = load_config()

app = FastAPI(
	title="Serka", description="An API for expose advanced search functionality"
)

_dao_instance: DAO | None = None


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
	return FileResponse("static/html/index.html")


def get_dao() -> DAO:
	global _dao_instance
	if _dao_instance is None:
		_dao_instance = DAO(
			ollama_host=config["ollama"]["host"],
			ollama_port=config["ollama"]["port"],
			chroma_host=config["chroma"]["host"],
			chroma_port=config["chroma"]["port"],
			default_embedding_model=config["ollama"]["embedding_models"][0],
			default_rag_model=config["ollama"]["rag_models"][0],
		)
	return _dao_instance


@app.get("/list", summary="List collections in the vector database")
def list() -> Dict[str, Sequence[str]]:
	return {"collections": get_dao().list_collections()}


@app.get("/peek", summary="Peek into a collection in the vector database")
def peek(
	collection: str = Query(
		description="Name of the collection to peek.",
		default=config["chroma"]["default_collection"],
	),
) -> Dict[str, Sequence[Dict[str, str]]]:
	return {"documents": get_dao().peek(collection)}


@app.get("/search", summary="Perform a semantic search in the vector database")
def semantic_search(
	q: str = Query(
		description="Query to perform the semantic search with.",
		examples=["Are there any pike in Windermere lake?"],
	),
	collection: str = Query(
		description="The name of the collection to query in the vector database.",
		default=config["chroma"]["default_collection"],
	),
	n: int = Query(
		description="Number of results to return.",
		default=10,
	),
) -> List[Dict[str, Any]]:
	return get_dao().query(collection, q, n)


@app.get("/fetch", summary="Fetch the latest metadata from the EIDC")
def fetch(
	url: str = Query(
		description="URL to fetch metadata from.",
		default=config["eidc"]["url"],
	),
	collection: str = Query(
		description="Name of the collection to store the fetched documents.",
		default=config["chroma"]["default_collection"],
	),
	source_type: Literal["eidc", "html"] = "eidc",
) -> Dict[str, Any]:
	return get_dao().insert(url, collection, source_type=source_type)


@app.get("/rag", summary="Perform a RAG query")
def rag(
	q: str = Query(
		description="Query to hand the RAG pipeline",
		examples=["Are there any pike in Windermere lake?"],
	),
	collection: str = Query(
		description="The name of the collection to query in the vector database.",
		default=config["chroma"]["default_collection"],
	),
) -> Dict[str, Any]:
	return get_dao().rag_query(collection, q)
