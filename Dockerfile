FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock README.md config.yaml /app/
COPY src /app/src
RUN uv sync
EXPOSE 8000
CMD ["uv", "run", "fastapi", "run", "src/serka/main.py", "--host", "0.0.0.0", "--port", "8000"]
