import os
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from serka.routers import chat, feedback, query
from serka.settings import Settings

_STATIC_DIR = "static"
_API_PREFIX = "/v1"
_settings = Settings()
_version = version("serka")

app = FastAPI(
	title="Serka",
	version=_version,
	description="An API to expose advanced search functionality"
	+ (" — **TEST MODE** (no backend connections)" if _settings.test_mode else ""),
)

if os.path.isdir(_STATIC_DIR):
	app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/health")
async def health():
	return {"status": "ok", "version": _version}


@app.get("/")
async def read_index():
	return FileResponse(f"{_STATIC_DIR}/html/index.html")


app.include_router(query.router, prefix=_API_PREFIX)
app.include_router(feedback.router, prefix=_API_PREFIX)
app.include_router(chat.router, prefix=_API_PREFIX)

if _settings.test_mode:
	from serka.routers.dependencies import get_dao, get_feedback_logger, get_stream_fn
	from serka.routers.mock import MockDAO, MockFeedbackLogger, mock_stream_fn

	app.dependency_overrides[get_dao] = lambda: MockDAO()
	app.dependency_overrides[get_feedback_logger] = lambda: MockFeedbackLogger()
	app.dependency_overrides[get_stream_fn] = mock_stream_fn
