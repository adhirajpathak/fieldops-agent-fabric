"""Chroma-backed RAG retriever over enterprise policy documents."""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from fieldops.config import Settings, get_settings


class KnowledgeRetriever:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        persist = Path(self._settings.chroma_persist_dir)
        persist.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="enterprise_policies",
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def document_count(self) -> int:
        return self._collection.count()

    def add_documents(self, ids: list[str], texts: list[str], metadatas: list[dict] | None = None) -> None:
        self._collection.upsert(ids=ids, documents=texts, metadatas=metadatas)

    def search(self, query: str, k: int = 4) -> list[dict]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(query_texts=[query], n_results=min(k, self._collection.count()))
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]
        return [
            {
                "id": doc_id,
                "text": text,
                "metadata": meta or {},
                "score": 1.0 - float(dist) if dist is not None else 0.0,
            }
            for doc_id, text, meta, dist in zip(ids, docs, metas, distances)
        ]
