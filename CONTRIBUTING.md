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
