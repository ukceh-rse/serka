FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml /app/
COPY src /app/src
RUN uv sync
EXPOSE 8000
CMD ["uv", "run", "src/serka-mcp/main.py"]
