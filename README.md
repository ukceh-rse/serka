# Serka
Serka (serĉi ekologio) is a protoype search tool for the UKCEH NCUK project. It uses modern AI techniques (LLMs, RAG, Vector Stores) to enhance the EIDC catalogue's search functionality.

## Podman Deployment
Serka can be deployed using [podman](https://podman.io/). You must ensure you have `podman`, `podman-compose` and [`nvidia-container-toolkit`](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/index.html) installed.

To run Serka and it's dependent services ([Ollama](https://ollama.com/), [Neo4j](https://neo4j.com/), [MondgoDB](https://www.mongodb.com/)) defined in `podman-compose.yml` use:
```
podman-compose --profile app up -d
```
> Note: Initially the Ollama service will download the required models listed in `config.yml`. This can take some time, but once the models are downloaded they should not need to be downloaded again.

To stop the running services:
```
podman-compose down
```
> ⚠️ **Warning:** Serka is designed to work with a GPU and you may find certain features slow if running without access to a GPU. The GPU configuration is declared in `podman-compose.yml` via: `devices: nvidia.com/gpu=all` in the `ollama` service definition.

## Ingest Data
Data is ingested into Serka from the EIDC catalogue and the Legilo API. A convenience script `scripts/ingest-data.py` is provided to ingest data through a data pipeline that will parse, construct a knowledge graph, create embeddings and save to the neo4j database. To run the script you must ensure that you have configured the correct variable in a local `.env` file:
```
LEGILO_USERNAME=yourusername
LEGILO_PASSWORD=yourpassword
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```
The legilo username and password should be those that you use to access the legilo service. If you do not have access this stage will be skipped with a warning. The neo4j username should always be `neo4j` and the password can be any of your choosing.

Once your `.env` file is set up you can run the ingestion pipeline:
```
uv run scripts/ingest-data.py <n>
```
Where `<n>` is the number of records from the EIDC catalogue you wish to ingest. Ingesting all records (over 2,000) from the EIDC can take several hours so for testing you may want to ingest a small number (default is 10).

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
The best way to run the Serka tool for development is to use podman to start the necessary services through podman-compose using the `dev` profile and then run the FastAPI Serka service locally:
```
podman-compose up neo4j ollama mongodb -d
uv run fastapi run src/serka/main.py --port 8080
```
