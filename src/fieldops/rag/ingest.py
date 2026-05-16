"""Ingest markdown/text policy docs from data/knowledge_base into Chroma."""

from __future__ import annotations

from pathlib import Path

from fieldops.config import get_settings
from fieldops.rag.retriever import KnowledgeRetriever


def chunk_text(text: str, max_chars: int = 800) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}".strip() if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks or [text]


def ingest_directory(kb_dir: Path | None = None) -> int:
    settings = get_settings()
    root = kb_dir or Path(settings.knowledge_base_dir)
    retriever = KnowledgeRetriever(settings)
    count = 0
    for path in sorted(root.glob("**/*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        raw = path.read_text(encoding="utf-8")
        doc_id_base = path.stem
        for i, chunk in enumerate(chunk_text(raw)):
            doc_id = f"{doc_id_base}::{i}"
            retriever.add_documents(
                ids=[doc_id],
                texts=[chunk],
                metadatas=[{"source": str(path.relative_to(root)), "chunk": i}],
            )
            count += 1
    return count


def main() -> None:
    n = ingest_directory()
    print(f"Ingested {n} chunks into {get_settings().chroma_persist_dir}")


if __name__ == "__main__":
    main()
