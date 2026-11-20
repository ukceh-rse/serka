"""Mock implementations for test mode.

Applied via app.dependency_overrides when TEST_MODE=true, allowing the frontend
to be developed and tested without Redis, Bedrock, or the MCP server.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from serka.settings import Settings

# Fixture datasets. Each becomes a search hit on the chunk holding its excerpt; the
# person, organisation, theme and document hits below refer to them.
_DATASETS: List[Dict[str, Any]] = [
	dict(
		uri="https://catalogue.ceh.ac.uk/documents/soil-carbon-upland-1978-2019",
		title="Long-term soil carbon stocks across UK upland ecosystems, 1978-2019",
		description="Organic carbon stocks in upland soils across the UK, sampled at 0-10cm, 10-20cm, and 20-30cm depths using standardised coring methods across peatlands, heathlands, and montane grasslands.",
		excerpt="This dataset contains measurements of organic carbon stocks in upland soils across the UK, collected between 1978 and 2019. Samples were taken at 0-10 cm, 10-20 cm, and 20-30 cm depths using standardised coring methods.",
		matched_on="description", score=0.951, publication_date="2020-03-12",
		licence="https://creativecommons.org/licenses/by/4.0/", access_rights="open", citations=14,
		identifiers=["https://doi.org/10.5285/abc111"], temporal_start="1978-01-01", temporal_end="2019-12-31",
		north_boundary=58.9, south_boundary=50.0, east_boundary=1.8, west_boundary=-7.5,
	),
	dict(
		uri="https://catalogue.ceh.ac.uk/documents/macroinvert-wye-2015-2022",
		title="Freshwater macroinvertebrate assemblages, River Wye catchment, 2015-2022",
		description="Macroinvertebrate community composition data collected from 47 sites within the River Wye catchment using standard kick-net sampling.",
		excerpt="Macroinvertebrate community composition data collected from 47 sites within the River Wye catchment. Kick-net sampling was conducted in spring and autumn following standard EA methodology.",
		matched_on="description", score=0.913, publication_date="2023-01-20",
		licence="https://creativecommons.org/licenses/by/4.0/", access_rights="open", citations=6,
		identifiers=["https://doi.org/10.5285/abc112"], temporal_start="2015-03-01", temporal_end="2022-10-31",
		north_boundary=52.3, south_boundary=51.6, east_boundary=-2.5, west_boundary=-3.4,
	),
	dict(
		uri="https://catalogue.ceh.ac.uk/documents/ukbms-transects-2000-2023",
		title="UK Butterfly Monitoring Scheme transect counts, 2000-2023",
		description="Weekly transect counts of butterfly species from over 2,500 sites across the UK, recorded by volunteer recorders between April and September each year.",
		excerpt="Weekly transect counts of butterfly species from over 2,500 sites across the UK, recorded by volunteer recorders between April and September each year.",
		matched_on="description", score=0.872, publication_date="2024-02-01",
		licence="http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/", access_rights="open",
		citations=41, identifiers=["https://doi.org/10.5285/abc113"], temporal_start="2000-04-01", temporal_end="2023-09-30",
		north_boundary=60.8, south_boundary=49.9, east_boundary=1.8, west_boundary=-8.2,
	),
	dict(
		uri="https://catalogue.ceh.ac.uk/documents/river-flow-gauging-2010-2023",
		title="Daily river flow gauging station records, England and Wales, 2010-2023",
		description="Daily mean river flow (m3/s) from the national gauging network, quality-controlled and infilled where short gaps occur.",
		excerpt="Daily mean river flow in cubic metres per second, derived from stage-discharge relationships at each gauging station, quality controlled against rating curves.",
		matched_on="lineage", score=0.834, publication_date="2024-06-15",
		licence="https://creativecommons.org/licenses/by/4.0/", access_rights="open", citations=9,
		identifiers=["https://doi.org/10.5285/abc114"], temporal_start="2010-01-01", temporal_end="2023-12-31",
		north_boundary=55.8, south_boundary=51.3, east_boundary=1.7, west_boundary=-5.2,
	),
	dict(
		uri="https://catalogue.ceh.ac.uk/documents/land-cover-map-2021",
		title="Land Cover Map 2021 (25m raster, GB)",
		description="A parcel-based land cover classification of Great Britain, derived from Sentinel-2 and Sentinel-1 satellite imagery.",
		excerpt="A parcel-based land cover classification of Great Britain for 2021, derived from Sentinel-2 and Sentinel-1 satellite imagery and validated against ground-truth survey data.",
		matched_on="description", score=0.798, publication_date="2022-05-10",
		licence="https://creativecommons.org/licenses/by/4.0/", access_rights="open", citations=27,
		identifiers=["https://doi.org/10.5285/abc115"], temporal_start="2021-01-01", temporal_end="2021-12-31",
		north_boundary=60.9, south_boundary=49.9, east_boundary=1.9, west_boundary=-8.6,
	),
	dict(
		uri="https://catalogue.ceh.ac.uk/documents/pollinator-monitoring-2017-2023",
		title="UK Pollinator Monitoring Scheme (PoMS) count data, 2017-2023",
		description="Standardised counts of flower-visiting insects along fixed transects at PoMS sites across the UK, alongside floral resource surveys.",
		excerpt="Standardised counts of flower-visiting insects along fixed 1km transects at PoMS sites across the UK, recorded alongside floral resource availability surveys.",
		matched_on="description", score=0.761, publication_date="2024-01-08",
		licence="https://creativecommons.org/licenses/by/4.0/", access_rights="open", citations=11,
		identifiers=["https://doi.org/10.5285/abc116"], temporal_start="2017-04-01", temporal_end="2023-09-30",
		north_boundary=59.4, south_boundary=50.0, east_boundary=1.8, west_boundary=-7.5,
	),
	dict(
		uri="https://catalogue.ceh.ac.uk/documents/breeding-bird-survey-1994-2023",
		title="Breeding Bird Survey population indices, UK, 1994-2023",
		description="Annual population indices for UK breeding bird species derived from volunteer transect surveys under the joint BTO/JNCC/RSPB scheme.",
		excerpt="Annual population indices for UK breeding bird species, derived from distance-sampled transect counts conducted by volunteer surveyors each spring.",
		matched_on="description", score=0.729, publication_date="2024-03-22",
		licence="http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/", access_rights="open",
		citations=33, identifiers=["https://doi.org/10.5285/abc117"], temporal_start="1994-01-01", temporal_end="2023-12-31",
		north_boundary=60.8, south_boundary=49.9, east_boundary=1.8, west_boundary=-8.2,
	),
	dict(
		uri="https://catalogue.ceh.ac.uk/documents/urban-air-quality-2018-2023",
		title="Urban air quality (NO2, PM2.5) monitoring, UK cities, 2018-2023",
		description="Hourly nitrogen dioxide and fine particulate matter concentrations from automatic monitoring stations in major UK cities.",
		excerpt="Hourly nitrogen dioxide and fine particulate matter (PM2.5) concentrations recorded at automatic urban monitoring stations, quality-assured against national reference methods.",
		matched_on="description", score=0.688, publication_date="2024-04-30",
		licence="https://creativecommons.org/licenses/by/4.0/", access_rights="restricted", citations=5,
		identifiers=["https://doi.org/10.5285/abc118"], temporal_start="2018-01-01", temporal_end="2023-12-31",
		north_boundary=57.5, south_boundary=51.3, east_boundary=0.2, west_boundary=-4.3,
	),
]


def _dataset_id(d: Dict[str, Any]) -> str:
	return "datasets/" + d["uri"].rsplit("/", 1)[1]


def _dataset_concept(d: Dict[str, Any]) -> Dict[str, Any]:
	"""The concept summary the MCP `search` tool returns for a dataset chunk."""
	return {
		"id": _dataset_id(d),
		"type": "dataset",
		"title": d["title"],
		"description": d["description"],
		"resource": d["uri"],
		"tags": [],
		"citations": d["citations"],
		"published": d["publication_date"],
	}


def _hit(concept: Dict[str, Any], n: int, text: str, score: float) -> Dict[str, Any]:
	return {"chunk_id": f"{concept['id']}#{n}", "text": text, "score": score, "concept": concept}


def _dataset_hit(d: Dict[str, Any], n: int = 0, text: Optional[str] = None, score: Optional[float] = None) -> Dict[str, Any]:
	return _hit(_dataset_concept(d), n, text or d["excerpt"], d["score"] if score is None else score)


def _other_hit(concept_id: str, okf_type: str, title: str, text: str, score: float, **extra: Any) -> Dict[str, Any]:
	concept = {"id": concept_id, "type": okf_type, "title": title, "description": None, "resource": None, "tags": [], **extra}
	return _hit(concept, 0, text, score)


_SOIL = _DATASETS[0]
_SOIL_DOC = f"{_dataset_id(_SOIL)}/docs/soil-sampling-protocol"

_MOCK_HITS: List[Dict[str, Any]] = sorted(
	[_dataset_hit(d) for d in _DATASETS]
	+ [
		# A second and a third passage of the top dataset, ranked below other datasets
		_dataset_hit(
			_SOIL, 1,
			"Cores were dried at 105 °C and analysed for total carbon by dry combustion; bulk density was measured on separate cores.",
			0.902,
		),
		_dataset_hit(
			_SOIL, 2,
			"Peatland sites were resampled in 2019 at the same grid points used in 1978, allowing paired comparisons of carbon change.",
			0.701,
		),
		_hit(
			{
				"id": _SOIL_DOC,
				"type": "document",
				"title": "soil-sampling-protocol.pdf",
				"description": None,
				"resource": None,
				"tags": [],
				"citations": _SOIL["citations"],
				"published": _SOIL["publication_date"],
			},
			0,
			f"Supporting document of [{_SOIL['title']}](/{_dataset_id(_SOIL)}). Each core was split into 10 cm sections "
			"and stored at 4 °C before analysis.",
			0.86,
		),
		_other_hit(
			"people/0000-0002-1111-2222", "person", "Dr. Alice Whitfield",
			f"Dr. Alice Whitfield, author of [{_SOIL['title']}](/{_dataset_id(_SOIL)}).", 0.71,
			resource="https://orcid.org/0000-0002-1111-2222",
		),
		_other_hit(
			"people/0000-0003-3333-4444", "person", "Dr. Raj Osei",
			"## Affiliations\n\n- [member of](/ontology/predicates/memberOf): [UK Centre for Ecology & Hydrology](/organisations/006jxzx88)",
			0.68,
			resource="https://orcid.org/0000-0003-3333-4444",
		),
		_other_hit(
			"organisations/006jxzx88", "organisation", "UK Centre for Ecology & Hydrology",
			"UK Centre for Ecology & Hydrology", 0.66, resource="https://ror.org/006jxzx88",
		),
		_other_hit(
			"themes/5f1d2c3b4a59", "theme", "Freshwater ecology",
			"## Broader themes\n\n- [broader](/ontology/predicates/broader): [Biodiversity](/themes/9a8b7c6d5e4f)",
			0.57,
			tags=["eidc"],
		),
	],
	key=lambda h: -h["score"],
)


def _search_result(hits: List[Dict[str, Any]]) -> str:
	return json.dumps({"hits": hits, "total": len(hits), "warnings": []})


_MOCK_ANSWER_CHUNKS = [
	"Soil carbon measurements for UK uplands are available in the ",
	f"[{_DATASETS[0]['title']}]({_DATASETS[0]['uri']}), ",
	"which covers 1978–2019 at three sampling depths. Related land cover context can be found in the ",
	f"[{_DATASETS[4]['title']}]({_DATASETS[4]['uri']}).",
]
# Stage -> default model ID, as the real pipeline reports it in RUN_METADATA.
_MOCK_MODELS = {
	name.removeprefix("models_"): f.default
	for name, f in Settings.model_fields.items()
	if name.startswith("models_") and name != "models_embedding"
}


def _mock_keyword_run(thread_id: str, run_id: str) -> List[str]:
	"""A scripted keyword run that follows the chat event contract, as encoded SSE lines."""
	from serka.chat.events import Emitter

	e = Emitter()
	m = _MOCK_MODELS

	def step(name: str, model: Optional[str], max_attempts: Optional[int] = 1) -> Any:
		return e.step(name, attempt=1, max_attempts=max_attempts, model=model)

	e.run_started(thread_id, run_id)
	with step("classify", m["classify"], max_attempts=None):
		e.custom("serka.classification", {"inScope": True, "label": "keyword", "reason": "Dataset search."})
	with step("route", None):
		e.metadata(m["synthesize_keyword"], m)
	with step("plan", m["plan_keyword"]):
		e.custom("serka.plan", {
			"summary": "Search the catalogue for datasets matching 'soil carbon uplands'.",
			"steps": ['search {"query": "soil carbon uplands", "type": "dataset"}'],
		})
	with step("execute", None):
		e.tool_call_start("mock-search", "search", json.dumps({"query": "soil carbon uplands", "type": "dataset"}))
		e.tool_call_result("mock-search", _search_result(_MOCK_HITS[:3]))
	with step("synthesize", m["synthesize_keyword"]):
		for chunk in _MOCK_ANSWER_CHUNKS:
			e.text_delta(chunk)
	with step("evaluate", m["evaluate"]):
		e.custom("serka.evaluation", {"attempt": 1, "passed": True, "score": 5, "problem": "none", "feedback": "Grounded and well cited."})
	e.text_end()
	e.custom("serka.outcome", {
		"status": "accepted", "path": "keyword", "attemptsUsed": 1, "maxAttempts": 1,
		"score": 5, "feedback": "Grounded and well cited.",
	})
	e.run_finished(thread_id, run_id)
	return _drain(e)


def _drain(e: Any) -> List[str]:
	"""Closes an Emitter and returns every encoded SSE line it queued."""
	e.close()
	lines: List[str] = []
	while (line := e.queue.get_nowait()) is not None:
		lines.append(line)
	return lines


_INSIGHT_DRAFT_1 = (
	"Butterfly numbers have changed over time. The UKBMS has data. "
	f"See [{_DATASETS[2]['title']}]({_DATASETS[2]['uri']})."
)
_INSIGHT_ANSWER = (
	"Long-term trends in UK butterfly and pollinator populations can be explored with two datasets. "
	f"The [{_DATASETS[2]['title']}]({_DATASETS[2]['uri']}) provides weekly transect counts from over 2,500 sites "
	"between 2000 and 2023, so it is the best source for multi-decade trends. "
	f"The [{_DATASETS[5]['title']}]({_DATASETS[5]['uri']}) adds standardised insect counts from 2017 to 2023, "
	"alongside floral resource surveys."
)


def _mock_insight_retry_run(thread_id: str, run_id: str) -> List[str]:
	"""A scripted insight run whose first draft fails evaluation (writing) and is accepted on attempt 2."""
	from serka.chat.events import Emitter
	from serka.chat.pipeline import MAX_ATTEMPTS

	e = Emitter()
	m = _MOCK_MODELS
	max_attempts = MAX_ATTEMPTS["insight"]

	def step(name: str, model: Optional[str], attempt: int = 1) -> Any:
		return e.step(name, attempt=attempt, max_attempts=max_attempts, model=model)

	e.run_started(thread_id, run_id)
	with e.step("classify", attempt=1, max_attempts=None, model=m["classify"]):
		e.custom("serka.classification", {"inScope": True, "label": "insight", "reason": "Asks about population trends."})
	with step("route", None):
		e.metadata(m["synthesize_insight"], m)
	with step("plan", m["plan_insight"]):
		e.custom("serka.plan", {
			"summary": "Find long-term butterfly and pollinator monitoring datasets and compare their coverage.",
			"steps": [
				'search {"query": "butterfly monitoring", "type": "dataset"}',
				'search {"query": "pollinator monitoring", "type": "dataset"}',
			],
		})
	with step("execute", m["execute_insight"]):
		for i, query in enumerate(["butterfly monitoring", "pollinator monitoring"]):
			call_id = f"mock-insight-search-{i + 1}"
			e.tool_call_start(call_id, "search", json.dumps({"query": query, "type": "dataset"}))
			hits = [_dataset_hit(_DATASETS[2 + 3 * i])] + _MOCK_HITS[:2]
			e.tool_call_result(call_id, _search_result(hits))
	with step("synthesize", m["synthesize_insight"], attempt=1):
		e.custom("serka.draft", {"attempt": 1, "text": _INSIGHT_DRAFT_1})
	with step("evaluate", m["evaluate"], attempt=1):
		e.custom("serka.evaluation", {
			"attempt": 1, "passed": False, "score": 2, "problem": "writing",
			"feedback": "Too vague: give the date ranges and mention the pollinator dataset.",
		})
	with step("synthesize", m["synthesize_insight"], attempt=2):
		e.custom("serka.draft", {"attempt": 2, "text": _INSIGHT_ANSWER})
	with step("evaluate", m["evaluate"], attempt=2):
		e.custom("serka.evaluation", {
			"attempt": 2, "passed": True, "score": 4, "problem": "none", "feedback": "Clear, grounded and cited.",
		})
	e.text(_INSIGHT_ANSWER)
	e.custom("serka.outcome", {
		"status": "accepted", "path": "insight", "attemptsUsed": 2, "maxAttempts": max_attempts,
		"score": 4, "feedback": "Clear, grounded and cited.",
	})
	e.run_finished(thread_id, run_id)
	return _drain(e)


def _mock_refused_run(thread_id: str, run_id: str) -> List[str]:
	"""A scripted out-of-scope run: classify, then refuse."""
	from serka import prompts
	from serka.chat.events import Emitter

	e = Emitter()
	m = _MOCK_MODELS
	e.run_started(thread_id, run_id)
	with e.step("classify", attempt=1, max_attempts=None, model=m["classify"]):
		e.custom("serka.classification", {"inScope": False, "label": None, "reason": "Not about environmental data."})
	e.metadata(m["classify"], m)
	with e.step("refuse", attempt=1, max_attempts=None, model=None):
		e.text(prompts.REFUSAL_MESSAGE)
	e.custom("serka.outcome", {
		"status": "refused", "path": None, "attemptsUsed": 0, "maxAttempts": None, "score": None, "feedback": None,
	})
	e.run_finished(thread_id, run_id)
	return _drain(e)


def _mock_insight_limit_run(thread_id: str, run_id: str) -> List[str]:
	"""A scripted run stopped by the daily insight cap: classify, route, limit."""
	from serka import prompts
	from serka.chat.events import Emitter
	from serka.chat.pipeline import MAX_ATTEMPTS

	e = Emitter()
	m = _MOCK_MODELS
	max_attempts = MAX_ATTEMPTS["insight"]
	e.run_started(thread_id, run_id)
	with e.step("classify", attempt=1, max_attempts=None, model=m["classify"]):
		e.custom("serka.classification", {"inScope": True, "label": "insight", "reason": "Needs reasoning."})
	with e.step("route", attempt=1, max_attempts=max_attempts, model=None):
		e.metadata(m["synthesize_insight"], m)
	with e.step("limit", attempt=1, max_attempts=max_attempts, model=None):
		e.text(prompts.INSIGHT_LIMIT_MESSAGE)
	e.custom("serka.outcome", {
		"status": "insight_limit_reached", "path": "insight", "attemptsUsed": 0, "maxAttempts": max_attempts,
		"score": None, "feedback": None,
	})
	e.run_finished(thread_id, run_id)
	return _drain(e)


def _mock_cached_run(thread_id: str, run_id: str) -> List[str]:
	"""A scripted run answered from the answer cache: only the cache step."""
	from serka.chat.events import Emitter

	e = Emitter()
	m = _MOCK_MODELS
	e.run_started(thread_id, run_id)
	with e.step("cache", attempt=1, max_attempts=None, model=None):
		e.metadata(m["synthesize_keyword"], m)
		e.text("".join(_MOCK_ANSWER_CHUNKS))
	e.custom("serka.outcome", {
		"status": "cached", "path": "keyword", "attemptsUsed": 0, "maxAttempts": None, "score": 5, "feedback": None,
	})
	e.run_finished(thread_id, run_id)
	return _drain(e)


def _select_run(query: str) -> Any:
	"""Test-mode scenario chosen by the query text: "trend" -> insight retry, "weather" -> refused,
	"quota" -> insight limit, "cached" -> answered from the answer cache."""
	q = query.lower()
	if "cached" in q:
		return _mock_cached_run
	if "quota" in q:
		return _mock_insight_limit_run
	if "trend" in q:
		return _mock_insight_retry_run
	if "weather" in q:
		return _mock_refused_run
	return _mock_keyword_run


async def get_mock_mcp_search():
	async def _search(
		q: str,
		type: Optional[str] = None,
		location: Optional[str] = None,
		published_after: Optional[str] = None,
		published_before: Optional[str] = None,
	) -> list:
		return [h for h in _MOCK_HITS if not type or h["concept"]["type"] == type]

	return _search


class MockFeedbackLogger:
	def log_feedback(self, feedback: Dict[str, Any]) -> None:
		pass


class MockUsageLimiter:
	"""Admits everything and stores nothing."""

	def check(self, client: str) -> None:
		return None

	def count(self, client: str) -> None:
		return None

	def admit(self, client: str) -> None:
		return None


def mock_stream_fn() -> Any:
	"""Drop-in replacement for get_stream_fn. Returns a stream handler that replays a
	scripted run (following the chat event contract) with realistic delays. The query text
	picks the run: "trend" plays insight with a retry, "weather" a refusal, "quota" the insight limit,
	"cached" a cached answer, anything else keyword."""
	from serka.chat.service import split_messages

	async def _events(lines: List[str]) -> AsyncIterator[str]:
		for line in lines:
			yield line
			await asyncio.sleep(0.15)

	def stream(run_input: Any, request: Request, count_run: Any = None) -> Response:
		query, _ = split_messages(run_input.messages)
		lines = _select_run(query)(run_input.thread_id, run_input.run_id)
		return StreamingResponse(_events(lines), media_type="text/event-stream")

	return stream
