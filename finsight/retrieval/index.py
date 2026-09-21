"""
Retrieval v2 index: chunks and sentences from finsight.corpus, in ChromaDB
(dense) and in-memory BM25 (lexical), sharing ids and metadata.

    index_document(session, document_id)   parse → chunk → embed → store
    all_chunks()                            every chunk record (eval coverage)
    chunk_by_id(cid)                        parent lookup for sentence hits
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from sqlmodel import Session

from finsight import config
from finsight.corpus import chunk_elements, parse_document
from finsight.corpus.health import parse_health
from finsight.models import Document
from finsight.retrieval.text import tokenize

logger = logging.getLogger(__name__)

CHUNKS = "finsight_v2_chunks"
SENTENCES = "finsight_v2_sentences"

_DOC_TYPE_LABELS = {
    "concall": "earnings call transcript",
    "press_release": "results press release",
    "fact_sheet": "results fact sheet",
    "annual_report": "annual report",
    "quarterly": "quarterly results",
    "annual": "annual report",
}

_client = None
_lock = threading.Lock()
_bm25 = {"chunks": None, "sentences": None, "built_at": 0.0, "dirty": True}
_chunk_cache: dict[str, dict] = {}


def context_header(doc: Document) -> str:
    name = (
        f"{doc.company_name} ({doc.symbol})"
        if doc.company_name and doc.symbol
        else (doc.company_name or doc.symbol or "")
    )
    parts = [name, _DOC_TYPE_LABELS.get(doc.doc_type or "", doc.doc_type or "document")]
    period = " ".join(x for x in (doc.fiscal_quarter, doc.fiscal_year) if x)
    if period:
        parts.append(period)
    return " · ".join(p for p in parts if p)


def _chroma():
    global _client
    if _client is None:
        import chromadb

        _client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
    return _client


def collection(name: str):
    return _chroma().get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine", "embedding_model": config.EMBEDDING_MODEL}
    )


def _embed(texts: list[str]) -> list[list[float]]:
    from finsight.rag.service import embed_documents

    return embed_documents(texts)


def delete_document(document_id: int) -> None:
    for name in (CHUNKS, SENTENCES):
        coll = collection(name)
        got = coll.get(where={"document_id": document_id}, include=[])
        if got["ids"]:
            coll.delete(ids=got["ids"])
    invalidate()


def invalidate() -> None:
    _bm25["dirty"] = True
    _chunk_cache.clear()
    from finsight.verification import evidence, pipeline

    evidence.clear_cache()
    pipeline.clear_cache()


def index_document(session: Session, document_id: int, *, force: bool = False) -> dict:
    doc = session.get(Document, document_id)
    if not doc or not doc.pdf_path:
        return {"status": "error", "message": "Document or file not found"}
    if doc.status == "indexed" and not force:
        return {"status": "already_indexed", "document_id": document_id}

    doc.status = "processing"
    session.add(doc)
    session.commit()
    t0 = time.time()
    try:
        parsed = parse_document(doc.pdf_path)
        if not parsed.elements:
            raise ValueError("No text extracted")
        header = context_header(doc)
        chunks = chunk_elements(parsed.elements, header=header)
        health = parse_health(doc.doc_type, parsed.elements, chunks)
        for w in health["warnings"]:
            logger.warning("parse health, document %d (%s): %s", document_id, Path(doc.pdf_path).name, w)
        delete_document(document_id)
        _write_text_and_pages(session, doc, parsed)

        base_meta = {
            "document_id": document_id,
            "symbol": doc.symbol or "",
            "doc_type": doc.doc_type or "",
            "fiscal_year": doc.fiscal_year or "",
            "fiscal_quarter": doc.fiscal_quarter or "",
            "context_header": header,
        }
        c_ids, c_docs, c_meta, c_index = [], [], [], []
        s_ids, s_docs, s_meta, s_index = [], [], [], []
        for c in chunks:
            cid = f"d{document_id}:c{c.chunk_index}"
            c_ids.append(cid)
            c_docs.append(c.text)
            c_index.append(c.index_text)
            c_meta.append(
                {
                    **base_meta,
                    "chunk_index": c.chunk_index,
                    "page_number": c.page,
                    "section": c.section or "",
                    "sub_section": "",
                    "speaker": c.speaker or "",
                    "kind": c.kind,
                    "index_text": c.index_text,
                    "display_text": c.display_text or "",
                }
            )
            if c.kind == "prose" and len(c.sentences) > 1:
                prefix = c.index_text[: len(c.index_text) - len(c.text)].rstrip()
                for n, sent in enumerate(c.sentences):
                    if len(sent) < 25:
                        continue
                    s_ids.append(f"{cid}:s{n}")
                    s_docs.append(sent)
                    s_index.append(f"{prefix}\n{sent}" if prefix else sent)
                    s_meta.append(
                        {
                            "document_id": document_id,
                            "chunk_id": cid,
                            "chunk_index": c.chunk_index,
                            "fiscal_year": doc.fiscal_year or "",
                            "fiscal_quarter": doc.fiscal_quarter or "",
                        }
                    )

        with _lock:
            coll = collection(CHUNKS)
            for i in range(0, len(c_ids), 256):
                sl = slice(i, i + 256)
                coll.add(ids=c_ids[sl], documents=c_docs[sl], metadatas=c_meta[sl], embeddings=_embed(c_index[sl]))
            if s_ids:
                coll = collection(SENTENCES)
                for i in range(0, len(s_ids), 256):
                    sl = slice(i, i + 256)
                    coll.add(ids=s_ids[sl], documents=s_docs[sl], metadatas=s_meta[sl], embeddings=_embed(s_index[sl]))
        invalidate()

        doc.status = "indexed"
        doc.chunk_count = len(chunks)
        doc.error_message = None
        doc.parse_health = json.dumps(health)
        session.add(doc)
        session.commit()
        return {
            "status": "indexed",
            "document_id": document_id,
            "chunks": len(chunks),
            "sentences": len(s_ids),
            "total_pages": parsed.total_pages,
            "seconds": round(time.time() - t0, 1),
            "health": health,
        }
    except Exception as e:
        logger.exception("index_document failed for %s", document_id)
        doc.status = "error"
        doc.error_message = str(e)[:500]
        session.add(doc)
        session.commit()
        return {"status": "error", "document_id": document_id, "message": str(e)[:500]}


def _write_text_and_pages(session: Session, doc: Document, parsed) -> None:
    """Verbatim full text next to the source file, and one PageMetadata row per page,
    for the parts of the app that still read them (document detail, division sentiment)."""
    from pathlib import Path

    from sqlmodel import select

    from finsight.models import PageMetadata

    pages: dict[int, list[str]] = {}
    sections: dict[int, str | None] = {}
    for el in parsed.elements:
        pages.setdefault(el.page, []).append(el.text)
        sections.setdefault(el.page, el.section)
    try:
        text_path = Path(doc.pdf_path).with_suffix(".txt")
        text_path.write_text("\n\n".join("\n\n".join(pages[p]) for p in sorted(pages)), encoding="utf-8")
        doc.text_path = str(text_path)
    except OSError:
        logger.warning("could not write text file for document %s", doc.id)
    for row in session.exec(select(PageMetadata).where(PageMetadata.document_id == doc.id)).all():
        session.delete(row)
    for p in sorted(pages):
        session.add(
            PageMetadata(document_id=doc.id, page_number=p, section_title=sections.get(p), text="\n\n".join(pages[p]))
        )
    session.commit()


# ---------------------------------------------------------------------------
# Lexical index and lookups
# ---------------------------------------------------------------------------


def _load(name: str) -> list[dict]:
    got = collection(name).get(include=["documents", "metadatas"])
    return [
        {"id": i, "text": t or "", "metadata": dict(m or {})}
        for i, t, m in zip(got["ids"], got["documents"], got["metadatas"], strict=True)
    ]


def bm25_indexes() -> dict:
    """{"chunks": (BM25Okapi, records), "sentences": (BM25Okapi, records)} — rebuilt lazily."""
    if not _bm25["dirty"]:
        return _bm25
    from rank_bm25 import BM25Okapi

    with _lock:
        chunks = _load(CHUNKS)
        sentences = _load(SENTENCES)
        _bm25["chunks"] = (
            (BM25Okapi([tokenize(r["metadata"].get("index_text") or r["text"]) for r in chunks]), chunks)
            if chunks
            else None
        )
        by_chunk = {r["id"]: r for r in chunks}
        _bm25["sentences"] = (
            (
                BM25Okapi(
                    [
                        tokenize(
                            (by_chunk.get(r["metadata"]["chunk_id"], {}).get("metadata", {}).get("context_header", ""))
                            + " "
                            + r["text"]
                        )
                        for r in sentences
                    ]
                ),
                sentences,
            )
            if sentences
            else None
        )
        _chunk_cache.clear()
        _chunk_cache.update(by_chunk)
        _bm25["dirty"] = False
        _bm25["built_at"] = time.time()
    return _bm25


def all_chunks() -> list[dict]:
    bm25_indexes()
    return list(_chunk_cache.values())


def chunk_by_id(cid: str) -> dict | None:
    bm25_indexes()
    return _chunk_cache.get(cid)
