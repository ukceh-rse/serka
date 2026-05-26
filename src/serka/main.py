from importlib.metadata import version

from fastapi import FastAPI

from serka.routers import chat, feedback, query
from serka.settings import Settings

_API_PREFIX = "/v1"
_settings = Settings()
_version = version("serka")

app = FastAPI(
	title="Serka",
	version=_version,
	description="An API to expose advanced search functionality"
	+ (" — **TEST MODE** (no backend connections)" if _settings.test_mode else ""),
)


@app.get("/health")
async def health():
	return {"status": "ok", "version": _version}


app.include_router(query.router, prefix=_API_PREFIX)
app.include_router(feedback.router, prefix=_API_PREFIX)
app.include_router(chat.router, prefix=_API_PREFIX)

if _settings.test_mode:
	from serka.routers.dependencies import get_feedback_logger, get_mcp_search, get_stream_fn
	from serka.routers.mock import MockFeedbackLogger, get_mock_mcp_search, mock_stream_fn

	app.dependency_overrides[get_mcp_search] = get_mock_mcp_search
	app.dependency_overrides[get_feedback_logger] = lambda: MockFeedbackLogger()
	app.dependency_overrides[get_stream_fn] = mock_stream_fn
