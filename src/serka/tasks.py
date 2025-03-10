from serka.models import TaskStatus, Result
from serka.dao import DAO
from typing import List
import requests


def scrape_task(
	task: TaskStatus,
	dao: DAO,
	urls: List[str],
	collection: str,
	source_type: str,
	unified_metadata: List[str],
):
	try:
		task.status = "running"
		result = dao.scrape(
			urls,
			collection,
			source_type=source_type,
			unified_metadata=unified_metadata,
		)
		task.status = "complete"
		task.result = result
	except Exception as e:
		task.status = "failed"
		task.result = {"error": str(e)}


def legilo_crawl_task(
	task: TaskStatus,
	dao: DAO,
	urls: List[str],
	collection: str,
	unified_metadata: List[str],
):
	task.status = "running"
	failures = []
	insertions = 0
	for url in urls:
		res = requests.get(
			url,
			headers={"content-type": "application/json"},
			params={
				"term": "recordType:Dataset",
			},
		)
		eidc_url = "https://catalogue.ceh.ac.uk/id/{id}"
		legilo_url = "https://legilo.eds-infra.ceh.ac.uk/{id}/documents"
		data = res.json()
		for item in data["results"]:
			try:
				metadata = {
					"title": item["title"],
					"url": eidc_url.format(id=item["identifier"]),
					"section": "Supporting Documentation",
				}
				dao.scrape(
					[legilo_url.format(id=item["identifier"])],
					collection,
					source_type="legilo",
					unified_metadata=unified_metadata,
					metadata=metadata,
				)
				insertions += 1
			except Exception as e:
				failures.append({"id": item["identifier"], "error": str(e)})
	task.status = "complete"
	task.result = Result(
		success=True,
		msg=f"Inserted {insertions} supporting document(s) source files into {collection}",
	)
