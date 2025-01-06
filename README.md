# Serka
Serka (serĉi ekologio) is a protoype search tool for the UKCEH NCUK project. It uses modern AI techniques (LLMs, RAG, Vector Stores) to enhance the EIDC catalogue's search functionality.

## Setup
Ensure you have [uv](https://docs.astral.sh/uv/) installed and run `uv sync` to create a virtual environment and install the required dependencies. You can then either activate the virtual environment `source .venv/bin/activate` or prepend further commands with `uv run`.
## Run
Start the API using `fastapi dev src/serka/main.py` and navigate to [http://localhost:8000/docs](http://localhost:8000/docs).
## Development
Before contributing, you should install the pre-commit hooks with `pre-commit install`.
