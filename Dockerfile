FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV LLM_PROVIDER=mock

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY mcp_servers ./mcp_servers

RUN pip install --no-cache-dir ".[gcp]"

EXPOSE 8080
CMD ["fieldops-api"]
