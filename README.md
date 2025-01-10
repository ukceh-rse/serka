# Serka
Serka (serĉi ekologio) is a protoype search tool for the UKCEH NCUK project. It uses modern AI techniques (LLMs, RAG, Vector Stores) to enhance the EIDC catalogue's search functionality.

## Setup
Ensure you have [uv](https://docs.astral.sh/uv/) installed and run `uv sync` to create a virtual environment and install the required dependencies. You can then either activate the virtual environment `source .venv/bin/activate` or prepend further commands with `uv run`.
## Run
Start the API using `fastapi dev src/serka/main.py` and navigate to [http://localhost:8000/docs](http://localhost:8000/docs).
## Development
Before contributing, you should install the pre-commit hooks with `pre-commit install`.
## Docker
To run using [docker](https://www.docker.com/) use `docker compose up -d` (add `--build` to force a rebuild of the image). The image should be running at [http://localhost:8000/docs](http://localhost:8000/docs)) and can be stopped with `docker compose down`.
### Docker Development Environment
`docker-compose-dev.yml` contains overwrite values for the main `docker-compose.yml` file that enable easier development. To use this develpment setup use:
```
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```
This setup allows the application to be run but the the main docker container will mount to the local `src` directory and hot reloading is enabled. The vector store is also exposed on port `8001` so that it can be directly connected to.
