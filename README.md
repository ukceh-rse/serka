# Serka
Serka (serĉi ekologio) is a prototype search tool for the UKCEH NCUK project. It uses modern AI techniques (LLMs, RAG, knowledge graphs) to enhance the EIDC catalogue's search functionality.

It is built with [FastAPI](https://fastapi.tiangolo.com/), [Neo4j](https://neo4j.com/), [Haystack](https://haystack.deepset.ai/), and [Pydantic AI](https://ai.pydantic.dev/), using Amazon Bedrock for LLM and embedding models.

## AWS Deployment
For AWS deployment instructions see [`terraform/README.md`](terraform/README.md).

## Running with Podman

Ensure you have [`podman`](https://podman.io/) and `podman-compose` installed.

Copy `.env.example` to `.env` and fill in the required values (username must be `neo4j` but password can be set to whatever you choose):
```
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your password>
```

Start all services:
```
podman-compose up -d
```

Stop all services:
```
podman-compose down
```

## Ingest Data

Data is ingested from the EIDC catalogue and optionally the Legilo API. To connect to Legilo, ensure your `.env` contains your credentials:
```
LEGILO_USERNAME=yourusername
LEGILO_PASSWORD=yourpassword
```

After starting all services run the ingestion pipeline:
```bash
uv run scripts/ingest-data.py <n>
```

Where `<n>` is the number of EIDC records to ingest. Ingesting all records (2,000+) can take several hours — use a small number (default: 10) for testing.

To ingest specific datasets instead, pass a file of EIDC IDs (one per line): `uv run scripts/ingest-data.py --ids-file tests/smoke/datasets.txt`.

## Smoke Test

`uv run scripts/smoke-test.py` runs an end-to-end check. It starts a throwaway Neo4j container on port 17687 and ingests the 10 datasets in `tests/smoke/datasets.txt`. It then starts the MCP server (port 8000) and API (port 19000), runs some search and chat queries, and tears everything down. It needs podman or docker and AWS credentials for Bedrock.

Add `--keep-running` to leave Neo4j, the MCP server and the API up after the checks so you can sanity-check things by hand. The script prints the endpoints and the command to start the UI against them. Press Ctrl+C to tear everything down.

## Stress Test

`tests/stress/locustfile.py` is a [Locust](https://locust.io) load test that mixes semantic searches with streamed chat questions. Alongside Locust's usual throughput and response time stats, it reports chat time to first token as its own stats row. It also prints tokens per second (per request and aggregate) at the end; tokens are estimated as characters / 4.

```
# Locally, without Bedrock/Neo4j costs: start the API in mock mode
TEST_MODE=true uv run fastapi run src/serka/main.py --port 9000
uv run locust -f tests/stress/locustfile.py --host http://localhost:9000 \
	--headless -u 50 -r 5 -t 2m --csv stress --metrics-json stress_chat.json
```

To test the AWS deployment, set `--host` to the ALB address (the UI proxies `/v1` to the API). Leave out `--headless` to use the web UI at http://localhost:8089. Use `--tags chat` or `--tags search` to load one endpoint only. Every chat against a real deployment is a Bedrock call, so ramp up gradually.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, commit guidelines, and release process.
