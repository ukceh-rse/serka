podman-compose -f container-compose-dev.yml down
podman-compose -f container-compose-dev.yml up -d

pkill -f "mcp-server/src/serka-mcp/main.py" 2>/dev/null || true
uv run mcp-server/src/serka-mcp/main.py >> mcp.log 2>&1 &

pkill -f "src/serka/main.py" 2>/dev/null || true
#uv run fastapi run src/serka/main.py --host 0.0.0.0 --port 8001 >> serka.log 2>&1 &

#xdg-open http://localhost:8001
