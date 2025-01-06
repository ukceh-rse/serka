from fastapi import FastAPI
import chromadb
from typing import Dict, Sequence

app = FastAPI()


def get_db() -> chromadb.api.ClientAPI:
	return chromadb.Client()


@app.get("/list")
def list() -> Dict[str, Sequence[str]]:
	return {"collections": get_db().list_collections()}
