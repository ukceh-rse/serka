# Serka
Serka (serĉi ekologio) is a protoype search tool for the UKCEH NCUK project. It uses modern AI techniques (LLMs, RAG, Vector Stores) to enhance the EIDC catalogue's search functionality.

## Setup
Ensure you have [uv](https://docs.astral.sh/uv/) installed and run:
```
uv sync
```
This will create a virtual environment and install the required dependencies. You can then activate the virtual environment with:
```
source .venv/bin/activate
```
Alternatively you can prepend all further commands with:
```
uv run
```

## Run
The application requires several supporting services to run correctly ([chromadb](https://docs.trychroma.com) and [ollama](https://ollama.com/)). The easiest way to run the whole application is using [docker](https://www.docker.com/) which creates all the necessary services for you:
```
docker compose up -d
```
You can add `--build` to the above command to force a rebuild of the docker image.
Once started, you can connect to the running image at: [http://localhost:8000/docs](http://localhost:8000/docs).
The application can be stopped with:
```
docker compose down
```
> **Note:** The `docker-compose.yml` configuration creates mounts in the current directory for the data files used by the chromdb and ollama services (`./.chromadb` and `./.ollama`).

## Development
### Pre-commit
Before contributing, you should install the pre-commit hooks with `pre-commit install`.

### Docker
`docker-compose-dev.yml` contains overwrite values for the main `docker-compose.yml` file that enable easier development. To use this develpment setup use:
```
docker compose -f docker-compose.dev.yml up -d
```
This setup allows the application to be run but the the main docker container will volume mount to the local `src` directory and has hot reloading enabled so that you can edit the source code for the main application whilst it is running. The vector store and LLM server are also also exposed on ports `8001` and `11435` respectively, so that they can be directly connected to for debugging.
