FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV LLM_PROVIDER=mock

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY mcp_servers ./mcp_servers

RUN pip install --no-cache-dir ".[gcp]"

# Pre-build RAG index at image build time (avoids blocking Cloud Run startup / health checks)
ENV CHROMA_PERSIST_DIR=/app/data/chroma
ENV KNOWLEDGE_BASE_DIR=/app/data/knowledge_base
RUN LLM_PROVIDER=mock fieldops-ingest

ENV PORT=8080
EXPOSE 8080
# Use uvicorn directly so Cloud Run PORT env is respected
CMD ["sh", "-c", "uvicorn fieldops.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
