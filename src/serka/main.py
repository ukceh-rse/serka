from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from serka.routers import query, feedback, graph


app = FastAPI(
	title="Serka", description="An API to expose advanced search functionality"
)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_index():
	return FileResponse("static/html/index.html")


app.include_router(query.router)
app.include_router(feedback.router)
app.include_router(graph.router)
