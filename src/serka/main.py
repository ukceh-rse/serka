from fastapi import FastAPI, Query, Depends, APIRouter, Body
from typing import Dict, Any, List, Literal
from serka.dao import DAO
import yaml
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from serka.models import Config, TaskStatus, Document, Result, RAGResponse
from serka.feedback import FeedbackLogger
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
	title="Serka", description="An API to expose advanced search functionality"
)

tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])
collections_router = APIRouter(prefix="/collections", tags=["Collections"])
query_router = APIRouter(prefix="/query", tags=["Query"])
feedback_router = APIRouter(prefix="/feedback", tags=["Feedback"])


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


@collections_router.get("/list", summary="List collections in the vector database")
def list() -> List[str]:
	return get_dao().list_collections()


@collections_router.get(
	"/peek", summary="Peek into a collection in the vector database"
)
def peek(
	collection: str = Query(
		description="Name of the collection to peek.",
		default=config.default_collection,
	),
	dao: DAO = Depends(get_dao),
) -> List[Document]:
	return dao.peek(collection)


@collections_router.delete(
	"/delete", summary="Delete a collection in the vector database"
)
def delete(
	collection: str = Query(
		description="The name of the collection to delete in the vector database.",
	),
	dao: DAO = Depends(get_dao),
) -> Result:
	return dao.delete(collection)


@query_router.get(
	"/semantic", summary="Perform a semantic search in the vector database"
)
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
) -> List[Document]:
	feedback_loggger.log_feedback(
		{"query": q, "collection": collection, "type": "semantic_search"}
	)
	return dao.query(collection, q, n)


@collections_router.post(
	"/insert", summary="Insert a document into the vector database"
)
def insert(
	document: Document,
	collection: str = Query(default=config.default_collection),
	dao: DAO = Depends(get_dao),
) -> Result:
	return dao.insert(document, collection)


@tasks_router.post(
	"/scrape", summary="Submit a task to asynchronously scrape from a source URL"
)
async def scrape(
	background_tasks: BackgroundTasks,
	urls: List[str] = Body(
		description="URL to fetch data from / start scraping from.",
		default=[config.collections[config.default_collection].url],
	),
	collection: str = Query(
		description="Name of the collection to store the fetched documents.",
		default=config.default_collection,
	),
	source_type: Literal["eidc", "legilo", "html"] = "eidc",
	dao: DAO = Depends(get_dao),
) -> TaskStatus:
	id = str(uuid.uuid4())
	task = TaskStatus(id=id, status="pending")
	tasks[id] = task

	def scrape_task():
		try:
			tasks[id].status = "running"
			result = dao.scrape(
				urls,
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


@tasks_router.get("/status", summary="Get the status of a task")
def status(id: str) -> TaskStatus:
	if id not in tasks:
		raise HTTPException(status_code=404, detail=f"Task with ID {id} not found")
	return tasks[id]


@query_router.get("/rag", summary="Perform a RAG query")
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
) -> RAGResponse:
	if config.rag_enabled is False:
		return RAGResponse(
			result=Result(
				success=False,
				msg="Generative answering is currently disabled. Please enable via `config.yaml`",
			),
			answer="",
			query=q,
		)
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


@feedback_router.get("/list", summary="Get feedback")
def get_feedback() -> List[Dict[str, Any]]:
	return feedback_loggger.get_feedback()


@feedback_router.post("/submit", summary="Log feedback")
def log_feedback(feedback: Dict[str, Any]) -> Result:
	feedback_loggger.log_feedback(feedback)
	return Result(success=True, msg="Feedback logged")


app.include_router(tasks_router)
app.include_router(collections_router)
app.include_router(query_router)
app.include_router(feedback_router)
