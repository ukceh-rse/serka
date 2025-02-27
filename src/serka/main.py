from fastapi import FastAPI, Query, Depends
from typing import Dict, Sequence, Any, List, Literal
from .dao import DAO
import yaml
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .models import Config, TaskStatus
from .feedback import FeedbackLogger
from fastapi import BackgroundTasks
import uuid
from fastapi import HTTPException

tasks: Dict[str, TaskStatus] = {}


def load_config():
	with open("config.yaml", "r") as f:
		config_data = yaml.safe_load(f)
	return Config(**config_data)


config = load_config()

app = FastAPI(
	title="Serka", description="An API for expose advanced search functionality"
)

dao_instance = DAO(
	ollama_host=config.ollama.host,
	ollama_port=config.ollama.port,
	chroma_host=config.chroma.host,
	chroma_port=config.chroma.port,
	default_embedding_model=config.embedding_models[0],
	default_rag_model=config.rag_models[0],
)

feedback_loggger = FeedbackLogger(config.mongo.host, config.mongo.port)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
	return FileResponse("static/html/index.html")


def get_dao() -> DAO:
	return dao_instance


@app.get("/list", summary="List collections in the vector database")
def list() -> Dict[str, Sequence[str]]:
	return {"collections": get_dao().list_collections()}


@app.get("/peek", summary="Peek into a collection in the vector database")
def peek(
	collection: str = Query(
		description="Name of the collection to peek.",
		default=config.default_collection,
	),
	dao: DAO = Depends(get_dao),
) -> Dict[str, Sequence[Dict[str, str]]]:
	return {"documents": dao.peek(collection)}


@app.get("/search", summary="Perform a semantic search in the vector database")
def semantic_search(
	q: str = Query(
		description="Query to perform the semantic search with.",
		examples=["Are there any pike in Windermere lake?"],
	),
	collection: str = Query(
		description="The name of the collection to query in the vector database.",
		default=config.default_collection,
	),
	n: int = Query(
		description="Number of results to return.",
		default=20,
	),
	dao: DAO = Depends(get_dao),
) -> List[Dict[str, Any]]:
	feedback_loggger.log_feedback(
		{"query": q, "collection": collection, "type": "semantic_search"}
	)
	return dao.query(collection, q, n)


@app.get("/scrape", summary="Submit a task to asynchronously scrape from a source URL")
async def scrape(
	background_tasks: BackgroundTasks,
	url: str = Query(
		description="URL to fetch data from / start scraping from.",
		default=config.collections[config.default_collection].url,
	),
	collection: str = Query(
		description="Name of the collection to store the fetched documents.",
		default=config.default_collection,
	),
	source_type: Literal["eidc", "html"] = "eidc",
	dao: DAO = Depends(get_dao),
) -> TaskStatus:
	id = str(uuid.uuid4())
	task = TaskStatus(id=id, status="pending")
	tasks[id] = task

	def scrape_task():
		try:
			tasks[id].status = "running"
			result = dao.insert(
				url,
				collection,
				source_type=source_type,
				unified_metadata=config.unified_metadata,
			)
			tasks[id].status = "complete"
			tasks[id].result = result
		except Exception as e:
			tasks[id].status = "failed"
			tasks[id].result = {"error": str(e)}

	background_tasks.add_task(scrape_task)
	return task


@app.get("/status", summary="Get the status of a task")
def status(id: str) -> TaskStatus:
	if id not in tasks:
		raise HTTPException(status_code=404, detail=f"Task with ID {id} not found")
	return tasks[id]


@app.get("/rag", summary="Perform a RAG query")
def rag(
	q: str = Query(
		description="Query to hand the RAG pipeline",
		examples=["Are there any pike in Windermere lake?"],
	),
	collection: str = Query(
		description="The name of the collection to query in the vector database.",
		default=config.default_collection,
	),
	dao: DAO = Depends(get_dao),
) -> Dict[str, Any]:
	if config.rag_enabled is False:
		return {
			"answer": "Generative answering is currently disabled. Please enable via `config.yaml`"
		}
	collection_desc = config.collections.get(
		collection,
		{
			"description": "No information about the original source of the documents is known."
		},
	)
	feedback_loggger.log_feedback(
		{"query": q, "collection": collection, "type": "rag_query"}
	)
	return dao.rag_query(collection, str(collection_desc), q)


@app.get("/feedback", summary="Get feedback")
def get_feedback():
	return feedback_loggger.get_feedback()


@app.post("/feedback", summary="Log feedback")
def log_feedback(feedback: Dict[str, Any]):
	feedback_loggger.log_feedback(feedback)
	return {"status": "success"}
