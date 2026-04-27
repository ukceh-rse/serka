# Serka
Serka (serĉi ekologio) is a prototype search tool for the UKCEH NCUK project. It uses modern AI techniques (LLMs, RAG, knowledge graphs) to enhance the EIDC catalogue's search functionality.

It is built with [FastAPI](https://fastapi.tiangolo.com/), [Neo4j](https://neo4j.com/), [Haystack](https://haystack.deepset.ai/), and [Pydantic AI](https://ai.pydantic.dev/), using Amazon Bedrock for LLM and embedding models.

## AWS Deployment
For AWS deployment instructions see [`terraform/README.md`](terraform/README.md).

## Running with Podman

Ensure you have [`podman`](https://podman.io/) and `podman-compose` installed.

Copy `.env.example` to `.env` and fill in the required values:
```
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your password>
```

### Run all services
```
podman-compose up -d
```

### Run only specific services

To run just Neo4j (e.g. for local development while running the app outside of a container):
```
podman-compose up neo4j -d
```

To run Neo4j and the MCP server only:
```
podman-compose up neo4j mcp -d
```

The Neo4j browser UI is available at http://localhost:7474 when running locally.

### Stop services
```
podman-compose down
```

## Development

Ensure you have [uv](https://docs.astral.sh/uv/) installed and run:
```
uv sync
```

For local development, start Neo4j via podman-compose and run the app directly:
```
podman-compose up neo4j -d
uv run fastapi dev src/serka/main.py --port 8080
```

## Ingest Data

Data is ingested from the EIDC catalogue and optionally the Legilo API. Ensure your `.env` contains the required Neo4j credentials and Legilo credentials (to ingest supporting docs):
```
LEGILO_USERNAME=yourusername
LEGILO_PASSWORD=yourpassword
```

Run the ingestion pipeline:
```
uv run scripts/ingest-data.py <n>
```

Where `<n>` is the number of EIDC records to ingest. Ingesting all records (2,000+) can take several hours — use a small number (default: 10) for testing.
