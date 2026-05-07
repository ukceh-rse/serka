"""Mock implementations for test mode.

Applied via app.dependency_overrides when TEST_MODE=true, allowing the frontend
to be developed and tested without Neo4j, Bedrock, or the MCP server.
"""

import asyncio
import json
from typing import Any, Dict, List

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

_MOCK_RESULTS: List[dict] = [
	{
		"result": {
			"item": {
				"doc_id": "mock-1",
				"content": (
					"This dataset contains measurements of organic carbon stocks in upland "
					"soils across the UK, collected between 1978 and 2019. Samples were taken "
					"at 0–10 cm, 10–20 cm, and 20–30 cm depths using standardised coring "
					"methods. Sites span peatlands, heathlands, and montane grasslands."
				),
			},
			"type": "TextChunk",
		},
		"dataset": {
			"uri": "https://catalogue.ceh.ac.uk/documents/soil-carbon-upland-1978-2019",
			"title": "Long-term soil carbon stocks across UK upland ecosystems, 1978-2019",
		},
		"score": 0.951,
		"description": "HAS_CHUNK",
	},
	{
		"result": {
			"item": {
				"doc_id": "mock-2",
				"content": (
					"Macroinvertebrate community composition data collected from 47 sites "
					"within the River Wye catchment. Kick-net sampling was conducted in "
					"spring and autumn following standard EA methodology."
				),
			},
			"type": "TextChunk",
		},
		"dataset": {
			"uri": "https://catalogue.ceh.ac.uk/documents/macroinvert-wye-2015-2022",
			"title": "Freshwater macroinvertebrate assemblages, River Wye catchment, 2015-2022",
		},
		"score": 0.913,
		"description": "HAS_CHUNK",
	},
	{
		"result": {
			"item": {
				"doc_id": "mock-3",
				"content": (
					"Weekly transect counts of butterfly species from over 2,500 sites across "
					"the UK, recorded by volunteer recorders between April and September each year."
				),
			},
			"type": "TextChunk",
		},
		"dataset": {
			"uri": "https://catalogue.ceh.ac.uk/documents/ukbms-transects-2000-2023",
			"title": "UK Butterfly Monitoring Scheme transect counts, 2000-2023",
		},
		"score": 0.872,
		"description": "HAS_CHUNK",
	},
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


async def get_mock_mcp_search():
	async def _search(q: str) -> list:
		return _MOCK_RESULTS

	return _search


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
