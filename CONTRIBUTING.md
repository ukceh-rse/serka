# Contributing

## Setup

Ensure you have [uv](https://docs.astral.sh/uv/) installed and run:
```bash
uv sync
```

### Running specific services

The Serka application has 3 services which must all be run in order to function (`redis`, `mcp` and `serka`). Each of these services can be run through Docker Compose individually.

To run just Redis (e.g. when running the app outside of a container):
```bash
docker compose up redis -d
```

To run Redis and the MCP server only:
```bash
docker compose up redis mcp -d
```

Search needs data in Redis: write a bundle with `uv run scripts/ingest-data.py <n>`, or rebuild the index from an existing bundle with `uv run scripts/load-bundle.py`.

To run the app locally for development instance:
```bash
uv run fastapi dev src/serka/main.py --port 8080
```

### Hot-reloading dev stack

`compose.dev.yml` runs the whole stack with the source directories bind-mounted, so saved
edits take effect without rebuilding images:

```bash
docker compose -f compose.dev.yml up --build
```

| Service       | Reload behaviour                                                     | URL                                            |
| ------------- | ------------------------------------------------------------------- | ---------------------------------------------- |
| `ui`          | Vite dev server with HMR (`./ui` mounted)                           | [localhost:5173](http://localhost:5173)        |
| `serka` (API) | `fastapi dev` auto-reloads on edits under `./src`                   | [localhost:9000](http://localhost:9000)        |
| `mcp`         | `watchfiles` restarts the server on edits under `./mcp-server/src` | [localhost:8000](http://localhost:8000)        |
| `redis`       | Same `redis-data` volume as `compose.yaml`, so no reload is needed  | `redis://localhost:6379`                       |

Notes:

- Open the app at [localhost:5173](http://localhost:5173); the Vite dev server proxies
  `/v1` to the `serka` service via `VITE_PROXY_TARGET`.
- The UI's `node_modules` lives in an isolated volume so host modules don't clash with the
  container; `npm install` runs on first start.
- The images are still built for their dependency layers, hence `--build` on first run.

### Tests

```bash
uv run pytest -m "not integration"
```

Integration tests (`-m integration`) need a separate Redis on port 6380, as search indexes only work in database 0 and the tests flush it: `docker run -d -p 6380:6379 redis:8.10.3` (or set `TEST_REDIS_URL`). The search tests also need AWS credentials for Bedrock, and skip without them.

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
