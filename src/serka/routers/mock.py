"""Mock implementations for test mode.

Applied via app.dependency_overrides when TEST_MODE=true, allowing the frontend
to be developed and tested without Neo4j, Bedrock, or the MCP server.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from serka.ontology import NODE_TYPES

# Fixture datasets. Each becomes a direct SearchHit (matched via its excerpt) and doubles
# as the "via" anchor for the Person/Organisation/Concept/Document hits below.
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


def _dataset_entity(d: Dict[str, Any]) -> Dict[str, Any]:
	"""The JSON-LD dataset entity the MCP server returns (mcp-server/src/serka-mcp/entities.py)."""
	w, s, e, n = d["west_boundary"], d["south_boundary"], d["east_boundary"], d["north_boundary"]
	return {
		"@id": d["uri"],
		"@type": ["dcat:Dataset"],
		"label": d["title"],
		"title": d["title"],
		"publication_date": d["publication_date"],
		"identifiers": d["identifiers"],
		"access_rights": d["access_rights"],
		"licence": d["licence"],
		"temporal": {"@type": "dcterms:PeriodOfTime", "start_date": d["temporal_start"], "end_date": d["temporal_end"]},
		"bbox": f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))",
		"citations": d["citations"],
	}


def _dataset_hit(d: Dict[str, Any]) -> Dict[str, Any]:
	return {
		"entity": _dataset_entity(d),
		"score": d["score"],
		"matched_on": d["matched_on"],
		"excerpt": d["excerpt"],
		"path": [],
	}


def _via(d: Dict[str, Any], predicate: str) -> Dict[str, Any]:
	return {
		"predicate": predicate,
		"entity": _dataset_entity(d),
	}


def _related_hit(
	entity_id: str, type_uri: str, label: str, properties: Dict[str, Any],
	predicate: str, via_dataset: Dict[str, Any], score: float,
) -> Dict[str, Any]:
	return {
		"entity": {"@id": entity_id, "@type": [type_uri], "label": label, **properties},
		"score": score,
		"matched_on": "metadata",
		"excerpt": None,
		"path": [_via(via_dataset, predicate)],
	}


_MOCK_HITS: List[Dict[str, Any]] = [_dataset_hit(d) for d in _DATASETS] + [
	_related_hit(
		"https://orcid.org/0000-0002-1111-2222", "foaf:Person", "Dr. Alice Whitfield",
		{"name": "Dr. Alice Whitfield"}, "pro:author", _DATASETS[0], 0.71,
	),
	_related_hit(
		"https://orcid.org/0000-0003-3333-4444", "foaf:Person", "Dr. Raj Osei",
		{"name": "Dr. Raj Osei"}, "scoro:principal-investigator", _DATASETS[1], 0.68,
	),
	_related_hit(
		"https://orcid.org/0000-0001-5555-6666", "foaf:Person", "Dr. Emily Carrow",
		{"name": "Dr. Emily Carrow"}, "pro:author", _DATASETS[6], 0.64,
	),
	_related_hit(
		"https://ror.org/006jxzx88", "foaf:Organization", "UK Centre for Ecology & Hydrology",
		{"name": "UK Centre for Ecology & Hydrology"}, "pro:publisher", _DATASETS[0], 0.66,
	),
	_related_hit(
		"https://ror.org/02b5d8509", "foaf:Organization", "Environment Agency",
		{"name": "Environment Agency"}, "scoro:data-curator", _DATASETS[3], 0.61,
	),
	_related_hit(
		"https://vocabs.ceh.ac.uk/concept/biodiversity", "skos:Concept", "Biodiversity",
		{"scheme": "https://vocabs.ceh.ac.uk/scheme/eidc"}, "dcat:theme", _DATASETS[2], 0.59,
	),
	_related_hit(
		"https://vocabs.ceh.ac.uk/concept/freshwater-ecology", "skos:Concept", "Freshwater ecology",
		{"scheme": "https://vocabs.ceh.ac.uk/scheme/eidc"}, "dcat:theme", _DATASETS[1], 0.57,
	),
	_related_hit(
		"https://vocabs.ceh.ac.uk/concept/climate-change", "skos:Concept", "Climate change",
		{"scheme": "https://vocabs.ceh.ac.uk/scheme/eidc"}, "dcat:theme", _DATASETS[4], 0.55,
	),
	_related_hit(
		"https://catalogue.ceh.ac.uk/documents/soil-carbon-upland-1978-2019/supporting-doc",
		"fabio:DigitalManifestation", "Soil sampling and analysis protocol (supporting document)",
		{"title": "Soil sampling and analysis protocol", "format": "application/pdf"},
		"dcterms:references", _DATASETS[0], 0.53,
	),
	_related_hit(
		"https://catalogue.ceh.ac.uk/documents/ukbms-transects-2000-2023/supporting-doc",
		"fabio:DigitalManifestation", "UKBMS transect walk methodology (supporting document)",
		{"title": "UKBMS transect walk methodology", "format": "application/pdf"},
		"dcterms:references", _DATASETS[2], 0.51,
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


def _matches_return_type(hit: Dict[str, Any], return_type: Optional[str]) -> bool:
	if not return_type:
		return True
	target = NODE_TYPES.get(str(return_type), str(return_type))
	return target in hit["entity"]["@type"]


async def get_mock_mcp_search():
	async def _search(
		q: str,
		return_type: Optional[str] = None,
		hops: int = 1,
		location: Optional[str] = None,
		published_after: Optional[str] = None,
		published_before: Optional[str] = None,
	) -> list:
		return [h for h in _MOCK_HITS if _matches_return_type(h, return_type)]

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
