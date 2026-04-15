"""Mock implementations of DAO, FeedbackLogger, and the chat stream function.

Applied via app.dependency_overrides when TEST_MODE=true, allowing the frontend
to be developed and tested without Neo4j, MongoDB, Bedrock, or the MCP server.
"""

import asyncio
import json
from typing import Any, Dict, List

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from serka.models import Document, GroupedDocuments, ScoredDocument

_MOCK_RESULTS: List[GroupedDocuments] = [
	GroupedDocuments(
		groupedby="Long-term soil carbon stocks across UK upland ecosystems, 1978-2019",
		docs=[
			ScoredDocument(
				score=0.951,
				document=Document(
					content=(
						"This dataset contains measurements of organic carbon stocks in upland "
						"soils across the UK, collected between 1978 and 2019. Samples were taken "
						"at 0–10 cm, 10–20 cm, and 20–30 cm depths using standardised coring "
						"methods. Sites span peatlands, heathlands, and montane grasslands."
					),
					metadata={
						"title": "Long-term soil carbon stocks across UK upland ecosystems, 1978-2019",
						"url": "https://catalogue.ceh.ac.uk/documents/soil-carbon-upland-1978-2019",
						"section": "Abstract",
						"subsection": "Overview",
					},
				),
			),
			ScoredDocument(
				score=0.887,
				document=Document(
					content=(
						"Field sampling followed the Countryside Survey protocol. Carbon content "
						"was determined by loss-on-ignition at 550°C for 4 hours. Bulk density "
						"was measured on undisturbed cores."
					),
					metadata={
						"title": "Long-term soil carbon stocks across UK upland ecosystems, 1978-2019",
						"url": "https://catalogue.ceh.ac.uk/documents/soil-carbon-upland-1978-2019",
						"section": "Methods",
						"subsection": "Sample Processing",
					},
				),
			),
		],
	),
	GroupedDocuments(
		groupedby="Freshwater macroinvertebrate assemblages, River Wye catchment, 2015-2022",
		docs=[
			ScoredDocument(
				score=0.913,
				document=Document(
					content=(
						"Macroinvertebrate community composition data collected from 47 sites "
						"within the River Wye catchment. Kick-net sampling was conducted in "
						"spring and autumn following standard EA methodology."
					),
					metadata={
						"title": "Freshwater macroinvertebrate assemblages, River Wye catchment, 2015-2022",
						"url": "https://catalogue.ceh.ac.uk/documents/macroinvert-wye-2015-2022",
						"section": "Abstract",
						"subsection": "Overview",
					},
				),
			),
		],
	),
	GroupedDocuments(
		groupedby="UK Butterfly Monitoring Scheme transect counts, 2000-2023",
		docs=[
			ScoredDocument(
				score=0.872,
				document=Document(
					content=(
						"Weekly transect counts of butterfly species from over 2,500 sites across "
						"the UK, recorded by volunteer recorders between April and September each year."
					),
					metadata={
						"title": "UK Butterfly Monitoring Scheme transect counts, 2000-2023",
						"url": "https://catalogue.ceh.ac.uk/documents/ukbms-transects-2000-2023",
						"section": "Abstract",
						"subsection": "Overview",
					},
				),
			),
		],
	),
]

_MOCK_STREAM_EVENTS = [
	{"type": "THINKING_START"},
	{"type": "TOOL_CALL_START", "toolCallName": "search_datasets"},
	{"type": "TOOL_CALL_START", "toolCallName": "get_dataset_documents"},
	{
		"type": "TEXT_MESSAGE_CONTENT",
		"delta": "Based on the EIDC catalogue, I found several relevant datasets.\n\n",
	},
	{
		"type": "TEXT_MESSAGE_CONTENT",
		"delta": "The **Long-term soil carbon stocks** dataset (1978–2019) is likely the most directly relevant.\n\n",
	},
	{
		"type": "TEXT_MESSAGE_CONTENT",
		"delta": "Would you like me to retrieve the full supporting documentation for any of these?",
	},
	{"type": "RUN_FINISHED"},
]


class MockDAO:
	def query(self, query: str) -> List[GroupedDocuments]:
		return _MOCK_RESULTS


class MockFeedbackLogger:
	def log_feedback(self, feedback: Dict[str, Any]) -> None:
		pass


def mock_stream_fn() -> Any:
	"""Drop-in replacement for get_stream_fn. Returns a stream handler that
	yields fake SSE events with realistic delays."""

	async def _events():
		for event in _MOCK_STREAM_EVENTS:
			yield f"data: {json.dumps(event)}\n\n"
			await asyncio.sleep(0.35)

	def stream(run_input: Any, request: Request) -> Response:
		return StreamingResponse(_events(), media_type="text/event-stream")

	return stream
