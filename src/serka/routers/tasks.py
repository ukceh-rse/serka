from fastapi import Query, Depends, APIRouter, Body
from serka.routers.dependencies import get_dao, get_config
from serka.models import TaskStatus, Config
from typing import Dict, List, Literal
from serka.jobs import scrape_task, legilo_crawl_task
from pydantic import HttpUrl
from serka.dao import DAO
from fastapi import BackgroundTasks
from fastapi import HTTPException
import uuid


tasks: Dict[str, TaskStatus] = {}
router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
	"/scrape", summary="Submit a task to asynchronously scrape from a source URL"
)
async def scrape(
	background_tasks: BackgroundTasks,
	urls: List[HttpUrl] = Body(
		description="List of urls to scrape data from.",
		default=["https://catalogue.ceh.ac.uk/eidc/documents"],
	),
	collection: str = Query(
		description="Name of the collection to store the fetched documents.",
		default=get_config().default_collection,
	),
	source_type: Literal["eidc", "legilo", "html"] = "eidc",
	dao: DAO = Depends(get_dao),
) -> TaskStatus:
	id = str(uuid.uuid4())
	task = TaskStatus(id=id, status="pending")
	tasks[id] = task
	background_tasks.add_task(
		scrape_task,
		task,
		dao,
		urls,
		collection,
		source_type,
		get_config().unified_metadata,
	)
	return task


@router.post(
	"/crawl", summary="Submit a task to asynchronously crawl from a source URL"
)
async def crawl(
	background_tasks: BackgroundTasks,
	urls: List[HttpUrl] = Body(
		description="List of urls to begin crawl from.",
		default=["https://catalogue.ceh.ac.uk/eidc/documents"],
	),
	collection: str = Query(default="eidc"),
	crawl_type: Literal["legilo", "web"] = "legilo",
	dao: DAO = Depends(get_dao),
	config: Config = Depends(get_config),
) -> TaskStatus:
	id = str(uuid.uuid4())
	task = TaskStatus(id=id, status="pending")
	tasks[id] = task

	if crawl_type == "web":
		raise HTTPException(
			status_code=501,
			detail="Web crawling is not yet implemented. Please use 'legilo' for now.",
		)

	background_tasks.add_task(
		legilo_crawl_task, task, dao, urls, collection, config.unified_metadata
	)
	return task


@router.get("/status", summary="Get the status of a task")
def status(id: str) -> TaskStatus:
	if id not in tasks:
		raise HTTPException(status_code=404, detail=f"Task with ID {id} not found")
	return tasks[id]
