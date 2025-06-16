# Serka
Serka (serĉi ekologio) is a protoype search tool for the UKCEH NCUK project. It uses modern AI techniques (LLMs, RAG, Vector Stores) to enhance the EIDC catalogue's search functionality.

## Podman Deployment
Serka can be deployed using [podman](https://podman.io/). You must ensure you have `podman`, `podman-compose` and [`nvidia-container-toolkit`](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html) installed.

To run Serka and it's dependent services ([Ollama](https://ollama.com/), [Neo4j](https://neo4j.com/), [MondgoDB](https://www.mongodb.com/)) use:
```
podman-compose -f podman-compose.yml up -d
```
> Note: Initially the Ollama service will download the required models listed in `config.yml`. This can take some time, but once the models are downloaded they should not need to be downloaded again.

To stop the running services:
```
podman-compose -f podman-compose.yml down
```

## Development
Ensure you have [uv](https://docs.astral.sh/uv/) installed and run:
```
uv sync
```
This will create a virtual environment and install the required dependencies. You can then activate the virtual environment with:
```
source .venv/bin/activate
```
Alternatively you can prepend commands with:
```
uv run
```

### Running Locally
The best way to run the Serka tool for development is to use podman to start the necessary services through podman-compose and then run the FastAPI Serka service locally:
```
podman-compose -f podman-compose.yml up neo4j ollama mongodb -d
uv run fastapi run src/serka/main.py --port 8080
```
