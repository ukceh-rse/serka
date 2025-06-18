FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock README.md .env /app/
COPY config-podman.yml /app/config.yml
COPY src /app/src
COPY static /app/static
RUN uv sync
EXPOSE 8000
CMD ["uv", "run", "fastapi", "run", "src/serka/main.py", "--host", "0.0.0.0", "--port", "8000"]
