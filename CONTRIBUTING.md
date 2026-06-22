# Contributing

## Setup

Ensure you have [uv](https://docs.astral.sh/uv/) installed and run:
```bash
uv sync
```

### Running specific services

The Serka application has 3 services which must all be run in order to function (`neo4j`, `mcp` and `serka`). Each of these services can be run through podman individually.

To run just Neo4j (e.g. when running the app outside of a container):
```bash
podman-compose up neo4j -d
```

The Neo4j browser UI is available at [localhost:7474](http://localhost:7474) when running locally.

To run Neo4j and the MCP server only:
```bash
podman-compose up neo4j mcp -d
```

To run the app locally for development instance:
```bash
uv run fastapi dev src/serka/main.py --port 8080
```

### Hot-reloading dev stack

`compose.dev.yml` runs the whole stack with the source directories bind-mounted, so saved
edits take effect without rebuilding images:

```bash
podman-compose -f compose.dev.yml up --build
```

| Service       | Reload behaviour                                                     | URL                                            |
| ------------- | ------------------------------------------------------------------- | ---------------------------------------------- |
| `ui`          | Vite dev server with HMR (`./ui` mounted)                           | [localhost:5173](http://localhost:5173)        |
| `serka` (API) | `fastapi dev` auto-reloads on edits under `./src`                   | [localhost:9000](http://localhost:9000)        |
| `mcp`         | `watchfiles` restarts the server on edits under `./mcp-server/src` | [localhost:8000](http://localhost:8000)        |
| `neo4j`       | Same `./.neo4j` data volume as `compose.yml` — no re-ingest needed | [localhost:7474](http://localhost:7474)        |

Notes:

- Open the app at [localhost:5173](http://localhost:5173); the Vite dev server proxies
  `/v1` to the `serka` service via `VITE_PROXY_TARGET`.
- The UI's `node_modules` lives in an isolated volume so host modules don't clash with the
  container; `npm install` runs on first start.
- The images are still built for their dependency layers, hence `--build` on first run.

## Commits

Commits follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. Use [Commitizen](https://commitizen-tools.github.io/commitizen/) to create commits interactively:

```bash
source .venv/bin/activate
cz commit
```

The prompt will also ask which AI tool assisted with the change (if any) and who reviewed it.

## Releases

Bump the version with Commitizen (updates `pyproject.toml`, creates a tag, updates `CHANGELOG.md`):

```bash
cz bump --prerelease alpha   # alpha releases
cz bump                      # standard releases
git push origin --tags
```
